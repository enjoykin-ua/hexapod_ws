# S4-7 — Test-Befehle (Terrain-anpassendes Stehen / Adaptive Stand)

> Du führst die Tests aus, knappe Status-Meldung zurück. **Ziel:** auf unebenem Grund (Rubicon)
> soll der Roboter im **STANDING** die Beine einzeln bis zum Boden absenken (aufsetzen) statt in der
> Luft zu hängen. **Aus** (Default) = STANDING exakt wie heute (starre Flachboden-Pose, keine
> Regression). Statischer Zwilling von S4-2 (adaptiver Touchdown), im Stand statt im Schwung. Stage 4
> **isoliert** (`leveling_enable:=false` — IMU/Leveling ist komplementär, hier nicht nötig).

## Konventionen

- **Sourcing** je Terminal: `source /opt/ros/jazzy/setup.bash && source ~/hexapod_ws/install/setup.bash`
- **Daemon:** vor dem ersten `param set` einmal `ros2 daemon stop`. Adaptiv-Param **live** umschalten.
- **Pipeline läuft per Default** (`enable_foot_contact:=true`; Rubicon bringt IMU + Contact-Plugin mit).
- **Opt-in:** `adaptive_stand_enable` Default **false** → erster Lauf = altes (starres) Verhalten (Referenz).
- **Beobachtungs-Topic:** `/foot_contacts` (6× 0/1, `Float64MultiArray`) zeigt pro Bein Bodenkontakt.
  Reihenfolge = leg_1..leg_6.

## Einmalig vorab: bauen
```bash
cd ~/hexapod_ws
source /opt/ros/jazzy/setup.bash
colcon build --packages-select hexapod_kinematics hexapod_gait hexapod_bringup hexapod_gazebo --symlink-install
# Fuel-Welt einmalig cachen, falls noch nicht:
gz fuel download -u "https://fuel.gazebosim.org/1.0/OpenRobotics/models/Rubicon"
```

## Offline-Vorprüfung (kein Sim nötig) — Envelope je Stance-Höhe
```bash
python3 tools/stand_conform_envelope_check.py            # Default max_depth 0.04
# erwartet: tief/mittel/hoch alle ✓ GREEN (Floor hoch = -0.140)
# Envelope-Grenze über alle Stance-Modi: max_depth 0.05 (0.06 → "hoch" RED).
```

> **Absenk-Tiefe (`stand_conform_max_depth`):** Default **0.04 m** (deckt Rubicon-Unebenheit ~3–5 cm;
> 0.02 war zu flach → Beine hingen über tieferen Senken). Tiefer geht **live bis 0.05** (envelope-
> verifiziert über alle Stance-Modi). Erreicht ein Fuß den Boden auch bei 0.05 nicht, ist der Dip dort
> > 5 cm → das ist die dokumentierte v1-Grenze (Körperhöhen-/Neigungs-Adaption = späterer Nachfolger).

---

## T1 — Uneben stehen: setzen die Füße auf? (A/B)

**▶ Terminal 1 — Rubicon-Welt + Roboter spawnen:**
```bash
source /opt/ros/jazzy/setup.bash && source ~/hexapod_ws/install/setup.bash
ros2 launch hexapod_bringup rubicon.launch.py
```
> Optional an eine rauere Stelle spawnen (mehr Höhenunterschied unter den Füßen): `spawn_x:=5`.

**▶ Terminal 2 — Aufstehen (Leveling isoliert AUS):**
```bash
source /opt/ros/jazzy/setup.bash && source ~/hexapod_ws/install/setup.bash
ros2 launch hexapod_gait gait.launch.py leveling_enable:=false
```
⏳ Aufstehen abwarten — Roboter steht (evtl. mit hängenden Beinen über Senken).

**▶ Terminal 3 — Kontakte beobachten:**
```bash
source /opt/ros/jazzy/setup.bash && source ~/hexapod_ws/install/setup.bash
ros2 topic echo /foot_contacts
```
→ **A) Referenz (adaptiv AUS):** auf unebenem Grund hängen einzelne Beine in der Luft, z.B. Muster
wie `[1.0, 1.0, 0.0, 1.0, 1.0, 0.0]` (2 Beine ohne Kontakt = über Senken).

**▶ Terminal 4 — adaptiv AN (live):**
```bash
source /opt/ros/jazzy/setup.bash && source ~/hexapod_ws/install/setup.bash
ros2 daemon stop
ros2 param set /gait_node adaptive_stand_enable true
```

