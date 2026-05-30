# Phase 13 Stage 0 — Hardware Init-Pose + Relay-Sequencing (Brainstorm)

> **Status:** ✅ SUPERSEDED 2026-05-30 — formalisiert in
> [`phase_13_stage_0_plan.md`](phase_13_stage_0_plan.md). Diese Datei bleibt
> als Brainstorm-Historie. **Entscheidung Weg A** (35°-Offset lebt nur in
> der Kalibrierung, rad=0 bleibt horizontal) — die in §6/§7 angedeutete
> "rad=0 = 35° hoch / URDF-femur-origin rotieren"-Variante (Weg B) wurde
> **verworfen** (siehe Plan §4). Mech-Umbau-Logik §6/§12 gilt weiter,
> Re-Cal aber im Weg-A-Sinn (pulse_zero = horizontal neu kalibrieren).
>
> **Brainstorming-Datei, nicht final. 2026-05-28.**
>
> **Vorgaenger:** [`phase_13_desktop_stage_a_initial_pose_plan.md`](phase_13_desktop_stage_a_initial_pose_plan.md)
> ist gescheitert weil das Plugin's "suspended-Preset"-Konzept nicht
> umsetzbar ist (siehe §2). Stage A wird durch Stage 0 ersetzt /
> obsoleted.
>
> **Naming-Konvention:** Stage **0** statt Buchstabe, weil das die
> Hardware-Phase **vor** allen Plugin-Stages (A, B, C, …) ist. Andere
> Stages behalten ihre Buchstaben (A=Initial-Pose-Preset war geplant,
> wird obsolet; B=LUT; C=PS4-Mapping; D/E=Live-Tests).

---

## 1. Zweck

Der Hexapod soll beim Plugin-Start in eine sinnvolle, mechanisch
sichere Init-Pose fahren — **Beine zeigen 35° nach oben** — damit
sowohl am Bench (aufgehängt) als auch auf dem Boden (liegender Hexapod)
ein sauberes Aufstehen zur Stand-Pose moeglich ist.

## 2. Wurzel-Problem (warum Stage A nicht funktioniert)

Im Phase 13 Stage A war geplant: Plugin sendet beim `on_activate` ein
"suspended"-Preset (Femurs auf +1.45 rad = vertikal hängend), Servo2040
führt das aus → Beine hängen passiv beim Start.

**Beobachtung (2026-05-28):** das funktioniert nicht.

Tests bestätigt:
- Pimoroni-`ServoCluster::pulse()` lässt den allerersten Pulse pro Pin
  nach `init()` zur Servo-MID (~1500 µs) gehen. Subsequent pulse-Calls
  funktionieren.
- Frame-Reordering im Plugin (SET_TARGETS vor ENABLE_SERVO) → kein Fix.
- Double-Pulse-Workaround (zweimal `pulse(target, true)` mit 20 ms
  dazwischen) → kein Fix.
- Warmup-Workaround (pulse + disable + pause + pulse) → kein Fix.
- **Relay-Sequenz** (PWMs setzen, dann Strom-Rail aufschalten via Relay)
  → kein Fix. Servos fahren beim Power-On trotzdem zur Servo-Mitte.

**Schlussfolgerung:** Das MID-on-Power-On-Verhalten ist **Servo-eigen**
(Hobby-Servo-Hardware-Charakteristik), nicht Pimoroni-Library. Es kann
weder durch Software-Sequencing noch Power-Sequencing umgangen werden.

Konsequenz: wir können nicht beim Init steuern WO der Servo physisch
landet. Wir können nur die **Mechanik so anpassen** dass die unvermeidbare
Mitte-Position unsere gewünschte Init-Pose ist.

## 3. Lösungs-Konzept

Drei Bausteine:

1. **Mechanische Verschiebung** des Femur-Segments: das Segment wird
   abmontiert und um 35° versetzt wieder am Servo befestigt. Servo bei
   Mitte (PWM=1500) → Femur zeigt 35° nach oben (statt horizontal).
   Coxa und Tibia bleiben unverändert (Mitte = sinnvolle Position).

