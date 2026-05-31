# Phase 13 Stage 0.5 — Test-Anleitung (Sim Init-Pose → Aufstehen)

> **Interaktive Stage.** Der User führt diese Befehle aus, meldet knappe
> Status (kein Voll-Output nötig). Plan: `phase_13_stage_0_5_sim_standup_plan.md`.
> Entscheidung §7.6: **nur Gazebo** (kein RViz in 0.5 — RViz-tf-Check → 0.6).
>
> **Alle Befehle hier sind vollständig + copy-paste-fähig.** Jeder Block ist
> ein eigenes Terminal (T#A / T#B …). Immer zuerst `source` in jedem neuen
> Terminal.

---

## 0. Vorbereitung (einmalig, in jedem Terminal `source`)

0.5 hat **`hexapod_description`** (ros2_control.xacro) + **`hexapod_bringup`**
(sim.launch.py) geändert. Beide bauen (0.3-Lektion R15: nie nur ein Paket
bauen, wenn mehrere geändert wurden), dann frisch sourcen.

```bash
cd ~/hexapod_ws
source /opt/ros/jazzy/setup.bash
colcon build --packages-select hexapod_description hexapod_bringup
source install/setup.bash
```

Pfad zur Sim-URDF (für den Gait-Limit-Check in T2) als Variable ablegen:

```bash
HEX_URDF="$(ros2 pkg prefix --share hexapod_description)/urdf/hexapod.urdf.xacro"
echo "$HEX_URDF"
```

---

## T1 — Sim startet in power_on_mid (NICHT T-Pose)

**Ziel:** Beweisen, dass `initial_value` vom gz-Plugin angewandt wird → der
Roboter spawnt in der echten HW-Init-Pose (Femurs hochgezogen ~−27°, Tibias
leicht eingeknickt, Bauch nahe Boden), **nicht** flach in T-Pose (alle rad≈0).

### T1-A — Sim starten (Terminal 1)

```bash
cd ~/hexapod_ws && source install/setup.bash
ros2 launch hexapod_bringup sim.launch.py
```

Warten bis Gazebo offen ist und die Log-Zeilen der 7 Spawner
(`joint_state_broadcaster` + `leg_1..6_controller`) „configured and activated"
zeigen.

### T1-B — Visuelle Prüfung (Gazebo-Fenster)

Beobachten + melden:
- [ ] Femurs zeigen **schräg nach oben** (Beine eingezogen), **nicht** waagrecht
      gestreckt (T-Pose).
- [ ] Bauch (`base_link`) liegt **nahe am Boden** (kleiner Drop von spawn_z=5 cm).
- [ ] Roboter ist **ruhig** (kein Zittern/Wegrutschen direkt nach dem Spawn).

### T1-C — Numerischer Beweis (Terminal 2): /joint_states == power_on_mid

```bash
cd ~/hexapod_ws && source install/setup.bash
ros2 topic echo /joint_states --once
```

**Erwartete Werte** (rad, ±0.03 Toleranz für Settle/Physik). Reihenfolge im
Echo ist alphabetisch nach Joint-Name — Werte pro Joint vergleichen:

| Joint | erwartet rad |
|---|---|
| leg_1_coxa / femur / tibia | −0.069 / −0.469 / +0.258 |
| leg_2_coxa / femur / tibia | +0.156 / −0.637 / +0.255 |
| leg_3_coxa / femur / tibia | −0.111 / −0.439 / +0.168 |
| leg_4_coxa / femur / tibia | +0.026 / −0.477 / +0.255 |
| leg_5_coxa / femur / tibia | +0.104 / −0.419 / +0.156 |
| leg_6_coxa / femur / tibia | +0.052 / −0.496 / +0.224 |

- [ ] **PASS** wenn die Femurs ≈ −0.42…−0.64 sind (NICHT ≈ 0).
      → `initial_value` wirkt, T1 grün.

> **⚠️ FALLBACK §7.5 — wenn die Femurs ≈ 0 sind (T-Pose):** dann ignoriert
> das gz-Plugin `initial_value`. **Nicht** debuggen-eskalieren — das ist der
> dokumentierte versionsabhängige Fall. Melden, dann entscheiden wir live
> zwischen §7.5-Option A (als Sim-Limitation dokumentieren, Aufstehen trotzdem
> von T-Pose zeigen) und B (Vorpose-Phase). **Kein Treiber-/System-Eingriff.**

> **Hinweis spawn_z (§7.2):** Liegt der Bauch nicht nahe genug am Boden oder
> spawnt der Roboter sichtbar *im* Boden, Sim mit Strg+C stoppen und mit
> anderem Wert neu starten, z.B.:
> ```bash
> ros2 launch hexapod_bringup sim.launch.py spawn_z:=0.08
> ```

---

## T2 — All-6 Stand-up, kein Kippen/Rutschen/Durchsacken

**Ziel:** Die fertige 0.4-STARTUP_RAMP-Logik fährt alle 6 Beine gleichzeitig
smooth zur Stand-Pose (radial 0.295 / body_height −0.080). gait_node startet
den Ramp automatisch beim ersten vollständigen `/joint_states`-Empfang —
**kein cmd_vel nötig**.

**Sim aus T1 weiterlaufen lassen.** Im **Terminal 2** den Gait starten:

```bash
cd ~/hexapod_ws && source install/setup.bash
HEX_URDF="$(ros2 pkg prefix --share hexapod_description)/urdf/hexapod.urdf.xacro"
ros2 launch hexapod_gait gait.launch.py \
    use_sim_time:=true \
    robot_description_file:="$HEX_URDF"
```

- `use_sim_time:=true` ist **Pflicht** in der Sim (Memory
  `project_phase13_gait_launch_sim_time_default`): ohne /clock blockt der
  rclpy-Timer den Ramp still.
- `robot_description_file:=$HEX_URDF` aktiviert den IK-Joint-Limit-Check
  (nicht-lenient) → die Sim verhält sich wie die HW und maskiert keine
  Limit-Verletzung (Memory `project_two_joint_limit_sources`).

Im Gazebo-Fenster über ~4 s (auto_standup_duration) beobachten + melden:
- [ ] **Alle 6 Beine** drücken **gleichzeitig** (nicht 3+3 gestaffelt).
- [ ] Körper hebt sich **gleichmäßig** vom Bauch, **kein Kippen** zu einer Seite.
- [ ] Füße **rutschen nicht** weg (μ=1.0 an den Füßen).
- [ ] Körper **sackt nicht durch** / fällt nicht zurück auf den Bauch.
- [ ] gait_node-Log: kein `IKError`, Übergang STARTUP_RAMP → STANDING.

> **⚠️ §7.4 — wenn der Bauch „klebt"/ruckt** beim Abheben (base_link hat nur
> Gazebo-Default-Reibung): melden. Fix-Option B = `base_link` in
> `hexapod.gazebo.xacro` niedrige Reibung (μ≈0.2) geben. Erst beobachten (A),
> B nur falls nötig.

