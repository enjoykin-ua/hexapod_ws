# Phase 13 Stage 0.6 — Test-Commands (HW aufgebockt: Init + Stand-up)

> **Übersicht:** [`phase_13_stage_0_plan.md`](phase_13_stage_0_plan.md) §6 (0.6).
> Baut auf **0.3** (Relay-gated Init-Sequenz, HW-verifiziert) + **0.4** (Stand-up-
> Logik, pure-python) + **0.5** (Sim-Aufstehen, validiert) auf. 0.6 = derselbe
> Flow auf **echter Hardware, aufgebockt**.
> **Form:** User führt aus dem Doc aus, knappe Status (Memory
> [[feedback_test_commands_in_doc_not_chat]], [[feedback_interactive_stage_test_doc]]).
> **Status:** 🟢 final (2026-05-31) — Live durch User: T1–T3 + T5 ✅, T4 = Füße
> wandern sichtbar einwärts → **Schürf-Befund auf HW bestätigt, kartesisches Aufstehen (neue Stage 0.7) getriggert.**

## ⚠️ Safety (CLAUDE.md §9 — erster HW-Stand-up)
- **Roboter aufgebockt** (Beine frei in der Luft, kein Bodenkontakt).
- **PSU-Kill-Switch griffbereit** — bei jedem unerwarteten Ruck/Stall sofort trennen.
- Erste Bewegung **langsam**: der Stand-up rampt über **~4 s** (konservativer
  0.4-Default, ~0.25–0.28 rad/s, weit unter dem 2.0-rad/s-URDF-Cap).
- Init schaltet den Relay **selbst** zu (0.3) — keine manuelle Relay-Steuerung nötig.

---

## Vorbereitung — alle in 0.3/0.4/0.5 geänderten Pakete bauen + sourcen
```bash
# Terminal 1 — Plugin (0.3) + Launch/URDF (0.3/0.5) + Gait (0.4 Stand-Pose):
cd ~/hexapod_ws
colcon build --packages-select hexapod_hardware hexapod_bringup hexapod_description hexapod_gait
source install/setup.bash
```
> Unit-Tests sind in 0.3 (hexapod_hardware 352/0/25) + 0.4 (hexapod_gait 357/0/25)
> bereits grün — 0.6 ist eine reine **Live**-Stage, kein erneuter CI-Lauf nötig.

Pfad zur HW-URDF (für den Gait-Limit-Check in T2) als Variable:
```bash
HEX_URDF="$(ros2 pkg prefix --share hexapod_description)/urdf/hexapod.urdf.xacro"
echo "$HEX_URDF"
```

---

## T1 — Init-Sequenz aufgebockt (Vorbedingung)
```bash
# Terminal 1 — startet Hardware + Relay-gated Init + JTCs (läuft weiter!).
ros2 launch hexapod_bringup real.launch.py initial_pose:=power_on_mid
```
**Erwartung (= 0.3-T2, hier als Vorbedingung):**
1. Femur-Pins enablen gestaffelt → **Relay klickt selbst EIN** → Femurs auf Servo-Mitte (~35° hoch), keine Bewegung.
2. Coxas, dann Tibias enablen (kleines Nachsetzen aus limp ok, **kein** Ruck).
3. **Alle 6 Beine** in der power_on_mid-Init-Pose, **kein** Bein bleibt unten.
4. Terminal-1-Log: **kein** `SAFETY FREEZE`/`OVERCURRENT`/`UNDERVOLTAGE`/`WATCHDOG`.

- [ ] **T1 PASS** = alle 6 Beine sauber in power_on_mid, Relay bleibt an.

Optional numerischer Beleg (Terminal 2):
```bash
cd ~/hexapod_ws && source install/setup.bash
ros2 topic echo /joint_states --once
```
Femurs ≈ −0.42…−0.64 rad (NICHT ≈0), Werte wie 0.5-T1-Tabelle (power_on_mid).

> **Falls Relay an-und-gleich-aus** mitten in der Sequenz: FW-Watchdog-Trip in
> der Settle-Lücke — sollte mit dem 0.3-R16-Heartbeat-Fix weg sein. Voraussetzung:
> `hexapod_hardware` frisch gebaut (Vorbereitung). Tritt es doch auf → melden.

---

## T2 — Stand-up all-6 aufgebockt (Kern von 0.6)
**T1-Launch in Terminal 1 weiterlaufen lassen.** In **Terminal 2** den Gait starten:
```bash
cd ~/hexapod_ws && source install/setup.bash
HEX_URDF="$(ros2 pkg prefix --share hexapod_description)/urdf/hexapod.urdf.xacro"
ros2 launch hexapod_gait gait.launch.py \
    use_sim_time:=false \
    robot_description_file:="$HEX_URDF"
```
- `use_sim_time:=false` — HW hat kein /clock (Default ist bereits false; explizit = unmissverständlich).
- `robot_description_file:=$HEX_URDF` — aktiviert den **nicht-lenienten IK-Limit-Check** im gait_node. Auf HW kritisch: eine Limit-Verletzung erscheint als `IKError` (statt als stiller Plugin-`safety_freeze`) — genau die Falle aus 0.4 (Memory `project_two_joint_limit_sources`).

