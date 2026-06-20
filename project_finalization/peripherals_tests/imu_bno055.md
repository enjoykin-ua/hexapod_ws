# IMU BNO-055 — Hello-World-Inbetriebnahme

> Isolierter Funktionsnachweis. Sensor liegt **neben** dem Roboter (nicht eingebaut),
> wird zum Test bewegt/gekippt. Gesamt-Kontext: [`00_overview.md`](00_overview.md).

## 1. Ziel & Hardware

- **Gerät:** BNO-055 (Bosch 9-DOF, On-Chip-Sensor-Fusion), schwarzes Board mit Blüten-Logo.
- **Anschluss:** Qwiic (JST-SH 4-polig) am Powerhead. Qwiic führt **alle** nötigen Leitungen:
  `GND`, `3.3V`, `SDA`, `SCL` → **keine** Extra-Verkabelung, **keine** separate Versorgung.
- **Ziel:** Bus läuft → Sensor antwortet (`0x28`) → fusionierte Euler-Winkel live auf der
  Konsole, die sich beim Kippen ändern.

## 2. Plan-Skizze (Logik)

1. **I2C aktivieren** in `/boot/firmware/config.txt` (`dtparam=i2c_arm=on`).
   Dazu **niedrige Baudrate** (`i2c_arm_baudrate=50000`) als Vorsichtsmaßnahme gegen das
   bekannte **Clock-Stretching** des BNO-055 (klassischer Pi-Fallstrick; auf Pi 5/RP1 evtl.
   unkritisch, aber billig abzusichern). → **Reboot durch User.**
2. **`i2c-tools`** installieren, `i2cdetect -y 1` → Adresse `0x28` (oder `0x29`) muss
   erscheinen. Das ist bereits der halbe Funktionsnachweis (Bus + Spannung + Sensor ok).
3. **Auslesen** mit minimalem Python-Skript über `smbus2` (kein Blinka/Board-Detection-Risiko
   auf Pi 5): Chip-ID prüfen → in **NDOF-Modus** (9-DOF-Fusion) schalten → Euler-Winkel +
   Kalibrierstatus in Schleife drucken.

**Design-Entscheidung — warum `smbus2` statt Adafruit-CircuitPython-Lib:**
Die Adafruit-Lib braucht Blinka, das auf Pi 5 (RP1) + Ubuntu mit Board-Detection und
`lgpio`-Shims zickt. `smbus2` ist reines I2C, keine GPIO-Lib, keine Plattform-Erkennung →
robuster für ein Hello-World. Die Adafruit-Lib bleibt optionale „schönere" Alternative (§8).

## 3. Tests-Liste

| Test | Prüft | Done wenn |
|---|---|---|
| T1 `i2cdetect` | Bus aktiv, Sensor adressierbar | `0x28` (o. `0x29`) in der Matrix |
| T2 Chip-ID | richtige Geräte-Identität | Skript meldet `CHIP_ID = 0xA0` |
| T3 Live-Werte | Fusion läuft, Daten plausibel | Heading/Roll/Pitch ändern sich beim Kippen |
| T4 Kalibrierung | Sensor kalibriert sich (optional) | Cal-Werte steigen Richtung 3 beim Bewegen |

**Bewusst NICHT getestet (scope-out):** ROS-Anbindung (`/imu/data`), Madgwick/Balance-Logik
(= Block A5, spätere Integration), Magnetometer-Genauigkeit/Hard-Iron-Kalibrierung,
Dauerlauf/Drift, UART-Modus.

## 4. Installation & Config

> **Vorab:** Pi einschalten und einloggen: `ssh hexapod-pi`

### 4.1 I2C aktivieren (idempotent)

```bash
grep -q '^dtparam=i2c_arm=on' /boot/firmware/config.txt \
  || echo 'dtparam=i2c_arm=on,i2c_arm_baudrate=50000' | sudo tee -a /boot/firmware/config.txt
```

Kontrolle, dass die Zeile drinsteht:

