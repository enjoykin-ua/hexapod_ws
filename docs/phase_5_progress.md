# Phase 5 — Fortschritt

Beim Neustart: diese Datei lesen, dann mit dem ersten offenen Schritt weitermachen.
Stufenplan A–G abgeleitet aus den 7 Roadmap-Schritten in `docs/phase_5_kinematics_gait.md`.

> **Konvention:** Pro erledigtem Bullet sofort `[ ]`→`[x]` setzen, nicht batchen
> (Memory-Eintrag `feedback_phase_progress_tracking.md`). Pro Stufe gilt:
> erst Konzept-Diskussion → User-OK → Implementierung → Verifikation.

> **Aus Phase 4 mitgenommen** (siehe `phase_4_progress.md` Phasenabschluss):
> - **KDL-Warning** `base_link has inertia, but KDL does not support root link
>   with inertia` (RSP, seit Phase 2). Funktional unkritisch; Drift = 0 mm/0°
>   in Phase-4-Stufe-F bestätigt. Reminder-Memory:
>   `project_phase5_kdl_warning_fix.md`. **Nur fixen, falls die Warning beim
>   IK/Gait-Debugging tatsächlich stört** (Logs spammt oder Fehler verbirgt).
>   Sonst auf Phase 6/7 schieben.
> - **Stand-Pose-IK-Smoke** als ersten Plausibilitätscheck der IK:
>   Wunsch-Foot-Pose (mit `body_height ≈ -0.055 m`) muss per IK ≈ `[0, -0.5, 1.0]`
>   pro Bein liefern. Zweistufig verifiziert: pure-python in Stufe B,
>   Live-Sim-Drift in Stufe C.

---

## Stufenübersicht

| Stufe | Inhalt | Roadmap | Liefert |
|---|---|---|---|
| A | Paket-Skelett `hexapod_kinematics` (config.py, Module-Stubs, leerer pytest grün) | (Vorbereitung) | DK1 vorbereitet |
| B | IK + FK + Pure-Python-Tests | Schritt 1 | DK1 ✅ |
| C | Paket-Skelett `hexapod_gait` + `stand_node` (One-Shot Neutral-IK) | Schritt 2 | DK2 vorbereitet, IK-Smoke live |
| D | Foot-Bodenkontakt-Sensoren (toggle-bar) als Live-Diagnose-Werkzeug | Schritt 2.5 (neu) | 6 Foot-Contact-Topics, ein/abschaltbar |
| E | Single-Leg-Schwung in der Luft (validiert IK→Trajectory-Pipeline) | Schritt 3 | Gait-Engine-Skelett |
| F | Statisches Tripod-Pattern in der Luft (alternierende Beine, kein Vortrieb) | Schritt 4 | DK5 vorbereitet |
| G | Vollständiger Tripod-Gait geradeaus per `/cmd_vel` | Schritt 5 | DK2, DK3, DK4, DK5 ✅ |
| H | Phasenabschluss + optional Schritt 6 (`angular.z`) / 7 (`linear.y`) | Schritt 6/7 | Phase 5 🟢 |

---

## Stufe A — Paket-Skelett `hexapod_kinematics`

**Ziel:** Pure-Python-Paket neben den ROS-Paketen — Mathematik-Library, die
in Stufe B die IK/FK trägt. **Wichtigste Architektur-Entscheidung:** kein
`import rclpy` in diesem Paket, damit es mit reinem `pytest` ohne ROS-Stack
testbar bleibt.

**Was wir machen:** `ament_python`-Paket erzeugen, Modul-Stubs (`leg_ik.py`,
`geometry.py`, `config.py`) anlegen, Bein-Geometrie-Konstanten als
dataclass nach `config.py` ziehen (Längen `L_coxa/L_femur/L_tibia`,
Mountpunkte pro Bein, Joint-Limits). Single Source of Truth: die Werte
müssen aus `hexapod_physical_properties.xacro` / `00_conventions.md` §11
übernommen werden, nicht erfunden.

**Konzept-Diskussionspunkte (vor Implementation):**
- **Build-Type:** `ament_python` (Setuptools) vs. `ament_cmake` mit Python-Hooks?
- **Geometrie-Quelle:** Werte aus xacro abschreiben oder runtime aus
  `robot_description` parsen?
- **dataclass-Layout:** ein `LegConfig` pro Bein oder ein `HexapodConfig`
  mit globalen Konstanten? Mirror-Symmetrie links/rechts wie kodiert?

