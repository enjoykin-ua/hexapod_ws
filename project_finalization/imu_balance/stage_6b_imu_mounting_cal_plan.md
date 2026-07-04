# Stufe 6 / IP2 — IMU-Montage-Kalibrierung (Umriss)

> **Umriss-Doc** (bewusst weniger ausführlich als IP1). Wird nach IP1 zum vollen §4-Plan ausgebaut —
> IP1s Erkenntnisse (v. a. ob AXIS_MAP die Quaternion dreht) formen IP2 direkt.
>
> **Status: ⚪ vorgeplant.** Voraussetzung: IP1 🟢 (Node liefert `/imu/data`, AXIS_MAP- + Zero-Offset-
> Params existieren). **Power-frei** — Roboter von Hand kippen / flach hinstellen, kein Servo-Strom.

## Ziel

Die **zwei** fixen Ausrichtungs-Werte bestimmen und als Node-Params festschreiben, sodass
`/imu/data` roll/pitch = die **wahre** Basis-Neigung liefert:

1. **AXIS_MAP** (grobe Lage, orthogonal): welche Chip-Achse = welche `base_link`-Achse + Vorzeichen.
2. **Zero-Offset** (`roll0`/`pitch0`, feiner Rest): Montage-Restschräge, damit „Basis eben → 0/0".

> Abgrenzung: **beides ist FIX** (Chip-vs-Basis, einmal). Das „Hang folgen statt ausgleichen" ist die
> **dynamische** Terrain-Slope-Schätzung (TF-1, schon designt) — nicht Teil von IP2.

## Vorgehen (Skizze)

### IP2.1 — AXIS_MAP bestimmen (Kipp-Test)
- Roboter definiert um **roll-Achse** kippen (links/rechts) → erwartet: `/imu/monitor` **roll** ändert
  sich, **pitch ≈ 0**, richtiges Vorzeichen (rechts runter → vereinbartes Vorzeichen). Ditto **pitch**.
- Stimmt eine Achse nicht / ist vertauscht / falsches Vorzeichen → `axis_map_config`/`axis_map_sign`
  aus der **BNO-Datenblatt-Placement-Tabelle** (P0–P7) wählen, in `real.launch.py` setzen, neu prüfen.
- **Contingency (aus IP1-Risiko 1):** falls AXIS_MAP die **Quaternion nicht** dreht (nur Euler/Vektoren)
  → statt AXIS_MAP die **Node-Rotation (Option B)** aktivieren (feste 90°-Quaternion-Komposition). Dann
  ist IP2.1 = die Rotations-Quaternion setzen statt der AXIS_MAP-Register.

### IP2.2 — Zero-Offset messen
- Roboter **flach auf ebenen Boden** stellen (Wasserwaage/ebene Platte).
- `/imu/monitor` roll/pitch ablesen → das **sind** `roll0`/`pitch0`.
- **Erst messen, dann entscheiden:** < ~1° → unter dem Leveling-Totband (1,5°), vernachlässigbar, Offset
  = 0 lassen. Ein paar Grad → als `roll_offset`/`pitch_offset`-Param setzen (in rad).
- Gegenprobe: mit gesetztem Offset flach hinstellen → roll/pitch ≈ 0.

### IP2.3 — Festschreiben
- `axis_map_config`/`axis_map_sign` (+ ggf. Zero-Offset) als Defaults in `real.launch.py` (bzw. einer
  IMU-Config-YAML), damit sie über Neustarts erhalten bleiben.
- Kurzer Doku-Eintrag (Werte + Messdatum) + Progress-Häkchen.

## Tests (Skizze)
- Kipp um jede Achse → nur die erwartete Achse reagiert, richtiges Vorzeichen.
- Flach → roll/pitch ≈ 0 (nach Offset).
- Optional: bekannter Neigungswinkel (Platte auf Keil, gemessen) → `/imu/monitor` zeigt ihn ±1–2°.

## Offene Punkte (für den Voll-Plan nach IP1)
- Ergebnis von IP1-Risiko 1 (AXIS_MAP ↔ Quaternion) → AXIS_MAP-Weg vs. Node-Rotation.
- Ablage der Werte: `real.launch.py`-Args vs. eigene `imu.yaml` (Konvention mit `servo_mapping.yaml`).
- Vorzeichen-Konvention roll/pitch final festnageln (gegen die Sim/`quat_to_roll_pitch`-Erwartung).