**✅ Erwartung:** mit AN senken die hängenden Beine langsam ab (bei `stand_conform_rate` 0.02 m/s;
4 cm ≈ 2 s) und **setzen auf** → `/foot_contacts` geht Richtung `[1,1,1,1,1,1]` (Senken bis 4 cm).
**Tiefe Dips (> `stand_conform_max_depth`) hängen** bewusst am Floor (`body_height − max_depth`) —
dokumentiert, kein Bug (Körperhöhe/-neigung-Adaption für tiefe Dips = späterer Nachfolger, §6). Der
Körper bleibt ruhig (x,y unverändert, nur z abgesenkt).

> ⚠️ **Wenn Beine noch hängen (z.B. `[100101]`, Beine 2/3/5 1–3 cm zu hoch):** der Dip dort ist tiefer
> als `stand_conform_max_depth`. **Live tiefer stellen** (envelope-sicher bis 0.05):
> ```bash
> ros2 daemon stop
> ros2 param set /gait_node stand_conform_max_depth 0.05
> ```
> Setzt der Fuß dann auf → es war nur die Tiefe. Setzt er auch bei 0.05 nicht auf → Dip > 5 cm (v1-Grenze).
> ⚠️ Falls ein Bein über einer **flachen** Stelle **fälschlich** absenkt statt bei Nominalhöhe zu
> verankern → melden (mit `/foot_contacts` + `L1 contact`-Log aus Terminal 2).

---

## T2 — Stance-Höhe per Controller wechseln → Re-Konform

Bei aktivem Adaptive die Stance-Höhe umschalten (Reposition + neue Höhe gekoppelt) — die Füße müssen
**neu konform** absenken (nicht mit altem Offset überstrecken). Wechsel per **PS4-Controller**.

**▶ Terminal 4 (oder eigenes) — Teleop starten:**
```bash
source /opt/ros/jazzy/setup.bash && source ~/hexapod_ws/install/setup.bash
ros2 launch hexapod_teleop joy_teleop.launch.py controller:=ps4_bt
#   per USB-Kabel:  controller:=ps4_usb
```
(Bluetooth: Controller per **PS-Taste** verbinden, ist gepairt/getrusted.)

**Bedienung (Stance-Modus wechseln):**
- **L2 = tiefer**, **R2 = höher** — jeweils **OHNE R1** (Dead-Man) drücken. 3 Modi: tief/mittel/hoch,
  geklemmt an den Enden.
- Der Wechsel läuft als Tripod-Reposition (Beine umsetzen) + `body_height`-Lerp → danach STANDING im
  neuen Modus.

**✅ Erwartung:** nach dem Modus-Wechsel (STANCE_SWITCH → STANDING) senken die Beine **frisch ab der
neuen body_height** neu konform ab (`/foot_contacts` wieder Richtung voll), **kein** Überstrecken /
kein Sprung. Der Re-Konform wird beim STANDING-Wiedereintritt automatisch getriggert.

> Alternativ ohne Controller (direkte Höhenänderung im Stand triggert denselben Re-Konform):
> `ros2 daemon stop && ros2 param set /gait_node body_height -0.100`

---

## T3 — AUS = wie heute (Regressions-Check)

```bash
ros2 daemon stop
ros2 param set /gait_node adaptive_stand_enable false
```
**✅ Erwartung:** die Füße bleiben exakt auf der starren Stand-Pose (`z = body_height`), hängende
Beine hängen wieder wie vorher — **bit-identisch zum Verhalten ohne das Feature** (Referenz A aus T1).

---

## T4 (optional) — Live-Tuning Tiefe / Rate

```bash
ros2 daemon stop
ros2 param set /gait_node stand_conform_max_depth 0.05   # tiefer reichen (m, ≥0; envelope-Max 0.05)
ros2 param set /gait_node stand_conform_rate 0.04        # schneller absenken (m/s, >0)
```
> Ungültige Werte werden abgewiesen (`max_depth ≥ 0`, `rate > 0`). Tiefere `max_depth` vorher offline
> prüfen: `python3 tools/stand_conform_envelope_check.py --max-depth 0.05` (0.06 → "hoch" RED).

---

## Contact-Live-Guard (Sicherheit)

Wie S4-2: `adaptive_stand_enable` wird pro Tick mit der **Pipeline-Frische** verUNDet. Toter/stale
Fußkontakt-Publisher (Topic verstummt > 0.5 s) → adaptiv **aus** → starre Stand-Pose (die Füße
sacken **nicht** auf den Floor durch). Kein separater Test nötig (Node-Smoke deckt es ab), aber falls
`/leg_<n>/foot_contact` in der Sim mal ausfällt: der Roboter fällt sichtbar auf die starre Pose zurück.

---

## Befund (Sim-Verify)

_(nach dem Lauf ausfüllen: setzen die Füße auf unebenem Grund auf? tiefe Dips dokumentiert? Re-Konform
bei Höhenwechsel? AUS bit-identisch?)_