```bash
grep -n 'i2c_arm' /boot/firmware/config.txt
```

### 4.2 Reboot — **durch den User**

```bash
sudo reboot
```

> ⚠️ Reboot führst **du** aus (CLAUDE.md §5). Danach neu einloggen: `ssh hexapod-pi`

### 4.3 i2c-tools installieren + Zugriff ohne sudo

```bash
sudo apt update
sudo apt install -y i2c-tools
```

Eigenen User in die `i2c`-Gruppe (damit `/dev/i2c-1` ohne sudo lesbar ist):

```bash
sudo usermod -aG i2c "$USER"
```

> ⚠️ Damit die Gruppe greift: **einmal aus-/wieder einloggen** (`exit`, dann erneut `ssh hexapod-pi`).
> Alternativ ohne Re-Login: die Test-Skripte mit `sudo` ausführen.

### 4.4 Python-venv + smbus2

```bash
sudo apt install -y python3-venv
python3 -m venv ~/bno055_venv
~/bno055_venv/bin/pip install --upgrade pip
~/bno055_venv/bin/pip install smbus2
```

## 5. Test-Befehle

### T1 — Bus scannen

```bash
i2cdetect -y 1
```

Erwartung: in der Matrix steht `28` (oder `29`). Falls nichts auf Bus 1 erscheint, andere
Busse durchprobieren:

```bash
for b in 0 1 2 3; do echo "=== Bus $b ==="; i2cdetect -y $b 2>/dev/null; done
```

### T2–T4 — Live-Auslesen

Skript anlegen (Ordner wird angelegt, falls nicht vorhanden):

```bash
mkdir -p ~/peripheries
cat > ~/peripheries/bno055_hello.py << 'PY'
#!/usr/bin/env python3
"""BNO-055 Hello-World: Chip-ID pruefen, NDOF-Fusion, Euler-Winkel + Cal-Status live."""
import time
from smbus2 import SMBus

I2C_BUS = 1            # /dev/i2c-1 (GPIO2=SDA, GPIO3=SCL); bei Bedarf anpassen
ADDR = 0x28            # ggf. 0x29

# Register
CHIP_ID = 0x00
OPR_MODE = 0x3D
PWR_MODE = 0x3E
SYS_TRIGGER = 0x3F
CALIB_STAT = 0x35
EUL_HEADING_LSB = 0x1A

MODE_CONFIG = 0x00
MODE_NDOF = 0x0C


def s16(lsb, msb):
    v = (msb << 8) | lsb
    return v - 65536 if v > 32767 else v


with SMBus(I2C_BUS) as bus:
    chip = bus.read_byte_data(ADDR, CHIP_ID)
    print(f"CHIP_ID = 0x{chip:02X} (erwartet 0xA0)")
    if chip != 0xA0:
        raise SystemExit("BNO-055 nicht erkannt — Adresse/Verkabelung pruefen.")

    # CONFIG -> Normal-Power -> NDOF (9-DOF-Fusion)
    bus.write_byte_data(ADDR, OPR_MODE, MODE_CONFIG)
    time.sleep(0.025)
    bus.write_byte_data(ADDR, PWR_MODE, 0x00)
    time.sleep(0.01)
    bus.write_byte_data(ADDR, SYS_TRIGGER, 0x00)
    time.sleep(0.01)
    bus.write_byte_data(ADDR, OPR_MODE, MODE_NDOF)
    time.sleep(0.02)
    print("Modus NDOF aktiv. Board bewegen/kippen — Werte muessen sich aendern.")
    print("(Strg-C beendet)\n")

    while True:
        cal = bus.read_byte_data(ADDR, CALIB_STAT)
        sys_c, gyr, acc, mag = (cal >> 6) & 3, (cal >> 4) & 3, (cal >> 2) & 3, cal & 3
        d = bus.read_i2c_block_data(ADDR, EUL_HEADING_LSB, 6)
        heading = s16(d[0], d[1]) / 16.0
        roll = s16(d[2], d[3]) / 16.0
        pitch = s16(d[4], d[5]) / 16.0
        print(f"Heading={heading:7.2f}  Roll={roll:7.2f}  Pitch={pitch:7.2f}  "
              f"| Cal sys={sys_c} gyr={gyr} acc={acc} mag={mag}   ", end="\r", flush=True)
        time.sleep(0.1)
PY
```

