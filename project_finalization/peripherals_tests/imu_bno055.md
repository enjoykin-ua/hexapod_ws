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

Skript anlegen:

```bash
cat > ~/bno055_hello.py << 'PY'
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
~/bno055_venv/bin/python ~/bno055_hello.py
```

> Falls „Permission denied" auf `/dev/i2c-1`: Re-Login vergessen (4.3) → entweder neu einloggen
> oder mit sudo: `sudo ~/bno055_venv/bin/python ~/bno055_hello.py`

**Verifikation:**
- T2: `CHIP_ID = 0xA0`.
- T3: Board kippen → `Heading/Roll/Pitch` ändern sich plausibel.
- T4 (optional): Board langsam in alle Richtungen drehen → `gyr`/`acc`/`mag` steigen Richtung 3.

## 6. Done-Kriterien (Checkliste)

- [ ] I2C aktiviert (`config.txt`), Pi rebootet
- [ ] `i2cdetect -y 1` zeigt `0x28` (oder `0x29`) — *Adresse notieren, falls 0x29*
- [ ] Skript meldet `CHIP_ID = 0xA0`
- [ ] Heading/Roll/Pitch ändern sich beim Kippen (live)
- [ ] (optional) Cal-Werte steigen beim Bewegen

Alle Pflicht-Bullets `[x]` → IMU-Hello-World **verifiziert**, Status in `00_overview.md` auf 🟢.

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
