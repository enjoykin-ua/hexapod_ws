# Phase 7 — Pi-Portierung & Hardware-Anbindung

**Dauer-Schätzung:** offen — HW-Bringup ist Kalenderzeit, nicht Story-Points
**Maschinen:** Raspberry Pi 4 (8 GB) **und** Desktop, plus Bench-Setup mit Servo2040
**Vorbedingung:** Phase 6 abgeschlossen, Sim funktioniert vollständig
**Verwandte Dokumente:**
- `phase_7_hw_port_handoff.md` — kompakter Codebase-Einstieg (existiert)
- `phase_7_safety_concept.md` — Defense-in-Depth, Failure-Modes (anzulegen vor Stufe C)
- `phase_7_servo_calibration.md` — Kalibrierungs-Methodik (anzulegen vor Stufe E)
- `phase_7_progress.md` — Live-Stufen-Tracker (anzulegen mit Stufe A)
- `phase_7_stage_<X>_test_commands.md` — pro Stufe (anzulegen vor jeder Stufe)

---

## Ziel

Der Hexapod-Code läuft auf dem Pi 4 mit echter Hardware (Servo2040 + 18
Servos, LiPo-versorgt). Software-Änderungen am Hexapod-Workspace
beschränken sich auf das neue Paket `hexapod_hardware` (C++ Custom
HardwareInterface) und ein neues Launch-File `real.launch.py` — der
restliche Stack (`hexapod_description`, `hexapod_kinematics`,
`hexapod_gait`, `hexapod_teleop`) bleibt **unverändert**.

Zusätzlich entsteht ein **eigenständiges Servo2040-Firmware-Repo** (C++,
Pimoroni-SDK), das nicht Teil von `hexapod_ws` ist und einen eigenen
CLAUDE.md-Kontext bekommt.

---

## Hardware-Inventar (BOM)

| Komponente | Spec / Modell | Status |
|---|---|---|
| Raspberry Pi 4 | 8 GB RAM | ✅ vorhanden |
| Pi-Storage | USB-3 SSD empfohlen statt SD | offen — entscheiden |
| Pi-Kühlung | passiv mit Heatsink oder aktiv | offen — entscheiden |
| Akku | Zeee 2S LiPo 7,4 V 5200 mAh 80C, XT60 | ✅ gewählt |
| LiPo-Ladegerät | Balance-Charger (ISDT/SkyRC) | zu beschaffen |
| LiPo-Safe-Bag | für Lagerung + Laden | zu beschaffen |
| Buck-Converter (Pi 5V) | **NICHT** der 9–36V-Typ! Suchen: 6–9 V → 5 V / ≥3 A | ⚠️ **OFFEN** — siehe Vorab-Entscheidung 1 |
| Hauptsicherung | KFZ-Flachsicherung 20–25 A in Akku-Plus | zu beschaffen |
| Hauptschalter | Akku → Schalter → Wandler + Servo2040 V+ | zu beschaffen |
| Anti-Spark (optional) | Loop-Plug mit Vorlade-Widerstand | nice-to-have |
| Bulk-Caps Servo-Rail | mind. 1000 µF + 100 nF nahe Servo2040 V+ | zu beschaffen |
| Servo2040 | Pimoroni, 18-Kanal RP2040 | ✅ vorhanden, Trace-Cut durchgeführt |
| Servos Coxa | 20 kg digital, 6 Stück, 4,8–8,4 V | ✅ gewählt |
| Servos Femur/Tibia | 35 kg digital, 12 Stück, 4,8–8,4 V | ✅ gewählt |
| Bench-PSU | RND Lab RND320-KA3305P, parallel-fähig (10 A) | ✅ vorhanden |
| Debug-Probe | Raspberry Pi Pico Debug Probe (SWD) | dringend empfohlen |
| 3D-Druck-Mat. | Bambu P1S — aktuell PLA matt schwarz | ✅ vorhanden, PETG/ASA als Option |
| Heat-Set-Inserts | M2/M3 Messing, einzuschmelzen | zu prüfen ob nötig |

---

## Vorab-Entscheidungen (Stufe 0)

Diese müssen **vor** dem Start von Stufe A geklärt sein, sonst baust du
auf wackliger Annahme.

| # | Entscheidung | Status / Wert |
|---|---|---|
| 1 | Buck-Converter passend zum 2S-LiPo (Eingang 6–9 V, 5 V/≥3 A Ausgang) | ⚠️ offen — der initial vorgesehene 9–36 V-Typ funktioniert nicht mit 2S |
| 2 | Hauptsicherungsgröße | ✅ 20–25 A KFZ-Flachsicherung |
| 3 | Schalter-Konzept | ✅ Akku → Sicherung → Schalter → (Wandler + Servo-Rail) |
| 4 | Servo2040-Pi-Protokoll | Vorentscheidung: Custom Binary über USB-CDC (`/dev/ttyACM0`). Frame mit CRC + Sequence-Counter. Final festzunageln in Stufe C |
| 5 | Servo2040-Firmware-SDK | ✅ Pimoroni C++ SDK |
| 6 | `hexapod_hardware` Sprache | ✅ **C++ zwingend** — `hardware_interface::SystemInterface` ist pluginlib-only, kein Python |
| 7 | Pi-Servo2040-Kommunikations-Layer | ✅ USB-C ↔ USB-A (CDC), kein GPIO-UART |

---

## Offene Punkte / Risiken

Konsolidiert aus der Vorab-Diskussion. Werden im jeweiligen Stufen-Done-Kriterium adressiert.

