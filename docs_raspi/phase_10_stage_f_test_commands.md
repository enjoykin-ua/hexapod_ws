# Phase 10 — Stufe F — Test-Anleitung (User-Smoke)

**Was geprüft wird:** Voll-Integration aller 3 leg_6-Servos unter IK +
gait_node-Kontrolle. Phase-12-Software-Pipeline wird hier durchgehend
verifiziert.

> 🚨 **Erste Walking-Trajectories.** PSU 7.0 V / **CC 8 A** (3 Servos).
> User-Hand am Bein vor Launch (Stage-D-Pattern).

**Stage F ist in zwei Halb-Stages aufgeteilt (User-Entscheid F-Q6):**

- **F-Phase-1:** F-T3 Lineal-Check (stromlos) + F-T4 Plugin-Bringup +
  F-T5 IK-Probe → Shutdown → Commit
- **F-Phase-2:** Bench-Setup wieder + F-T6 gait_node + cmd_vel +
  PSU-Display-Beobachtung (F-T8 CSV deferred zu Phase 12) → Shutdown → Commit

Doppelter Bringup-Aufwand für mehr Sicherheits-Anker zwischen IK-Test
und Walking-Test.

**Plan:** [`phase_10_stage_f_plan.md`](phase_10_stage_f_plan.md)
**Sicherheits-Setup:** [`phase_10_safety_setup.md`](phase_10_safety_setup.md)

**Was NICHT in Stage F ausgeführt wird:**
- Vel/Accel-Limit-Eintrag in `controllers.real.yaml` (Stage G)
- Boden-Walking (Phase 12)

---

---

# 🟢 F-Phase-1: F.1 + F.2 (Lineal + IK-Probe)

## Bench-Setup (VOR allen Tests!)

1. **Bench-PSU OUTPUT AUS**
2. **CC-Limit umstellen 4 A → 8 A** (3-Servo-Bein, Mutter-Plan §B)
3. Setpoint bleibt **7.0 V**
4. **Servo2040 USB** am Desktop sichtbar:
   ```bash
   ls -l /dev/ttyACM*
   ```
5. **Alle 3 leg_6-Servos anstecken:**
   - Coxa → Pin 15
   - Femur → Pin 16
   - Tibia → Pin 17
   - Polaritäts-Check pro Stecker (braun/rot/gelb)
6. **leg_5:** ruhige Default-Pose
7. **User-Hand bereit:** Bein in Phase-5-Stand-Position vorzuhalten
   (Fuß ~5–10 cm unter Body, alle Joints leicht geknickt). PSU-Aus-Knopf
   griffbereit.
8. **PSU OUTPUT AN** → Strom-Anzeige < 400 mA idle (3 Servos)
   - > 1 A = Verdacht auf Kurzschluss, sofort AUS

---

## F-T3 — F.1 Bein-Geometrie-Lineal-Check (~15 min, stromlos)

> **Stromlos:** für F.1 wird **kein Plugin gestartet**. Reine
> mechanische Messung. PSU kann AN bleiben, aber Plugin-Aktivierung
> kommt erst in F-T4.

### Mess-Schritte

Bein in geometrische Default-Pose halten (Coxa radial außen, Femur
horizontal, Tibia gestreckt). Pro Segment Lineal/Schieblehre anlegen:

| Segment | URDF (mm) | Mess-Punkt (Achse → Achse) | Toleranz |
|---|---|---|---|
| Coxa | 43.6 | Coxa-Joint-Welle → Femur-Joint-Welle | ±5 mm |
| Femur | 79.94 | Femur-Joint-Welle → Tibia-Joint-Welle | ±5 mm |
| Tibia | 200.0 | Tibia-Joint-Welle → Fuß-Spitze | ±5 mm |

**Bei Abweichung > 5 mm:**
- STOP, gemeinsam überlegen ob URDF angepasst wird
- Anpassung in `src/hexapod_description/urdf/hexapod_physical_properties.xacro`
- `colcon build --packages-select hexapod_description hexapod_hardware`
- F-T4 retest mit angepasster Geometrie

**User-Bestätigung F-T3:**
- [ ] Coxa-Länge: ___ mm (URDF 43.6 mm, ±5 mm OK?)
- [ ] Femur-Länge: ___ mm (URDF 79.94 mm)
- [ ] Tibia-Länge: ___ mm (URDF 200.0 mm)
- [ ] Alle 3 innerhalb ±5 mm → F-T4 starten

---

## F-T4 — F.2 Plugin-Bringup mit User-Hand (~3 min)