Ausführen:

```bash
~/bno055_venv/bin/python ~/peripheries/bno055_hello.py
```

> Falls „Permission denied" auf `/dev/i2c-1`: Re-Login vergessen (4.3) → entweder neu einloggen
> oder mit sudo: `sudo ~/bno055_venv/bin/python ~/peripheries/bno055_hello.py`

**Verifikation:**
- T2: `CHIP_ID = 0xA0`.
- T3: Board kippen → `Heading/Roll/Pitch` ändern sich plausibel.
- T4 (optional): Board langsam in alle Richtungen drehen → `gyr`/`acc`/`mag` steigen Richtung 3.

## 5b. Anhang: Alle Sensorwerte live auslesen (optional)

Über die Euler-Winkel hinaus liefert der BNO-055 noch deutlich mehr — alles, was der Chip
kann, in einer aktualisierenden Live-Anzeige. Was angezeigt wird:

| Kanal | Einheit | Bedeutung |
|---|---|---|
| **Euler** | ° | Fusionierte Orientierung (Heading/Roll/Pitch) |
| **Quaternion** | – | Fusionierte Orientierung, singularitätsfrei (für Regelung besser) |
| **Accel** | m/s² | Roher Beschleunigungssensor **inkl.** Schwerkraft |
| **LinAccel** | m/s² | Lineare Beschleunigung, **Schwerkraft herausgerechnet** (Fusion) |
| **Gravity** | m/s² | Reiner Schwerkraftvektor (Fusion) — zeigt „wo unten ist" |
| **Gyro** | °/s | Drehraten |
| **Mag** | µT | Magnetfeld (Kompass; störanfällig nahe Servos/Strom) |
| **Temp** | °C | Chip-Temperatur |
| **Calib** | 0–3 | Kalibrierstatus sys/gyr/acc/mag |

Skript anlegen:

