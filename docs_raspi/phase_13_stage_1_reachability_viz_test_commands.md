# Phase 13 Stage 1 / Teil 1 — Test-Commands: Reachability-Viz benutzen

> **Plan:** [`phase_13_stage_1_walk_optimization_plan.md`](phase_13_stage_1_walk_optimization_plan.md) §4.1.
> **Was:** zeigt die **erreichbare Fuß-Hülle pro Bein** in RViz — 🔵 mit aktuellem
> Tibia-Limit (+1.30) vs 🔴 zusätzlich mit voller kalibrierter Tibia-Beuge (~150°).
> **Form:** Du führst aus, knappe Status zurück.
> Pure FK — **keine Sim/HW nötig**, läuft nur gegen das URDF-Modell.

---

## 0 — Build + Setup (einmalig nach Code-Änderung)

```bash
cd ~/hexapod_ws
colcon build --packages-select hexapod_gait hexapod_description
source install/setup.bash
```

---

## 1 — Starten (Default: leg_1)

```bash
cd ~/hexapod_ws && source install/setup.bash
ros2 launch hexapod_gait reachability_viz.launch.py
```

**Was hochkommt:**
- **RViz** mit dem Hexapod-Modell (Fixed Frame `base_link`).
- Ein **Joint-Slider-Fenster** (`joint_state_publisher_gui`) — damit kannst du jedes
  Gelenk bewegen und das Bein **in der Wolke** herumfahren.
- Die **Fuß-Wolke von leg_1**:
  - 🔵 **blau** = wohin der Fuß *jetzt* kann (aktuelles URDF-Tibia-Limit).
  - 🔴 **rot** = der *zusätzliche* Raum mit voller Tibia-Beuge (~150°) = verschenkter Spielraum.

> Falls die Wolke nicht erscheint: in RViz links bei **„Reachability"** prüfen, dass
> Häkchen an ist; Fixed Frame muss `base_link` sein (ist in der Config so).

---

## 2 — Bein umschalten / alle 6 / rotes Limit (live, ohne Neustart)

**2. Terminal:**
```bash
cd ~/hexapod_ws && source install/setup.bash

# anderes Bein anzeigen (leg_1 .. leg_6)
ros2 param set /reachability_viz leg leg_3

# alle 6 Beine gleichzeitig
ros2 param set /reachability_viz leg all

# zurück auf ein Bein
ros2 param set /reachability_viz leg leg_1

# rotes Tibia-Beuge-Limit ausprobieren (rad) — Wolke wächst/schrumpft
ros2 param set /reachability_viz tibia_full_upper 2.0    # ~115°
ros2 param set /reachability_viz tibia_full_upper 2.6    # ~149° (Default)

# Punkt-Dichte (höher = feiner, aber träger; Default 14)
ros2 param set /reachability_viz resolution 18
```
Die Änderung wirkt beim nächsten Re-Publish (~1,5 s). Im RViz-Launch-Terminal
loggt der Node jeweils `… → N blau + M rot`.

**Alternativ direkt beim Launch:**
```bash
ros2 launch hexapod_gait reachability_viz.launch.py leg:=all
ros2 launch hexapod_gait reachability_viz.launch.py leg:=leg_4 resolution:=10
ros2 launch hexapod_gait reachability_viz.launch.py with_jsp_gui:=false   # ohne Slider
```

---

## 3 — Was du siehst / wie interpretieren

- Die **gesamte Wolke** (blau+rot) = das 3D-Volumen, in dem der Fuß *überhaupt* sein kann.
  - **Coxa** (±24°) fächert links-rechts, **Femur** (±90°) hoch-runter, **Tibia** nah↔fern.
- 🔴 **Rot wächst nach innen/unten** — dorthin bringt die stärkere Beugung den Fuß
  *näher an den Körper*. Genau das brauchen wir für die feet-closer Lauf-Pose (Teil 2.2).
- **⚠️ Update Stage 1 Teil 2.1 (2026-06-02):** Das URDF-Tibia-Limit ist jetzt auf
  **+2.50 (143°)** freigeschaltet (war +1.30). Damit reicht der **Slider** (er liest die
  URDF-Limits) **jetzt bis +2.50** — du kannst das Bein also in den *früher* roten
  Bereich fahren. Die **blaue** Wolke reicht entsprechend bis +2.50; **rot** zeigt nur
  noch den schmalen Rest bis zum Mechanik-Max (`tibia_full_upper`, default 2.60).
  *(Vor dem Unlock klemmte der Slider bei +1.30 und die rote Zone war Vorschau —
  `tibia_full_upper` ändert nur die Wolke, nicht das URDF-Limit/den Slider.)*

---

## 4 — Beenden

Im Launch-Terminal **Strg+C** (beendet RViz + alle Nodes).

---

## 5 — Troubleshooting

| Symptom | Ursache / Fix |
|---|---|
| Keine Wolke | RViz: Display **„Reachability"** aktiv? Fixed Frame = `base_link`? Node-Log im Terminal („N blau + M rot")? |
| „Fixed Frame does not exist" | `static_transform_publisher` (world→base_link) muss laufen — kommt aus dem Launch; kurz warten. |
| Modell fehlt | `robot_state_publisher` braucht `/joint_states` → Slider-GUI (`with_jsp_gui:=true`) muss laufen. |
| `leg='xyz' unbekannt` im Log | nur `leg_1`..`leg_6` oder `all`. |
| Ruckelt bei `all` | `resolution` runter (z.B. 10) — 6 Beine × N³ Punkte. |

---

## Findings / Status (User) — Checkliste 1.5

| Check | Status | Notiz |
|---|---|---|
| RViz zeigt Modell + Fuß-Wolke (leg_1) | | |
| Blau (aktuell) vs Rot (extra Tibia) sichtbar/unterscheidbar | | |
| Bein-Umschalten live funktioniert (leg_3, all) | | |
| Rote Zone wächst nach innen/unten (verschenkter Raum plausibel) | | |
| Slider bewegen das Bein in der Wolke | | |
| Darstellung ok? (Punktgröße / Dichte / Farben) | | ggf. Wunsch hier |