| # | Punkt | Adressiert in Stufe |
|---|---|---|
| 1 | Buck-Converter passend zum 2S-LiPo | Vorab 1, vor Stufe B |
| 2 | Hauptsicherung 20–25 A einbauen | B |
| 3 | Hauptschalter + Anti-Spark | B |
| 4 | Low-Voltage-Cutoff (Software auf Servo2040 oder HW-Modul) | C |
| 5 | LiPo-Ladegerät beschaffen | vor Akku-Inbetriebnahme |
| 6 | LiPo-Safe-Bag + Lade-Lokation (nicht-brennbare Unterlage) | vor Akku-Inbetriebnahme |
| 7 | Servo2040 Trace-Cut → GND-Continuity per Multimeter prüfen | B |
| 8 | USB-CDC vs UART final bestätigen | C |
| 9 | Per-Servo `enable()` gestaffelt → kein gleichzeitiger Inrush | C (Firmware) |
| 10 | Mechanische Vorpositionierung der Beine vor Power-On | E |
| 11 | PLA-Risiken bekannt — kritische Teile später ggf. in PETG/ASA | F/G falls Probleme |
| 12 | Pi-Shutdown-Disziplin vor Hauptschalter (SSH `shutdown`) | A (Prozedur dokumentieren) |
| 13 | Strommessung pro Servo via Servo2040 Current-Sense nutzen | C (Firmware) |
| 14 | Firmware-Sicherheitsebenen (Clamp/Watchdog/Strom-Limit/Soft-Ramp) | C |
| 15 | Lab-Netzteil-Spannung physisch markieren | vor B |
| 16 | Heat-Set-Inserts bei Servo-Halterungen | F falls Schraubenausriss |
| 17 | Drehmoment-Reality-Check: 35 kg-Servo vs. Stolperer-Last-Spitze | E (mit Strommessung verifizieren) |
| 18 | Servo-Mapping-Tabelle (Output 0–17 ↔ Joint) finalisieren | C |
| 19 | Cable-Management der 18 Servokabel | F |
| 20 | Mechanische End-Stop-Prüfung (Beine ohne Power durchschwenken) | E |

---

## Sicherheits-Konzept (Kurzform)

Die Vollversion mit Failure-Modes-Tabelle steht in
`phase_7_safety_concept.md` (wird vor Stufe C geschrieben). Hier nur die
Defense-in-Depth-Ebenen als Übersicht:

| Ebene | Wo implementiert | Schützt vor |
|---|---|---|
| 1 — Hard-Clamp pro Servo | Servo2040-Firmware vor PWM-Output | Software-Bug mit Out-of-Range-Sollwert |
| 2 — Watchdog | Servo2040-Firmware (Timeout > N ms ohne Pi-Frame → PWM aus) | Pi-Crash, USB-Disconnect, Software-Hang |
| 3 — Per-Servo Strom-Limit | Servo2040-Firmware mit Current-Sense | Mechanischer Stall, IK-Bug, Kollision |
| 4 — Total-Strom-Limit | Servo2040-Firmware | Mehrfach-Stall, Verkabelungsfehler |
| 5 — Soft-Ramp-Limit | Servo2040-Firmware (max ΔPulse/Tick) | Sprünge auch bei "valid" Sollwerten |
| 6 — JTC Velocity/Acc-Limits | `controllers.real.yaml` reduziert | High-Level-Software-Fehler |
| 7 — Dead-Man-Switch | `joy_to_twist` (R1 muss gedrückt sein) | User-Fehler, unbeabsichtigte Aktivierung |
| 8 — Physischer Kill-Switch | Hauptschalter trennt Akku | Worst Case, alles andere versagt |

**Goldene Regeln bis Stufe H:**
- Roboter **immer aufgebockt** (Beine in der Luft) bei allen Stufen vor H.
- Bench-PSU mit niedriger Strombegrenzung beginnen (1,5 A für erste Servo-Tests), inkrementell hochziehen.
- Erstinbetriebnahme **nie** am Akku, immer am Lab-Netzteil.
- Wenn etwas unerwartetes passiert: **erst Strom aus, dann analysieren**, nicht umgekehrt.

---

## Stufen-Übersicht

| Stufe | Inhalt | Vorbedingung | Hauptrisiko |
|---|---|---|---|
| A | Pi-Plattform Setup (OS, ROS2, Workspace, DDS, ohne HW) | — | gering |
| B | Strom-Bench-Aufbau, Verkabelung, Bulk-Caps, Boards ohne Servos | A, Vorab-Entsch. 1 erledigt | mittel (Verkabelung) |
| C | Servo2040-Firmware-Repo, Protokoll, Watchdog, Limits | B | hoch (HW-Safety beginnt hier) |
| D | `hexapod_hardware` C++ Plugin, Loopback-Mode first | C | mittel |
| E | Single-Leg aufgebockt + Per-Servo-Kalibrierung | D, Servos einzeln testbar | mittel (mechanisch) |
| F | Stand-Pose alle 18 aufgebockt | E | hoch (erster Vollstrom) |
| G | Tripod-Gait in der Luft (alle 18 koordiniert) | F | mittel |
| H | Stand + langsamer Walk auf Boden (gesichert) | G | hoch (Sturz-Risiko) |
| I | PS4-Vollbetrieb, Tuning, Yaw-Drift-Charakterisierung | H | gering |
| J | Phasen-Doku-Abschluss, Konventionen, Tag | I | — |

---

## Stufen im Detail

### Stufe A — Pi-Plattform Setup

**Ziel:** Pi läuft headless mit ROS 2 Jazzy. Workspace baut. DDS-Discovery zu Desktop funktioniert. Stack-Komponenten ohne HW lassen sich starten.

#### A.1 OS-Image flashen

- Raspberry Pi Imager oder `dd`.
- Image: **Ubuntu Server 24.04 LTS (64-bit)** für arm64. Kein Desktop, headless.
- Imager-Settings: Hostname `hexapod-pi`, SSH aktivieren, User + Passwort, WLAN-Credentials.
- **USB-3-SSD bevorzugen** statt SD-Karte: SD korrumpiert bei jeder schmutzigen Abschaltung (= Servo-Brown-out + Pi runter), SSD verzeiht das.

#### A.2 Erstbootup, Update

```bash
sudo apt update
# KEIN apt full-upgrade — gezielte Pakete reichen
sudo apt install -y vim git curl net-tools
```

#### A.3 Locale, Universe-Repo

Identisch zu Phase 0 Schritte 1–2.

#### A.4 ROS2-Installation