> 🚨 **Reihenfolge wie Stage D:** Hand zuerst, dann Launch.

### Schritt 1: Hand am Bein

User hält leg_6 in Phase-5-Stand-Position (Fuß ~5–10 cm unter Body,
ungefähr da wo Stand-Pose den Fuß hätte). Hand bleibt aktiv.

### Schritt 2: Plugin starten

```bash
# Terminal 1
cd ~/hexapod_ws
source install/setup.bash
ros2 launch hexapod_bringup real.launch.py loopback_mode:=false
```

### Schritt 3: Log-Sequenz beobachten

Wie Stage D: `on_init`, `on_configure`, `on_activate complete`, 18×
ENABLE_SERVO + neutral SET_TARGETS. Keine Trips.

### Schritt 4: Hand wegnehmen

Wenn alle 3 Servos sauber halten → **langsam** Hand wegnehmen. Servos
halten Bein in Joint-Mitten-Pose (Coxa radial außen, Femur horizontal,
Tibia gestreckt).

**User-Bestätigung F-T4:**
- [ ] Plugin-Bringup ohne Errors
- [ ] Alle 3 Servos halten Bein-Pose stabil nach Hand-Wegnehmen

---

## F-T5 — F.2 IK-Probe-Test (~15 min, **Loopback first, dann real**)

> **Zwei-Phasen-Strategie zur IK-Validation** (User-Vorschlag 2026-05-17):
> 1. **Loopback-Test** zuerst — Plugin echo't Goals ohne USB, RViz zeigt
>    simulierte Bewegung. Keine Bench-PSU, kein Servo-Risiko. Validiert
>    nur die IK-Mathematik + Trajectory-Generierung.
> 2. **Real-Test** danach — Plugin mit echter Servo2040-Verbindung,
>    Bench-PSU an, Bein bewegt sich physisch.
>
> Hintergrund: nach dem Tibia-Update (0.1787→0.200 m) hat sich der
> erreichbare Workspace für leg_6 verschoben. Default-Punkte im
> IK-Probe-Skript wurden auf Phase-5-Stand-Pose-Geometrie umgestellt
> (`(0.278, 0.256, -0.047)` → `(0.278, 0.256, -0.017)`). Loopback-Test
> zeigt ob die IK auflöst, bevor wir echte Servos riskieren.

### Phase-A: Loopback-Test (~7 min)

Wenn F-T4 schon `loopback_mode:=false` läuft, erst stoppen:

```bash
# Terminal 1: Ctrl-C → real.launch.py shutdown
# Bench-PSU OUTPUT AUS (kein Strom-Risiko während Loopback)
```

Loopback starten:

```bash
# Terminal 1
cd ~/hexapod_ws
source install/setup.bash
ros2 launch hexapod_bringup real.launch.py loopback_mode:=true
```

**Wichtig:** im Loopback-Modus spricht das Plugin NICHT mit der
Servo2040. Es echo't `command_state == current_state` zurück. Das
heißt:
- Plugin braucht keine USB-Verbindung
- Bench-PSU darf AUS bleiben
- Servos bewegen sich **nicht physisch**
- RViz zeigt die simulierte Bewegung (echo-state → tf2 → RobotModel)

RViz starten (Terminal 2):

```bash
rviz2  # Add RobotModel + TF (base_link)
```

IK-Probe ausführen (Terminal 3):

```bash
source ~/hexapod_ws/install/setup.bash
python3 ~/hexapod_ws/tools/phase_10_f2_ik_probe.py
```

**Erwartung im Loopback:**
- Skript loggt 2 IK-Ergebnisse (angles_a, angles_b)
- Action-Goal an `/leg_6_controller/follow_joint_trajectory` mit `status=SUCCEEDED`
- **RViz:** leg_6 bewegt sich sichtbar zu Goal A (Stand-Pose), dann
  3 cm vertikal hoch zu Goal B, in ~4 s
- **Echtes Bein:** bewegt sich **nicht** (Servos stromlos)

**Bei IKError im Loopback:**
- Punkte sind geometrisch nicht erreichbar → Default-Werte im Skript
  anpassen
- Kein Risiko, Plugin läuft weiter, einfach Skript modifizieren und neu
  starten

**Bei `status=SUCCEEDED` + saubere RViz-Bewegung:** → Loopback OK,
weiter zu Phase-B.

**Loopback shutdown:**

```bash
# Terminal 1: Ctrl-C
```

### Phase-B: Real-Test (~8 min)