### Design-Entscheidungen Stufe A

> **Format:** Pro Entscheidung: alle ernsthaft erwogenen Optionen mit
> Tradeoffs, plus die gewählte Variante. Sodass bei späterem Re-Design
> die ursprüngliche Diskussion abrufbar ist (Memory-Eintrag
> `feedback_decision_alternatives_log.md`).

#### 1. Build-Type

**Optionen:**
- **A) `ament_python`** (Setuptools-basiert). Pro: ROS2-Standard für
  Pure-Python-Pakete, `pytest` läuft via `colcon test` out-of-the-box,
  saubere `entry_points`-Mechanik (relevant für `hexapod_gait` in
  Stufe C, hier irrelevant). Contra: keine.
- **B) `ament_cmake` mit Python-Hooks.** Pro: würde späteren C++-Anteil
  (z. B. performance-kritische IK-Variante) erlauben. Contra: zusätzliche
  CMake-Komplexität ohne Nutzen, keine C++-Variante geplant.

**Gewählt: A** — IK macht 6 × 50 Hz = 300 Aufrufe/s, numpy bewältigt
das mit Reserve auch auf dem Pi 4. CLAUDE.md §2 sagt: C++ kommt in
Phase 7 nur in `hexapod_hardware`, nicht in `hexapod_kinematics`.

#### 2. Geometrie-Quelle (Längen, Mountpunkte, Limits)

**Optionen:**
- **A) Werte aus xacro abschreiben + Cross-Check-Test.** `config.py` hat
  Konstanten, ein `pytest` parst die xacro und vergleicht. Pro: Library
  bleibt Pure-Python ohne ROS-/URDF-Parser-Dependency, Test fängt
  Drift ab. Contra: zwei Stellen müssen bei Änderungen gepflegt werden
  (durch den Test aber unkritisch).
- **B) Runtime aus `robot_description` parsen** (z. B. via `urdf_parser_py`).
  `config.py` enthält keine Zahlen, sondern `HexapodConfig.from_urdf(...)`.
  Pro: single source of truth zur Laufzeit. Contra: Pure-Python-Test
  braucht ein vorab-generiertes URDF-Fixture, das bei jeder xacro-
  Änderung neu generiert werden muss; `urdf_parser_py`-Dependency
  bricht die ROS-Stack-Unabhängigkeit der Library.

**Gewählt: A** — Bein-Geometrie aus dem CAD ist fix und ändert sich
nicht mehr (User-Aussage 2026-05-08). Damit ist der "two places"-Nachteil
in der Praxis irrelevant; die Pure-Python-Reinheit der Library wiegt
schwerer.

**Falls später Re-Design nötig** (z. B. weil CAD-Tuning doch wieder
ansteht): zu B umschwenken, indem `config.py` einen `from_urdf`-Loader
bekommt und `HEXAPOD` zur Laufzeit aus `xacro` (oder gecachtem URDF)
befüllt wird. Cross-Check-Test bleibt dann als Konsistenz-Test der
hartkodierten Defaults.

#### 3. dataclass-Layout

**Optionen:**
- **A) `LegConfig` pro Bein, `HexapodConfig` als Container** mit
  `legs: list[LegConfig]`. IK-Signatur: `leg_ik(x, y, z, leg_cfg: LegConfig)`.
  Pro: Test-Configs trivial konstruierbar (Custom-Bein mit `L_*=1.0`),
  asymmetrie-tolerant (vorderes Beinpaar mit anderer Geometrie wäre
  trivial). Contra: ~6× Konstruktor-Boilerplate.
- **B) Globale Konstanten + Mountpunkt-Tabelle** (`L_COXA = 0.0436`,
  `LEG_MOUNTS: dict[str, dict]`). IK-Signatur: `leg_ik(x, y, z, leg_id: str)`.
  Pro: kompakt. Contra: setzt voraus, dass alle Beine identisch sind
  und bleiben; Test-Code muss `LEG_MOUNTS` global mocken statt eigene
  Test-Config zu konstruieren.
- **C) Ein einziges `HexapodConfig` mit Listen pro Eigenschaft**
  (`mounts: list`, `lengths: tuple`). Verworfen: erschwert sowohl
  Pro-Bein-Variation als auch Test-Config-Konstruktion.

**Gewählt: A** — Test-Komfort wiegt schwerer als die ~30 Zeilen
Boilerplate. Auch wenn die 6 Beine **mechanisch identisch** sind und
das `is_left`-Flag nicht in der IK-Math gebraucht wird (alle Beine
nutzen dasselbe `<xacro:macro name="leg">`, Spiegelung steckt nur in
`mount_yaw`), bleibt LegConfig die saubere Modellierung.