```bash
sudo apt install -y \
  ros-jazzy-ros-base \
  ros-jazzy-ros2-control \
  ros-jazzy-ros2-controllers \
  ros-jazzy-xacro \
  ros-jazzy-joy \
  ros-dev-tools
```

**Nicht installiert auf Pi:**
- `ros-jazzy-desktop` (kein RViz)
- `ros-jazzy-ros-gz` (kein Gazebo)
- `ros-jazzy-gz-ros2-control` (Sim-Plugin)

#### A.5 Environment

```bash
echo "source /opt/ros/jazzy/setup.bash" >> ~/.bashrc
echo "export ROS_DOMAIN_ID=42" >> ~/.bashrc      # IDENTISCH zu Desktop
echo "export RMW_IMPLEMENTATION=rmw_fastrtps_cpp" >> ~/.bashrc
source ~/.bashrc
```

#### A.6 DDS-Konnektivität testen

Desktop: `ros2 run demo_nodes_cpp talker`
Pi: `ros2 run demo_nodes_py listener`

Erwartung: Pi empfängt vom Desktop.

> **Wenn nichts ankommt:** Firewall (`sudo ufw status`), gleiche `ROS_DOMAIN_ID`?, gleiches Subnetz / WLAN-Isolation?, `ros2 multicast send/receive` Diagnose, ggf. `ros2 daemon stop && start` auf beiden.

#### A.7 Workspace klonen, bauen ohne Sim-Pakete

```bash
cd ~
git clone <repo-url> hexapod_ws
cd hexapod_ws
touch src/hexapod_gazebo/COLCON_IGNORE   # Sim-Paket auf Pi überspringen
colcon build --symlink-install
```

#### A.8 Shutdown-Prozedur dokumentieren

In `phase_7_progress.md` Stufe A festhalten:
- **Immer** `sudo shutdown -h now` per SSH bevor Hauptschalter aus.
- Warten bis grüne LED am Pi erlischt.
- **Erst dann** Strom trennen.
- Begründung: Pi 4 + Linux + USB-SSD verzeiht keine schmutzige Abschaltung im laufenden Schreibvorgang.

#### A.9 Stack-Smoke-Test ohne HW

```bash
ros2 launch hexapod_teleop joy_teleop.launch.py
# PS4 anschließen, /cmd_vel und /cmd_body_height per `ros2 topic echo` prüfen
```

`gait_node` startet ohne `hexapod_hardware` nicht (keine HW-Interfaces) — das ist erwartet, kommt mit Stufe D.

**Done-Kriterium A:**
1. Pi headless via SSH erreichbar
2. Workspace baut grün (außer `hexapod_gazebo`)
3. DDS Desktop ↔ Pi bidirektional
4. PS4-Controller publisht `/cmd_vel` sichtbar
5. Shutdown-Prozedur dokumentiert

---

### Stufe B — Stromarchitektur Bench-Aufbau

**Ziel:** Komplettes Strom-Setup elektrisch verdrahtet, vermessen, **ohne Servos angeschlossen**. Bench-PSU als Quelle (noch kein Akku!).

#### B.1 Buck-Converter-Wahl

⚠️ Hard-Blocker — siehe Vorab-Entscheidung 1. Bevor Stufe B startet, muss ein 6–9 V → 5 V/≥3 A-Buck beschafft sein. Empfehlungen:
- Pololu D24V50F5 (5 V / 5 A, 7,5–22 V Input) — Industriestandard
- BEC aus RC-Bereich (Castle Creations, Hobbywing) — speziell für 2–6S-LiPo gemacht

#### B.2 Verkabelungs-Plan zeichnen

Skizze in `phase_7_progress.md` Stufe B aufnehmen:

```
Bench-PSU (7,4 V, CC=1,5 A) ─┬─[Sicherung 20A]─[Schalter]─┬─→ Servo2040 V+ (Servo-Rail)
                              │                            └─→ Buck-Eingang
                              │                                     │
                              │                                     └─→ Pi 5V (via USB-C oder GPIO)
                              │
                              └─ GND (Stern!) ────────────────────────→ Pi GND, Servo2040 GND
```

Akku-Anschluss kommt **erst nach** erfolgreichem Bench-Test. Bis dahin XT60-Verlängerung mit Krokoklemmen ans Lab-PSU.

#### B.3 GND-Stern physisch verifizieren

Multimeter Continuity-Mode:
- Pi-GND ↔ Servo2040-GND: durchgängig (< 0,5 Ω inkl. Kabel)
- Servo2040-Logic-GND ↔ Servo2040-Power-GND: durchgängig (sollte board-intern verbunden sein, trotzdem messen — der Trace-Cut könnte versehentlich GND mit getroffen haben)
- PSU-GND ↔ alle drei GND-Punkte: durchgängig

#### B.4 Bulk-Caps an Servo-Rail bestücken

Mindestens 1000 µF Elko (Polarität!) + 100 nF Keramik in Parallel, möglichst nah an den Servo2040-Schraubklemmen V+/GND. Reduziert Spannungseinbrüche bei Lastsprüngen.

#### B.5 Erst-Power-Up ohne Servos

PSU auf **7,4 V** und Strombegrenzung **0,5 A**.

Reihenfolge:
1. PSU aus, alles verkabelt, Schalter offen.
2. PSU einschalten, Schalter weiter offen → 0 A.
3. Spannung am PSU-Display prüfen, Spannung an Akku-Eingang messen.
4. Schalter zu → kurzer Inrush durch Bulk-Caps (CC-Limit greift evtl. einmal kurz, OK).
5. Spannung am Servo2040 V+ prüfen, Spannung am Buck-Ausgang prüfen (5 V?), Spannung am Pi-5V prüfen.
6. **Pi noch nicht booten lassen!** Erst nur Stromkreis ohne Last verifizieren.

Wenn Schritt 5 i.O.: Pi via USB-Kabel an Buck-Ausgang anschließen, Pi sollte hochbooten. Strom-Monitor am PSU beobachten — Pi-Idle zieht ~0,4 A, Boot-Peak ~0,8 A.

#### B.6 Servo2040 USB an Pi anschließen