> Erst nach erfolgreichem Loopback-Test!

User-Hand am Bein in Phase-5-Stand-Position vorhalten, dann:

```bash
# Bench-PSU OUTPUT AN (wieder)
# Terminal 1: real launch
ros2 launch hexapod_bringup real.launch.py loopback_mode:=false
```

Hand wegnehmen sobald Servos stabil halten.

> **Kein Strom-Logger** (F.4 deferred zu Phase 12). Stattdessen
> **PSU-Display beobachten** während IK-Probe läuft — Peak-Strom-Wert
> merken (informativer Sanity-Check, kein CSV).

IK-Probe ausführen (Terminal 3):

```bash
source ~/hexapod_ws/install/setup.bash
python3 ~/hexapod_ws/tools/phase_10_f2_ik_probe.py
```

**Erwartung im Real-Modus:**
- Wie Loopback **plus** echte Servo-Bewegung
- **Echtes Bein:** Fuß bewegt sich linear vertikal um ~3 cm hoch in ~4 s
- **RViz:** synchron zur echten Bewegung
- **PSU-Display:** Strom-Peak < 4 A erwartet
- Kein Stall-Brumm

**Bei Fehler:**
- IK-Error sollte nach Loopback-Phase nicht mehr auftreten
- Servo brummt → pulse_min/max zu eng (Stages-C/D/E-Werte überprüfen)
  oder direction-Fehler
- Bein bewegt sich nicht trotz „SUCCEEDED" → Servo-Verkabelung oder
  Plugin-USB-Issue prüfen

**User-Bestätigung F-T5:**
- [ ] Phase-A Loopback: IK ohne IKError, RViz zeigt 3 cm vertikale Bewegung
- [ ] Phase-B Real: Fuß bewegt sich linear vertikal ~3 cm
- [ ] RViz und echtes Bein synchron
- [ ] Kein Stall-Brumm
- (F.4 CSV-Logging deferred zu Phase 12 — kein CSV für F.2 nötig)

---

## 🛑 F-Phase-1 Ende — Shutdown vor Commit

```bash
Terminal 4: (IK-Probe-Skript ist von selber beendet)
Terminal 3: Ctrl-C (Logger stoppen)
Terminal 1: Ctrl-C → real.launch.py shutdown (18× DISABLE_SERVO)
```

Dann:
1. **Bench-PSU OUTPUT AUS**
2. **Coxa, Femur, Tibia von Servo2040 abziehen**
3. PSU bleibt 7.0 V eingestellt

**User-Bestätigung F-Phase-1-Shutdown:**
- [ ] real.launch.py sauber heruntergefahren
- [ ] PSU OUTPUT AUS
- [ ] Alle 3 Servos abgeklemmt

**→ User-Commit F-Phase-1**, dann weiter mit F-Phase-2.

---

# 🟢 F-Phase-2: F.3 + F.4 (gait_node + Strom-Auswertung)

## Bench-Setup (wieder anstecken)