`is_left`-Flag bewusst weggelassen (YAGNI): mechanische Symmetrie
macht es überflüssig. Falls später benötigt, lässt es sich aus
`mount_xyz.y > 0` ableiten.

**Falls später Re-Design nötig** (z. B. weil die Library sehr ROS-näher
genutzt werden soll): zu B umschwenken, indem `LegConfig` durch globale
Konstanten ersetzt und `leg_ik` auf `leg_id`-Lookup umgestellt wird.
Bei dann sehr engem Coupling wäre das ein vertretbarer Refactor.

---

- [x] Build-Type entschieden (`ament_python`), Geometrie-Quelle (abschreiben + Cross-Check-Test), dataclass-Layout (`LegConfig` pro Bein + `HexapodConfig`-Container) abgestimmt
- [x] `ros2 pkg create --build-type ament_python --license Apache-2.0 ... hexapod_kinematics` in `src/`
- [x] Modul-Stubs angelegt: `leg_ik.py` + `geometry.py` (jeweils Docstring mit erwarteter API als Stufe-B-Vormerker), `config.py` (volle Implementation), `__init__.py` (Re-Export `HEXAPOD`, `HexapodConfig`, `LegConfig`)
- [x] `setup.py` / `package.xml` Description gesetzt (Pure-Python IK/FK Library, Phase-5-Kontext); Test-Deps unverändert (`python3-pytest` aus auto-gen genügt — `numpy` deferiert auf Stufe B, wo IK-Math sie braucht)
- [x] `config.py` mit Geometrie-Konstanten (`L_coxa=0.0436`, `L_femur=0.07994`, `L_tibia=0.1787`, `foot_radius=0.008`, alle Joint-Limits, alle 6 Mountpunkte mit `mount_yaw`) als `HexapodConfig` mit 6× `LegConfig` (frozen dataclasses)
- [x] `test/test_config.py`: 7 Cross-Check-Tests gegen `hexapod_physical_properties.xacro` (regex-parsing der `<xacro:property>`-Werte, dann Längen + Limits + Mountpunkt-Formeln verifiziert) — Workspace-Pfad via `Path(__file__).resolve().parents[3]`
- [x] `colcon build --packages-select hexapod_kinematics` grün (1.13 s)
- [x] `colcon test --packages-select hexapod_kinematics` grün: **9 passed, 1 skipped** (copyright skipped wie immer; 7× Cross-Check + flake8 + pep257)

### Umsetzungsnotizen Stufe A

**Geometrie-Quelle gemäß Stufe-A-Design-Entscheidung 2:** `config.py`
spiegelt die `<xacro:property>`-Werte aus
[hexapod_physical_properties.xacro](../src/hexapod_description/urdf/hexapod_physical_properties.xacro)
(Längen, Limits) und die Mountpunkt-Formeln aus
[hexapod.urdf.xacro](../src/hexapod_description/urdf/hexapod.urdf.xacro)
(`±body_length/2`, `±body_width/2`, `±body_width_middle/2`,
`mount_yaw ∈ {±π/4, ±π/2, ±3π/4}`). Cross-Check-Test parst die
properties-Datei per Regex und re-evaluiert die Mountpunkt-Formeln —
Drift in beiden Dateien wird abgefangen.

**`is_left`-Flag bewusst weggelassen (YAGNI):** Mechanik aller 6 Beine
ist identisch (selbes `<xacro:macro name="leg">`), Spiegelung steckt
ausschließlich in `mount_yaw`. Test
`test_all_legs_mechanically_identical` macht das explizit. IK-Math
in Stufe B wird für alle 6 Beine identisch sein — kein Vorzeichen-Flip
nötig.

**Pure-Python-Test-Reinheit:** Kein `import rclpy`, kein
`urdf_parser_py`. Test reicht via Path-Resolution in das
Sibling-Package — funktioniert weil `colcon test` aus dem Source-Tree
läuft. Falls jemand die Tests aus einem temp-dir ausführt, fällt
`pytest.fail()` mit klarer Diagnose.

**Style-Konventionen für ament_python entdeckt:**
- `flake8-quotes` (Q000): Single Quotes für Strings, Triple-Double-Quotes
  nur für Docstrings.