Servo2040 Logic wird über USB-C vom Pi versorgt (oder umgekehrt, je nach Verkabelung). USB-Verbindung steht.

Pi: `dmesg | tail` sollte Servo2040-Enumeration zeigen.

```bash
ls -l /dev/ttyACM*
```

Sollte `/dev/ttyACM0` (oder ACM1) auftauchen, owned by `dialout`.

```bash
sudo usermod -aG dialout $USER
# einmal aus- und einloggen
```

**Done-Kriterium B:**
1. Buck-Converter im Spec-Bereich beschafft und montiert
2. GND-Stern verifiziert
3. Bulk-Caps montiert
4. PSU → Buck → Pi-Boot funktioniert stabil, kein Spannungsabfall < 4,8 V
5. Servo2040 als `/dev/ttyACMx` vom Pi erkannt
6. Verkabelungsskizze in Progress-File dokumentiert

---

### Stufe C — Servo2040-Firmware Bring-up

**Ziel:** Eigenständiges Servo2040-Firmware-Repo mit definierten Sicherheitsebenen. Pi kann einen einzelnen Test-Servo bewegen, Watchdog greift bei USB-Disconnect, Hard-Limits halten.

> Diese Stufe ist **die kritischste**. Hier wird entschieden, ob ein Software-Fehler in der Pi-Seite einen Hardware-Schaden verursachen kann oder nicht. Defense-in-Depth-Ebenen 1–5 leben hier.

#### C.1 Servo2040-Repo aufsetzen

- Eigenständiges Git-Repo, **nicht** Teil von `hexapod_ws`.
- Arbeitsname-Vorschlag: `hexapod_servo2040_fw`.
- Existierenden Code als Vorlage ins Repo importieren (User hat bereits eine erste Implementierung).
- Eigene `CLAUDE.md` anlegen mit:
  - Sprache C++ (Pimoroni-SDK)
  - Pico-SDK + Pimoroni-Libraries als Submodule oder Pfade
  - Build-System (üblicherweise CMake mit Pico-SDK)
  - Coding-Konventionen (Naming, Header-Struktur)
  - Hinweis: **kein** ROS2 in diesem Repo, nur Embedded
  - Protokoll-Definition als verbindlicher Anhang

#### C.2 Pimoroni-SDK-Doku-Review

Aktiv prüfen, bevor Code geschrieben wird:
- Welche PWM-Frequenzen sind pro Kanal unterstützt? (Digital-Servos vertragen meist 250–333 Hz, müssen aber empirisch bestätigt werden)
- Kann `enable()` pro Servo einzeln aufgerufen werden? **Diese Frage explizit verifizieren** — von der Antwort hängt die Boot-Pose-Sequenz ab. Pimoroni-Library hat das im Prinzip, aber gegen die aktuelle SDK-Version gegenchecken.
- Current-Sense-API: wie gemultiplext, welche ADC-Range, welcher Konversionsfaktor?
- USB-CDC: ist es Bulk-Endpoint mit eigenem Treiber, oder Standard-CDC-ACM? (Bestimmt, ob Pi `termios` reicht oder spezielle Konfiguration nötig)

#### C.3 Protokoll definieren und einfrieren

**Vorschlag — final festzunageln in dieser Stufe:**

Frame-Format (Binary, COBS-framed über USB-CDC):
```
[SEQ:1] [CMD:1] [LEN:1] [PAYLOAD:LEN] [CRC16:2]
```

Kommandos (Beispiele, anzupassen):
- `0x01 SET_TARGETS` — Payload: 18 × int16 Pulse-Width in µs (oder int16 Joint-Position in milliradian, je nach Design-Entscheidung)
- `0x02 GET_STATE` — Antwort: aktuelle Positionen + Per-Servo-Strom + Fehler-Bits
- `0x03 ENABLE_SERVO` — Payload: Servo-Index + on/off
- `0x04 SET_CALIBRATION` — Payload: Servo-Index + Offset + Scale (persistiert in Flash?)
- `0x7F ERROR_REPORT` — Servo2040 → Pi unsolicited bei Limit-Verletzung

**Design-Entscheidung pro Repo dokumentieren:**
- Pulse-µs vs. Joint-radian als Wire-Format? (Pulse-µs ist näher an HW; Joint-radian erfordert Kalibrierung in Firmware. Empfehlung: **Pulse-µs auf der Wire**, Pi macht die Joint-→-Pulse-Konversion mit Kalibrierungs-Tabelle. Hält die Firmware dumm.)
- Update-Rate Pi → Servo2040: 50 Hz reicht (GAIT_NODE läuft ohnehin mit 50 Hz). 100 Hz als Headroom OK.
- Bytes/Sekunde-Budget: 50 Hz × ~50 Byte/Frame = 2,5 kB/s — USB-CDC hat 1+ MB/s Bandbreite, kein Engpass.

> **Hinweis:** Falls der User-Bestand bereits ein anderes Protokoll spricht, dieses prüfen und entweder behalten (wenn es CRC + Watchdog hat) oder upgraden. Nicht aus Eitelkeit neu erfinden.

#### C.4 Firmware-Sicherheitsebenen implementieren

Reihenfolge im Code, jede Ebene vor der nächsten verifizieren:

**Ebene 1 — Hard-Clamp pro Servo:**
```cpp
// Pro Servo: kalibrierte pulse_min / pulse_max in Flash oder als Konstante
if (target_pulse < pulse_min[i]) target_pulse = pulse_min[i];
if (target_pulse > pulse_max[i]) target_pulse = pulse_max[i];
```
Verifikation: Pi schickt absichtlich Out-of-Range, beobachten dass Servo nicht über Limit fährt.

**Ebene 2 — Watchdog:**
```cpp
// Timeout-Konstante: z.B. 200 ms
if (millis() - last_valid_frame > WATCHDOG_TIMEOUT_MS) {
    disable_all_servos();   // PWM aus, NICHT auf Default-Pose anfahren
    state = WATCHDOG_TRIPPED;
}
```
Verifikation: USB-Kabel ziehen während Bewegung — Servo geht stromlos (mit dem Ohr hörbar, Servo wird "weich").