---

## T3 — Endpose stabil

**Sim + gait aus T2 weiterlaufen lassen.** Nach Abschluss des Ramps:

- [ ] Roboter steht **mehrere Sekunden ruhig** in der Stand-Pose, kein
      Nachschwingen, kein Wegdriften, kein Einknicken.

Optional numerische Bestätigung (Terminal 3) — Stand-Pose ≈ coxa 0 / femur
−0.240 / tibia +0.758 für alle 6 Beine:

```bash
cd ~/hexapod_ws && source install/setup.bash
ros2 topic echo /joint_states --once
```

- [ ] **PASS** wenn alle 6 Beine ≈ (0.0 / −0.24 / +0.76) rad (±0.03).

---

## T4 — RViz-Konsistenz — ENTFÄLLT in 0.5 (§7.6)

Entscheidung §7.6: **nur Gazebo** in 0.5. Gazebo rendert das Modell bereits
mit Physik; RViz spiegelt nur `/joint_states` (tf-Frame-Check) und wäre hier
nahezu redundant. Der RViz-tf-Konsistenz-Check wird in **0.6 (HW)** gemacht,
wo RViz das einzige Visualisierungsfenster ist. **T4 in 0.5 = N/A.**

---

## 5. Aufräumen

Beide Launches mit **Strg+C** beenden (zuerst Terminal 2 = gait, dann
Terminal 1 = sim). Prüfen, dass `gz sim` und `ros2`-Prozesse beendet sind:

```bash
pgrep -af "gz sim|ros2 launch|gait_node|ros2_control_node" || echo "alle Prozesse beendet"
```

---

## 6. Done-Mapping (→ phase_13_stage_0_progress.md 0.5.x)

| Test | Progress-Bullet |
|---|---|
| Build grün | 0.5.4 |
| T1-B/C power_on_mid (nicht T-Pose) | 0.5.5 |
| T2 all-6 Stand-up sauber | 0.5.6 |
| T3 Endpose stabil | 0.5.7 |
| T4 RViz | 0.5.8 (N/A §7.6 — → 0.6) |