- `flake8-import-order` (I100/I201): Strikt PEP-8-Gruppen (stdlib →
  third-party → local) mit Leerzeilen zwischen Gruppen, intra-Gruppe
  alphabetisch nach Modul-Name. **`hexapod_kinematics` wird vom Plugin
  als Third-Party erkannt** (nicht Application — kein
  `application-import-names` config), also gehört es in dieselbe Gruppe
  wie `pytest` (alphabetisch davor: h < p).
- `pep257` (D213): Mehrzeilige Docstrings — Summary erst auf Zeile 2
  (Leerzeile nach den öffnenden `"""`).

Diese Konventionen gelten für alle künftigen Python-Pakete in der
Phase (Stufen B-G), insbesondere `hexapod_gait`. Der erste Build kostete
zwei flake8/pep257-Iterationen, weil ich PEP-8-default-Quoting/Spacing
gewohnt war — Memory-Hinweis dazu nicht nötig, der Style ist im Code
jetzt fixiert und in Stufe B-H einfach übernehmbar.

**Was Stufe A explizit NICHT macht:**
- Keine IK-Math in `leg_ik.py` (Stufe B)
- Keine FK-Math in `leg_ik.py` (Stufe B)
- Keine Frame-Helper in `geometry.py` (Stufe B)
- Kein `numpy`-Import (Stufe B)
- Keine ROS-Knoten (Stufe C aufwärts)
- Kein Smoke-Test gegen `[0, -0.5, 1.0]` (Stufe B als pure-python-Test, Stufe C live)

---

## Stufe B — IK + FK + Pure-Python-Tests

**Ziel:** Geschlossene-Form-IK pro Bein, dazu FK als Inversen-Tester. **Done-
Kriterium 1 Phase 5 erfüllt.**

**Was wir machen:** `leg_ik(x, y, z, leg_cfg) → (θ_coxa, θ_femur, θ_tibia)`
nach dem Schema im `phase_5_kinematics_gait.md`. `leg_fk` als Verifikation.
`IKError` bei out-of-reach (Cosinus-Argument außerhalb `[-1, 1]`). Vorzeichen-
und Knie-Konvention (Knie oben/unten, links/rechts-Spiegelung) pro Bein
durchverifiziert. `numpy` für Trigonometrie.

**Konzept-Diskussionspunkte:**
- **Knie-Konvention:** "Knie oben" ⇒ `θ_femur = α + β`. Hexapod-Standard.
  Verifizieren am eigenen Modell.
- **Bein-Frame-Definition:** Origin = `coxa_joint`-Position, `+X` zeigt
  von base_link weg (radial nach außen), `+Z` nach oben — passt das zur
  Bein-Mountpunkt-Rotation aus xacro?
- **Spiegelung links/rechts:** Linke Beine (1, 2, 3) vs. rechte (4, 5, 6) —
  müssen Vorzeichen invertiert werden, oder bleibt das bei der `mount_yaw`-
  Rotation und das Bein-Frame-Math ist links=rechts identisch?
- **Geometrische Smoke-Tests:** welche fünf Punkte testen den Solver am
  saubersten ab? (Neutral, max-Reach, min-Reach, lateral, vertikal.)
- **Phase-4-Übergabe-Smoke:** Inverser Wert `[0, -0.5, 1.0]` muss aus
  Foot-Position bei `body_height ≈ -0.055 m` herauskommen — das ist der
  härteste Vorzeichen-Test.

**Konzept-Doku:** `docs/phase_5_ik_explained.md` (geschlossene Form,
Knie-Konvention, Bein-Frame, FK-Verifikation).

- [ ] Konzept besprochen (Knie-Konvention, Frame-Konvention, Spiegelung)
- [ ] `leg_ik` implementiert nach Roadmap-Schema (atan2/Cosinussatz)
- [ ] `leg_fk` implementiert (3D-Vorwärtskinematik)
- [ ] `IKError`-Exception bei out-of-reach
- [ ] `test_ik_neutral_pose`: FK(IK(p)) ≈ p für mehrere Punkte (atol=1e-6)
- [ ] `test_ik_out_of_reach`: `IKError` wird geworfen
- [ ] `test_ik_phase4_handover_smoke`: IK(neutral-foot bei body_height=-0.055) ≈ `[0, -0.5, 1.0]` pro Bein
- [ ] `test_ik_left_right_symmetry`: spiegelbild-symmetrische Punkte → spiegelbild-symmetrische Winkel
- [ ] `colcon test --packages-select hexapod_kinematics` grün, alle Tests grün
- [ ] `phase_5_ik_explained.md` geschrieben

