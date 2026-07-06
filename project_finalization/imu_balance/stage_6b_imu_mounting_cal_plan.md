# Stufe 6 / IP2 — IMU-Montage-Kalibrierung (AXIS_MAP + Zero-Offset)

> **Status: 🟢 abgeschlossen** — IP2.1–IP2.4 HW-verifiziert (AXIS_MAP `0x21`/`0x04` + yaw-unabhängiger
> Zero-Offset). Ergebnis, Design-Log (yaw-Bug + Fix) und Self-Review im
> [Progress-File](imu_balance_progress.md) (Stufe 6 / IP2).
> Voraussetzung war: **IP1 🟢** (Node liefert `/imu/data`,
> `axis_map_config`/`axis_map_sign` + `roll_offset`/`pitch_offset` als Params vorhanden). **Power-frei** —
> Roboter von Hand kippen / flach hinstellen, kein Servo-Strom.
>
> **Vorlauf:** IP1.7 (Pi-Kipp-Test) hat die Montage vermessen → der AXIS_MAP-Weg ist bestätigt tragfähig,
> die konkrete Fehlausrichtung ist bekannt (s. u.). Dieser Plan setzt sie um.

---

## 0. Kontext + IP1.7-Befund (der Input)

`/imu/data` läuft live am Pi (BNO-055, NDOF, 50 Hz, achsen-entkoppelt). **Aber** die Sensor-Achsen sind
gegen `base_link` verdreht — im Kipp-Test (Betriebslage, Körper oben, reproduzierbar) gemessen:

| Bewegung (physisch) | base_link-Erwartung (REP-103) | Sensor meldet (Default-AXIS_MAP P1) |
|---|---|---|
| rechte Seite (−Y) hoch | **roll −** | **pitch +24°** |
| Nase (+X) hoch | **pitch −** | **roll −15°** |
| flach | 0 / 0 | roll ~2.6 / pitch ~1.2 (Restschräge) |

Daraus die Achsen-Zuordnung:
- `Sensor_roll  = +base_pitch`
- `Sensor_pitch = −base_roll`
- ⇒ **Sensor-X = base-Y, Sensor-Y = −base-X, Sensor-Z = base-Z** = eine **+90°-Drehung um Z** (`R_z(+90°)`).