```bash
mkdir -p ~/peripheries
cat > ~/peripheries/bno055_full.py << 'PY'
#!/usr/bin/env python3
"""BNO-055 Voll-Auslesung: alle Sensor-/Fusionswerte live (smbus2)."""
import sys
import time
from smbus2 import SMBus

I2C_BUS = 1
ADDR = 0x28            # ggf. 0x29

# Daten-Register (LSB) + Skalierung
CHIP_ID = 0x00
ACC_DATA = 0x08        # 6 B, /100  -> m/s^2 (inkl. g)
MAG_DATA = 0x0E        # 6 B, /16   -> uT
GYR_DATA = 0x14        # 6 B, /16   -> dps
EUL_DATA = 0x1A        # 6 B, /16   -> Grad
QUA_DATA = 0x20        # 8 B, /16384-> einheitslos
LIA_DATA = 0x28        # 6 B, /100  -> m/s^2 (ohne g)
GRV_DATA = 0x2E        # 6 B, /100  -> m/s^2 (Schwerkraftvektor)
TEMP = 0x34            # 1 B        -> Grad C
CALIB_STAT = 0x35
UNIT_SEL = 0x3B
OPR_MODE = 0x3D
PWR_MODE = 0x3E
SYS_TRIGGER = 0x3F

MODE_CONFIG = 0x00
MODE_NDOF = 0x0C


def s16(lo, hi):
    v = (hi << 8) | lo
    return v - 65536 if v > 32767 else v


def vec(buf, scale):
    return (s16(buf[0], buf[1]) / scale,
            s16(buf[2], buf[3]) / scale,
            s16(buf[4], buf[5]) / scale)


with SMBus(I2C_BUS) as bus:
    if bus.read_byte_data(ADDR, CHIP_ID) != 0xA0:
        raise SystemExit("BNO-055 nicht erkannt — Adresse/Verkabelung pruefen.")

    bus.write_byte_data(ADDR, OPR_MODE, MODE_CONFIG)
    time.sleep(0.025)
    bus.write_byte_data(ADDR, UNIT_SEL, 0x00)     # m/s^2, dps, Grad, Celsius
    bus.write_byte_data(ADDR, PWR_MODE, 0x00)     # Normal
    bus.write_byte_data(ADDR, SYS_TRIGGER, 0x00)
    bus.write_byte_data(ADDR, OPR_MODE, MODE_NDOF)
    time.sleep(0.02)
    print("NDOF aktiv — alle Werte live. (Strg-C beendet)\n")

    first = True
    while True:
        ax, ay, az = vec(bus.read_i2c_block_data(ADDR, ACC_DATA, 6), 100.0)
        mx, my, mz = vec(bus.read_i2c_block_data(ADDR, MAG_DATA, 6), 16.0)
        gx, gy, gz = vec(bus.read_i2c_block_data(ADDR, GYR_DATA, 6), 16.0)
        eh, er, ep = vec(bus.read_i2c_block_data(ADDR, EUL_DATA, 6), 16.0)
        q = bus.read_i2c_block_data(ADDR, QUA_DATA, 8)
        qw, qx = s16(q[0], q[1]) / 16384.0, s16(q[2], q[3]) / 16384.0
        qy, qz = s16(q[4], q[5]) / 16384.0, s16(q[6], q[7]) / 16384.0
        lx, ly, lz = vec(bus.read_i2c_block_data(ADDR, LIA_DATA, 6), 100.0)
        vx, vy, vz = vec(bus.read_i2c_block_data(ADDR, GRV_DATA, 6), 100.0)
        t = bus.read_byte_data(ADDR, TEMP)
        if t > 127:
            t -= 256
        cal = bus.read_byte_data(ADDR, CALIB_STAT)
        cs, cg, ca, cm = (cal >> 6) & 3, (cal >> 4) & 3, (cal >> 2) & 3, cal & 3

        lines = [
            f"Euler   (deg)   Heading={eh:8.2f}  Roll={er:8.2f}  Pitch={ep:8.2f}",
            f"Quaternion      w={qw:7.4f}  x={qx:7.4f}  y={qy:7.4f}  z={qz:7.4f}",
            f"Accel  (m/s^2)  x={ax:8.3f}  y={ay:8.3f}  z={az:8.3f}",
            f"LinAccel(m/s^2) x={lx:8.3f}  y={ly:8.3f}  z={lz:8.3f}",
            f"Gravity(m/s^2)  x={vx:8.3f}  y={vy:8.3f}  z={vz:8.3f}",
            f"Gyro    (dps)   x={gx:8.2f}  y={gy:8.2f}  z={gz:8.2f}",
            f"Mag      (uT)   x={mx:8.2f}  y={my:8.2f}  z={mz:8.2f}   [NDOF: 0 = normal]",
            f"Temp     (C)    {t}",
            f"Calib           sys={cs}  gyr={cg}  acc={ca}  mag={cm}",
        ]
        out = "".join(s + "\033[K\n" for s in lines)
        if not first:
            out = f"\033[{len(lines)}F" + out      # Cursor hoch -> in-place Update
        sys.stdout.write(out)
        sys.stdout.flush()
        first = False
        time.sleep(0.1)
PY
```

Ausführen:

```bash
~/bno055_venv/bin/python ~/peripheries/bno055_full.py
```

Die Anzeige aktualisiert sich an Ort und Stelle (kein Scrollen). **Strg-C** beendet.
Spannend zum Ausprobieren: **Gravity** zeigt immer „nach unten" (kippst du den Sensor, wandert
der Vektor); **LinAccel** ist ~0 in Ruhe und schlägt nur bei echtem Schütteln/Beschleunigen aus
(weil die Schwerkraft rausgerechnet ist).