---

## Stufe C — Paket-Skelett `hexapod_gait` + `stand_node`

**Ziel:** Erste Begegnung der IK mit dem ROS-Stack. Knoten ruft Neutral-IK,
publisht **einmal** je eine `JointTrajectory` an alle 6 `leg_*_controller`,
Roboter steht in Wunsch-Pose. Phase-4-Übergabe-Live-Smoke: Drift bleibt ≈ 0.

**Was wir machen:** `hexapod_gait` als `ament_python`-Paket anlegen,
`stand_node.py` schreiben. Knoten lädt Geometrie aus `hexapod_kinematics`,
berechnet Foot-Targets in Neutral-Pose (z. B. `body_height = -0.055`,
`x_foot = leg_x_neutral`), ruft IK pro Bein, publisht 6× `JointTrajectory`
mit `time_from_start = 4 s` (analog Phase-4-Stufe-F sanfter Anfahrt).

**Konzept-Diskussionspunkte:**
- **Neutral-Pose-Definition:** wo soll der Fuß im Bein-Frame stehen? `(r_neutral, 0, body_height)`
  mit `r_neutral = L_coxa + L_femur*cos(α_n)` ... — am sinnvollsten so, dass IK
  exakt `[0, -0.5, 1.0]` zurückgibt (validiert Stufe-B-Smoke live).
- **Topic-Format:** `JointTrajectory` per Publisher (Phase-4-Pattern)
  oder `FollowJointTrajectory`-Action? Phase 4 nutzte CLI-Pub, also
  Pattern bleiben.
- **Launch-Integration:** `stand_node` als optionaler Node in
  `sim.launch.py`, oder eigenes Launch `stand.launch.py`?
- **One-Shot vs. Periodic:** Knoten exit nach Pub oder bleibt am Leben?
  (Empfehlung: bleibt mit `keep_alive` und republisht nicht — Trajectory
  hält Endpunkt, JTC blockiert weitere Goals nicht.)

**Test-Doku** (interaktive Stufe): `docs/phase_5_stage_C_test_commands.md`.

- [ ] Konzept besprochen (Neutral-Pose, Topic-Pattern, Launch-Integration)
- [ ] `hexapod_gait` Paket-Skelett (`ament_python`, deps: rclpy, hexapod_kinematics, trajectory_msgs)
- [ ] `stand_node.py` implementiert (IK→6× JointTrajectory, One-Shot)
- [ ] Optional: Launch-File / Launch-Argument-Erweiterung
- [ ] `colcon build --packages-select hexapod_gait` grün
- [ ] `phase_5_stage_C_test_commands.md` geschrieben
- [ ] **Live-Verifikation:** Sim startet, `stand_node` fährt Pose, Roboter steht auf 6 Foot-Kugeln
- [ ] **Live-Smoke:** Joint-Werte aus `/joint_states` ≈ `[0, -0.5, 1.0]` pro Bein (toleranz ±0.01 rad)
- [ ] **Drift-Check:** `gz model -m hexapod -p` über 5 s konstant (< 1 mm / < 0.5°)

---

## Stufe D — Foot-Bodenkontakt-Sensoren (toggle-bar)

**Ziel:** Pro Foot ein binäres Bodenkontakt-Signal als ROS-Topic
(`/leg_<n>/foot_contact`), ein-/abschaltbar via Launch-Argument
`enable_foot_contact:=true|false`. Diagnose-Werkzeug für die
Live-Stufen E-G (Schwung, Tripod, Gait). **Kein Konsumenten-Knoten in
Phase 5** — nur Publisher + Bridge.

**Was wir machen:**
- Neue xacro-Datei `hexapod.foot_contact.xacro` mit
  `<sensor type="contact">`-Block pro `foot_link` (6×) und Gazebo-Plugin,
  das die Kontakt-Events publisht.
- Top-Level `hexapod.urdf.xacro` per `<xacro:if value="${enable_foot_contact}">`
  conditional including; xacro-Argument `enable_foot_contact` definiert.
- `hexapod_bringup/sim.launch.py`: LaunchArg `enable_foot_contact` gesetzt
  und an xacro-Aufruf durchgereicht; ein zweiter `ros_gz_bridge`-Node
  (Foot-Contact-Mappings) per `IfCondition` conditional gestartet.