2. **Relay** (GP26 / A0-Header-Pin auf Servo2040, normally-open,
   high-trigger). Default LOW = Relay aus = Servos depowered. Plugin
   kann via neuem Protocol-Frame `RELAY_CONTROL` GPIO 26 HIGH setzen
   → Servos kriegen Strom.

3. **Plugin-Init-Sequenz** mit gestaffelter ENABLE-Reihenfolge nach
   Joint-Typ (Femurs → Coxas → Tibias), um Strom-Spitze beim Relay-On
   zu reduzieren und visuelle Klarheit beim Init zu haben.

## 4. Init-Sequenz (Plugin `on_activate`)

| # | Schritt | Erwartetes Verhalten |
|---|---|---|
| 1 | Plugin Boot, Relay GPIO 26 default LOW | Servos depowered |
| 2 | RESET-Frame an Servo2040 | FW-State zurueckgesetzt |
| 3 | SET_TARGETS für alle 18 Pins = pulse_zero | target_pulse_us[i] gesetzt; Servos noch depowered |
| 4 | ENABLE_SERVO für die 6 Femur-Pins (1, 4, 7, 10, 13, 16) mit 50 ms Stagger | servo_enabled[i]=true; PWM-Output am Pin aktiv aber Servos haben kein Strom |
| 5 | Neuer Frame `RELAY_CONTROL(on=1)` → Servo2040 setzt GP26 HIGH | Relay schließt → V+ Rail an → Servos kriegen Strom → alle 6 Femurs fahren zur Servo-Mitte = nach Umbau **35° hoch** |
| 6 | ~1 s warten | Femurs in Position |
| 7 | ENABLE_SERVO für die 6 Coxa-Pins (0, 3, 6, 9, 12, 15) mit Stagger | Coxas fahren zur Mitte (radial nach außen) |
| 8 | ~1 s warten | |
| 9 | ENABLE_SERVO für die 6 Tibia-Pins (2, 5, 8, 11, 14, 17) mit Stagger | Tibias fahren zur Mitte (in Verlängerung des Femurs) |
| 10 | ~1 s warten | **→ Init-Pose erreicht: alle 6 Beine 35° hoch + radial außen + gestreckt** |

## 5. Aufstehen-Sequenz (Plugin oder separate Node, NACH Init)

Tripod 3+3:

1. **Tripod A** (Beine 1, 3, 5) fährt smooth (~2-3 s) von Init-Pose zur
   Stand-Pose.
   - Bench: Beine schwenken nach unten in die Stand-Pose-Position.
   - Boden: Foots drücken gegen Boden → Body wird hochgehoben (3 Stütz-
     Punkte tragen den Body).
2. **Tripod B** (Beine 2, 4, 6) fährt zur Stand-Pose.
   - Body schon hoch → Foots gehen in die Luft + erreichen Stand-Pose-
     Position
3. → Voll-Stand erreicht.

Implementation: vermutlich neuer Engine-State `STAND_UP_TRIPOD_A` und
`STAND_UP_TRIPOD_B` in `gait_engine.py`, getriggert wenn Init-Pose
abgeschlossen.

## 6. Mechanik: Vorgehen Femur-Umbau

**Cal-Sparen-Trick (User-Workflow, präzisiert 2026-05-28):**

Die Idee ist NICHT manuell um 35° zu messen, sondern den **Servo selbst
die 35°-Position anfahren zu lassen** und das Segment dann in der
**ursprünglichen Mitte-Stellung** wieder festzuschrauben. So ist die
Verschiebung mech-exakt ohne manuelle Winkelmessung.

Schritt-für-Schritt:

1. Plugin in speziellen Cal-Mode bringen — kommandiere alle Femur-Joints
   auf **rad=-0.611 (=-35°)** bzw. **+0.611 (+35°)** je nach Bein-Seite
   (Direction-Map). Damit fährt der Servo physisch die 35°-Hoch-Position
   an, das Femur-Segment zeigt 35° nach oben.
2. **Pro Bein:** User schraubt das Femur-Segment am Servo-Horn ab. Das
   Servo-Horn bleibt am Servo (Servo-Achse-Winkel unverändert).