1. **Bench-PSU OUTPUT AUS** (sollte aus sein nach F-Phase-1-Shutdown)
2. **CC-Limit weiter 8 A**, Setpoint 7.0 V
3. **Alle 3 Servos wieder anstecken** (Coxa Pin 15, Femur Pin 16, Tibia Pin 17)
4. **Stock-Halterungs-Check (Self-Review-Punkt #12):**
   - Sichtprüfung wie viel Spielraum leg_6 mech. nach unten hat unter der
     Aufhängung
   - Tripod-step_height = 3 cm → Bein hebt sich bei jedem Schwung 3 cm
     unter der Stand-Pose-Position
   - Falls Bein gegen Stock-Halterung schlagen könnte: leg_6 etwas
     anders aufhängen oder Stand-Pose-Punkt anpassen
5. **leg_5:** weiter in ruhiger Default-Pose
6. **User-Hand bereit** Bein horizontal vorzuhalten (wie F-Phase-1)
7. **PSU OUTPUT AN** → < 400 mA idle erwartet

---

## F-T4b — Plugin-Bringup für F-Phase-2 (~3 min)

> Re-Bringup wie F-T4 in F-Phase-1, gleiche Hand-Mitigation.

```bash
# Terminal 1
cd ~/hexapod_ws
source install/setup.bash
# (USER-HAND AM BEIN HORIZONTAL HALTEN, DANN:)
ros2 launch hexapod_bringup real.launch.py loopback_mode:=false
```

Hand wegnehmen sobald Servos halten. Plugin bleibt für F-T6 + F-T8 an.

---

## F-T6 — F.3 gait_node + cmd_vel (~10 min)

> **Plugin (Terminal 1) läuft.** Wir bauen drüber den gait-Layer auf.

> **F.4-Strom-Profil deferred** (User-Entscheid F-Phase-1-Self-Review):
> kein CSV-Logger — aufgehängtes Bein liefert keine repräsentativen
> Werte für Stage G/Phase 12. **Stattdessen:** PSU-Display während
> Walking beobachten, Peak-Strom merken (z.B. „~2.3 A" in progress.md
> als Stage-G-Sanity-Datenpunkt notieren).

### Schritt 1: RViz starten (Terminal 2, falls noch nicht offen)

```bash
rviz2  # Add RobotModel + TF (base_link)
```

### Schritt 2: gait_node mit HW-Args starten (Terminal 3)

> ⚡ **HW-Args zwingend** — `gait.launch.py` Default ist für Sim
> (`body_height=-0.052`, `use_sim_time=true`). Ohne Override:
> - `body_height=-0.052` (Sim-Workaround) wäre 5 mm tiefer als HW-Stand
> - `use_sim_time=true` würde gait-Timer auf `/clock`-Topic warten,
>   das im HW-Pfad nicht existiert → **gait hängt komplett**

```bash
source ~/hexapod_ws/install/setup.bash
ros2 launch hexapod_gait gait.launch.py \
  body_height:=-0.047 \
  use_sim_time:=false
```

**Erwartete Logs:**
- gait_node spawned
- State-Machine in STANDING-Default
- /cmd_body_height und andere Topics publiziert
- **PSU-Display:** Stand-Strom-Verbrauch stabil, typisch < 1 A

**Sim-Sicherheit:** dieser CLI-Override ändert **nichts** an
`gait.launch.py` selbst. Beim nächsten Sim-Aufruf
(`ros2 launch hexapod_gait gait.launch.py` ohne Args) lädt der
Sim-Default (-0.052) automatisch wieder.

### Schritt 3: cmd_vel füttern (Terminal 4)

> ⚡ **`--rate 10` ist Pflicht!** Ohne explizite Rate defaultet
> `ros2 topic pub` auf 1 Hz, was unter dem gait_node `cmd_vel_timeout=0.5 s`
> liegt → gait_node fällt nach jedem Pub auf `default_linear_x=0`
> zurück, Walking stottert nur Bruchteile.

```bash
source ~/hexapod_ws/install/setup.bash
ros2 topic pub --rate 10 /cmd_vel geometry_msgs/Twist '{linear: {x: 0.02}}'
```

**Erwartung:**
- gait_node schaltet auf WALKING-State
- Generiert Tripod-Pattern für alle 6 Beine
- **leg_6:** schwingt physisch vor/zurück im Tripod, Fuß-Hub ~3 cm —
  **hier wird Coxa stark schwingen** (Tripod-Vorwärts = Coxa-Hub)
- **RViz:** alle 6 Beine im Tripod-Pattern visualisiert
- **PSU-Display:** Peak-Strom merken (typische Erwartung 1–3 A bei
  `linear.x=0.02`, aufgehängtes Bein ohne Bodenlast)

### Schritt 4: Stock-Halterungs-Sichtkontrolle (Self-Review-Punkt #12)

Während des Walking-Tests **periodisch** visuell prüfen:
- Schlägt leg_6 in Aufhängung beim Hochschwung an?
- Bleibt > 1 cm Abstand zu mechanischer Halterung?

Falls Kontakt mit Halterung: PSU sofort AUS, Stand-Pose-Punkt anpassen
(`body_height` weiter nach unten setzen oder Aufhängung neu justieren).

### Schritt 5: ANY_SERVO_OVERCURRENT-Toleranz-Regel (Self-Review-Punkt #6)

> ⚠️ **Wichtig:** im Log werden wahrscheinlich `ANY_SERVO_OVERCURRENT`-
> Frames für leere Pins 0-14 auftauchen (Phase-9-Stolperfalle: Firmware
> misst Strom-Sensoren auch ohne angeschlossenen Servo).

**Toleranz-Regel:**
- **Tolerieren** wenn der Error nur Pins 0-14 betrifft (in dem Log-Eintrag
  steht meist welcher Servo-Index betroffen ist)
- **STOP wenn Pin 15, 16 oder 17 betroffen** (das sind die echten leg_6-
  Servos, kein false-positive)
- Plus tolerieren wenn das Bein visuell sauber läuft, ohne Brumm oder Trip

Cross-Phase-Anmerkung: in Phase 12 mit allen 18 Servos angeschlossen wird
dieses false-positive von selbst verschwinden. Firmware-Fix optional in
Phase 13+ (Pin-Maske für aktive Servos).

### Schritt 6: ~10 s laufen lassen, dann Ctrl-C alle Terminals

```
Terminal 4: Ctrl-C (cmd_vel pub stoppen)
Terminal 3: Ctrl-C (gait.launch.py stoppen) — leg_6 fährt zurück in Stand-Pose
```

**Plugin (Terminal 1) bleibt an** für eventuelle Re-Tests.

**Wenn F-T6 hängt aber F-T5 grün war:**
- Problem in gait_node oder cmd_vel-Mapping (nicht IK!)
- Debug: `ros2 topic echo /leg_6_controller/joint_trajectory` (was sendet gait_node?)
- Vergleich mit F.2-IK-Output: gleiche Joint-Werte?

**User-Bestätigung F-T6:**
- [ ] gait_node startet ohne Fehler (mit `body_height:=-0.047 use_sim_time:=false`)
- [ ] `cmd_vel` mit `--rate 10` wird angenommen, gait wechselt zu WALKING-State
- [ ] leg_6 schwingt physisch im Tripod-Pattern (Femur+Tibia deutlich, Coxa minimal — siehe Hinweis unten)
- [ ] Alle 6 Beine in RViz zeigen Tripod
- [ ] Kein Stall, kein WATCHDOG_TRIPPED
- [ ] **Stock-Halterungs-Check OK** (leg_6 schlägt nicht in Aufhängung)
- [ ] Kein OVERCURRENT auf Pin 15/16/17 (false-positives auf 0-14 toleriert)
- [ ] **PSU-Peak-Strom notiert** (in progress.md als Stage-G-Sanity-Datenpunkt)

### Hinweis: Coxa-Schwung bei `linear.x=0.02` ist by-design klein

Erwartete Coxa-Drehung mit gait_node-Defaults (cycle_time=2.0,
step_length_max=0.05):
- Stride = `linear.x × stance_duration = 0.02 × 1.0 = 2 cm`
- Coxa-Schwung = `atan2(2 cm, 27 cm) ≈ 4.2°`
- Servo-Pulse-Auflösung 1 µs ≈ 0.0058 rad → 12 µs Pulse-Schwung total
  → in echter Hardware visuell **nicht erkennbar** (Servo-Eigen-Toleranz
  + Mechanik-Spiel verdeckt es)

**Walking funktioniert** trotzdem korrekt — gait_node sendet die
Tripod-Trajectories, Plugin echo't im Loopback bzw. fährt im Real
die Servos. Die Stride-Größe ist Stage-G/Phase-12-Polish:
- Stage G: `controllers.real.yaml` Vel/Accel-Limits → mit Bench-Daten
  (oder Sim × 0.7) bestimmen, ggf. höhere `step_length_max` ableiten
- Phase 12 Stufe G „Limits hochziehen": schrittweise `linear.x` von
  0.02 → 0.05 → Phase-5-Werte (Mutter-Plan-Phase-12-Plan)

**Beobachtung Stance→Swing-Übergang:** kurze schnelle Bewegung beim
Wechsel zwischen den beiden Tripod-Phasen ist by-design (Velocity-
Vorzeichenwechsel im Cycle). Mit Bodenreibung in Phase 12 anders
fühlbar (Bein zieht den Body), aufgehängt sieht's etwas abrupt aus.

---

## F-T7 — F-Phase-2 Shutdown (~3 min)

```bash
Terminal 4: Ctrl-C (cmd_vel pub stoppen)
Terminal 3: Ctrl-C (gait.launch.py)
Terminal 1: Ctrl-C (real.launch.py → 18× DISABLE_SERVO)
```

Dann:
1. **Bench-PSU OUTPUT AUS**
2. **Alle 3 Servos abziehen**
3. PSU bleibt 7.0 V eingestellt

**User-Bestätigung F-T7:**
- [ ] Alle Launches sauber heruntergefahren
- [ ] PSU AUS, Servos abgeklemmt

---

## F-T8 — F.4 Strom-Profil-Auswertung — **deferred zu Phase 12**

> **User-Entscheid F-Phase-1-Self-Review:** F.4 CSV-Auswertung in
> Phase 10 entfällt, weil aufgehängtes Bein keine repräsentativen
> Werte für Stage G / Phase 12 liefert. Memory-Pendenz
> `project_phase10_real_yaml_vel_limits.md` bleibt aktiv für Phase 12
> (Voll-Bringup mit Last + Bodenkontakt).

**Statt CSV-Auswertung in Phase 10:**

- PSU-Display-Beobachtung während F-T6: Peak-Strom-Wert (z.B. „~2.3 A")
  im `phase_10_progress.md` F-Phase-2-Block als Sanity-Datenpunkt
  notieren
- **Stage G nutzt `Sim × 0.7`-Strategie** für Vel/Accel-Limits in
  `controllers.real.yaml` (Mutter-Plan-Empfehlung)
- **Phase 12** macht die echte Strom-Profil-Auswertung mit 18 Servos
  unter Last → dann werden die `controllers.real.yaml`-Limits nachfein
  verfeinert (Stage G ist konservativer Erst-Wurf)

**User-Bestätigung F-T8 (verschlankt):**
- [ ] PSU-Peak-Strom während F-T6 notiert in progress.md
- [ ] Verständnis: Phase 12 macht echtes Strom-Profil mit Last
- [ ] Werte in Stage-F-Notizen (`phase_10_progress.md` Stage-F-Sektion) übernommen

---

## Fehlerdiagnose-Tabelle

| Symptom | Wahrscheinliche Ursache | Fix |
|---|---|---|
| F.1 Längen-Abweichung > 5 mm | reale Bein-Geometrie ≠ URDF | URDF anpassen in `hexapod_physical_properties.xacro`, rebuild |
| F.2 IK wirft IKError | Zielpunkt geometrisch unerreichbar | Andere Punkte testen (näher zum Bein, höher) oder Bein-Längen prüfen |
| F.2 Fuß bewegt sich aber nicht linear vertikal | direction-Werte oder pulse-Cal stimmen nicht | RViz-Sync prüfen (sollte gleich aussehen); ggf. Stages C/D/E retest |
| F.2 Action-Goal wird abgelehnt | joint_names falsch oder positions außerhalb URDF-Limits | IK-Output prüfen; sollte in ±1.57/±1.57/±1.50 sein |
| F.3 gait_node startet nicht | Phase-6-Übergabe-Defaults stimmen für HW nicht | siehe PHASE.md Phase-6-Übergabe (body_height=-0.047 für HW); gait params überprüfen |
| F.3 leg_6 schwingt nicht | gait_node sendet evtl. an falschen Controller-Namen | `ros2 topic echo /leg_6_controller/joint_trajectory` prüfen |
| ANY_SERVO_OVERCURRENT für Pin 0–14 | false-positive aus Firmware ohne Servo am Pin | aus Stolperfallen-Liste tolerieren, leg_6 selbst sauber? |
| WATCHDOG_TRIPPED während gait | gait_node update_rate zu langsam | controller_manager + gait_node Rate prüfen |
| Strom-Peak > 6 A | mehrere Servos gleichzeitig im Stall | PSU AUS, gait params reduzieren |

---

## Done-Kriterium Stage F (User-Smoke-Anteil)

**F-Phase-1 User bestätigt:**
- [ ] F-T3 F.1 Lineal-Check: alle 3 Längen ±5 mm OK
- [ ] F-T4 F.2 Plugin-Bringup mit allen 3 Servos + Hand-Mitigation
- [ ] F-T5 F.2 IK-Probe-Test: 3 cm Fuß-Hub, keine Stalls, CSV aufgezeichnet
- [ ] F-Phase-1-Shutdown sauber

**→ User-Commit F-Phase-1**

**F-Phase-2 User bestätigt:**
- [ ] Bench-Setup wieder + Stock-Halterungs-Check
- [ ] F-T4b Re-Bringup ok
- [ ] F-T6 gait_node + cmd_vel: Tripod-Pattern an leg_6 sichtbar, kein OVERCURRENT auf Pin 15/16/17
- [ ] F-T7 Shutdown sauber
- [ ] F-T8 Strom-CSV-Auswertung übernommen (CSVs in `~/hexapod_ws/data/phase_10/`)

**→ User-Commit F-Phase-2**

Claude bestätigt (jeweils nach User-Smoke pro Halb-Stage):
- [ ] colcon build grün
- [ ] colcon test grün (208/0/20 + 18/0/0)
- [ ] Self-Review in `phase_10_progress.md`
- [ ] Phase-12-Pipeline-Erkenntnisse + Stage-G-Vorbereitungs-Tabelle