**Ebene 3 — Per-Servo Strom-Limit:**
```cpp
// Gleitender Mittelwert über N Samples
if (current_avg[i] > STALL_THRESHOLD_MA[i]) {
    disable_servo(i);
    send_error_frame(SERVO_OVERCURRENT, i);
}
```
Schwellen: 80 % des Datenblatt-Stallstroms pro Servo-Typ.
Verifikation: Servo manuell blockieren — Servo wird stromlos, Error-Frame am Pi sichtbar.

**Ebene 4 — Total-Strom-Limit:**
```cpp
if (sum_currents > TOTAL_MAX_MA) {
    disable_all_servos();
    send_error_frame(TOTAL_OVERCURRENT, 0);
}
```
Schwelle: konservativ, etwas über Stand-Pose-Erwartung (5 A), unter dem, was der Akku-Pfad zulässt.

**Ebene 5 — Soft-Ramp:**
```cpp
// max ΔPulse pro Tick — z.B. 20 µs/Tick bei 100 Hz = 2000 µs/s
int16_t delta = target_pulse - current_pulse[i];
if (abs(delta) > MAX_DELTA_PER_TICK) {
    delta = (delta > 0 ? 1 : -1) * MAX_DELTA_PER_TICK;
}
current_pulse[i] += delta;
```
Verifikation: Pi schickt sofortigen Sprung von Min auf Max — Servo fährt rampig, nicht in einem Sprung.

#### C.5 Per-Servo gestaffelter Start

```cpp
void boot_sequence() {
    // Alle Servos mit Stand-Pose-Sollwert konfigurieren, aber disabled
    for (int i = 0; i < 18; i++) {
        servos[i].set_target_us(stand_pose_us[i]);
        // NICHT enable() rufen
    }
    // Gestaffelt enablen
    for (int i = 0; i < 18; i++) {
        servos[i].enable();
        sleep_ms(50);   // 18 × 50 ms = 900 ms total
    }
}
```

#### C.6 Servo-Mapping-Tabelle finalisieren

In Firmware (Konstanten) und parallel in `hexapod_hardware/config/servo_mapping.yaml`:

```
servo2040_output_to_joint:
  0:  {joint: leg_1_coxa_joint,  direction:  1}
  1:  {joint: leg_1_femur_joint, direction:  1}
  2:  {joint: leg_1_tibia_joint, direction:  1}
  3:  {joint: leg_2_coxa_joint,  direction:  1}
  ...
  15: {joint: leg_6_coxa_joint,  direction: -1}
  16: {joint: leg_6_femur_joint, direction: -1}
  17: {joint: leg_6_tibia_joint, direction: -1}
```

`direction` ist nötig, weil links- und rechts-symmetrische Beine spiegelverkehrt drehen. Wert wird empirisch in Stufe E verifiziert.

#### C.7 Low-Voltage-Cutoff

Servo2040 hat einen ADC am Servo-Rail. Spannung samplen, wenn < 6,0 V (= LiPo bei ~3,0 V/Zelle): Warning-Frame an Pi. < 5,8 V: alle Servos disablen.

Wert konservativ ansetzen, der Akku-Innenwiderstand erzeugt unter Last bereits einen Sag — false-positives unter Walking-Last vermeiden, aber irreversiblen Tiefentladungs-Schaden verhindern.

#### C.8 Standalone-Test mit einem Servo

Ein einzelner Test-Servo (kein Bein), ohne Last, am Servo2040-Output 0. Pi schickt Pulse-Sollwerte via einfachem Python-Test-Script (nicht ROS, einfach `pyserial`). Servo fährt, Position lesbar, Strommessung lesbar, Watchdog testbar.

**Done-Kriterium C:**
1. Eigenes Servo2040-Repo mit CLAUDE.md + Protokoll-Dokumentation
2. Per-Servo-`enable()`-API verifiziert in der SDK
3. Hard-Clamp greift bei Out-of-Range-Sollwert (Test bestanden)
4. Watchdog disabled alle Servos bei USB-Disconnect (Oszi oder hörbar verifiziert)
5. Strom-Limit pro Servo disabled bei manueller Blockade
6. Soft-Ramp verifiziert (kein Sprung-Sollwert)
7. Standalone-Test: ein Servo fährt definiert, Strom messbar
8. Servo-Mapping-Tabelle final festgelegt

---

### Stufe D — `hexapod_hardware` C++ Plugin

**Ziel:** ROS-`SystemInterface`-Plugin spricht Servo2040, `ros2 control` Lifecycle vollständig durchlaufbar — zunächst im Loopback-Mode (ohne Servos), dann mit echtem Servo2040 aber **noch ohne Servos angeschlossen**. PWM-Pulse mit Oszi verifizieren.

#### D.1 Paket-Skelett

```bash
cd ~/hexapod_ws/src
ros2 pkg create --build-type ament_cmake --license Apache-2.0 hexapod_hardware
```

Abhängigkeiten in `package.xml`:
```xml
<depend>hardware_interface</depend>
<depend>pluginlib</depend>
<depend>rclcpp</depend>
<depend>rclcpp_lifecycle</depend>
```

#### D.2 SystemInterface implementieren

| Methode | Aufgabe |
|---|---|
| `on_init` | Joint-Liste aus URDF einlesen, interne Strukturen, Kalibrierungs-YAML laden |
| `on_configure` | Serial-Port öffnen (`/dev/ttyACM0`, termios oder libserial), Handshake mit Servo2040 |
| `on_activate` | `ENABLE`-Frame senden (gestaffelter Start läuft auf Servo2040-Seite) |
| `on_deactivate` | `DISABLE`-Frame, Port schließen |
| `export_state_interfaces` | je Joint: `position` (+ optional `velocity`, `effort` aus Stromsensing) |
| `export_command_interfaces` | je Joint: `position` |
| `read` | aktuelles `GET_STATE`-Frame parsen, Joint-Positionen in `state_`-Vektor |
| `write` | `command_`-Vektor → Joint-rad → Pulse-µs via Kalibrierung → `SET_TARGETS`-Frame |