3. User montiert das Femur-Segment **in der ursprünglichen
   horizontalen Mitte-Position** wieder am Servo-Horn fest (= dort wo es
   vorher bei Servo-Mitte war).
4. Nach Festschrauben aller 6 Femurs: Plugin kommandiert rad=0
   (= Servo-Mitte). Servo dreht zurück um 35° in die Original-Mitte-
   Position. Aber das Femur-Segment hat jetzt einen 35°-Offset relativ
   zur Servo-Achse → das Segment zeigt jetzt **35° nach oben** statt
   horizontal.
5. **Effekt:** die Cal-pulse_zero (1460 für LEG 1 etc.) wird semantisch
   neu definiert: war "Femur horizontal", ist jetzt "Femur 35° hoch".
   Plus: Servo-Hardware-Mitte (PWM=1500) zeigt auch ungefähr "35° hoch"
   (kleine Differenz pulse_zero ↔ 1500 = ~3°, vernachlässigbar).
6. **Direction-Map bleibt unverändert** — Servo wird nicht gedreht.
7. Links/Rechts-Spiegelung: Vorzeichen von ±35° hängt vom Direction-Bit
   des Femur-Pins ab (zu prüfen pro Bein beim Umbau).

## 7. URDF & Cal — was muss angepasst werden

**URDF (`hexapod_description/urdf/leg.xacro`):**
- `femur_joint`-Origin braucht jetzt eine Y-Rotation um +35° (oder -35°
  je nach Bein-Seite/Direction). Optionen:
  - (a) `<origin>` des `femur_joint` rotieren — saubere Lösung im IK-Sinn
  - (b) `<visual>` und `<collision>` des `femur_link` rotieren — weniger
    invasiv aber unsauber

  → wir nehmen die saubere Lösung (a).
- `joint_limits` für Femur: nach Umbau verschiebt sich die mech-Range
  asymmetrisch.

**Cal (`hexapod_hardware/config/servo_mapping.yaml`):**
- `pulse_zero` bleibt unverändert (User schraubt bei rad=0 um — die
  pulse_zero entspricht weiterhin "Servo bei Mitte = Default-Init-Pose").
- `pulse_max` (= "Femur Richtung boden", war joint_upper=+1.493): nach
  Umbau ist das eine andere physische Position. **MUSS neu kalibriert
  werden** — User fährt mit rqt_reconfigure den Servo bis zum neuen
  mech-Anschlag und notiert die PWM.
- `pulse_min` (= "Femur Richtung körper, oben"): MUSS neu kalibriert
  werden, ähnlich. Vermutlich verkürzt sich die Bewegung nach oben weil
  mech-Kollision mit Body / Coxa eintritt.

**Symmetrie-Überlegung (User-Hinweis):**
- Stage F hatte symmetrische URDF-Limits eingestellt (alle 6 Beine
  identisch: coxa ±0.415 / femur ±1.493 / tibia ±1.161).
- Nach Umbau wird die mech-Range asymmetrisch. Wenn z.B. der obere
  mech-Anschlag in Phase-13-Stage-0-Setup bei +0.882 rad ist (= alter
  +1.493 - 0.611 wegen 35° Shift), wäre eine **symmetrische Beschränkung**
  auf ±0.882 nötig (alles >0.882 würde im "unten"-Bereich bleiben).
- **Frage:** wollen wir symmetrische rad-Limits (User-Stil aus Stage F),
  oder asymmetrische Limits die die echte Mech-Range nutzen?

## 8. Hardware-Items

- **Relay:** vorhanden, normally-open, high-trigger, angeschlossen an
  GP26 (= A0 header). Quelle: [`pimoroni_servo_fix/src/test_relay_power_sequence.cpp`](../../pimoroni_servo_fix/src/test_relay_power_sequence.cpp).
- **PSU:** Bench-Netzgerät 7.4 V (2S LiPo Ziel-Spannung), Strom genug
  für alle 18 Servos.

## 9. Tests-Plan