> **Hinweis Magnetometer:** Im NDOF-Modus liest der **Rohmag dauerhaft 0** — das ist **normal**,
> kein Defekt. Der BNO-055 **verbraucht das Magnetometer in der Fusion intern** (Heading/Quaternion
> sind mag-gestützt) und blendet die rohen `MAG_DATA`-Register im Fusions-Modus aus. Den **Rohwert**
> siehst du nur im **AMG-/MAGONLY-Modus** (Skript in §5c). **Für den Hexapod wird der Rohmag nicht
> benötigt:** Balance/Leveling läuft über Accel+Gyro; ein Kompass nahe den 18 Servos/LiPo-Leitungen
> ist ohnehin durch Störfelder unbrauchbar (gemessen ~230 µT statt Erdfeld ~50 µT). Verifiziert:
> echter BNO-055 (IDs `A0/FB/32/0F`), Mag liefert in AMG reale Werte.

## 5c. Anhang: Rohe Sensoren ohne Fusion (AMG-Modus, optional)

Wenn du den **rohen Magnetometer-Wert** live sehen willst, nutze den **AMG-Modus** (Accel + Mag +
Gyro, **ohne** Fusion). Trade-off: dafür gibt es **kein** Euler/Quaternion/LinAccel/Gravity (das
sind alles Fusions-Produkte). Beides gleichzeitig in einem Modus geht nicht — die Modi schließen
sich gegenseitig aus.

```bash
mkdir -p ~/peripheries
cat > ~/peripheries/bno055_amg.py << 'PY'
#!/usr/bin/env python3
"""BNO-055 AMG-Modus: rohe Accel/Mag/Gyro live (KEINE Fusion -> kein Euler/Quaternion)."""
import sys
import time
from smbus2 import SMBus

I2C_BUS = 1
ADDR = 0x28            # ggf. 0x29

CHIP_ID = 0x00
ACC_DATA = 0x08        # 6 B, /100 -> m/s^2
MAG_DATA = 0x0E        # 6 B, /16  -> uT
GYR_DATA = 0x14        # 6 B, /16  -> dps
TEMP = 0x34
CALIB_STAT = 0x35
UNIT_SEL = 0x3B
OPR_MODE = 0x3D
PWR_MODE = 0x3E
SYS_TRIGGER = 0x3F

MODE_CONFIG = 0x00
MODE_AMG = 0x07


def s16(lo, hi):
    v = (hi << 8) | lo
    return v - 65536 if v > 32767 else v


def vec(buf, scale):
    return (s16(buf[0], buf[1]) / scale,
            s16(buf[2], buf[3]) / scale,
            s16(buf[4], buf[5]) / scale)


with SMBus(I2C_BUS) as bus:
    if bus.read_byte_data(ADDR, CHIP_ID) != 0xA0:
        raise SystemExit("BNO-055 nicht erkannt — Adresse/Verkabelung pruefen.")

    bus.write_byte_data(ADDR, OPR_MODE, MODE_CONFIG)
    time.sleep(0.025)
    bus.write_byte_data(ADDR, UNIT_SEL, 0x00)     # m/s^2, dps, Celsius
    bus.write_byte_data(ADDR, PWR_MODE, 0x00)     # Normal
    bus.write_byte_data(ADDR, SYS_TRIGGER, 0x00)
    bus.write_byte_data(ADDR, OPR_MODE, MODE_AMG)
    time.sleep(0.02)
    print("AMG aktiv (roh, KEINE Fusion) — Mag zeigt jetzt Werte. (Strg-C beendet)\n")

    first = True
    while True:
        ax, ay, az = vec(bus.read_i2c_block_data(ADDR, ACC_DATA, 6), 100.0)
        mx, my, mz = vec(bus.read_i2c_block_data(ADDR, MAG_DATA, 6), 16.0)
        gx, gy, gz = vec(bus.read_i2c_block_data(ADDR, GYR_DATA, 6), 16.0)
        t = bus.read_byte_data(ADDR, TEMP)
        if t > 127:
            t -= 256
        cal = bus.read_byte_data(ADDR, CALIB_STAT)
        cg, ca, cm = (cal >> 4) & 3, (cal >> 2) & 3, cal & 3

        lines = [
            f"Accel (m/s^2)  x={ax:8.3f}  y={ay:8.3f}  z={az:8.3f}",
            f"Mag    (uT)    x={mx:8.2f}  y={my:8.2f}  z={mz:8.2f}",
            f"Gyro   (dps)   x={gx:8.2f}  y={gy:8.2f}  z={gz:8.2f}",
            f"Temp   (C)     {t}",
            f"Calib          gyr={cg}  acc={ca}  mag={cm}   (kein sys: AMG hat keine Fusion)",
        ]
        out = "".join(s + "\033[K\n" for s in lines)
        if not first:
            out = f"\033[{len(lines)}F" + out
        sys.stdout.write(out)
        sys.stdout.flush()
        first = False
        time.sleep(0.1)
PY
```