Kritisch in `write()`: Joint-→-Pulse-Konversion mit Per-Servo-Offset und -Scale aus `servo_mapping.yaml`. Plus `direction` (±1).

#### D.3 Plugin-Registrierung

`hexapod_hardware.xml`:
```xml
<library path="hexapod_hardware">
  <class name="hexapod_hardware/HexapodSystemHardware"
         type="hexapod_hardware::HexapodSystemHardware"
         base_class_type="hardware_interface::SystemInterface">
    <description>Hexapod via Servo2040 USB-CDC.</description>
  </class>
</library>
```

`CMakeLists.txt`:
```cmake
pluginlib_export_plugin_description_file(hardware_interface hexapod_hardware.xml)
```

#### D.4 URDF-Anpassung (xacro-Argument)

```xml
<xacro:arg name="use_sim" default="true"/>
<xacro:property name="use_sim" value="$(arg use_sim)"/>

<ros2_control name="HexapodSystem" type="system">
  <hardware>
    <xacro:if value="${use_sim}">
      <plugin>gz_ros2_control/GazeboSimSystem</plugin>
    </xacro:if>
    <xacro:unless value="${use_sim}">
      <plugin>hexapod_hardware/HexapodSystemHardware</plugin>
      <param name="serial_port">/dev/ttyACM0</param>
      <param name="baudrate">1000000</param>
      <param name="calibration_file">$(find hexapod_hardware)/config/servo_mapping.yaml</param>
    </xacro:unless>
  </hardware>
  <!-- joint definitions wie Phase 4 -->
</ros2_control>
```

#### D.5 `controllers.real.yaml`

Kopie von `controllers.yaml`, aber:
- **`use_sim_time: false`**
- Velocity- und Acceleration-Limits drastisch reduziert (ca. 30 % der Sim-Werte) für Bring-up. Werden in Stufe I hochgezogen.

#### D.6 `real.launch.py`

```python
# Pseudocode-Skelett
controller_manager = Node(
    package='controller_manager', executable='ros2_control_node',
    parameters=[robot_description, controllers_real_yaml])

robot_state_publisher = Node(...)   # use_sim_time=false
joint_state_broadcaster = Spawner(...)
leg_controllers = [Spawner('leg_<n>_controller') for n in 1..6]

# KEIN Gazebo, KEIN ros_gz_bridge
```

#### D.7 Loopback-Test ohne Servo2040

`hexapod_hardware` bekommt einen `loopback_mode`-Param. Wenn true: `read()` liefert zuletzt geschriebene Pos als State zurück, kein Serial-Port. Damit ist der gesamte `ros2_control`-Stack auf dem Pi testbar ohne dass irgendwas an Servos hängt.

`ros2 control list_controllers` zeigt 1 JSB + 6 JTC active.

#### D.8 Echte Servo2040-Anbindung ohne Servos

`loopback_mode:=false`. Servo2040 angeschlossen (Stufe C-Repo geflasht), **keine Servos** an den Servo2040-Outputs. JTC schickt Trajectory → `hexapod_hardware::write()` → `SET_TARGETS` → Servo2040 generiert PWM-Pulse.

Verifikation mit Oszi oder Logic-Analyzer an einem Servo2040-Output-Pin: PWM-Signal mit erwarteter Pulsweite (1500 µs für Joint=0).

**Done-Kriterium D:**
1. `hexapod_hardware` baut und lädt als pluginlib-Plugin
2. xacro-Switch sim/real funktioniert (Builds beider Varianten grün)
3. `real.launch.py` startet ohne Fehler auf Pi
4. Loopback-Mode: alle Controller active
5. Echte Anbindung: PWM-Pulse am Servo2040-Output messbar und korrekt
6. `controllers.real.yaml` mit reduzierten Limits committed

---

### Stufe E — Single-Leg Bring-up + Kalibrierung

**Ziel:** Roboter aufgebockt. **Nur ein Bein** elektrisch angeschlossen. Per-Servo-Kalibrierung erhoben und in YAML eingetragen. Bein fährt definierte Trajektorien sauber.

#### E.1 Mechanische End-Stop-Prüfung (alle Beine, stromlos)

Bevor irgendein Servo bestromt wird: jedes Bein per Hand komplett durchschwenken. Welche Endlagen schlägt das Bein gegen Body oder anderes Bein? Diese Winkel ggf. **enger** als URDF-Limit in `servo_mapping.yaml` als Hard-Clamp eintragen.

#### E.2 Per-Servo-Kalibrierung Bein 1

Bein 1 elektrisch anschließen (Coxa, Femur, Tibia). Lab-PSU mit CC = 2 A für ein Bein.

Pro Servo:
1. Joint-Sollwert 0 rad → wo steht der Servo wirklich (visuell, mit Winkelmesser oder Foto-Referenz)?
2. `pulse_offset_us` so eintragen, dass Joint=0 dem mechanischen Ausgangspunkt entspricht.
3. Joint-Sollwert +π/4 rad → wo steht der Servo? Stimmt der Winkel?
4. `pulse_per_radian` justieren bis Soll-Ist-Winkel passt.
5. `direction` (±1) verifizieren.

In `hexapod_hardware/config/servo_mapping.yaml` einzelne Einträge ergänzen.

#### E.3 Bewegungstest Bein 1

Manuelle `JointTrajectory`-Goals an `/leg_1_controller/joint_trajectory`. Stand-Pose anfahren, kleine Bewegungen.

Strom-Monitor (Servo2040 Current-Sense via `read()`-Effort-Interface): Profil über Trajektorie aufnehmen. Sollte nirgendwo nahe Stall-Strom.

#### E.4 Single-Leg-Swing-Test

`stand_node` für Bein 1 nutzen + `gait_node` mit nur Bein 1 aktiv (geht nicht direkt, aber `cmd_vel` mit niedrigem Wert und beobachten ob Bein 1 schwingt — bei Tripod ist Bein 1 im A-Tripod).