| # | Test | Wer | Wann |
|---|---|---|---|
| T1 | Mech-Umbau pro Bein durchführen | User (manuell) | nach Plan-Freigabe |
| T2 | Cal neu für Femurs (pulse_min + pulse_max) | User (rqt_reconfigure + servo_mapping.yaml-Edit) | nach Umbau |
| T3 | URDF anpassen (leg.xacro femur_joint origin + neue rad-Limits) | Claude | nach Cal |
| T4 | FW erweitern um RELAY_CONTROL-Frame + Plugin-Service `/hexapod_relay_set` | Claude | parallel zu T2/T3 |
| T5 | Init-Sequenz im Plugin's on_activate implementieren (Femur→Relay→Coxa→Tibia) | Claude | nach T4 |
| T6 | gait_engine.py: STAND_UP_TRIPOD_A/B States für Aufstehen | Claude | nach T5 |
| T7 | rqt + Gazebo Sim: Init + Aufstehen visualisieren | User | nach T6 |
| T8 | Hardware + RViz live: Init + Aufstehen testen, aufgebockt | User+Claude | nach T7 |
| T9 | Bodenkontakt-Test: Hexapod liegt, Aufstehen via Tripod | User+Claude | nach T8 grün |

## 10. Offene Fragen / Bedenken (User + Claude)

1. **Symmetrische vs asymmetrische rad-Limits nach Umbau** (User-Frage,
   siehe §7): nach Cal entscheiden.
   - **User 2026-05-28:** klar, das muss geprüft werden nach dem
     Re-Cal. Entscheidung wird datengetrieben sein (was die Mech
     tatsächlich zulässt).

2. **Direction-Map nach Umbau**: User sagt bleibt gleich (Servo wird
   nicht gedreht, nur Segment). Aber pro Bein-Seite Vorzeichen ±35°
   bei §6 Schritt 1 prüfen.
   - **User 2026-05-28:** bestätigt — bei Umbau pro Bein direkt prüfen
     ob die Direction noch zu "+35° = nach oben" passt.

3. ~~**Brown-out beim Relay-On**~~ — **User 2026-05-28:** PSU schafft
   das, kein Issue. Punkt gestrichen.

4. **Aufstehen vom Boden vs Bench** — funktioniert dieselbe Tripod-3+3-
   Sequenz für beide Fälle, oder brauchen wir zwei Varianten?
   - **User 2026-05-28:** wir behandeln beide Fälle mit derselben
     Sequenz. Live-Test wird zeigen ob es klappt.

5. **Gazebo-Sim genau genug**: kann gz_ros2_control die Servo-Drehmoment-
   vs-Body-Gewicht-Dynamik beim Aufstehen abbilden?
   - **User 2026-05-28:** Servo-Drehmoment in Realität reicht (sind
     stark genug). Gazebo-Genauigkeit zusammen mit Claude prüfen wenn
     Sim-Stage erreicht — ausprobieren.

6. ~~**GP26-Pin frei**~~ — **User 2026-05-28:** Pin ist bereits am
   Relay verbunden, funktioniert, Relay schaltet sauber. Punkt
   gestrichen.

7. **Mech-Anschlag-Limit bei Umbau-Pose**: nach Umbau sind die Servos
   bei rad=0 (= 35° nach oben). Mech-Range muss neu kalibriert werden.
   - **User 2026-05-28:** klar — neue pulse_min/pulse_max via
     rqt_reconfigure pro Femur-Pin anfahren und PWM-Werte notieren,
     dann in `servo_mapping.yaml` eintragen. Das ist der schnellste
     Workflow.

## 11. Cross-References

**Plan-Vorgänger (obsolete oder umzubauen):**
- [`phase_13_desktop_stage_a_initial_pose_plan.md`](phase_13_desktop_stage_a_initial_pose_plan.md) — Stage A,
  jetzt obsolete weil Servo-MID-Verhalten Konzept zerstört.
- [`phase_13_servo2040_fix.md`](phase_13_servo2040_fix.md) — FW-Fix-Versuch (Fix 3.1/3.2/3.4 + Double-Pulse + Warmup),
  alle Workarounds haben nicht funktioniert. Daher Hardware-Workaround statt FW-Workaround.