gait_node startet den STARTUP_RAMP **automatisch** beim ersten vollständigen
`/joint_states` (= power_on_mid) — **kein cmd_vel nötig**.

**Erwartung (am aufgebockten Roboter über ~4 s beobachten):**
- [ ] **Alle 6 Beine** fahren **gleichzeitig** smooth in die Stand-Pose (nicht 3+3 gestaffelt).
- [ ] Bewegung **ruckfrei**, **kein** Servo-Stall, **kein** hartes Springen.
- [ ] Terminal 1: **kein** `SAFETY FREEZE`/`OVERCURRENT`/`WATCHDOG`. Terminal 2: **kein** `IKError`, Übergang STARTUP_RAMP → STANDING.

> Aufgebockt heißt: die Beine nehmen die Stand-Konfiguration **in der Luft** ein
> (kein Gewicht, kein Körperheben). Verifiziert wird die Stand-up-**Bewegung** +
> dass kein Servo unter der Winkel-Änderung stallt/freezt.

---

## T3 — Endpose stabil
**Launches weiterlaufen lassen.** Nach Abschluss des Ramps:
- [ ] Beine halten die Stand-Pose **mehrere Sekunden ruhig**, kein Zittern/Nachschwingen, kein Drift.
- [ ] Relay bleibt an, **kein** verspäteter Trip nach dem Ramp.

Optional numerisch (Terminal 3) — Stand-Pose ≈ coxa 0 / femur −0.240 / tibia +0.758 alle 6:
```bash
cd ~/hexapod_ws && source install/setup.bash
ros2 topic echo /joint_states --once
```

---

## T4 — Schürf-Beurteilung (visuell) → Trigger für das kartesische Aufstehen
> Zweck: entscheiden, ob das kartesische Aufstehen
> ([`phase_13_stage_0_7_cartesian_standup_plan.md`](phase_13_stage_0_7_cartesian_standup_plan.md),
> nach Trigger als Stage 0.7 umnummeriert) aktiviert wird (Schürf-Befund aus 0.5,
> Memory `project_phase13_standup_foot_scrape`).

Während T2 (Stand-up) die **Fußspitzen** beobachten:
- [ ] Wandern die Füße beim Aufstehen sichtbar **nach innen** (Richtung Körpermitte)?
      (Sim-FK sagt: erst ~+7 mm raus, dann ~−22 mm rein in der zweiten Hälfte.)

**Bewertung:**
- **Füße wandern sichtbar einwärts** → Schürf-Befund auf HW bestätigt →
  kartesisches Aufstehen aktivieren (wird **Stage 0.7**, Boden-Test → 0.8).
- **Kaum/keine Einwärts-Wanderung** → am Boden ggf. unkritisch → zurückstellen,
  endgültige Entscheidung am Boden-Test.

> Hinweis: Aufgebockt tritt **kein** echtes Schürfen auf (kein Bodenkontakt) — du
> beurteilst die **Fuß-Wanderung in der Luft** als Indikator. Das echte Schürfen
> unter Last misst erst der Boden-Test.

---

## T5 — Shutdown stromlos (Regression)
```bash
# Terminal 2: Strg+C (gait), dann Terminal 1: Strg+C (real.launch.py)
```
- [ ] Relay wird stromlos (bei Strg+C via FW-Watchdog-Fail-safe, 0.3-T5-Verhalten), Servos limp.
```bash
pgrep -af "ros2 launch|gait_node|ros2_control_node" || echo "alle Prozesse beendet"
```

---

## Done-Mapping (→ phase_13_stage_0_progress.md 0.6.x)
| Test | Bullet |
|---|---|
| Build grün | 0.6.1 |
| T1 Init-Sequenz aufgebockt (alle 6 power_on_mid, Relay an) | 0.6.2 |
| T2 Stand-up all-6 sauber, kein Stall/Freeze/IKError/Trip | 0.6.3 |
| T3 Endpose stabil | 0.6.4 |
| T4 Schürf-Beurteilung → 0.7-Entscheidung notiert | 0.6.5 |
| T5 Shutdown stromlos | 0.6.6 |
| Self-Review nach Live | 0.6.7 |

## Findings (User, 2026-05-31)
| Test | Status | Beobachtung |
|---|---|---|
| T1 Init aufgebockt | ✅ | alle 6 power_on_mid, Relay an, kein Trip |
| T2 Stand-up all-6 | ✅ | sauber hochgefahren, kein Stall/Freeze/IKError/Trip |
| T3 Endpose stabil | ✅ | stabil, kein Drift |
| T4 Schürf-Wanderung (0.7?) | ✅ Befund | **Füße wandern sichtbar einwärts → Schürf-Befund HW-bestätigt → kartesisches Aufstehen aktiviert (neue Stage 0.7)** |
| T5 Shutdown stromlos | ✅ | Rail aus, Servos limp |