**Done-Kriterium E:**
1. Alle Beine mechanisch durchgeschwenkt, Endlagen dokumentiert
2. Bein 1: Kalibrierung erhoben, in YAML eingetragen
3. Bein 1 fährt Stand-Pose mit < 5° Abweichung pro Joint
4. Strom-Profil pro Servo dokumentiert, < 80 % Stall
5. Kein Stall, kein mechanischer Anschlag

---

### Stufe F — Voller Stand aufgebockt

**Ziel:** Alle 18 Servos angeschlossen, kalibriert. Roboter weiter aufgebockt. Stand-Pose von der **stromlosen** Servo-Schiene aus anfahren.

#### F.1 Restliche 5 Beine kalibrieren

Wie E.2, aber für Beine 2–6.

#### F.2 Cable-Management

18 Servokabel durch definierte Kanäle führen. Spiralkabelschlauch oder Kabelbinder. Wo Kabel über Gelenke laufen: Mindest-Biegeradius respektieren, kein Knick bei Endlagen.

#### F.3 Boot-Pose-Sequenz live testen

1. Pi hochgefahren, ROS-Stack läuft, `real.launch.py` aktiv, `controllers.real.yaml` mit reduzierten Limits.
2. Servo-Schiene **noch stromlos** (Hauptschalter aus).
3. JTC bekommt Stand-Pose-Sollwerte (mechanisch passend, Beine sind manuell vorpositioniert).
4. Hauptschalter zu → Servo2040 ruft Boot-Sequenz, 18 × 50 ms gestaffelt enablen.
5. Spannung am Servo-Rail mit Oszi mitschneiden: erwarteter Dip beim Anfahren, aber keine Brown-out < 6,0 V.
6. Erwartetes Verhalten: Beine fahren sanft, nicht ruckartig, in Stand-Pose.

#### F.4 Stand-Pose-Stabilität

5 Min in Stand-Pose halten. Strom-Mittelwert pro Servo loggen, Temperatur der Servo-Gehäuse mit Hand fühlen oder IR-Thermometer.

**Done-Kriterium F:**
1. Alle 18 Servos kalibriert in YAML
2. Cable-Management ordentlich, keine Klemm- oder Scheuerstellen
3. Boot-Pose-Sequenz funktioniert ohne Brown-out
4. Stand-Pose 5 min stabil
5. Kein Servo > 50 °C nach 5 min Stand
6. Body-Pose visuell symmetrisch (Kalibrierung wirkt für alle Beine)

---

### Stufe G — Tripod-Gait in der Luft

**Ziel:** Vollständiger Tripod-Cycle aufgebockt, Beine hängen frei. Synchronität und Trajektorien-Glätte verifizieren.

#### G.1 Foot-Contact-Workaround

In Sim kommen `/foot_contact_*`-Topics aus Gazebo. Auf realer HW gibt's diese Sensoren nicht (außer du baust sie nach — kein Scope von Phase 7).

Optionen:
- **Open-Loop:** `gait_node`-Param `enable_foot_contact:=false` setzen. State-Machine läuft rein zeitgesteuert. Wahrscheinlich der pragmatische Weg.
- **Mock-Topic:** Dummy-Publisher publisht permanent `true` auf allen `/foot_contact_*`. Hässlich, aber kompatibel mit dem bestehenden Code.

Empfehlung Open-Loop, dafür den Stand-Drop in der State-Machine prüfen (in Sim wurde `body_height = -0.052` als JTC-Lag-Workaround genutzt; real auf -0.047 setzen).

#### G.2 Schwenk-Test

`gait_node` starten. `cmd_vel.linear.x = 0.05` per `ros2 topic pub` (nicht PS4 — noch).

Erwartung: drei Beine schwingen, drei "stützen" (in der Luft, ohne Last). Sieht symmetrisch aus? Trajektorien glatt? Keine JTC-Tracking-Lags wie in Sim (echte Servos haben keinen Lag).

#### G.3 Omnidirektional

`cmd_vel.linear.y`, `cmd_vel.angular.z`, Kombinationen. Alle Phase-5-Stufe-H-Modi durchprobieren, in der Luft.

#### G.4 PS4 als Eingabe

`joy_teleop.launch.py` zusätzlich starten. PS4-Controller in der Hand. R1-Dead-Man, D-Pad-Bewegung — wie in Phase 6, aber jetzt mit echter HW (immer noch aufgebockt!).

**Done-Kriterium G:**
1. Tripod-Cycle sichtbar synchron in der Luft
2. Omnidirektional alle Modi funktional
3. PS4-Teleop aufgebockt funktioniert
4. Strom-Profil dokumentiert, keine Stalls
5. Servo-Temperaturen < 60 °C nach 5 min Walk-in-Luft

---

### Stufe H — Stand + Walk auf Boden (gesichert)

**Ziel:** Roboter vom Bock. Hängevorrichtung über dem Roboter, Hand am Kill-Switch. Stand mit Gewicht, dann langsamer Walk.

#### H.1 Hängevorrichtung

Seil/Gurt durch Body-Aufhängung, an Decken-Haken oder Stativ. Roboter kann den Boden berühren, fällt aber nicht um, lässt sich bei Bedarf hochziehen.

#### H.2 Stand-Test mit Last

Stand-Pose von der Last her: trägt der Femur-Servo das halbe Roboter-Gewicht? Erwarteter Strom pro Femur-Servo: 1–2 A statisch. Wenn deutlich höher: Servo arbeitet gegen sich selbst (Kalibrierungs-Fehler) oder mechanische Verspannung.

5 min stehen. Sinkt der Body merklich (= Servo-Droop)? Werden Servos heiß?

#### H.3 Erster Schritt

`max_linear_x` in `gait_node`-Params auf 0,02 m/s. Per PS4 (R1 + D-Pad ↑). Roboter macht einen Schritt, vielleicht zwei.

Beobachten:
- Tracking visuell OK? (Beine landen wo erwartet?)
- Yaw-Drift sichtbar?
- Stürzt der Roboter beim Schritt? (Hängevorrichtung fängt ab — kein Schaden)
- Kommen Servo-Strom-Spitzen vor, die Limits triggern?

Bei Sturz: nicht in Panik mehr Code schreiben, sondern erst analysieren (Stromlog, Video).