**Phase-13-Kontext:**
- [`phase_13_desktop_pre_bringup_plan.md`](phase_13_desktop_pre_bringup_plan.md) — übergeordneter
  Stage-Plan. Stage-Übersicht §2 muss angepasst werden:
  Stage 0 vor Stage A einfügen, Stage A's Status auf obsolete.
- [`phase_13_full_bringup.md`](phase_13_full_bringup.md) — Pi-Phase, später.

**Hardware-Code:**
- Relay-Test: [`pimoroni_servo_fix/src/test_relay_power_sequence.cpp`](../../pimoroni_servo_fix/src/test_relay_power_sequence.cpp)
- FW: [`hexapod_servo_driver/src/main.cpp`](../../hexapod_servo_driver/src/main.cpp) — RELAY_CONTROL Frame hier hinzufügen
- Plugin: [`hexapod_hardware/src/hexapod_system.cpp`](../src/hexapod_hardware/src/hexapod_system.cpp) — on_activate Sequenz umbauen, /hexapod_relay_set Service

**URDF:**
- [`hexapod_description/urdf/leg.xacro`](../src/hexapod_description/urdf/leg.xacro) — femur_joint origin

**Cal:**
- [`hexapod_hardware/config/servo_mapping.yaml`](../src/hexapod_hardware/config/servo_mapping.yaml) — pulse_min/max neu nach Umbau

**Servo-Cal-Stage-F:** [`servo_real_cal_stage_f_urdf_symmetrize_plan.md`](servo_real_cal_stage_f_urdf_symmetrize_plan.md) — Symmetrie-Pattern,
falls wir das wiederverwenden wollen.

**Phase-Status:**
- [`PHASE.md`](../PHASE.md) — Phase 13 Desktop ist aktuell; Stage A → obsolete; Stage 0 wird neue erste Stage.
- [`PHASE_NOTES.md`](../PHASE_NOTES.md) — Retro über Stage-A-Fail rein.

## 12. Zusatzinfos die nicht vergessen werden duerfen

- **GP26 / A0-Header** ist der Relay-Pin.
- **Relay-Logik:** GP26 LOW = Relay aus, GP26 HIGH = Relay ein.
- **Test-Code** mit RELAY-Pattern ist schon vorhanden:
  `pimoroni_servo_fix/src/test_relay_power_sequence.cpp` — kann als
  Vorlage für FW-Code dienen.
- **Pimoroni-Library liegt lokal:** `/home/enjoykin/pimoroni-pico/`
  (nur lesen, nicht ändern für unsere FW).
- **Pico SDK:** `/home/enjoykin/pico-sdk/` (env `PICO_SDK_PATH`).
- **Picotool-Pfad:** `/home/enjoykin/picotool/build/picotool`
  (sudo wegen fehlender udev-rules; oder
  `python3 tools/flash_and_verify.py` aus hexapod_servo_driver-Repo).
- **Build-Workflow FW:** `cd hexapod_servo_driver/build && cmake .. && make -j$(nproc) && sudo picotool load Hexapod_servo_driver.uf2`.
- **Mech-Umbau-Sequenz (User):**
  1. Plugin kommandiert alle Femurs auf rad=0 (= aktuell horizontal).
  2. User schraubt Femur-Segment ab, dreht 35° nach oben, montiert fest.
  3. Resultat: bei rad=0 (Servo-Mitte) zeigt Femur jetzt 35° hoch.
- **Diagnose-Scripts (Servo2040-Side, ohne Plugin):**
  - `hexapod_servo_driver/tools/diagnose_phase13_fix.py`
  - `hexapod_servo_driver/tools/diagnose_phase13_visual.py`
  - `hexapod_servo_driver/tools/diagnose_single_pin_pwm.py`
  - `hexapod_servo_driver/tools/diagnose_single_leg.py`
  Können wiederverwendet werden für Stage-0-Verifikation.

---

**Brainstorm-Status:** offen für Diskussion, NICHT final. Nach
Phase-13-Stage-0-Plan-Freigabe wird daraus die formale Plan-Doku
(`phase_13_stage_0_plan.md`).