**Konzept-Diskussionspunkte (vor Implementation):**
- **Sensor-Granularität:** 6 separate Topics (`/leg_<n>/foot_contact`) als
  `std_msgs/Bool` vs. ein gesammeltes Topic (`/foot_contacts` als
  `std_msgs/UInt8` mit Bit-Maske oder als Custom-Array)? Trade-off
  Lesbarkeit (`echo` pro Bein direkt) vs. Konsumenten-Bequemlichkeit
  (alle 6 in einer Message).
- **Toggle-Architektur:** xacro-Argument-Inclusion (sensor-Block fehlt
  bei OFF — saubere Trennung, sim-restart-pflichtig) vs. always-on-URDF
  + nur Bridge togglen (einfacher, kontinuierlicher Sim-Overhead).
- **Topic-Typ:** `std_msgs/Bool` (binär, simpel) vs.
  `gazebo_msgs/ContactsState` (mit Force-Vektoren — overkill für
  Schalter-Emulation) vs. `geometry_msgs/Wrench`. Empfehlung: `Bool`
  (passt zum HW-Switch-Modell in Phase 7).
- **Hysterese / Filterung:** Direkter Sensor-Output kann bouncen bei
  knappen Kontakten. Sim: vermutlich glatt; HW (Phase 7): Switch-Bouncing
  möglich. Erstmal kein Filter, in Phase 7 ggf. Debounce-Zeit
  (z. B. 20 ms) im HW-Treiber.
- **Topic-Namensschema** als Pattern für Phase 7: `/leg_<n>/foot_contact`
  (per-leg) oder `/foot_contact/leg_<n>`? Empfehlung: ersteres, weil
  konsistent zu `/leg_<n>_controller/...` aus Phase 4.

**Test-Doku** (interaktive Stufe): `docs/phase_5_stage_D_test_commands.md`
mit Schritt-für-Schritt-Befehlen pro Terminal, Toggle-ON- und Toggle-OFF-
Pfad, erwartete Topic-Listen.

- [ ] Konzept besprochen (Granularität, Toggle-Mechanik, Topic-Typ)
- [ ] `hexapod_description/urdf/hexapod.foot_contact.xacro` angelegt (xacro-Macro für Kontakt-Sensor pro `foot_link`)
- [ ] Top-Level-`hexapod.urdf.xacro`: xacro-Argument `enable_foot_contact` mit Default `true`, conditional Include der neuen Datei
- [ ] `hexapod_bringup/sim.launch.py`: LaunchArg `enable_foot_contact` deklariert, an xacro-Command-Aufruf durchgereicht
- [ ] Foot-Contact-Bridge-Mappings (6×) als separater `ros_gz_bridge`-Node mit `IfCondition(LaunchConfiguration('enable_foot_contact'))`
- [ ] `colcon build --packages-select hexapod_description hexapod_bringup` grün
- [ ] `xacro hexapod.urdf.xacro enable_foot_contact:=true` rendert sauber, `... :=false` rendert ohne Sensor-Blöcke
- [ ] `phase_5_stage_D_test_commands.md` geschrieben
- [ ] **Live-Verifikation Toggle ON:** Sim startet mit `enable_foot_contact:=true`, `ros2 topic list` zeigt 6× `/leg_<n>/foot_contact`, in Stand-Pose alle 6 = `True`
- [ ] **Live-Funktional:** Bein 1 manuell anheben (per Trajectory-Goal aus dem Boden) → `/leg_1/foot_contact` wird `False`, andere bleiben `True`
- [ ] **Live-Verifikation Toggle OFF:** Sim startet mit `enable_foot_contact:=false`, **keine** `foot_contact`-Topics in `topic list`, kein Plugin-Lade-Fehler in Logs

---

## Stufe E — Single-Leg-Schwung in der Luft

**Ziel:** Ein Bein fährt periodisch eine Sinus-Bahn in der Luft, andere 5
bleiben in Stand-Pose. Validiert die volle IK→Trajectory-Pipeline unter
50-Hz-Tick-Bedingungen. **Gait-Engine-Skelett entsteht hier.**

**Was wir machen:** `gait_node.py` als rclpy-Knoten mit 50-Hz-Timer,
ruft pro Tick `swing_traj(leg, t)` für ausgewähltes Bein, IK, publisht
`JointTrajectory` mit kurzem `time_from_start` (≈ 0.05 s — der Hack aus
der Roadmap). Andere 5 Beine in Stand-Pose. `swing_traj` als halbsinus-
Bogen (start → top → end, in Bein-Frame x-Richtung).