**Done-Kriterium H:**
1. Stand mit Gewicht stabil > 30 s
2. Mindestens 1 m Walk geradeaus ohne Eingriff
3. Hängevorrichtung wurde nicht benötigt (Sturz-frei)
4. Kein Servo-Strom-Limit getriggert
5. Yaw-Drift charakterisiert (Wert dokumentiert)

---

### Stufe I — Vollbetrieb + Tuning

**Ziel:** PS4-Vollbetrieb wie in Phase 6, etappenweise Limits hochziehen.

- `max_linear_x` schrittweise hochziehen (0,02 → 0,05 → Phase-5-Wert)
- `body_height` auf -0,047 verifizieren
- L2/R2 Body-Lift testen
- Omnidirektional auf Boden
- Yaw-Drift charakterisieren (in 1 m Geradeaus-Walk wie viel Grad?)
- Akku-Test: vom Bench-PSU auf Akku umschalten, gleicher Walk-Test
- Battery-Runtime messen (vermutlich 20–40 min Walk)

**Done-Kriterium I:**
1. PS4-Vollbetrieb wie Phase 6 auf realer HW
2. Akku-Betrieb über mind. 10 min ohne Probleme
3. Yaw-Drift in Doku
4. Spannungsverlauf Akku unter Walk-Last in Doku
5. Servo-Temperaturen nach 10 min Walk dokumentiert

---

### Stufe J — Phasen-Doku-Abschluss

- `phase_7_progress.md` mit Live-Werten finalisieren
- `00_conventions.md` ergänzen (siehe nächster Abschnitt)
- Memory-Einträge für Cross-Phase-Themen
- `phase_7_pi_port.md` aktualisieren mit "Bekannte offene Punkte"
- Git-Commit + Tag `phase-7-done`
- `PHASE.md` markiert Phase 7 als abgeschlossen
- Retrospektive: was lief gut, was hat länger gedauert, was ist offen für Phase 8

---

## Stolperfallen

| Symptom | Ursache | Fix |
|---|---|---|
| Knoten auf Desktop sieht keine Knoten auf Pi | unterschiedliche `ROS_DOMAIN_ID`, Firewall, WLAN-Isolation | `ros2 daemon stop && start` beidseitig, Multicast-Test |
| `controller_manager` findet Plugin nicht | `pluginlib_export_plugin_description_file` fehlt | XML + CMake prüfen |
| `read`/`write` nicht aufgerufen | Controller im falschen State | `ros2 control list_controllers`, manuell aktivieren |
| Servo-Bewegung ruckartig | `update_rate` zu niedrig, Soft-Ramp zu aggressiv | `update_rate` ↑, Ramp-Param justieren |
| Servo-Position weicht stark von Soll ab | Kalibrierung Pulse-µs ↔ rad falsch | `servo_mapping.yaml` Offset/Scale anpassen |
| Servos fahren in falsche Richtung | `direction` (±1) im Mapping falsch | YAML korrigieren |
| Roboter zittert beim Stehen | digitale Servos kompensieren minimale Abweichungen | JTC-`stopped_velocity_tolerance` ↑, Trajectory-Filter |
| Brown-out beim Stand-Pose-Anfahren | Bulk-Caps zu klein oder Strom-Begrenzung am PSU zu niedrig | Caps ↑, PSU CC ↑ |
| Watchdog feuert ständig | Pi-Timing-Jitter zu hoch, Watchdog-Timeout zu eng | Timeout auf 300 ms |
| Pi sieht `/dev/ttyACM0` nicht | USB-Kabel, Permission, oder Servo2040 nicht enumeriert | `dmesg`, `lsusb`, dialout-Gruppe |
| Akku-Spannung fällt zu schnell unter Last | Akku-Innenwiderstand, schlechte Lötstelle, zu dünner Querschnitt | Verkabelung prüfen, Akku per Hi-C-Test verifizieren |

---

## Was in dieser Phase **NICHT** gemacht wird

- Keine Algorithmus-Änderungen an Gait oder IK (außer Bugfixes)
- Kein PREEMPT-RT-Kernel — Standard-Kernel reicht für 50 Hz Gait
- Keine zusätzlichen Sensoren (IMU, Lidar, Kamera, echte Foot-Contact-Sensoren) — separate Phase 8
- Kein Bluetooth-PS4 — Stufe-B-Defer aus Phase 6 bleibt
- Keine Closed-Loop-Yaw-Correction
- Keine TARA/CRA-Vollanalyse — `phase_7_safety_concept.md` ist eine Light-Version

---

## Konventions-Erweiterungen für `00_conventions.md`

Wird in Stufe J befüllt mit:
- Servo-Pulse-Range pro Servo-Typ (Coxa 20 kg vs. Femur/Tibia 35 kg, jeweils min/max µs)
- Servo-Mapping-Konvention (Output 0–17 ↔ Joint-Name + direction)
- Sicherheits-Defaults (Watchdog-Timeout, Soft-Ramp-Max-ΔPulse, Strom-Schwellen)
- Boot-Pose-Sequenz-Timing
- Cross-Reference auf `01_hardware_change_workflow.md` und `phase_7_safety_concept.md`
- LiPo-Sicherheits-Regeln (Lade-Lokation, Cutoff-Spannung, Lagerspannung)

---

## Phasenabschluss-Checkliste

- [ ] Alle Stufen-Done-Kriterien erfüllt
- [ ] Erster Walk auf Boden erfolgreich (Stufe H)
- [ ] PS4-Vollbetrieb auf Akku (Stufe I)
- [ ] Sicherheits-Doku in `phase_7_safety_concept.md` final
- [ ] Kalibrierungs-Doku in `phase_7_servo_calibration.md` final
- [ ] Konventionen erweitert in `00_conventions.md`
- [ ] System-Backup des Pi-Images (USB-SSD-Image)
- [ ] Git-Commit + Tag `phase-7-done` (im hexapod_ws **und** im Servo2040-Firmware-Repo)
- [ ] `PHASE.md` aktualisiert
- [ ] Retrospektive in `phase_7_progress.md`
