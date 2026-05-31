# Phase 13 Stage 0.7 — Test-Anleitung (0.7.7 Sim-Visualisierung) 🟢 FERTIG (2026-05-31)

> Plan: [`phase_13_stage_0_7_cartesian_standup_plan.md`](phase_13_stage_0_7_cartesian_standup_plan.md).
> Verständnis-Doku: [`phase_13_stage_0_7_cartesian_standup_creation_steps_description.md`](phase_13_stage_0_7_cartesian_standup_creation_steps_description.md).
> **Interaktiv** — User führt aus dem Doc aus, knappe Status-Meldungen
> (Memory [[feedback_test_commands_in_doc_not_chat]], [[feedback_interactive_stage_test_doc]]).
> **Ziel 0.7.7:** sehen, dass der Roboter in Gazebo jetzt **kartesisch
> schürffrei** aufsteht (Füße in Phase 2 senkrecht, kein Einwärts-Schürfen mehr).
> Done-Kriterium der Stage (Strom) misst erst der **Boden-Test 0.8** — hier nur
> kinematische Sicht.

---

## 0. Vorbereitung (in jedem Terminal `source`)

0.7 hat **`hexapod_gait`** geändert (Engine + Node). Bauen + sourcen:

```bash
cd ~/hexapod_ws
source /opt/ros/jazzy/setup.bash
colcon build --packages-select hexapod_gait
source install/setup.bash
```

URDF-Pfad als Variable (für den nicht-lenienten IK-Limit-Check in T2):

```bash
HEX_URDF="$(ros2 pkg prefix --share hexapod_description)/urdf/hexapod.urdf.xacro"
echo "$HEX_URDF"
```

---

## T1 — Sim starten, power_on_mid-Startpose (wie 0.5)

### T1-A — Gazebo (Terminal 1)
```bash
cd ~/hexapod_ws && source install/setup.bash
ros2 launch hexapod_bringup sim.launch.py
```
Warten bis Gazebo offen ist und die 7 Spawner („Configured and activated")
durch sind. Der Roboter spawnt in power_on_mid (Femurs hoch, Bauch ~am Boden),
**wie in 0.5** — daran hat 0.7 nichts geändert.

- [ ] Roboter liegt ruhig auf dem Bauch, Beine eingezogen (nicht T-Pose).

---

## T2 — Kartesisches Aufstehen beobachten (Kern von 0.7.7)

**Sim aus T1 weiterlaufen lassen.** In **Terminal 2** den Gait starten — der
Default ist jetzt `standup_mode:=cartesian` (explizit gesetzt = unmissverständlich):

```bash
cd ~/hexapod_ws && source install/setup.bash
HEX_URDF="$(ros2 pkg prefix --share hexapod_description)/urdf/hexapod.urdf.xacro"
ros2 launch hexapod_gait gait.launch.py \
    use_sim_time:=true \
    robot_description_file:="$HEX_URDF" \
    standup_mode:=cartesian
```
- `use_sim_time:=true` Pflicht in der Sim (Memory `project_phase13_gait_launch_sim_time_default`).
- `robot_description_file` aktiviert den IK-Limit-Check (nicht-lenient).

Der Ramp läuft über `auto_standup_duration` (Default 4 s), davon 40 % Phase 1
(Touchdown), 60 % Phase 2 (Push). **Im Gazebo-Fenster beobachten + melden:**

- [ ] **Phase 1** (~erste 1,6 s): die Füße fahren von eingezogen **nach unten**
      zum Boden — fast senkrecht, ohne den Bauch zu heben.
- [ ] **Phase 2** (~restliche 2,4 s): der **Körper hebt sich senkrecht**, die
      **Fußspitzen bleiben auf ihrem Bodenpunkt stehen** — **kein** Einwärts-
      Wandern mehr (das ist der ganze Sinn der Stage).
- [ ] Übergang Phase1→Phase2 ruckfrei, kein Kippen, kein Wegrutschen.
- [ ] Terminal 2: Log `Cartesian-Standup gestartet: … (phase1=0.40, bh_start=-0.0135)`;
      **kein** `IKError`; Übergang nach STANDING.

> **Direkter Vergleich (optional, sehr aufschlussreich):** Sim + gait beenden,
> dann mit dem **alten** Modus neu starten und denselben Aufstehvorgang ansehen —
> hier *sieht* man das Einwärts-Schürfen:
> ```bash
> # Terminal 1: sim.launch.py neu;  Terminal 2:
> ros2 launch hexapod_gait gait.launch.py use_sim_time:=true \
>     robot_description_file:="$HEX_URDF" standup_mode:=joint_space
> ```

---

## T3 — Endpose stabil

**Weiterlaufen lassen.** Nach Abschluss:
- [ ] Roboter steht ruhig in der Stand-Pose, kein Nachschwingen/Drift.

Optional numerisch (Terminal 3) — Stand-Pose ≈ coxa 0 / femur −0.240 / tibia +0.758:
```bash
cd ~/hexapod_ws && source install/setup.bash
ros2 topic echo /joint_states --once
```

---

## T4 — body_height_start-Gegenprobe (§8.7)

Beobachten, ob der berechnete Touchdown-Wert (−0,0135 m) zur **Sim-Bauch-Auflage**
passt:
- [ ] Setzen die Füße am **Ende von Phase 1** sauber auf (nicht schon vorher
      schürfend, nicht erst nach hörbarem „Durchfallen" des Körpers)?

**Falls es nicht passt** (Füße setzen zu früh = schürfen in Phase 1, oder Körper
sackt am Übergang durch), `body_height_start` live justieren und T2 wiederholen —
z. B. etwas höher (weniger negativ):
```bash
# Terminal 3 (gait_node läuft): Wert testen, dann Sim+gait neu starten
ros2 param set /gait_node body_height_start -0.012
```
> Hinweis: Der Aufsteh-Trigger feuert nur **einmal** (beim ersten /joint_states).
> Für einen erneuten Versuch Sim + gait neu starten; den getesteten Wert dann als
> Launch-Arg `body_height_start:=…` mitgeben.

---

## 5. Aufräumen
Strg+C in Terminal 2 (gait), dann Terminal 1 (sim).
```bash
pgrep -af "gz sim|ros2 launch|gait_node" || echo "alle Prozesse beendet"
```

---

## Done-Mapping (→ phase_13_stage_0_progress.md 0.7.x)
| Test | Bullet |
|---|---|
| Build grün | (Teil 0.7.6) |
| T1 Sim power_on_mid | — (Vorbedingung, = 0.5) |
| T2 kartesisch, Füße in Phase 2 senkrecht / kein Schürfen | **0.7.7** |
| T3 Endpose stabil | 0.7.7 |
| T4 body_height_start passt | 0.7.7 |

## Findings (User, 2026-05-31) — 🟢 0.7.7 komplett
| Test | Status | Beobachtung |
|---|---|---|
| T1 power_on_mid | ✅ | Sim startet liegend in power_on_mid (wie 0.5) |
| T2 Phase 1 + Phase 2 | ✅ | „sah sehr gut aus" — kartesisch schürffrei, Füße in Phase 2 senkrecht |
| T3 Endpose stabil | ✅ | exakt coxa 0 / femur −0.240 / tibia +0.758, velocity ~1e-10, kein Drift |
| T4 body_height_start passt | ✅ | kein Durchsacken/Rutschen am Übergang → −0.0135 m passt zur Sim-Auflage |