**Konzept-Diskussionspunkte:**
- **Trajektorien-Form:** Bezier vs. Sinus? Phase-5-Plan nennt beides,
  Sinus reicht (einfacher, weniger Parameter).
- **`time_from_start = 2/Rate = 0.04 s` Hack:** dokumentieren als
  Designwarnung im `gait_explained`-Doc. Refactor-Schuld auf Phase 7.
- **Welches Bein für Single-Leg-Test:** Bein 1 (vorne links) — gut
  sichtbar in der Default-Gazebo-Kamera-Position.
- **Parameter via `declare_parameter`:** `step_height = 0.02`,
  `cycle_time = 1.0`, `which_leg = 1`.

**Konzept-Doku:** `docs/phase_5_gait_explained.md` (State-Machine,
Stütz/Schwung-Trajektorien, Phasen-Sync, 50-Hz-Hack).

- [ ] Konzept besprochen (Sinus-Bahn-Parameter, Tick-Rate, welches Bein)
- [ ] `gait_node.py` Skelett (rclpy, 50-Hz-Timer, Parameter-Declaration)
- [ ] `trajectory_gen.py` mit `swing_traj(t, params)` — Sinus-Halbbogen
- [ ] `gait_engine.py` Skelett (für jetzt: nur Single-Leg-Modus)
- [ ] Launch-Integration oder CLI-Run-Anleitung
- [ ] `phase_5_stage_E_test_commands.md` geschrieben
- [ ] **Live-Verifikation:** Bein 1 schwingt sichtbar in der Luft, andere 5 stehen still
- [ ] **Numerisch:** `/joint_states` zeigt periodische Bewegung nur für `leg_1_*`
- [ ] **Kein Bein knickt ein:** Stützbeine halten Stand-Pose stabil
- [ ] `phase_5_gait_explained.md` (erste Hälfte: State-Machine + Trajektorien)

---

## Stufe F — Statisches Tripod-Pattern in der Luft

**Ziel:** Beide Tripod-Gruppen schwingen abwechselnd, **ohne Vortrieb**.
Roboter aufgebockt oder Stand-only-Modus (Schwung-Hub klein genug, dass
er nicht fällt). Validiert State-Machine + Phasen-Sync.

**Was wir machen:** Erweitert `gait_engine`: Gruppe A {1, 3, 5} und
B {2, 4, 6}, Phasen-Offset 0.5. Stützphase = Stand (kein Vortrieb,
nur Halten). Schwungphase = Sinus-Bogen wie Stufe E, aber alle drei
Beine der schwingenden Gruppe synchron.

**Konzept-Diskussionspunkte:**
- **Stützphase ohne Vortrieb:** Foot bleibt am Neutral-Punkt (kein
  rückwärtiges Schieben). Erst in Stufe G kommt Body-Vortrieb dazu.
- **Aufbock-Modus vs. Stand-on-Ground:** Soll Stufe F den Roboter
  aufgebockt testen (Beine in der Luft, nichts trägt), oder mit kleinem
  `step_height` so dass die Stützgruppe ihn trägt? **Empfehlung:**
  Letzteres, weil Aufbocken in Sim umständlich und weil es G vorbereitet.
- **State-Machine STANDING↔WALKING-Trigger:** zunächst über Parameter
  `enable_walk` boolean — `cmd_vel`-Subscriber kommt erst in Stufe G.

- [ ] Konzept besprochen (Aufbock vs. Stand-on-Ground, State-Machine-Trigger)
- [ ] `gait_engine` erweitert: Tripod-Gruppen + Phasen-Offset
- [ ] STANDING- und WALKING-State implementiert (mit `enable_walk`-Param-Trigger)
- [ ] `phase_5_stage_F_test_commands.md` geschrieben
- [ ] **Live-Verifikation:** Drei Beine heben sich, drei stehen — alternierend
- [ ] **Phasen-Sync:** Gruppe A oben → Gruppe B unten, exakte Phasen-Differenz 0.5
- [ ] **Roboter steht stabil** (kippt nicht, rutscht nicht)
- [ ] `phase_5_gait_explained.md` zweite Hälfte (Phasen-Sync, Tripod-Mathematik)

---

## Stufe G — Vollständiger Tripod-Gait geradeaus per `/cmd_vel`

**Ziel:** **Phase-5-Done-Kriterien 2, 3, 4, 5 erfüllt.** `/cmd_vel.linear.x = 0.05`
bewirkt sichtbares Vorwärtslaufen, `cmd_vel = 0` → STANDING-Rückfall mit
Timeout, Tripod-Sequenz erkennbar.

