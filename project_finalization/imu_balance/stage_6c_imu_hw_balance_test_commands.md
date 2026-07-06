# Stufe 6 / IP3 — Test-Befehle: IMU-Balance-Tuning auf HW (GROB)

> ⚠️ **Grob-Skizze, vor Umsetzung im nächsten Chat feinjustieren.** Voraussetzung: IP1/IP2 🟢,
> **2S-LiPo dran, aufgebockt** (CLAUDE.md §9), **DDS Dev↔Pi** funktioniert (Schritt 0). Plan:
> [`stage_6c_imu_hw_balance_tuning_plan.md`](stage_6c_imu_hw_balance_tuning_plan.md).
> Die konkreten Gain-Zahlen unten sind **Sim-Startwerte** — am Roboter nachziehen.

## Schritt 0 — DDS Dev↔Pi (Logging/RViz) sicherstellen

Über den Handy-Hotspot ist DDS-Multicast blockiert. Einer der beiden Wege:
```bash
# Variante A — Fast-DDS-Unicast (Profildatei liegt am Dev: ~/fastdds_hotspot.xml)
#   auf BEIDEN (Pi + Dev): IPs in der XML prüfen, dann export vor jedem ros2-Aufruf:
export FASTRTPS_DEFAULT_PROFILES_FILE=~/fastdds_hotspot.xml
export ROS_DOMAIN_ID=42                       # auf beiden gleich!
#   am Dev zusätzlich Firewall für den Pi öffnen:
sudo ufw allow from 192.168.75.0/24           # (IP-Bereich ggf. anpassen)
# Test: am Dev `ros2 topic list | grep imu`  -> Pi-Topics sichtbar?

# Variante B — Dev + Pi ins Router-Netz (Multicast geht dort nativ, kein Extra-Setup)
```

## Schritt 1 — HW-Bringup (Servo-Stack + IMU + Gait)

```bash
# Pi, Terminal A — Servo-Stack + IMU (2S-LiPo dran, aufgebockt!):
ros2 launch hexapod_bringup real.launch.py loopback_mode:=false enable_imu:=true
#   -> Controller aktiv + Relay/Servo-Power + bno055_imu (lädt imu_calibration.yaml) + imu_monitor

# Pi, Terminal B — Gait-Node (WICHTIG: use_sim_time:=false, sonst blockt der Timer still):
ros2 launch hexapod_gait gait.launch.py use_sim_time:=false
#   -> gait_node mit allen tip_*/leveling_*/slope_*-Params (live per `ros2 param set`)
```
> ⚠️ Exakte Launch-Args/Reihenfolge (real vs. gait, Auto-Standup) im nächsten Chat gegen die aktuelle
> `gait.launch.py`/`ramp_walk.launch.py` verifizieren — hier nur der grobe Aufbau.

## Schritt 2 — IP3.1 Kipp-Erkennung kalibrieren (aufgebockt, defensiv zuerst)

```bash
# Baseline: Rausch-Niveau im Stand beobachten (Dev):
ros2 topic echo /imu/monitor        # roll/pitch-Ruhe-Rauschen ansehen
# Schwellen live justieren (Dev oder Pi):
ros2 param set /gait_node tip_angle_warn_deg  <X>
ros2 param set /gait_node tip_angle_crit_deg  <Y>
ros2 param set /gait_node tip_rate_crit_dps   <Z>
ros2 param set /gait_node tip_debounce_ticks  <N>
```
**Prüfen:** Ruhe + langsamer Gang → **kein** WARN/CRIT (fehlalarmfrei). Von Hand kippen (aufgebockt) →
CRIT + Freeze **rechtzeitig**. Werte notieren.

## Schritt 3 — IP3.2 Statisches Leveling (STANDING)

```bash
ros2 param set /gait_node leveling_mode    horizontal
ros2 param set /gait_node leveling_kd      <klein starten, z.B. 0.01>   # Sim-Default 0.03
ros2 param set /gait_node deadband_deg     1.5
ros2 param set /gait_node slew_max_dps     <klein>                       # Korrektur-Rate begrenzen
ros2 param set /gait_node leveling_enable  true
```
**Prüfen:** im Stand → **kein Zittern/Oszillieren**. Leicht kippen / schiefe Unterlage → Körper
**levelt zurück**. `Kd` schrittweise hoch, bis knapp vor Oszillation, dann zurück. HW-Werte notieren.

## Schritt 4 — IP3.3 Terrain-Following im Laufen (höchstes Risiko, langsam!)

```bash
ros2 param set /gait_node leveling_mode  terrain     # roll->0, pitch folgt Hang + Gyro-D
# dann langsam geradeaus laufen (Teleop/cmd_vel), erst flach:
```
**Prüfen:** flach geradeaus → Gyro-D dämpft das Gang-Wackeln, **kein Aufschwingen**. Dann leichter Hang
→ Körper **folgt** statt zu kämpfen. Grenz-Hang + Gyro-D-Wert notieren. **Kill-Switch bereit.**

## Schritt 5 — Logging + RViz am Dev

```bash
# gleiche ROS_DOMAIN_ID + DDS (Schritt 0):
ros2 topic echo /imu/monitor                        # live roll/pitch
ros2 bag record /imu/data /imu/monitor /imu/slope   # Bag liegt am DEV (nicht Pi-SD)
rviz2 -d install/hexapod_description/share/hexapod_description/config/view_hw.rviz
#   -> Modell neigt sich mit der echten Lage; Leveln sichtbar
```

## Was NICHT hier getestet wird (→ separat/später)
- **Taster/Fußkontakt-Closed-Loop (S4)** gleichzeitig — eigener HW-Test; Kombi-Integration danach.
- **Quer-Hang (`TF-Quer`)**, **Auto-Tuning**, **Kante/Stufe** (S4-Terrain).

## Ergebnis sichern
HW-Gains (`tip_*`, `leveling_kd/deadband/slew`, Gyro-D) in eine **HW-Preset-YAML** (analog
`hexapod_gait/config/presets/`) + Doku-Eintrag (HW-Werte vs. Sim-Defaults) → Progress-File IP3.