Ausführen:

```bash
~/bno055_venv/bin/python ~/peripheries/bno055_amg.py
```

Jetzt zeigt **Mag** echte Werte (in Servo-/Metallnähe betragsmäßig groß). Es fehlen dafür die
Fusions-Werte. Danach setzt `bno055_full.py` beim Start wieder NDOF — du musst nichts zurückstellen.

## 6. Done-Kriterien (Checkliste)

- [x] I2C aktiviert (`config.txt`), Pi rebootet
- [x] `i2cdetect -y 1` zeigt `0x28`
- [x] Skript meldet `CHIP_ID = 0xA0`
- [x] Heading/Roll/Pitch ändern sich beim Kippen (live)
- [x] Cal-Werte steigen beim Bewegen (gyr/acc → 3)
- [x] Voll-Auslesung (§5b) live: alle Fusions- + Rohwerte plausibel
- [x] Echtheit bestätigt (IDs `A0/FB/32/0F`); Mag funktioniert in AMG (§5c)

✅ **IMU-Hello-World verifiziert.** Mag-Rohwert im NDOF=0 ist normal (s. §5b); für den Hexapod
nicht benötigt. Status in `00_overview.md` = 🟢.

## 7. Troubleshooting

| Symptom | Ursache / Fix |
|---|---|
| `i2cdetect` zeigt nichts | I2C nicht aktiv (config.txt-Zeile fehlt / Reboot vergessen); Qwiic-Stecker prüfen |
| Adresse `0x29` statt `0x28` | ADR-Pin gezogen → im Skript `ADDR = 0x29` setzen |
| Sporadische `OSError`/`I/O error` beim Lesen | Clock-Stretching → Baudrate weiter senken: in 4.1 `i2c_arm_baudrate=10000`, Reboot |
| `CHIP_ID` ≠ `0xA0` | falsches Gerät auf der Adresse / Verkabelung; mit `i2cdetect` gegenchecken |
| `Permission denied` `/dev/i2c-1` | i2c-Gruppe nicht aktiv → Re-Login oder `sudo` (4.3) |
| `ModuleNotFoundError: smbus2` | venv-Python nicht benutzt → vollen Pfad `~/bno055_venv/bin/python` verwenden |

## 8. Offene Punkte / spätere Integration

- **ROS-Pfad (Block A5):** fertiger Treiber `bno055` (flynneva) für Jazzy publisht
  `sensor_msgs/Imu` auf `/imu/data` (= Konvention aus `architecture.md`). Erst bei echter
  Integration, **dann** in die regulären Docs ziehen.
- **Adafruit-Lib-Alternative:** `adafruit-circuitpython-bno055` + `adafruit-blinka`
  (komfortabler: Euler/Quaternion/lineare Beschleunigung als Properties) — nur falls Blinka
  auf Pi 5/Ubuntu sauber läuft. Für Hello-World nicht nötig.
- **Montage-Orientierung:** beim Einbau Achsen-Ausrichtung (REP-103: +X vorne, +Z oben)
  festlegen — relevant erst für A5, nicht für diesen Test.