Das passt zur dokumentierten Montage („flach, mittig, in 90°-Schritten verschraubt"). Die IMU ist
**normal** orientiert (Z oben, `flach ≈ 0`, nicht kopfüber) — es fehlt nur die 90°-Z-Korrektur + der
feine Zero-Offset.

## 1. Ziel

Zwei **fixe** Ausrichtungs-Werte bestimmen + festschreiben, sodass `/imu/data` roll/pitch die **wahre**
`base_link`-Neigung liefert (Konsument unverändert):

1. **AXIS_MAP** (grobe 90°-Lage): dreht die Chip-Achsen im Chip auf `base_link`.
2. **Zero-Offset** (`roll0`/`pitch0`, feiner Rest): die ~2° Montage-Restschräge, damit „Basis eben → 0/0".

> Abgrenzung: **beides FIX** (Chip-vs-Basis, einmal). Das „Hang folgen statt ausgleichen" ist die
> **dynamische** Terrain-Slope-Schätzung (TF-1, separat) — **nicht** Teil von IP2.

## 2. Logik-Skizze / Vorgehen

### 2.1 AXIS_MAP herleiten (aus dem IP1.7-Befund)

BNO-055-Datenblatt §3.4 (Axis Remap). Register-Semantik:
- **`AXIS_MAP_CONFIG` (0x41):** bits `[1:0]`=Ausgabe-X, `[3:2]`=Ausgabe-Y, `[5:4]`=Ausgabe-Z; Wert je Feld
  `00=X_chip, 01=Y_chip, 10=Z_chip` (welche **Chip**-Achse auf die jeweilige **Ausgabe**-Achse geht).
- **`AXIS_MAP_SIGN` (0x42):** bit0=X-Vorzeichen, bit1=Y, bit2=Z; `1 = negativ`.

Wir wollen Ausgabe = `base_link`. Aus dem Befund (`Sensor-X = base-Y`, `Sensor-Y = −base-X`, `Sensor-Z = base-Z`):
- **Ausgabe-X** soll `base-X` sein `= −Chip-Y` → Feld X = `Y` (01), X-Sign = **negativ**.
- **Ausgabe-Y** soll `base-Y` sein `= +Chip-X` → Feld Y = `X` (00), Y-Sign = positiv.
- **Ausgabe-Z** soll `base-Z` sein `= +Chip-Z` → Feld Z = `Z` (10), Z-Sign = positiv.

⇒ **`AXIS_MAP_CONFIG = 0b10_00_01 = 0x21`**, **`AXIS_MAP_SIGN = 0b001 = 0x01`** (Kandidat).

> ⚠️ Die BNO-AXIS_MAP-Semantik ist notorisch fehleranfällig (Ausgabe←Chip vs. Chip←Ausgabe leicht
> verwechselt). Deshalb: **Kandidat setzen, dann am Sensor per Kipp-Test verifizieren** — nicht blind
> festschreiben. Bei Fehlschlag die logisch nächste Variante testen (z. B. Sign-Bits X↔Y tauschen, oder
> Config 0x21 vs. die gespiegelte Placement-Tabellen-Alternative).

### 2.2 AXIS_MAP setzen + verifizieren (IP2.1)

```
Node mit axis_map_config:=0x21 axis_map_sign:=0x01 neu starten (Param).
Kipp-Test wiederholen (wie IP1.7, Betriebslage):
  rechte Seite (−Y) hoch  -> ERWARTET jetzt: roll NEGATIV, pitch ~0
  Nase (+X) hoch          -> ERWARTET jetzt: pitch NEGATIV, roll ~0
Erfolg  -> AXIS_MAP korrekt (beweist zugleich: AXIS_MAP dreht die Quaternion mit).
Fehlschlag (Quaternion unverändert vertauscht) -> AXIS_MAP dreht Quaternion NICHT
  -> Contingency: Node-Rotation (Option B), feste R_z(−90°)-Quaternion-Komposition im Node
     (analog zur Zero-Offset-Komposition in build_imu, aber fixe 90°).
```

**Vorzeichen final gegen die Sim/`quat_to_roll_pitch`-Erwartung** festnageln (dieselbe Konvention, die
`gait_node._on_imu` + Leveling nutzen — falsches Vorzeichen = positive Rückkopplung/Aufschwingen).

### 2.3 Zero-Offset messen (IP2.2)

```
Roboter FLACH auf ebenen Boden / ebene Platte (Wasserwaage).
/imu/monitor roll/pitch ablesen -> das SIND roll0/pitch0 (nach AXIS_MAP, in Grad -> rad).
Entscheiden:
  |Wert| < ~1°  -> unter dem Leveling-Totband (1,5°) -> Offset 0 lassen (vernachlässigbar).
  einige Grad  -> als roll_offset/pitch_offset (rad) setzen.
Gegenprobe: mit Offset flach hinstellen -> roll/pitch ~0.
```

### 2.4 Festschreiben (IP2.3)

- Werte in **`hexapod_sensors/config/imu_calibration.yaml`** schreiben (analog `servo_mapping.yaml`):
  `axis_map_config`/`axis_map_sign` (+ ggf. `roll_offset`/`pitch_offset`). `real.launch.py` lädt sie für
  den `bno055_imu`-Node (`parameters=[imu_calibration_yaml, {use_sim_time: False}]`), der isolierte
  Test-Start via `ros2 run … --params-file …/imu_calibration.yaml`. So greifen die Werte über **beide**
  Startwege + über Neustarts. `imu_calibration.yaml` in `setup.py` `data_files` mit installieren.
- Doku-Eintrag (Werte + Messdatum) + Progress-Häkchen.

## 3. Tests-Liste (mit Begründung)

| Test | Prüft | Ort |
|---|---|---|
| **Kipp roll-Achse** (rechte Seite hoch) | nach AXIS_MAP: **roll** reagiert (neg.), pitch ~0 | Live (Pi) |
| **Kipp pitch-Achse** (Nase hoch) | nach AXIS_MAP: **pitch** reagiert (neg.), roll ~0 | Live (Pi) |
| **Quaternion-Dreh-Nachweis** | AXIS_MAP≠Default ändert die publizierte Orientierung (sonst Contingency) | Live (Pi) |
| **Flach nach Offset** | `/imu/monitor` roll/pitch ≈ 0 (±Totband) auf ebener Fläche | Live (Pi) |
| **Bekannter Winkel** (optional) | Platte auf gemessenem Keil → `/imu/monitor` zeigt ihn ±1–2° | Live (Pi) |

**Bewusst NICHT (→ scope-out):**
- **Node-Unit-Tests für AXIS_MAP:** die Register-Schreibsequenz ist HW-Verhalten (Chip-intern), am Dev
  nicht sinnvoll simulierbar; die Zero-Offset-Mathematik ist bereits in IP1.6 unit-getestet.
- **Closed-Loop (Leveling bewegt Beine) / Gain-Retuning** → IP3 (`stage_6c`), braucht Servo-Power (Phase 8).
- **Yaw/Heading** — mag-basiert, driftet, ungenutzt.

## 4. Progress-Checkliste (→ Progress-File, Done-Vertrag)

```
IP2 (IMU-Montage-Kalibrierung):
- [x] IP2.1 AXIS_MAP config=0x21 / sign=0x04 (BNO-Placement P0, empirisch aus 4 Signs) — Kipp-Test: rechte Seite hoch → roll neg, Nase hoch → pitch neg (REP-103 = Sim)
- [x] IP2.2 Zero-Offset roll -2.2°/pitch 3.3° (-0.0384/0.0576 rad); ⚠️ World-frame-Erst-Ansatz war yaw-abhängig (pitch 3.3→6.5) → Fix: Body-frame-Komposition (rechts), yaw-unabhängig (Sim + yaw-Sweep-Test + HW)
- [x] IP2.3 Werte in imu_calibration.yaml + real.launch.py (parameters) + setup.py data_files
- [x] IP2.4 kritische Self-Review-Tabelle (im Progress-File)
```

## 5. Design-Entscheidungen (mit Alternativen)

| Entscheidung | Gewählt | Verworfen | Warum |
|---|---|---|---|
| Ausrichtung | **AXIS_MAP im Chip** | Node-Rotation (B) | IP1.7 zeigt konsistente Quaternion → AXIS_MAP-Weg tragfähig; B bleibt **Contingency**, falls AXIS_MAP die Quaternion doch nicht dreht (IP2.1 beweist es) |
| AXIS_MAP-Wert | **hergeleitet (0x21/0x01) + verifiziert** | Placement-Tabelle P0–P7 raten | Herleitung aus dem gemessenen +90°-Z ist nachvollziehbar; Verifikation am Sensor schützt vor der fehleranfälligen Register-Semantik |
| Zero-Offset | **erst messen, dann entscheiden** | pauschal setzen | < ~1° liegt unter dem Leveling-Totband → 0 lassen spart einen Param; nur echte Restschräge festschreiben |
| Ablage der Cal-Werte | **`imu_calibration.yaml`** (config/) | real.launch.py-Args-only; Node-Code-Defaults | greift bei launch **und** isoliertem `ros2 run --params-file` (Args-only greifen beim isolierten Start NICHT); konsistent mit `servo_mapping.yaml`; Cal von Treiber-Code getrennt |

## 6. Entschieden (User-Review) + verbleibende Punkte

**Entschieden (User-Review):**
- **Ausrichtung = AXIS_MAP im Chip** (Kandidat `0x21`/`0x01`, am Sensor verifizieren). Node-Rotation (B)
  nur als **Contingency** — Node-Änderung nur, wenn IP2.1 zeigt, dass der AXIS_MAP die Quaternion nicht dreht.
- **Ablage = `hexapod_sensors/config/imu_calibration.yaml`** — greift bei launch **und** isoliertem
  `ros2 run --params-file`, konsistent mit `servo_mapping.yaml`.

**Verbleibend (in IP2.1/IP2.2 zu klären, kein offener Design-Punkt):**
- **Vorzeichen-Konvention** final gegen `tip_monitor.quat_to_roll_pitch` + `gait_node._on_imu` +
  Leveling-Vorzeichen prüfen (rechte Seite runter → welches roll-Vorzeichen erwartet das Leveling?),
  damit HW == Sim und kein Aufschwingen.
- **RViz-Verifikation** optional nachholen (hängt am DDS-über-Hotspot-Multicast) — für IP2 fachlich nicht
  nötig, der Log-Kipp-Test ist gleichwertig.

## 7. Handoff / Code-Anker

- **Params (existieren, IP1):** `axis_map_config` (0x41-Wert), `axis_map_sign` (0x42-Wert),
  `roll_offset`/`pitch_offset` (rad) in [`bno055_imu.py`](../../src/hexapod_sensors/hexapod_sensors/bno055_imu.py).
- **Ablage (IP2.3, neu anzulegen):** `hexapod_sensors/config/imu_calibration.yaml` (Node-Param-Block) →
  in `setup.py` `data_files` installieren + in `real.launch.py` als `parameters` an den Node hängen.
- **Init-Sequenz:** AXIS_MAP wird in `_init_sensor` **in CONFIG, vor NDOF** geschrieben (Datenblatt-Pflicht).
- **Zero-Offset-Komposition:** `build_imu` dreht `q_corr(−roll0,−pitch0,0)` vor die Sensor-Quaternion
  (IP1.6 unit-getestet). Node-Rotation-Contingency würde hier eine feste 90°-Quaternion analog einhängen.
- **Register:** `AXIS_MAP_CONFIG=0x41`, `AXIS_MAP_SIGN=0x42` (Default P1: `0x24`/`0x00`).
- **Bringup/Test:** [`stage_6_hw_imu_test_commands.md`](stage_6_hw_imu_test_commands.md) (Kipp-Test-Prozedur,
  Node-Neustart mit Param-Override).
