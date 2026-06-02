# Stage A1 — Test-Commands: Torque-/Hitze-Viz

> **Plan:** [`A1_torque_viz_plan.md`](A1_torque_viz_plan.md). **Form:** Du führst aus,
> knappe Status zurück. Pure-Viz/Analyse — **keine HW nötig** (Sim/HW optional).
> Param `total_mass` = echtes Gewicht (3.0) für belastbare Zahlen; sonst URDF-Massen (~2.63).

---

## 0 — Build (einmalig nach Code-Änderung)
```bash
cd ~/hexapod_ws
colcon build --packages-select hexapod_gait hexapod_description
source install/setup.bash
```

## S1 — Stand-Pose anzeigen (Default, das was du wolltest)
Zeigt die aktuelle **feet-closer Stand-Pose** (radial 0.215 / body_height −0.120) +
die Gelenk-Auslastung direkt am Modell:
```bash
cd ~/hexapod_ws && source install/setup.bash
ros2 launch hexapod_gait torque_viz.launch.py total_mass:=3.0
```
**Was du siehst (RViz):**
- Hexapod in der Stand-Pose, Fixed Frame `base_link`.
- **Pro Femur- und Tibia-Gelenk:** eine **farbige Kugel am Gelenk** (Anker) + darüber
  Text **„L<n> Femur/Tibia / <N·m> / <%>"** (z.B. `L1 Femur  +0.69Nm 20%`).
  Farbe: grün <50 % / gelb 50–80 % / rot >80 % der Servo-Nennleistung.
- **Coxa wird ausgelassen** (≈0 unter Vertikallast).
- **Cyan-Kugel** = Schwerpunkt (CoG) auf Boden-Ebene, **Polygon** = Stütz-Fläche,
  Text **„CoG OK (Marge … mm)"**. Rot/„INSTABIL" falls CoG außerhalb.

> Die Text-Zahlen drehen sich zur Kamera (TEXT_VIEW_FACING) — die **Kugel am Gelenk**
> + das **L<n>-Label** sagen dir, zu welchem Gelenk die Zahl gehört.

**Andere Pose ansehen** (live oder beim Launch):
```bash
ros2 launch hexapod_gait torque_viz.launch.py total_mass:=3.0 radial:=0.25 body_height:=-0.08
# oder live:
ros2 param set /pose_publisher radial 0.25
ros2 param set /pose_publisher body_height -0.08
ros2 param set /torque_viz total_mass 3.0
```

## S2 — Posen per Slider erkunden
```bash
ros2 launch hexapod_gait torque_viz.launch.py pose:=slider total_mass:=3.0
```
→ `joint_state_publisher_gui`-Slider; beim Bewegen ändern sich N·m/% + CoG/Polygon live.

## S3 — Neben Sim/HW (echte Pose, inkl. Laufen)
Faithfulste Variante — zeigt die **reale** Pose während Standup/Reposition/Laufen:
```bash
# Terminal A: Sim ODER HW + Gait wie gewohnt (mit feet_closer-Preset) starten.
# Terminal B:
cd ~/hexapod_ws && source install/setup.bash
ros2 run hexapod_gait torque_viz --ros-args -p total_mass:=3.0
```
Dann in der laufenden RViz eine **MarkerArray-Anzeige auf `/torque_markers`** hinzufügen
(oder die `view_torque.rviz` laden). Während des Laufens siehst du die Last live wandern.

## S4 — Sweep (last-optimale Pose finden, CLI)
```bash
cd ~/hexapod_ws && source install/setup.bash
python3 tools/torque_sweep.py --total-mass 3.0 \
    --radial-min 0.18 --radial-max 0.30 --radial-step 0.01 \
    --height-min -0.120 --height-max -0.060 --height-step 0.01
```
→ Tabelle (Femur%/Tibia%/Peak/Balance/Marge) + Empfehlung „last-minimal" / „best balanciert".

---

## Findings / Status (User)
| Check | Status | Notiz |
|---|---|---|
| S1 Stand-Pose lädt, Zahlen am Gelenk lesbar (Kugel + L<n>-Label) | | |
| Farben (grün/gelb/rot) + CoG/Polygon/Marge plausibel | | |
| S2 Slider: Werte ändern sich live | | |
| S3 (optional) neben Sim/HW: Last wandert beim Laufen | | |
| S4 Sweep liefert sinnvolle last-optimale Pose | | |

> **Befund Desktop-Sweep (3,0 kg):** Peak ~15–30 %; statisch **Femur > Tibia** (Hebelarm).
> Falls HW-Tibia heißer → Dynamik/Lauf oder Servo-Kühlung → am laufenden Roboter beobachten.