**Was wir machen:** `cmd_vel`-Subscriber, body-frame-Mapping (linear.x
schiebt Stützbeine entgegen Fahrtrichtung im Bein-Frame), Timeout-basierter
STANDING-Rückfall (>0.5 s ohne `cmd_vel` → in Neutral-Pose stoppen).

**Konzept-Diskussionspunkte:**
- **cmd_vel → step_length-Mapping:** `step_length ∝ linear.x * cycle_time`?
  Konstantes T und linear.x skaliert Schrittweite — am einfachsten.
  Alternative: T anpassen. Empfehlung: konstantes T, Schrittweite skaliert.
- **Body-Frame ↔ Bein-Frame:** Ein Geradeaus-Schritt `linear.x` in
  base_link wird in jedem Bein-Frame zu einem Schritt in dessen lokaler
  X-Richtung — Mount-Yaw-Rotation berücksichtigen!
- **Timeout-Logik:** `last_cmd_time`-Stempel pro Tick prüfen, > 0.5 s
  ohne → STANDING. Phase-5-Stolperfalle "Roboter zittert weiter" damit
  vermieden.
- **Limits:** `step_length_max = 0.04 m` (aus Roadmap), darüber clamping.

- [ ] Konzept besprochen (cmd_vel-Mapping, Body↔Bein-Frame-Rotation, Timeout)
- [ ] `cmd_vel`-Subscriber + Body-Frame-Mapping in `gait_engine`
- [ ] STANDING-Timeout-Rückfall (> 0.5 s ohne cmd_vel)
- [ ] Stützphase mit Vortrieb (Foot rückwärts entgegen Fahrtrichtung)
- [ ] `phase_5_stage_G_test_commands.md` geschrieben
- [ ] **Live-Verifikation DK3:** `cmd_vel.linear.x = 0.05` → Roboter läuft sichtbar vorwärts
- [ ] **Live-Verifikation DK4:** `cmd_vel = 0` → Roboter bleibt nach <0.5 s in Stand-Pose stehen
- [ ] **Live-Verifikation DK5:** Tripod-Sequenz erkennbar (3 schwingen, 3 stützen, alternierend)
- [ ] **Numerisch:** Body-X bewegt sich vorwärts (gz model -m hexapod -p), Drift in y/yaw klein
- [ ] **Kein Wegrutschen, keine Kollisionen mit Chassis** (Stolperfallen-Check)

---

## Stufe H — Phasenabschluss + optional Schritt 6/7

**Ziel:** Phase 5 formell schließen.

**Optional in dieser Phase:**
- **Schritt 6:** `cmd_vel.angular.z` → Drehen um Z-Achse. Beine bewegen sich
  tangential zu Body-Center.
- **Schritt 7:** `cmd_vel.linear.y` → Seitwärtslaufen.
- **KDL-Warning-Fix:** mit Dummy-Root-Link, falls in Phase 5 störend.
  Sonst auf Phase 6/7 schieben.

- [ ] Alle 5 Done-Kriterien aus `phase_5_kinematics_gait.md` erfüllt
- [ ] `pytest` in `hexapod_kinematics` grün
- [ ] Tripod-Gait-Diagramm in `hexapod_gait/README.md`
- [ ] Parameter-Werte in `controllers.yaml` und Gait-Config dokumentiert
- [ ] `hexapod_kinematics/README.md` (Zweck, Test-Aufruf, IK-Konvention)
- [ ] `hexapod_gait/README.md` (Zweck, Launch-Aufruf, cmd_vel-Format, Stolperfallen)
- [ ] `phase_5_ik_explained.md` und `phase_5_gait_explained.md` final
- [ ] (optional) Schritt 6 (`angular.z`) implementiert + verifiziert
- [ ] (optional) Schritt 7 (`linear.y`) implementiert + verifiziert
- [ ] (optional) KDL-Warning gefixt — sonst auf Phase 6/7 schieben (Memory bleibt)
- [ ] Workspace-`README.md` um Phase-5-Bericht ergänzt
- [ ] Timeshift-Snapshot `phase_5_done` — User-Aufgabe
- [ ] Git-Commit + Tag `phase-5-done` — User-Aufgabe
- [ ] `PHASE.md` auf Phase 6 aktualisiert (Status: Phase 5 🟢, Phase 6 🟡)
- [ ] Retro: Was lief gut, was hat länger gedauert, was bleibt offen
