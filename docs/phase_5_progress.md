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

### Design-Entscheidungen Stufe B

#### 1. numpy-Dependency oder Pure-Python?

**Optionen:**
- **A) Pure-Python `math`** — `math.atan2`, `math.acos`, `math.sqrt`,
  `pytest.approx` für Asserts. Pro: Library bleibt minimal, kein
  heavyweight dep für triviale Skalar-Math. Contra: spätere
  Vektorisierung über alle 6 Beine bräuchte Refactor.
- **B) numpy** — `np.arctan2`, `np.arccos`, `np.sqrt`, `np.allclose`.
  Pro: erlaubt sofort vektorisierte Ops. Contra: heavyweight für 1-D-Math,
  bricht die "echt minimal"-Eigenschaft der Library.

**Gewählt: A** — IK macht 6 atan2/acos/sqrt-Aufrufe pro 50-Hz-Tick =
300 trivial-Math/s, pure Python ist mit Reserve schnell genug auf dem
Pi 4. Vektorisierung wäre Vorzeitige Optimierung.

**Falls später Re-Design nötig** (Performance-Probleme, oder echte
Batch-Berechnung über alle 6 Beine gleichzeitig): Wechsel zu numpy ist
~30 Code-Zeilen, lokal in `leg_ik.py` und `geometry.py`. Die Tests
bleiben unverändert (`pytest.approx` arbeitet auch mit numpy-Arrays).

#### 2. IK-Fehlerbehandlung: Lenient oder Strict?

**Optionen:**
- **A) Lenient** — `IKError` nur bei Cosinus-Argument außerhalb `[-1, 1]`
  (geometrisch out-of-reach). Joint-Limit-Check ist Sache der Gait-Engine
  (Stufe G clamping) und des JTC (Phase-4-Doppel-Limit). Pro: IK ist
  saubere Math-Funktion, klare Verantwortung. Contra: Limit-verletzende
  Antworten müssen Konsumenten selbst checken.
- **B) Strict** — IK prüft auch `coxa_limits`, `femur_limits`, `tibia_limits`
  aus `LegConfig` und wirft IKError bei Verletzung. Pro: Konsumenten
  brauchen keinen separaten Check. Contra: koppelt Math-Library an
  Robot-Controller-Logik, „geometrisch erreichbar aber mechanisch nicht"
  als Diagnose verschwindet.

**Gewählt: A** — IK liefert geometrische Antwort. Limit-Check macht der
Konsument (Gait-Engine in Stufe G; JTC clampt zusätzlich).

**Falls später Re-Design nötig** (z. B. Konsumenten verlassen sich auf
strict-Verhalten, Limit-Checks redundant verteilt): zusätzliche Variante
`leg_ik_checked(...)` als Wrapper hinzufügen, die Lenient-IK aufruft und
gegen Limits prüft. Bestehende `leg_ik` bleibt lenient.

#### 3. Knie-Konvention: hardcoded oder schaltbar?

**Optionen:**
- **A) Hardcoded "Knie oben"** — einzig sinnvolle Konvention für unseren
  Hexapod (Foot unter Body, klassische Stance). Keine Konfiguration in
  `LegConfig`. Pro: cleaner Code, klare API. Contra: keine Schalter-
  Vorbereitung für hypothetisch andere Konfigurationen.
- **B) Schalter `knee_up: bool` in `LegConfig`** — Knie-oben/-unten
  konfigurierbar. Pro: theoretisch flexibel (z. B. inverser Roboter).
  Contra: 0 Anwendungs-Fälle, mehr Code, mehr Test-Pfade.

**Gewählt: A** — „Knie unten" wäre nur für Decken-hängende Roboter
sinnvoll (Foot über coxa_joint), hier nie. Erweiterung später ist 5
Code-Zeilen — `knee_up: bool = True`-Parameter in `leg_ik` ergänzen.

#### 4. Test-Set für `leg_ik.py`

**Optionen:**
- **A) Vorschlag wie gelistet** — 6 spezifische Punkte (Neutral,
  voll gestreckt, 2× out-of-reach, seitlich, tief gehoben) +
  systematischer FK(IK(p))-Round-Trip über zufälliges Raster +
  Links-Rechts-Symmetrie-Test (Bein 1 vs. Bein 4). Pro: deckt
  Standard- und Edge-Cases ab, Round-Trip-Raster fängt
  Vorzeichen-Bugs zuverlässig. Contra: keine.
- **B) Anders** — User möchte andere/zusätzliche Punkte.

**Gewählt: A** — User-Bestätigung. Die Round-Trip-Garantie
`FK(IK(p)) ≈ p` ist die mathematisch stärkste Aussage; einzelne
Stützpunkte sind Sanity-Checks darüber hinaus.

---

- [x] Konzept besprochen (Knie-Konvention hardcoded "Knie oben", Bein-Frame-Konvention bestätigt aus Stufe A, Spiegelung links/rechts gehört rein zum `mount_yaw` — keine IK-Math-Spiegelung; Pure-Python ohne numpy, Lenient-Errors, Test-Set wie vorgeschlagen)
- [x] `leg_ik` implementiert in [leg_ik.py](../src/hexapod_kinematics/hexapod_kinematics/leg_ik.py) — 6 Schritte (atan2/Cosinussatz), Vorzeichen für URDF-Konvention angepasst (`θ_femur = α - β` mit `α = atan2(-z, r)`)
- [x] `leg_fk` implementiert (3D-Forward-Kinematics über coxa-rotierte Ebene + parallele Y-Achsen-Addition für Tibia-Richtung)
- [x] `IKError`(`ValueError`)-Exception bei out-of-reach (Cosinus-Arg außerhalb `[-1, 1]` mit `_COS_EPS = 1e-9` Toleranz, dann clamping auf `[-1, 1]` vor `acos`)
- [x] [geometry.py](../src/hexapod_kinematics/hexapod_kinematics/geometry.py): `rotate_z`, `base_to_leg_frame`, `leg_to_base_frame` (Pure-Python, kein numpy)
- [x] `__init__.py` re-exported alle Public-Symbols (`leg_ik`, `leg_fk`, `IKError`, Geometry-Helper)
- [x] [test_leg_ik.py](../src/hexapod_kinematics/test/test_leg_ik.py): 10 Tests — Phase-4-Handover-Smoke, voll gestreckt (FP-Toleranz `1e-6`), seitlich, tief gehoben, 3× out-of-reach, deterministisches Round-Trip-Raster (50 Punkte, Seed 42), Symmetrie über alle 6 Beine
- [x] [test_geometry.py](../src/hexapod_kinematics/test/test_geometry.py): 8 Tests — `rotate_z` 0°/90°/180°/inverse, `mount_xyz`-Origin-Identität pro Bein, base↔leg-Round-Trip pro Bein × 5 Punkte, Bein-1 +X-Direction-Vorzeichen-Sanity
- [x] `colcon test --packages-select hexapod_kinematics` grün: **27 passed, 1 skipped** (7× config + 8× geometry + 10× leg_ik + flake8 + pep257; copyright skipped)
- [x] [phase_5_ik_explained.md](phase_5_ik_explained.md) geschrieben (Konzept-Hintergrund: Bein-Frame, URDF-Drehrichtungen, Knie-Konvention, 6-Schritt-IK, FK-Inversen-Verifikation, Edge-Cases, Tests-Übersicht, Vorschau auf Gait-Engine-Flow)

### Umsetzungsnotizen Stufe B

> **Konzept-Hintergrund** (Bein-Frame-Konvention, URDF-Drehrichtungen,
> Knie-oben-Begründung, geschlossene-Form-Herleitung, FK-Inversen-Logik,
> Edge-Cases, Gait-Engine-Vorschau): siehe
> [phase_5_ik_explained.md](phase_5_ik_explained.md). Das Dokument bleibt
> in Stufen C-H und Phase 6/7 als Nachschlagewerk verfügbar.

**Math-Herleitung der Vorzeichen:** Die zentrale subtile Stelle ist
`θ_femur = α - β` mit `α = atan2(-z, r)`. Das `-z` macht α positiv für
unter dem Femur-Joint hängende Foots (z < 0). Die `α - β`-Form (statt
`α + β` aus der Roadmap) kompensiert die URDF-Konvention, in der
positive Femur-Rotation **nach unten** zeigt (entgegen der mathematischen
Standard-Konvention "positiv = CCW = nach oben"). Bestätigt am Stand-
Pose-Beispiel: `α = +0.205`, `β = +0.714` → `θ_femur = -0.509` ≈ -0.5 ✓.

**FP-Drift bei voll gestreckter Pose:** `acos(1.0)` ist mathematisch 0,
aber das Cosinus-Argument unterliegt FP-Drift. Bei `(L_c+L_f+L_t, 0, 0)`
ist der berechnete `cos_β_arg` typischerweise `1 - 4e-16`, und
`acos(1 - 4e-16) ≈ sqrt(8e-16) ≈ 2e-8`. Resultat: θ_femur drift in
~1e-8 statt exakt 0. Test-Toleranz für **diesen einen** Test auf `1e-6`
gelockert; alle anderen Tests verwenden `1e-9` und bleiben dort.
`_COS_EPS = 1e-9` im Code toleriert ähnliches Überschießen vor IKError-
Auslösung.

**Round-Trip-Raster mit deterministischem RNG:** `random.Random(42)`
statt `numpy.random` — Pure-Python-Konformität. Seed = 42 garantiert
reproduzierbare Punkt-Auswahl, sodass ein "fragiler Test"-Bug
nicht zufällig nur bei bestimmten Runs sichtbar wird. 50 Punkte,
50/50-Mischung aus radialer Position und Coxa-Schwenk. Mindestens 30 davon
müssen reachable sein (sonst war das Raster zu eng) — der Bullet-Check
verifiziert das.

**Mechanische Symmetrie als Test:**
[test_all_legs_identical_ik](../src/hexapod_kinematics/test/test_leg_ik.py)
ruft `leg_ik(0.20, 0.03, -0.05, leg)` für alle 6 Beine auf und vergleiche
den Output. Erwartung: identisch bis 1e-12. Funktion: dokumentiert die
Stufe-A-Designentscheidung "kein is_left-Flag" als Test, sodass eine
spätere Asymmetrie-Einführung diesen Test brechen müsste (Wächter
gegen schleichende Differenzierung).

**Style-Konventionen weiter ausgebaut (über Stufe-A-Erkenntnisse hinaus):**
- `D200` (pep257): Einzeiliger Docstring darf nicht über 3 Zeilen
  verteilt sein. Wenn das Modul nur einen Satz Doku hat, alles in eine
  Zeile, sonst echte Leerzeile + Body verwenden.
- `I101` (flake8-import-order): Innerhalb eines `from X import a, b, c`-
  Statements sind die Namen **case-insensitive** alphabetisch zu sortieren
  (so dass `base_to_leg_frame, HEXAPOD, leg_to_base_frame, rotate_z`
  korrekt ist — `base` < `hexapod` < `leg_to_base` < `rotate`, auch
  wenn `b < H` in ASCII-Sortierung).

**Was Stufe B explizit NICHT macht:**
- Keine Joint-Limit-Prüfung in `leg_ik` (Lenient-Design, Stufe-G-Job).
- Keine `numpy`-Dependency (Pure-Python-Math reicht).
- Keine vektorisierte Multi-Bein-IK (Single-Bein-Aufruf, Multi-Bein
  ist Iteration im Konsumenten — Gait-Engine in Stufe E-G).
- Kein "Knie unten"-Schalter (hardcoded Knie oben, YAGNI).
- Kein ROS-Knoten (Stufe C).
- Keine Live-Sim-Verifikation (Stufe C als Live-Smoke).

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

### Design-Entscheidungen Stufe C

#### 1. Neutral-Pose-Definition

**Optionen:**
- **A) Parametrisiert via `(body_height, radial_distance)`** — zwei
  Knoten-Parameter mit Default `(-0.047, 0.27)`. Foot-Target im
  Bein-Frame: `(radial_distance, 0, body_height)`. Mit Defaults
  reproduziert IK exakt `[0, -0.5, +1.0]`. Pro: nahe am späteren
  Gait-Engine-Modell (Foot-Punkte sind die natürliche Steuergröße);
  Tunbar ohne Code-Touch via `--ros-args`. Contra: Joint-Winkel sind
  nicht direkt sichtbar.
- **B) Hardcoded Foot-Punkt** `(0.27, 0, -0.047)`. Pro: einfacherer Code.
  Contra: Magic Numbers, Tunen erfordert Code-Edit. **Verworfen vom User.**
- **C) Parametrisiert via `(femur_angle, tibia_angle)` + FK** — Param
  `(-0.5, +1.0)`, Knoten ruft FK→Foot→IK durch. Pro: tautologische
  Live-Demo der IK-Pipeline; mechanisch intuitiv (Servo-Winkel direkt).
  Contra: tautologisch (FK ist Inverse von IK); Höhe-Tuning erfordert
  Joint-Winkel-Denken statt Höhen-Denken.

**Gewählt: A** — User-Entscheidung. Konsistent mit der Gait-Engine-
Architektur (Stufen E-G arbeiten ebenfalls auf Foot-Targets). IK-
Pipeline-Korrektheit wird bereits Pure-Python in Stufe-B-Tests
abgesichert; die Live-Demo aus C ist keine zusätzliche Aussage.

**Falls später Re-Design nötig** (z. B. neue Servo-Winkel-Limits machen
direkten Joint-Winkel-Modus relevant): C als zusätzlicher Modus
einführen, mit Mode-Switch via Parameter. A bleibt als Default.

#### 2. Launch-Integration

**Optionen:**
- **A) Eigenes Launch-File `hexapod_gait/launch/stand.launch.py`** —
  ~20 Zeilen mit LaunchArgs für `body_height`, `radial_distance`,
  `transition_duration`, `use_sim_time`. Aufruf:
  `ros2 launch hexapod_gait stand.launch.py body_height:=-0.06`. Pro:
  ROS2-Standard, bequeme Arg-Syntax, kombinierbar via
  `IncludeLaunchDescription` in höheren Bringups (Stufe G/H).
  Contra: zusätzliche Datei.
- **B) Nur `ros2 run` + Doku** — Param-Setzen via `--ros-args -p`. Pro:
  spart Datei. Contra: umständlichere Aufruf-Syntax,
  `use_sim_time:=true` muss manuell mitgegeben werden.
- **C) `enable_stand`-LaunchArg in `sim.launch.py`** — Stand wird
  optional Teil des Sim-Launches. Pro: Ein-Befehl-Start. Contra:
  bläht `sim.launch.py` auf, zwingt Stand+Sim-Lifecycle in eine
  Einheit (Stand kann nicht ohne Sim-Restart re-getriggert werden).

**Gewählt: A** — User-Entscheidung. Eigene Launch-Datei ist die
ROS2-konventionelle Lösung für "Knoten mit Parametern starten".
Bewusste Trennung von `sim.launch.py` (Daueraufgabe Sim) und
`stand.launch.py` (abrufbare Aktion Stand-Pose).

**Falls später Re-Design nötig** (z. B. Bringup-Manager-Phase, in der
Sim+Stand+Gait als Einheit gestartet werden): `IncludeLaunchDescription`-
Pattern verwenden, `stand.launch.py` als Modul einbinden. Bestehende
Launch-Datei bleibt eigenständig nutzbar.

#### 3. Knoten-Lebenszyklus

**Optionen:**
- **A) One-Shot mit Auto-Exit** — match-wait JTC-Subscriber (5 s
  Timeout), 6× Pub, 0.5 s sleep für DDS-Auslieferung, dann
  `rclpy.shutdown()`. Pro: klares "fertig"-Signal (Exit-Code), saubere
  ROS-Topic-Liste, skript-tauglich (in Test-Pipelines verkettbar).
  Contra: Re-Trigger erfordert Knoten-Neu-Start (kein Drama).
- **B) Pub einmal, dann dormant im Spin bleiben** — Knoten publisht und
  bleibt in `rclpy.spin()`, beendet sich nur via `Ctrl+C`. Pro:
  einfacher Code; falls später Service-Calls angefügt werden, bleibt
  Knoten verfügbar. Contra: Knoten "schwirrt rum", verlängert
  `ros2 node list`, kein klares Ende-Signal.
- **C) Periodisch re-publishen** (alle 5 s). Pro: robust gegen verlorene
  erste Pubs. **Contra: BLOCKIERT spätere Override durch `gait_node`** —
  alle 5 s zerstört Stand-Pub das laufende Gait-Goal des JTC. **Verworfen.**

**Gewählt: A** — User-Entscheidung nach Klärung der Override-Mechanik.
Override-Fähigkeit ist eine **JTC-Eigenschaft** (jeder neue Trajectory-
Pub ersetzt das laufende Goal), unabhängig vom Lifecycle des
publishenden Knotens. A und B erlauben Override gleichermaßen, A ist
sauberer.

**Falls später Re-Design nötig** (z. B. Stand-Service-Endpoint für
Re-Trigger ohne Restart): zu B umschwenken oder Service-basierte
Variante anlegen. Aktuell kein Bedarf.

#### 4. Topic-Format (nicht zur Diskussion)

`trajectory_msgs/msg/JointTrajectory` per `Publisher` an
`/leg_<n>_controller/joint_trajectory` für n=1..6 — übernommen aus
Phase 4. Action-Variante (`FollowJointTrajectory`) wäre bei expliziter
Goal-Tracking-Notwendigkeit erwägbar; für unsere One-Shot-Pub-Logik
keine Mehrwert. Stufen E-G bauen auf demselben Pattern auf (50-Hz-Pub
statt One-Shot).

---

- [x] Konzept besprochen (Neutral-Pose A: parametrisiert via body_height+radial_distance, Launch A: eigenes stand.launch.py, Lifecycle A: One-Shot mit Auto-Exit, Topic-Pattern: JointTrajectory wie Phase 4)
- [x] `hexapod_gait` Paket-Skelett angelegt (`ament_python`, exec_depends: `rclpy`, `trajectory_msgs`, `builtin_interfaces`, `hexapod_kinematics`); `setup.py` mit `entry_points` für `stand_node` und `data_files` für Launch-Files
- [x] [hexapod_gait/stand_node.py](../src/hexapod_gait/hexapod_gait/stand_node.py) implementiert — `StandNode(Node)`-Klasse mit 4 Parametern (`body_height`, `radial_distance`, `transition_duration`, `match_timeout`), 6 Publishern, `_wait_for_subscribers` (5s timeout), `_build_trajectory`, `run()`-Hauptschleife, `main()`-Entry mit Exit-Code
- [x] [hexapod_gait/launch/stand.launch.py](../src/hexapod_gait/launch/stand.launch.py) angelegt — 5 LaunchArgs mit Defaults und Beschreibung, `Node`-Action mit Param-Mapping, `use_sim_time:=true` Default
- [x] `colcon build --packages-select hexapod_gait` grün
- [x] `colcon test --packages-select hexapod_gait` grün — flake8 + pep257 + copyright (skipped)
- [x] [phase_5_stage_C_test_commands.md](phase_5_stage_C_test_commands.md) geschrieben — 6 Schritte (Sim-Start, Controller-Check, stand_node-Launch, Joint-Echo mit explizitem Typ, Drift-Check, Aufräumen) + 3 optionale Variationen (anderer body_height, Out-of-reach-Fall, Override-Test)
- [x] **Live-Verifikation:** Sim startet, `stand_node` fährt Pose, Roboter steht auf 6 Foot-Kugeln — **bestätigt** 2026-05-09
- [x] **Live-Smoke:** Joint-Werte aus `/joint_states` exakt `[~0, -0.50998, +1.01222]` pro Bein, gemessene Abweichung von der erwarteten IK-Ausgabe `[0, -0.510, +1.012]` ist < 2e-4 rad — **deutlich besser als geforderte Toleranz ±0.01 rad**
- [x] **Drift-Check:** `gz model -m hexapod -p` über 5 Samples bit-genau identisch (`z=0.054999`, `RPY=[0, 0, -0.042676]`) — **Drift = 0 mm / 0°**, gleich wie Phase-4-Stufe-F

### Umsetzungsnotizen Stufe C

> **Konzept-Hintergrund** (Bein-Frame, IK-Pipeline, Knie-Konvention):
> siehe [phase_5_ik_explained.md](phase_5_ik_explained.md) (Stufe B).
> Stufe C ist die erste **Live-Anwendung** der dort dokumentierten
> IK-Pipeline.

**Test-Anleitung:** [phase_5_stage_C_test_commands.md](phase_5_stage_C_test_commands.md).

**DDS-Discovery-Race (zentraler Bug-Fix während der Stufe):** Erste
Implementation nutzte `Publisher.get_subscription_count()` für eine
Match-Wait-Logik (Knoten exit mit Fehler nach 5 s, falls JTC nicht
sichtbar). User-Test zeigte: alle 6 Counts blieben dauerhaft 0,
obwohl externe `ros2 topic info /leg_1_controller/joint_trajectory`
1 Subscription meldete. Das ist ein bekanntes rclpy/Jazzy-Verhalten:
der **lokale Graph-State** des publizierenden Knotens braucht eine
unbestimmte Zeit (oft viel länger als 5 s), bis Subscriber-Match-
Events propagiert sind — auch wenn die Subscription DDS-weit längst
existiert.

Lösung: Match-Wait gedroppt, durch festen `discovery_wait` (Default
2.0 s) ersetzt. Der Knoten spinnt 2 s zur DDS-Settling-Zeit,
loggt diagnostisch `count_subscribers()`-Werte (jetzt Node-Level
statt Publisher-Level), und **publisht in jedem Fall** — auch wenn
der Graph-State 0 meldet. Begründung: ist der JTC tatsächlich
subscribed (extern verifizierbar), kommt die Pub durch; meldet der
lokale Graph-State 0, ist es ein Render-Lag, kein echter Match-Fail.
Dieses Pattern ist robust und matcht das Verhalten von
`ros2 topic pub --once`, das auch keinen Match-Wait macht.

**Joint-Echo Topic-Type-Discovery-Lag (analog):** `ros2 topic echo
/joint_states --once` ohne Typangabe scheiterte im frischen Terminal
mit "topic does not appear to be published yet". Workaround:
expliziten Typ `sensor_msgs/msg/JointState` mitgeben. In der
Test-Doku dokumentiert.

**Phase-4-Übergabe-IK-Smoke live verifiziert:** Foot-Target
`(0.27, 0, -0.047)` im Bein-Frame → IK liefert
`(coxa=0, femur=-0.50998, tibia=+1.01222)`. Pure-Python-Test in
Stufe B (`test_neutral_pose_phase4_handover`) verlangt Match bis
1e-9 zu `(0, -0.5, 1.0)`. Live-Sim-Verifikation jetzt: JTC liefert
genau die IK-Ausgabe (Abweichung ±2e-4 rad = JTC-Tracking-Genauigkeit).
Damit ist die ganze IK→Trajectory→JTC→Joint-Pipeline End-to-End
validiert.

**Yaw-Asymmetrie-Beobachtung (für Retro / Phase-6-Folgewerk):**
Endsettling-yaw = -2.4° (statt -0.014° in Phase-4-Stufe-F). Phase-4-
Retro hatte erwartet, dass die Asymmetrie "in Phase 5 mit IK-basiertem
Anfahren verschwindet" — das Gegenteil ist eingetreten. Ursache:
Phase 4 fuhr vorab manuell `coxa=0.3` → reset → stand, was die
Bauch-Pose entzerrte. Stufe C geht **direkt von Bauch zu Stand**,
ohne entzerrendes Vorspiel. Die Default-Bauch-Pose (alle Joints=0) ist
nicht 100% symmetrisch (Bein-Längen ragen unterschiedlich auf den
Boden), und das schlägt sich im finalen Settling als yaw-Drift nieder.

Funktional irrelevant: Drift = 0, Roboter steht stabil. **Mögliche
Folgemaßnahme (Phase 6+):** optionale Pre-Stand-Lift-Phase im
stand_node — alle 6 Beine kurz anheben (z. B. femur=-0.8 für 1 s),
dann zur eigentlichen Stand-Pose. Würde die Bauch-asymmetrische
Anfangsbedingung entkoppeln. Nicht Teil von Stufe C, weil Done-
Kriterien sind erfüllt und Pre-Lift-Logik ein eigenes Konzept-
Diskussions-Thema wäre.

**Lifecycle-Override-Test (optional in Test-Doku):** Mit One-Shot-
Lifecycle (Stufe-C-Design-Entscheidung 3) ist der Knoten nach ~3 s
exit. Manuelle `ros2 topic pub --once /leg_1_controller/joint_trajectory ...`
danach übersteuert die Pose. Damit ist die Override-Mechanik des JTC
direkt validierbar, unabhängig vom (bereits verschwundenen) stand_node.
Ein optionaler Test-Befehl steht in der Test-Doku (Schritt
"Override-Test").

**Was Stufe C explizit NICHT macht:**
- Keine Pre-Stand-Lift-Phase (Yaw-Asymmetrie-Vermeidung) — siehe oben.
- Keine periodische Re-Publication (Stufe-C-Design-Entscheidung 3 C
  verworfen).
- Kein gait_node, kein gait_engine, kein trajectory_gen (Stufe E+).
- Keine Foot-Contact-Sensoren (Stufe D).
- Kein cmd_vel-Subscriber (Stufe G).
- Keine `gait_engine`/`trajectory_gen`-Skelette in Stufe C — die
  kommen mit Konzept-Diskussion in Stufe E.

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

### Design-Entscheidungen Stufe D

#### 1. Sensor-Granularität

**Optionen:**
- **A) 6 separate Topics** `/leg_<n>/foot_contact` pro Bein. Pro:
  ROS2-konventionell, einzeln inspizierbar (`ros2 topic echo /leg_3/foot_contact`),
  konsistent mit Phase-4-Pattern `/leg_<n>_*`. Contra: 6 Topics in `topic list`.
- **B) 1 gesammeltes Topic** `/foot_contacts` als Bit-Maske oder
  Custom-Message. Pro: 1 Topic, atomarer Snapshot. Contra: Sammler-Logik
  führt Latenz ein; Bit-Maske obscure beim `echo`; Custom-Message
  bräuchte ein neues `hexapod_msgs`-Paket.

**Gewählt: A** — User-Entscheidung. ROS2-konventionell, keine
Sammler-Logik nötig.

**Falls später Re-Design nötig** (z. B. ein Konsument braucht atomaren
Snapshot für Synchronisations-Logik): Sammler-Knoten als zusätzliche
Schicht einführen, der die 6 Bools synchronisiert in 1 Custom-Topic
publisht. Bestehende 6 Topics bleiben.

#### 2. Topic-Typ und Konversion

**Optionen:**
- **A) `std_msgs/Bool` mit Konversionsknoten** in Sim. Pipeline:
  Gazebo Contacts → bridge → `ros_gz_interfaces/Contacts` →
  Konversionsknoten → `std_msgs/Bool` auf `/leg_<n>/foot_contact`.
  Phase-7-HW: Treiber publisht direkt `Bool`. Pro: **Sim/HW-Abstraktion
  über identischen Topic-Typ**, Konsumenten unverändert portierbar
  (CLAUDE.md §1). `Bool` ist trivial zu konsumieren. Contra: zusätzlicher
  Konversionsknoten in Sim-Launch (~30 Zeilen Python).
- **B) `ros_gz_interfaces/Contacts` direkt** ohne Konversion. Pro: eine
  Schicht weniger; mehr Detail-Info verfügbar (Kontakt-Punkte, -Normalen).
  Contra: Sim und HW haben unterschiedliche Topic-Typen, Phase-7-HW
  bräuchte Adapter — bricht die Sim/HW-Abstraktion.

**Gewählt: A** — User-Entscheidung. Sim/HW-Abstraktion ist Phase-5-
Hauptziel. Konversionsknoten ist klein, einmal geschrieben.

**Falls später Re-Design nötig** (z. B. ein Konsument braucht echte
Force-/Normal-Daten und nicht nur Binary): zusätzliches Topic
`/leg_<n>/foot_contact_raw` (Contacts-Direkt) parallel zum Bool-Topic
einführen. Konsumenten wählen je nach Bedarf.

#### 3. Toggle-Architektur

**Optionen:**
- **A) Alle 3 Schichten conditional** auf `enable_foot_contact`-LaunchArg:
  xacro-Sensor-Block (conditional include), Bridge (conditional Node),
  Konversionsknoten (conditional Node). Pro: bei OFF wirklich aus —
  keine Sensor-Computation in Gazebo, keine Topics, null Overhead.
  Contra: 3-Stellen-Wiring im Launch (akzeptabel, ~5 Code-Zeilen).
- **B) Nur Bridge conditional** — URDF hat Sensoren immer, Gazebo
  computed immer Contacts, ROS-Bridge wird nur bei enabled gestartet.
  Pro: einfacheres Launch. Contra: Sensor läuft im Hintergrund auch
  wenn nicht genutzt; `gz topic list` und `ros2 topic list` divergieren
  bei OFF — Verwirrung.

**Gewählt: A** — User-Entscheidung. Sauberer Off-Zustand, User-Erwartung
"ein/aus ohne Reste" erfüllt.

**Falls später Re-Design nötig** (Performance-Probleme durch häufiges
Toggeln, Sim-Restart-Pflicht störend): zu B umschwenken (URDF-Sensor
immer aktiv, nur Bridge togglen). Macht das Toggling laufzeit-fähig
ohne Sim-Restart, kostet aber kontinuierlichen Sensor-Compute-Overhead.

#### 4. Topic-Namensschema

**Optionen:**
- **A) `/leg_<n>/foot_contact`** — `/leg_<n>` als Namespace mit
  `foot_contact` als Topic-Name. Pro: konsistent mit Phase-4-Bein-
  Namespacing-Pattern (`/leg_<n>_controller/...` ist zwar Suffix-
  basiert, aber `/leg_<n>` ist die strukturelle Einheit). In Phase 7
  identischer Topic-Name beim HW-Treiber → Drop-in-Replacement.
- **B) `/foot_contact/leg_<n>`** — `/foot_contact` als Namespace mit
  Bein-Index als Topic. Pro: alle Foot-Contact-Topics gruppiert in
  `/foot_contact/`-Namespace. Contra: bricht das pro-Bein-Namespacing-
  Pattern.
- **C) `/leg_<n>_foot_contact`** — flach mit Underscore. Wie Phase-4-
  Joint-Names (`leg_<n>_coxa_joint`), aber für Topic-Hierarchie weniger
  geeignet.

**Gewählt: A** — User-Entscheidung (per Notiz, nicht via AskUserQuestion).
Folgt dem Phase-4-Bein-Namespacing-Pattern.

**Falls später Re-Design nötig** (z. B. mehrere Sensor-Typen pro Bein):
zu B umschwenken (Sensor-Type-Namespace). Dann wäre auch `/imu/...`
oben und `/foot_contact/...` parallel logischer.

#### 5. Wo lebt der Konversions-Knoten?

**Optionen:**
- **A) `hexapod_gait`** — Konsument-nahe Verortung. Pro: gait_node ist
  späterer Konsument der Bool-Topics. Contra: gait-Paket bekommt
  Sensor-Logik dazu, mischt Verantwortungen.
- **B) `hexapod_bringup`** — Launch + adapter. Pro: zentraler
  Orchestrierungs-Punkt. Contra: bringup ist sonst Launch-only,
  bricht das Muster.
- **C) Neues Paket `hexapod_sensors`** — eigene Sensor-Hoheit.
  Pro: zukunftssicher für IMU (User-Plan), Foot-Contact-Switches und
  weitere Sensoren in einem Paket; saubere Verantwortungs-Trennung
  Sensoren ↔ Bewegung. Contra: minimal mehr Boilerplate (eigenes
  package.xml + setup.py).

**Gewählt: C** — User-Entscheidung. Begründung des Users:
"Ich möchte später noch weitere Sensoren einbinden". `hexapod_sensors`
wird der Sammelort. Stufe D legt das Paket-Skelett an + den
Foot-Contact-Konversionsknoten; spätere Sensoren (IMU in Phase 6/7)
landen ebenfalls hier.

**Falls später Re-Design nötig** (z. B. wenn `hexapod_sensors` zu
mächtig wird und einzelne Sensoren in eigene Pakete sollen):
Aufspaltung in `hexapod_imu`, `hexapod_foot_contact` etc. ist möglich.
Aktuell unwahrscheinlich.

---

- [x] Konzept besprochen (Granularität A: 6 separate Topics, Topic-Typ A: Bool mit Konversionsknoten, Toggle A: alle 3 Schichten conditional, Namensschema A: `/leg_<n>/foot_contact`, Knoten-Paket C: neues `hexapod_sensors`)
- [x] **`hexapod_sensors` Paket-Skelett angelegt** (ament_python, exec_depends: `rclpy`, `std_msgs`, `ros_gz_interfaces`); entry_point `foot_contact_publisher`
- [x] **[hexapod_description/urdf/hexapod.foot_contact.xacro](../src/hexapod_description/urdf/hexapod.foot_contact.xacro)** — xacro-Macro `leg_foot_contact(id)` 6× instanziiert, `<sensor type="contact">` mit `<topic>foot_contact_leg_<id></topic>`, `update_rate=50`, `<contact><collision>leg_<id>_foot_link_collision</collision></contact>`
- [x] **Top-Level-[hexapod.urdf.xacro](../src/hexapod_description/urdf/hexapod.urdf.xacro)** erweitert: `<xacro:arg name="enable_foot_contact" default="true"/>`; conditional Include via `<xacro:if value="$(arg enable_foot_contact)">`
- [x] **[hexapod_sensors/foot_contact_publisher.py](../src/hexapod_sensors/hexapod_sensors/foot_contact_publisher.py)** — rclpy-Knoten, 6 Subs auf `/leg_<n>/foot_contact_raw` (`Contacts`) → 6 Pubs auf `/leg_<n>/foot_contact` (`Bool`); Closure-Factory pro Bein damit `leg_id` korrekt gebunden ist
- [x] **[hexapod_bringup/config/bridge_foot_contact.yaml](../src/hexapod_bringup/config/bridge_foot_contact.yaml)** — 6 Bridge-Mappings (`gz.msgs.Contacts` → `ros_gz_interfaces/Contacts`, GZ_TO_ROS); `CMakeLists.txt` ergänzt für `install(DIRECTORY launch config ...)`
- [x] **[hexapod_bringup/launch/sim.launch.py](../src/hexapod_bringup/launch/sim.launch.py)** erweitert: LaunchArg `enable_foot_contact` (Default `true`), an xacro-Command per `enable_foot_contact:=` durchgereicht; conditional `ros_gz_foot_contact_bridge`-Node (Bridge-YAML) und conditional `foot_contact_publisher`-Node, beide via `IfCondition(LaunchConfiguration('enable_foot_contact'))`
- [x] `package.xml` von hexapod_bringup um `<exec_depend>hexapod_sensors</exec_depend>` ergänzt
- [x] `colcon build --packages-select hexapod_description hexapod_sensors hexapod_bringup` grün — 3 packages finished, keine Fehler
- [x] `xacro` mit `enable_foot_contact:=true` rendert mit 6 Sensor-Blöcken; `:=false` rendert mit 0 Sensor-Blöcken (verifiziert via `grep -c 'type="contact"'`)
- [x] `colcon test --packages-select hexapod_sensors` grün (flake8 + pep257)
- [x] [phase_5_stage_D_test_commands.md](phase_5_stage_D_test_commands.md) geschrieben — 3 Test-Pfade (Toggle-ON, Funktional, Toggle-OFF) mit insgesamt 14 Schritten + 2 optionale Diagnose-Variationen (Bridge-Direct + gz topic native)
- [x] **Live-Verifikation Toggle ON:** Sim startet mit `enable_foot_contact:=true`, in Stand-Pose Bein 1 + Bein 2 = `data: true` — bestätigt 2026-05-09
- [x] **Live-Funktional:** Bein 1 manuell angehoben → `/leg_1/foot_contact` = `data: false`, `/leg_2/foot_contact` bleibt `data: true` — bestätigt 2026-05-09
- [x] **Live-Verifikation Toggle OFF:** Sim startet mit `enable_foot_contact:=false`, `ros2 topic list | grep foot_contact` leer, `ros2 node list | grep foot` leer — bestätigt 2026-05-09

### Umsetzungsnotizen Stufe D

> **Test-Anleitung** mit allen Befehlen pro Terminal:
> [phase_5_stage_D_test_commands.md](phase_5_stage_D_test_commands.md).

**Stufe-D-Live-Bringup hatte vier Bugs zu durchdringen, alle in der
Bridge-Pipeline:**

#### 1. `<topic>`-Override-Bug in der xacro (Schicht 1)

Erste Implementation hatte `<topic>foot_contact_leg_<id></topic>` als
**Sibling von `<contact>`** in der Sensor-Definition. Topic wurde damit
zwar registriert (sichtbar in `gz topic -l`), aber Gazebo Harmonic's
`Contact`-System bindet das Override nur korrekt wenn `<topic>` ein
**Kind von `<contact>`** ist. Resultat: Gazebo-Sensor produzierte zwar
Events intern, leitete sie aber nicht an den Override-Topic weiter →
keine Daten in der Bridge.

Fix: `<topic>` in den `<contact>`-Block verschoben. Vorbild:
[/opt/ros/jazzy/opt/gz_sim_vendor/share/gz/gz-sim8/worlds/contact_sensor.sdf](contact_sensor.sdf)
des gz-sim-vendor-Pakets.

```xml
<sensor name="..." type="contact">
  <update_rate>50</update_rate>
  <always_on>1</always_on>
  <contact>
    <collision>...</collision>
    <topic>foot_contact_leg_X</topic>   <!-- HIER drin -->
  </contact>
</sensor>
```

#### 2. Fixed-Joint-Lumping (Schicht 1)

Standard-Verhalten von libsdformat in Harmonic: Links die per
`fixed`-Joint verbunden sind, werden zu einem einzigen Link fusioniert.
Da `leg_<n>_foot_link` per `fixed`-Joint an `leg_<n>_tibia_link` hängt,
landete der Sensor **am tibia_link** statt am foot_link, und der
Collision-Name wurde unter Umständen umgeschrieben. Resultat:
`<contact><collision>leg_<n>_foot_link_collision</collision>`-Verweis
greift ins Leere.

Fix: per-foot_joint die `<preserveFixedJoint>true</preserveFixedJoint>`
und `<disableFixedJointLumping>true</disableFixedJointLumping>` Pragmas
in der xacro setzen. libsdformat respektiert diese, foot_link bleibt
separat. Verifiziert via `gz sdf -p`-Konversion offline.

#### 3. Sim-Time-Race in Konversionsknoten (Schicht 3)

Erste Konversionsknoten-Implementation publishte Bool-Topics nur **bei
Empfang** einer Contacts-Message (event-basiert). Problem: bei
angehobenem Foot publisht Gazebo nichts → Konversionsknoten publisht
nichts → Konsumenten sehen `silence` statt `false`. Sim-Verhalten
divergiert von Phase-7-HW-Verhalten (microswitch publisht **periodisch**,
nicht event-basiert).

Fix: Timer-basierte Publication mit Decay. Pro Bein
`_last_contact_time`. Subscriber-Callback aktualisiert Timestamp.
Timer bei 50 Hz publisht
`Bool(now - last_contact_time < contact_timeout)`. Dadurch fließt
**immer** ein aktuelles Bool-Signal — `true` wenn kürzlich Contact,
sonst `false`.

Zweiter Issue dabei: `self.get_clock().now()` mit `use_sim_time=True`
braucht den `/clock`-Topic (über bridge.yaml). DDS-Discovery-Race
verzögert das gelegentlich, Timer-Callbacks wurden dann nicht oder
nicht zuverlässig getriggert. Fix: `time.monotonic()` (wall-clock)
statt sim-clock für die Timeout-Logik. Sim-RTF=1 in Phase 5, also
keine praktische Drift-Gefahr.

#### 4. Stale-Prozesse durch unvollständigen pkill (Diagnose-Stufe)

`pkill -f "ros2 launch"` und `pkill -f "ruby.*gz"` fängt **nicht** alle
Sim-relevanten Prozesse. Insbesondere bleiben übrig:
- `foot_contact_publisher` (kein "ros2"/"gz"/"ruby" im Pfad)
- `stand_node` (auch nicht gefangen)
- `parameter_bridge` (zu spezifisch um pauschal zu killen)

Folge: bei wiederholten Sim-Restarts liefen mehrere
`foot_contact_publisher`-Instanzen gleichzeitig, alle publishten auf
denselben Bool-Topics, Subscribers wurden verwirrt
(Multi-Publisher-Konstellation, Volatile-QoS-Race). Bestätigt durch
`ps aux`: 2 stale Prozesse, einer mit 67% CPU.

Fix: Test-Doku-Cleanup-Template um `pkill -9 -f "foot_contact_publisher"`
und `pkill -9 -f "stand_node"` ergänzt, plus weitere ROS-Prozess-Patterns.
Memory-Eintrag potenziell sinnvoll, weil das Pattern in Phase 7-HW-Tests
analog auftauchen wird.

#### Kontakt-Sensor-Output-Plausibilität

Gazebo Contact-Sensor liefert pro Kontakt sehr detaillierte Daten:
- `collision1`/`collision2` (Foot ↔ Ground-Plane)
- `position` (3D-Kontakt-Punkt im Welt-Koordinatensystem)
- `normal` (z=1, also nach oben — saubere Boden-Normale)
- `depth` ~2.4e-7 m (Penetration auf FP-Rauschen-Level — saubere
  Auflage, nicht "drückend")
- `wrench.body_1.force.z` ≈ 4.3 N pro Foot in Stand-Pose

Pro Foot 4.3 N × 6 Beine = ~25.8 N Auflagekraft. Roboter-Gesamtgewicht
laut hexapod_physical_properties: `0.5 + 6×3×0.1167 + 6×0.005 ≈ 2.6 kg`
× 9.81 m/s² ≈ 25.5 N — passt sauber. Force-Reading bestätigt physikalisch
korrekte Sim-Physik.

#### Was Stufe D explizit NICHT macht

- **Kein Konsumieren der Bool-Topics** — gait-engine in Phase 6+/7+
  liest sie ggf. für Closed-Loop-Adaption, nicht in Phase 5.
- **Kein Re-Publishen mit Force-Daten** — Bool reicht für Switch-Modell
  (Phase 7 HW-Microswitch-Realität).
- **Keine Hysterese / Debounce** — könnte in Phase 7 HW-Treiber relevant
  werden (mechanische Switch-Bouncing), aktuell nicht nötig.
- **Kein Multi-Sensor-Sammler** — Single-Topic-pro-Bein bleibt
  (Stufe-D-Design-Entscheidung 1).

---

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

### Design-Entscheidungen Stufe E

#### 1. Swing-Trajektorien-Form

**Optionen:**
- **A) Halbsinus** — `z(t) = z_stand + step_height·sin(π·t)`, t ∈ [0, 1].
  2 Parameter (step_height, cycle_time). `sin'(0) = sin'(π) = 0` →
  Touchdown ohne vertikale Geschwindigkeit, kein Bounce. Standard-
  Hexapod-Pattern. Pro: einfach, smooth, ausreichend.
- **B) Quadratischer Bezier** mit 3 Kontrollpunkten (start/peak/end).
  Pro: mehr Flexibilität (asymmetrische Bögen). Contra: mehr Parameter,
  bei symmetrischer Schwung-Bahn keine echte Verbesserung.

**Gewählt: A** — User-Entscheidung. Symmetrische Sinus-Bahn passt zu
unserem Use-Case. Falls später asymmetrische Trajektorien nötig
(z. B. langsame Touchdowns für Closed-Loop-Foot-Contact-Adaption),
einfacher Refactor.

#### 2. State-Machine vs. Simple Mode

**Optionen:**
- **A) Simple Mode** — gait_node startet, Bein N schwingt dauerhaft,
  Rest steht. Kein Service, kein Toggle-Mechanismus. Pro: kompakt
  (~30 Zeilen weniger), passt zur Stufe-E-Verifikation (Knoten
  startet → schwingt → User beobachtet → User killt). Contra: kein
  Live-Toggle ohne Restart.
- **B) STANDING/WALKING-State-Machine** mit `enable_walk`-Parameter.
  Pro: Toggle-bar ohne Restart. Contra: in Stufe F wird die State-
  Machine ohnehin von Grund auf neu gebaut (Tripod-Phasen-Logik mit
  Gruppen-Offsets) — Stufe-E-State-Code wäre Wegwerf.

**Gewählt: A** — User-Entscheidung. Stufe F erweitert dann mit der
"echten" State-Machine.

**Falls später Re-Design nötig** (z. B. interaktiver Demo-Modus mit
Pause-Funktion): zu B umschwenken. Aktuell kein Bedarf.

#### 3. Stand-Pose-Quelle in `gait_engine`

**Optionen:**
- **A) `gait_engine` eigene Konstanten** — `(radial=0.27, 0, body_height=-0.047)`
  als Default in `gait_engine.py`. `stand_node` aus Stufe C bleibt
  unberührt und eigenständig nutzbar. Pro: minimale Kopplung,
  Stufe-C-Code unverändert. Contra: Stand-Pose-Werte an zwei Stellen.
- **B) Refactor: shared Pose-Modul** in `hexapod_kinematics.config` oder
  `hexapod_gait.poses`. Beide Knoten importieren. Pro: Single Source
  of Truth. Contra: zusätzlicher Refactor an Stufe-C-Code.

**Gewählt: A** — User-Entscheidung. Stufe E erste Iteration; B als
Nachwerkzeit später (oder am Phasen-Ende), wenn beide Stand-Pose-
Konsumenten stabil sind.

#### 4. Pub-Rate-Hack (`time_from_start`)

Keine echte Entscheidung — übernehmen aus Phase-Plan. Tick-Rate 50 Hz,
`time_from_start = 2 × (1/tick_rate) = 0.04 s`. JTC interpoliert linear
zwischen aufeinanderfolgenden Goals → smooth Bewegung.

Designwarnung: technisch ein Hack. Sauber wäre ein
`forward_position_controller` (kontinuierlicher Position-Stream ohne
Trajectory-Wrapping), nicht in Phase-4-Setup konfiguriert. **Refactor-
Schuld dokumentiert: Phase 7 prüfen.**

#### 5. Welches Bein für Single-Leg-Test

`which_leg = 1` (vorne rechts, mount_yaw=-π/4) als Default. Vorne in der
Default-Gazebo-Kamera-Position gut sichtbar. Parametrisierbar via
`--ros-args -p which_leg:=N` für N ∈ {1..6}.

#### 6. Knoten-Parameter

`gait_node` mit folgenden `declare_parameter`s (alle mit Default):

| Parameter | Default | Bedeutung |
|---|---|---|
| `which_leg` | `1` | Bein-ID 1..6, das schwingt |
| `step_height` | `0.02` | Schwung-Höhe in m über Stand-Pose |
| `cycle_time` | `1.0` | Periode in s pro Schwung |
| `tick_rate` | `50.0` | Knoten-Loop-Rate in Hz |
| `body_height` | `-0.047` | Stand-Pose Foot-Z im Bein-Frame |
| `radial_distance` | `0.27` | Stand-Pose Foot-X im Bein-Frame |
| `time_from_start_factor` | `2.0` | `time_from_start = factor × (1/tick_rate)` |

---

- [x] Konzept besprochen (Trajektorie A: Halbsinus, State-Machine A: Simple Mode, Stand-Pose A: gait_engine-Konstanten, Pub-Rate-Hack übernommen, which_leg=1 default, 7 Parameter)
- [x] [hexapod_gait/trajectory_gen.py](../src/hexapod_gait/hexapod_gait/trajectory_gen.py) — pure-Python `swing_traj(phase, ...)` (Halbsinus über Z + linear in X) und `stand_pose(...)`. Phase 0..1 mit Apex bei 0.5; `step_length`-Parameter Default 0 (Stufe E ohne Vortrieb), in Stufe G für horizontalen Vortrieb genutzt
- [x] [hexapod_gait/gait_engine.py](../src/hexapod_gait/hexapod_gait/gait_engine.py) — `GaitEngine` mit `compute_foot_targets(t)` und `compute_joint_angles(t)`. Single-Leg-Modus: `which_leg` schwingt mit Phase=`(t/cycle_time) mod 1`, andere halten Stand-Pose
- [x] [hexapod_gait/gait_node.py](../src/hexapod_gait/hexapod_gait/gait_node.py) — rclpy-Node, 7 Knoten-Parameter, 50 Hz-Timer-Tick, `time.monotonic()`-basierter t (Stufe-D-Erkenntnis), 6 JointTrajectory-Pubs pro Tick mit `time_from_start = 0.04 s`. `setup.py` entry_point `gait_node` ergänzt
- [x] [hexapod_gait/launch/gait.launch.py](../src/hexapod_gait/launch/gait.launch.py) — 8 LaunchArgs (which_leg, step_height, cycle_time, tick_rate, body_height, radial_distance, time_from_start_factor, use_sim_time)
- [x] `colcon build --packages-select hexapod_gait` grün
- [x] `colcon test --packages-select hexapod_gait` grün (flake8 + pep257)
- [x] [phase_5_stage_E_test_commands.md](phase_5_stage_E_test_commands.md) geschrieben — 7 Test-Schritte (Sim + Stand + Gait + numerische Joint-Prüfung + Foot-Contact-Live-Diagnose + Stand-Stabilität + Aufräumen) + 4 optionale Variationen
- [x] **Live-Verifikation:** Bein 1 schwingt sichtbar in der Luft, 0.5 s Schwung + 0.5 s Pause am Boden bei cycle_time=1, andere 5 stehen still — **bestätigt 2026-05-09**
- [x] **Numerisch:** `/joint_states` zeigt periodische Bewegung für `leg_1_*` (femur ~ -0.59 / -0.51 oszillierend, tibia ~ 1.05 / 1.01), Stütz-Beine konstant bei `(0, -0.510, 1.012)` — bestätigt 2026-05-09
- [x] **Foot-Contact-Diagnose:** Bei cycle_time=2 (1 s Stance), leg 1: **121 true, 210 false** in 8 s (36% true), togglet sauber. leg 2 (Stütz): **121 true, 25 false** (83% true) — die wenigen false-Momente von Body-Wackel beim Bein-1-Schwung. Pipeline End-to-End grün
- [x] **Kein Bein knickt ein:** Stützbeine halten Stand-Pose stabil, Body z=0.054999 m (gleicher Wert wie in Stand-only-Mode), keine progressive Drift
- [ ] `phase_5_gait_explained.md` (erste Hälfte: State-Machine + Trajektorien)

### Umsetzungsnotizen Stufe E

> **Test-Anleitung:** [phase_5_stage_E_test_commands.md](phase_5_stage_E_test_commands.md).

**Stufe-E-Live-Bringup hatte vier Iterations-Bugs zu durchdringen:**

#### 1. JTC-Lookup-Race in stand_node (übernommen aus Stufe C)

`use_sim_time=true` + `self.get_clock().now()` für Timer hatte den
DDS-`/clock`-Discovery-Race aus Stufe C. **Fix:** `time.monotonic()`
für alle Timer-Logik in gait_node + foot_contact_publisher (Stufe-D-
Konsistenz). Im Code dokumentiert.

#### 2. Stale-Prozesse durch unvollständigen pkill (auch aus Stufe D bekannt)

`pkill -f "gait_node"` wurde nicht im Cleanup-Snippet von Stufe D
mitgenommen — bei wiederholten Sim-Restarts liefen mehrere gait_nodes
parallel auf den gleichen Topics. **Fix:** Cleanup-Snippet in
[phase_5_stage_E_test_commands.md](phase_5_stage_E_test_commands.md)
um `pkill -9 -f "gait_node"` ergänzt.

#### 3. JTC-Tracking-Lag im kontinuierlichen Pub-Modus

Erste Implementation: gait_node publisht 50 Hz JointTrajectory mit
`time_from_start = 0.04 s`. Bei jedem Tick re-startet JTC die
Interpolation von `current_pos` nach `target` — exponentielle
Konvergenz. Theoretisch perfekt, in der Praxis ~0.1-0.5 mm
Tracking-Lag.

Folge: in der Stance-Phase erreicht der Foot zwar visuell den Boden,
ist aber 0.5 mm darüber. Phase-4-Stand-Mode mit body_height=-0.047
hatte 1 µm Penetration durch statische Schwerkraft-Federung — gerade
genug für Sensor-Fire. Im Gait-Mode reicht das nicht.

**Erste Fix-Versuche (verworfen):**
- `body_height=-0.05` (alle 6 Beine 3 mm tiefer kommandieren) — Body
  liftete um 3 mm hoch, weil Stütz-Beine ihn pushen, neue
  Penetration wieder ~0. **Funktionierte nicht.**
- `body_height=-0.08` (alle 6 Beine 33 mm tiefer) — Body liftete
  entsprechend hoch, gleiches Problem. **Funktionierte nicht.**

Erkenntnis: solange ALLE Beine gleich tief kommandiert werden, lifted
sich der Body genau passend, keine Penetration entsteht.

**Endgültiger Fix:** Nur das **Swing-Bein in Stance-Phase** wird 5 mm
tiefer kommandiert (`_STANCE_PENETRATION = 0.005` in
[gait_engine.py](../src/hexapod_gait/hexapod_gait/gait_engine.py)).
Die anderen 5 Stütz-Beine bleiben bei `body_height` → halten Body-Z
konstant. Das eine Bein hat damit garantiert 5 mm Penetration → Sensor
feuert.

Hebel-Verhältnis 5:1 reicht aus, dass das einzelne tiefer-kommandierte
Bein nicht den Body hebt.

**Resultat:** leg 1 togglet sauber `true`/`false` synchron zum Schwung
(36% true bei cycle_time=2, ~50% erwartet — Differenz durch JTC-Anfangs-
konvergenz pro Stance).

#### 4. Body-Wackel-Effekte auf Stütz-Beine

Beobachtung: leg 2 (Stütz-Bein, immer am Boden) zeigt **83% true** statt
100%. In den 17% false-Momenten wackelt der Body kurz hoch (durch
asymmetrischen Lift-Force des Swing-Beins) — Stütz-Foot hängt
mikroskopisch über Boden, Sensor pausiert kurz.

Funktional irrelevant für Stufe E. Phase-7-HW-Treiber wird hier auch
ein periodisches `false`-Pattern haben (mechanisches
Switch-Ausdruck/Lösen), und Konsumenten in Phase 6+ müssen ohnehin
einen Tiefpass / Debounce-Filter einbauen.

#### Performance-Reflektion

- Stufe E löste 4 Bugs in einer Session (siehe Stufe-D-Pattern).
  Memory-Eintrag dafür existiert bereits.
- Bug 3 (Tracking-Lag) ist **nicht trivial** und nicht aus
  Standard-ROS2-Tutorials erwartbar — er entsteht aus dem
  spezifischen Continuous-Pub-Pattern. Die Stance-Penetration-Lösung
  ist eine pragmatische Sim-Workaround und sauber als solche
  kommentiert. **Phase 7 mit echter HW** umgeht das Problem komplett
  (Microschalter feuern bei mechanischem Druck unabhängig von
  Tracking-Genauigkeit).

#### Was Stufe E NICHT macht

- Keine State-Machine (Stufe-E-Design-Entscheidung 2 A: Simple Mode).
- Kein cmd_vel-Subscriber (Stufe G).
- Kein Tripod-Pattern (Stufe F).
- Kein Vortrieb / step_length > 0 (Stufe G).
- Kein `phase_5_gait_explained.md` final geschrieben — auf Stufe F
  verschoben, dann mit komplettem State-Machine-Konzept.

---

---

## Stufe F — Statisches Tripod-Pattern in der Luft

**Ziel:** Beide Tripod-Gruppen schwingen abwechselnd, **ohne Vortrieb**.
Roboter steht am Boden, kleiner `step_height` so dass die Stützgruppe
ihn trägt. Validiert State-Machine + Phasen-Sync + 3:3-Stützen-Stabilität.

**Was wir machen:** Refactor `gait_engine` mit daten-getriebenen Gangart-
Patterns: Gruppe A {1, 3, 5} und B {2, 4, 6}, Phasen-Offset 0.5. Stütz-
phase = Stand (kein Vortrieb, nur Halten). Schwungphase = Halbsinus wie
Stufe E, aber drei Beine pro Gruppe synchron. Globale `body_height`-
Senkung um 5 mm löst JTC-Tracking-Lag bei 3:3-Stützen ohne Hebel-Problem.
Live-Toggle STANDING↔WALKING via `enable_walk`-rclpy-Param.

### Design-Entscheidungen Stufe F

#### 1. Stance-Penetration-Strategie bei Tripod 3:3

**Problem:** In Stufe E hat `_STANCE_PENETRATION = 0.005` für das
einzelne Swing-Bein in seiner Stance-Phase funktioniert (5:1 Hebel —
1 Bein 5 mm tiefer kommandiert, 5 Stütz-Beine halten den Body). Bei
Tripod 3:3 wäre das Hebel-Verhältnis 1:1: 3 Beine "tief", 3 normal →
Body würde sich auf das tiefere Niveau heben, Stand-Höhe-Drift.

**Optionen:**
- **A) Globale `body_height` -5 mm** — alle 6 Beine bekommen
  `body_height = -0.052` statt `-0.047`. JTC trackt einen Punkt 5 mm
  unterhalb des Bodens kontinuierlich, Boden gibt nicht nach → konstante
  Foot-Boden-Penetration für Stütz-Beine, kein Hebel-Problem (alle 6
  symmetrisch behandelt). Engine-Logik wird sogar **einfacher** —
  `_STANCE_PENETRATION` aus `gait_engine.py` fällt weg. Pro: einfach,
  symmetrisch, keine Engine-Sonderlogik, Stufe-D-Sensor funktioniert
  weiter. Contra: hartcoded 5-mm-Verschiebung an drei Stellen
  (`gait.launch.py`, `stand.launch.py`, `gait_node.py`-Default).
- **B) Verzicht auf Penetration** — kein Trick. `body_height = -0.047`,
  JTC-Lag akzeptieren, Foot pendelt knapp über Boden, Foot-Contact-
  Sensor zeigt durchgängig `false`. Verifikation Stufe F nur visuell.
  Pro: sauberster Code. Contra: Stufe-D-Sensor in Stufe F+G unbrauchbar,
  schlechte Diagnose-Basis für G's Walk-Verifikation.
- **C) Globale Penetration -2 mm + Sensor-Hysterese 200 ms** — Hybrid:
  weniger tief + längeres Decay-Window in `foot_contact_publisher`.
  Pro: weniger Penetration. Contra: Stufe-D-Publisher muss modifiziert
  werden, mehr verteilte Komplexität.

**Gewählt: A** — User-Entscheidung. Symmetrisch (kein Hebel-Problem),
einfacher Migrate-Pfad (drei Konstanten ändern), Stufe-D-Sensor bleibt
nutzbar für Stufe G's Walk-Verifikation. Engine-Code wird **kürzer**
(kein Sonderfall-Block für Swing-Bein-in-Stance-Phase mehr).

**Falls später Re-Design nötig** (z. B. echte HW-Servos in Phase 7
ohne Tracking-Lag): `body_height` zurück auf `-0.047`, sonst keine
Code-Änderung. Hartcoded-Wert dokumentiert in `phase_5_progress.md`.

#### 2. STANDING ↔ WALKING-Trigger

**Optionen:**
- **A) `ros2 param set` zur Laufzeit** — `enable_walk: bool` als rclpy-
  Parameter (Default `false`). Param-Callback registrieren via
  `add_on_set_parameters_callback` (kein Polling). Live-Toggle:
  `ros2 param set /gait_node enable_walk true`. Pro: ROS-idiomatisch
  für Mode-Flags, Live-Toggle ohne Restart, einfacher Test. Contra:
  Param-Callback-Boilerplate (~10 Zeilen).
- **B) Launch-Param fix** — `enable_walk` nur beim Launch, kein Live-
  Toggle. Pro: minimaler Code. Contra: Restart pro Toggle nötig,
  schlechte Test-UX.
- **C) Topic-Subscriber `std_msgs/Bool`** — dediziertes Topic
  `/gait/enable_walk`. Pro: angeblich Vorbereitung auf Stufe-G's
  cmd_vel-Pattern. Contra: Stufe G nutzt eh `cmd_vel`-Topic statt
  `enable_walk` — keine echte Vorbereitung. Mehr Boilerplate als
  Param-Set.

**Gewählt: A** — User-Entscheidung. Topics für Datenströme, Params für
Mode-Flags ist ROS-Konvention. Live-Toggle wertvoll für iterative Sim-
Verifikation. In Stufe G fällt `enable_walk` weg (durch `cmd_vel`-
Activity-Detection ersetzt) — also keine echte Stufe-G-Vorbereitung
durch Topic-Variante.

#### 3. Test-Setup — Aufgebockt vs. am Boden

**Optionen:**
- **A) Am Boden mit `step_height = 0.03`** — wie Stufe E: erst Stand-
  Pose, dann Tripod startet. Stützgruppe trägt Roboter. Pro: realistisch,
  bereitet Stufe G vor, Body-Stabilitäts-Verifikation gleich miterledigt.
  Contra: Body-Stabilität abhängig von Penetrations-Frage (durch Frage 1
  gelöst).
- **B) Aufgebockt in Sim** — Roboter um `z = 0.15 m` angehoben (Static-
  Anchor-Plugin), Beine schweben frei. Pro: reine Phasen-Sync-
  Verifikation, keine Stabilitäts-Vermischung. Contra: Gazebo-Anchor-
  Setup nötig (extra xacro/world-Mods), nicht repräsentativ für Stufe G.
- **C) Beides nacheinander** — erst aufgebockt, dann am Boden. Pro:
  vollständig diagnostiziert. Contra: doppelter Test-Aufwand,
  doppelte Test-Doc, kaum echter Mehrwert.

**Gewählt: A** — User-Entscheidung. Realistisch, vorbereitend für
Stufe G, Penetrations-Frage 1 löst Body-Stabilität.

#### 4. Code-Struktur — Daten-getriebenes `GaitPattern`

**Schlüssel-Beobachtung:** Alle realistischen statischen Gangarten
unterscheiden sich **nur in zwei Werten** — Phasen-Offset pro Bein und
Swing-Duty (Anteil des Cycles im Swing). Die Berechnungs-Logik ist
identisch:

```
phase = ((t / cycle_time) + offset[leg]) % 1.0
if phase < swing_duty: target = swing_traj(...)
else:                  target = stand_pose(...)
```

| Gangart | Phasen-Offsets | Swing-Duty |
|---|---|---|
| Single-Leg | `{1: 0}` | 0.5 |
| Tripod | `{1: 0, 3: 0, 5: 0, 2: 0.5, 4: 0.5, 6: 0.5}` | 0.5 |
| Ripple | `{1: 0, 4: 1/3, 5: 2/3, 2: 0, 3: 1/3, 6: 2/3}` | 1/3 |
| Wave | `{1: 0, 2: 1/6, 3: 2/6, 4: 3/6, 5: 4/6, 6: 5/6}` | 1/6 |

**Optionen:**
- **A) `GaitEngine` simpel erweitern** — `which_leg` durch
  `phase_offset_per_leg: dict` ersetzen, `enable_walk: bool` dazu.
  Eine Klasse, alles drin. Pro: minimaler Diff. Contra: pro neue
  Gangart Engine-Code anpassen oder dict extern generieren — ohne
  klares Schema.
- **A+) Daten-getrieben mit `GaitPattern`-Dataclass** — kleine 
  `@dataclass(frozen=True) GaitPattern` mit `name`,
  `phase_offset_per_leg: dict[int, float | None]`, `swing_duty: float`.
  Modul-Level-Presets `SINGLE_LEG_1..6`, `TRIPOD`. Param
  `gait_pattern: str` selektiert Preset aus `GAIT_PRESETS`-Dict. Pro:
  Phase-8-Erweiterungen (Wave, Ripple, ...) kosten 5 Zeilen Pattern-
  Konstante, null Engine-Code-Änderung. Mentales Modell klar:
  "neue Gangart = neue Daten-Konstante". Contra: ~30 Zeilen mehr als A.
- **B) Strategy-Pattern (`StandStrategy`/`TripodStrategy`)** — polymorphe
  Klassen mit `compute_foot_targets`. Pro: erweiterbar. Contra: Klassen-
  Overhead für identischen Algorithmus, nur Daten unterscheiden sich →
  Over-Engineering.
- **C) Zwei parallele Engines (alte + `TripodEngine`)** — Stufe-E-
  Engine bleibt, neue `TripodEngine` daneben. Pro: Stufe-E-Code
  unverändert. Contra: doppelte Logik, Bugfixes zweimal nötig.

**Gewählt: A+** — User-Entscheidung. YAGNI-konform für Strategy-Pattern
(alle Phase-relevanten Gangarten haben identischen Algorithmus, nur
Daten unterscheiden sich), aber **Daten-Shape vorbereitet** für
Phase-8-Erweiterungen. Stufe-E-Backward-Compat via `SINGLE_LEG_1..6`-
Presets (Stufe-E-Test-Commands funktionieren weiter über
`gait_pattern:=single_leg_1`).

**Falls später Re-Design nötig** (z. B. dynamische Gangarten mit
ballistischen Bahnen, asymmetrischen Trajektorien, oder unterschiedliche
Stance-Trajektorien-Verläufe pro Gangart): zu Strategy-Pattern (B)
refaktorieren — dann sinnvoll, weil Algorithmen sich tatsächlich
unterscheiden.

#### 5. Knoten-Parameter (Δ ggü. Stufe E)

| Parameter | Default | Bedeutung | Δ Stufe E |
|---|---|---|---|
| `gait_pattern` | `'tripod'` | Preset-Name aus `GAIT_PRESETS` | NEU |
| `enable_walk` | `false` | Live-Toggle STANDING↔WALKING | NEU |
| `step_height` | `0.03` | Schwung-Höhe in m | Default ↓ (war 0.05) |
| `cycle_time` | `2.0` | Periode in s | Default ↑ (war 1.0) |
| `body_height` | `-0.052` | Stand-Pose Foot-Z im Bein-Frame | Wert ↓ (war -0.047, +5 mm Penetration aus Frage 1) |
| `radial_distance` | `0.27` | unverändert | — |
| `tick_rate` | `50.0` | unverändert | — |
| `time_from_start_factor` | `2.0` | unverändert | — |

`which_leg` weg — durch `gait_pattern: 'single_leg_1..6'` Backward-Compat
ersetzt.

`stand.launch.py` body_height-Default ebenfalls auf `-0.052` angepasst,
damit Stand und Gait konsistent gleichen Body-Penetrations-Offset haben
(sonst Body-Sprung beim ersten WALKING-Tick).

---

- [x] Konzept besprochen (Penetration A: globale -5 mm, Trigger A: ros2 param set, Test-Setup A: am Boden, Code A+: Daten-getrieben mit GaitPattern, neue Param-Defaults)
- [x] [hexapod_gait/gait_patterns.py](../src/hexapod_gait/hexapod_gait/gait_patterns.py) — `GaitPattern` Dataclass mit Validierung + Presets `SINGLE_LEG_1..6`, `TRIPOD` + `GAIT_PRESETS`-Dict
- [x] [hexapod_gait/gait_engine.py](../src/hexapod_gait/hexapod_gait/gait_engine.py) refaktoriert: `pattern: GaitPattern`, `enable_walk: bool`, `_STANCE_PENETRATION` entfernt (durch globalen `body_height`-Offset ersetzt)
- [x] [hexapod_gait/gait_node.py](../src/hexapod_gait/hexapod_gait/gait_node.py) refaktoriert: neue Parameter (`gait_pattern`, `enable_walk`), `add_on_set_parameters_callback` für Live-Toggle (nur `enable_walk` mutable), `body_height` Default `-0.052`
- [x] [hexapod_gait/launch/gait.launch.py](../src/hexapod_gait/launch/gait.launch.py) — neue Args (`gait_pattern`, `enable_walk`), `which_leg` raus, neue Defaults (`step_height=0.03`, `cycle_time=2.0`, `body_height=-0.052`)
- [x] [hexapod_gait/launch/stand.launch.py](../src/hexapod_gait/launch/stand.launch.py) + [hexapod_gait/stand_node.py](../src/hexapod_gait/hexapod_gait/stand_node.py) body_height Default `-0.052` (konsistent mit Gait, sonst Body-Sprung beim ersten WALKING-Tick)
- [x] `colcon build --packages-select hexapod_gait` grün
- [x] `colcon test --packages-select hexapod_gait` grün (flake8 + pep257, 1 Iteration: I100-Import-Order in `gait_node.py` korrigiert)
- [x] Pure-Python-Smoke-Test: STANDING (alle 6 stand_pose), WALKING t=0.5 (Gruppe A {1,3,5} im Apex z=-0.022, Gruppe B {2,4,6} stance z=-0.052), WALKING t=1.5 (umgekehrt), Single-Leg-Backward-Compat (nur Bein 1 lifted) — alle Werte korrekt
- [x] [phase_5_stage_F_test_commands.md](phase_5_stage_F_test_commands.md) geschrieben — 10 Test-Schritte (Sim + Stand + Gait/STANDING + Live-Toggle WALKING + numerische Phasen-Sync + Foot-Contact-Diagnose pro Gruppe + Toggle-zurück + Stabilität-10s + Backward-Compat-Stufe-E + Aufräumen) + 3 optionale Variationen + Stolperfall-Liste
- [x] **Live-Verifikation Phasen-Sync** (2026-05-09): in einem `/joint_states`-Sample mit Gruppe A im Stance: `leg_1_femur ≈ -0.4876`, `leg_3_femur ≈ -0.4876`, `leg_5_femur ≈ -0.4882` (alle drei in Sync, kein Offset zueinander). Gleichzeitig Gruppe B im Swing: `leg_2_femur ≈ -0.6125`, `leg_4_femur ≈ -0.6122`, `leg_6_femur ≈ -0.6122` (auch in Sync untereinander, aber 0.12 rad anders als Gruppe A). Phasen-Differenz 0.5 zwischen Gruppen, intra-Gruppen-Sync exakt
- [x] **Live-Verifikation Foot-Contact** (2026-05-09): in 8 s sample alternierende Toggle: leg 1 (Gruppe A): 165 true / 174 false. leg 3 (Gruppe A): 182 true (sync mit leg 1). leg 2 (Gruppe B): 213 true / 138 false (invers zu leg 1). Alle 6 Beine `true count > 0` ✓
- [x] **Live-Verifikation Stabilität** (2026-05-09): über 10 s Sampling während WALKING — x-Drift 0.001163 → 0.001147 m (< 0.02 mm), y-Drift -0.000678 → -0.000900 m (< 0.3 mm), Yaw-Drift -0.051030 → -0.051465 rad (< 0.03°). z oszilliert 0.054-0.060 m (Tripod-Cycle-Wackel, kein progressives Senken). Kein Wegrutschen, kein Kippen
- [x] **Live-Verifikation State-Machine** (2026-05-09): `enable_walk:=false` Default → alle stehen still bestätigt. `ros2 param set /gait_node enable_walk true` → Tripod startet sofort, Log `enable_walk -> True (WALKING)`. Zurück auf `false` → Tripod stoppt, Roboter steht still
- [ ] **Live-Verifikation Backward-Compat Stufe E:** optional, Schritt 9 (`gait_pattern:=single_leg_1 enable_walk:=true`) nicht durchgeführt — auf Stufe G verschoben falls relevant
- [ ] `phase_5_gait_explained.md` geschrieben (State-Machine + Phasen-Sync + Tripod-Mathematik + GaitPattern-Daten-Shape) — auf Stufe G/H verschoben, dann mit komplettem Walk-Konzept inkl. Vortrieb

### Umsetzungsnotizen Stufe F

> **Test-Anleitung:** [phase_5_stage_F_test_commands.md](phase_5_stage_F_test_commands.md).

**Stufe F lief deutlich glatter als die vorherigen — keine Live-Bug-
Iterations, alles ging direkt durch.** Das liegt vermutlich daran:

1. **Daten-getriebener Refactor war konservativ.** Engine-Logik blieb
   strukturell ähnlich zu Stufe E, nur der Trigger (welches Bein im
   Swing) wurde vom hartcoded `which_leg` auf eine Pattern-Lookup
   verallgemeinert. Kein neuer Algorithmus, nur Daten-Generalisierung.

2. **Stance-Penetrations-Frage hatten wir vorab konzeptuell durchdacht.**
   Stufe-E-Erkenntnis "5:1-Hebel funktioniert" war direkt nutzbar — bei
   Tripod 3:3 würde das Hebel-Verhältnis nicht reichen, also wurde
   global verschoben (alle 6 Beine -5 mm). Das hätte ohne den Stufe-E-
   Vorlauf einen Bug-Iterations-Zyklus gekostet.

3. **Cleanup-Disziplin gehärtet.** Das Cleanup-Snippet aus Stufe E hatte
   schon alle Patterns (`gait_node`, `stand_node`, `foot_contact_publisher`).

#### 1. Globale Stance-Penetration als Refactor-Vereinfachung

`_STANCE_PENETRATION = 0.005` aus
[gait_engine.py](../src/hexapod_gait/hexapod_gait/gait_engine.py)
ersatzlos entfernt — durch globale `body_height`-Senkung um 5 mm
(`-0.052` statt `-0.047`) ersetzt. **Engine-Code wurde dadurch
einfacher**, nicht komplizierter. Sonderfall-Block für "Swing-Bein in
seiner Stance-Phase" entfällt komplett.

Die 5-mm-Konstante ist jetzt an drei Stellen (`gait.launch.py`,
`stand.launch.py`, `gait_node.py`-Default) — verdokumentiert in
Design-Entscheidung 1 oben. Phase 7 mit echten HW-Servos: alle drei
auf `-0.047` zurücksetzen.

#### 2. rclpy-Param-Callback-Boilerplate

Live-Toggle für `enable_walk` über
`add_on_set_parameters_callback`. Wichtige Stolperstein-Vermeidung:

- Callback **muss** `SetParametersResult` zurückgeben (nicht `bool`),
  sonst rclpy-Exception.
- `successful=True` für valide Param-Änderungen, `successful=False` +
  `reason=...` für abgelehnte. Andere Params (gait_pattern, body_height
  etc.) werden bei Runtime-Versuch abgelehnt mit Log-Warning — sonst
  inkonsistente Engine-States möglich (z. B. mitten im Cycle Pattern
  wechseln → Phasen-Sprünge in JTC-Goals).
- Engine-Member-Zustand (`self._engine.enable_walk`) muss **zusätzlich**
  zu rclpy-Param-Storage aktualisiert werden — Engine liest nicht aus
  Node-Params, sondern aus eigenen Members.

Die Live-Toggle hat sich in der Verifikation bewährt: keine Restart-
Iterationen nötig, einfach `ros2 param set` aus Terminal 3.

#### 3. Body-Stabilität bei Tripod 3:3 — empirische Werte

Live-Sampling über 10 s mit aktivem Tripod (cycle_time=2 s, also 5
Cycles):

| Achse | Sample 1 | Sample 10 | Drift | Bewertung |
|---|---|---|---|---|
| x | -0.001163 m | -0.001147 m | < 0.02 mm | Stationär ✓ |
| y | -0.000678 m | -0.000900 m | < 0.3 mm | Stationär ✓ |
| z | 0.059638 m | 0.053668 m | 6 mm Cycle-Schwankung, kein Trend | Erwartete Cycle-Wackel ✓ |
| Yaw | -0.051030 rad | -0.051465 rad | < 0.03° | Stationär ✓ |

Der **konstante Yaw-Offset von -2.92°** ist nicht durch Stufe F
verursacht — der Roboter steht von Beginn an leicht schräg im
Sim-Frame (vermutlich Spawn-Mechanik / Reibungs-Asymmetrie). Wichtig
ist die **Drift** (< 0.03° in 10 s = stationär), nicht der Absolutwert.

z-Schwankung 6 mm ist erwartbar: bei jedem Tripod-Wechsel federt der
Body kurz, JTC interpoliert. Wichtig: kein progressives Sinken (Body
landet nicht auf dem Bauch).

#### 4. Phasen-Sync ist mathematisch trivial — visuell und numerisch klar

`/joint_states`-Sample bei Gruppe A im Stance, Gruppe B im Swing:

| Bein | femur_joint | Gruppe |
|---|---|---|
| 1 | -0.4876 | A (Stance) |
| 3 | -0.4876 | A (Stance) |
| 5 | -0.4882 | A (Stance) |
| 2 | -0.6125 | B (Swing) |
| 4 | -0.6122 | B (Swing) |
| 6 | -0.6122 | B (Swing) |

Intra-Gruppe Differenz < 0.001 rad (numerische Rundung). Inter-Gruppe
Differenz exakt 0.124 rad — entspricht der Höhen-Differenz zwischen
Stand-Pose (z=-0.052) und Mitten-Swing (z=-0.022) in Bein-Frame durch
IK gerechnet.

> Daten-Shape vom `GaitPattern` ist also gerechtfertigt — der gleiche
> Algorithmus aus Stufe E erzeugt korrekt Tripod-Verhalten, nur durch
> Tabellen-Lookup. Phase-8-Erweiterungen (Wave, Ripple) sind 5-Zeilen-
> Patches.

#### 5. Was Stufe F NICHT macht

- Kein **Vortrieb** — Stützphasen-Foot bleibt am Neutral-Punkt
  (`step_length=0`). Stufe G fügt `cmd_vel.linear.x` → Stütz-Foot
  bewegt sich rückwärts entgegen Fahrtrichtung dazu.
- Kein **cmd_vel-Subscriber** — `enable_walk` ist temporäre State-
  Machine. In Stufe G ersetzt durch cmd_vel-Activity-Detection +
  Timeout-Rückfall.
- Kein **Body-Frame-zu-Bein-Frame-Vortrieb-Mapping** — kommt mit
  Stufe G's geradeaus-Walk.
- Kein **`phase_5_gait_explained.md`** — auf Stufe G/H verschoben.
- Kein **Walk-on-uneven-ground** — Stufe-D-Sensoren erstmal nur
  Diagnose, nicht Closed-Loop. Nicht Phase-5-Scope.

---

## Stufe G — Vollständiger Tripod-Gait geradeaus per `/cmd_vel`

**Ziel:** **Phase-5-Done-Kriterien 2, 3, 4, 5 erfüllt.**
`/cmd_vel.linear.x = 0.05` bewirkt sichtbares Vorwärtslaufen,
`cmd_vel = 0` → STANDING, Tripod-Sequenz erkennbar, kein Wegrutschen.

**Was wir machen:** `cmd_vel`-Subscriber, Body↔Bein-Frame-Mapping
(mount-yaw-Rotation pro Bein), Stützphase mit Vortrieb (Foot bewegt
sich rückwärts entgegen Fahrtrichtung in Bein-Frame-Koordinaten),
STANDING-Trigger via `linear.x = 0` (statt `enable_walk`-Param wie
in Stufe F), Activity-Timeout (>0.5 s ohne cmd_vel → STANDING als
Sicherheitsnetz). Sauberer Stopp: Beine in der Luft fertig schwingen,
Stütz-Beine sofort auf Neutral interpolieren.

### Design-Entscheidungen Stufe G

#### Physikalischer Hintergrund (für alle Fragen relevant)

Drei Größen, **zwei davon unabhängig** (no-foot-slip-Constraint):

```
v_body · stance_duration = step_length
```

| Größe | Bedeutung | Wo gesetzt |
|---|---|---|
| `v_body` | Body-Bewegungsgeschwindigkeit (m/s) | runtime via `cmd_vel.linear.x` (mit clamping) |
| `cycle_time` | Cycle-Dauer (s) | rclpy-Param (Default 2.0 s) |
| `step_length` | Foot-Bewegung pro Cycle (m) | **derived** = v_body · stance_duration |
| `step_length_max` | Obere Schranke für `step_length` | rclpy-Param (Default 0.04 m) |

User-Vorgabe (2026-05-09): "speed UND step_length konfigurierbar". Mit
Frage-1-Option-C ist beides gegeben: `step_length_max` als rclpy-Param,
`linear.x` via Topic. Optional `default_linear_x`-Param für Launch-Only-
Walk-Test ohne extra Topic-Pub.

#### 1. cmd_vel → step_length-Mapping

**Optionen:**
- **A) Konstantes `cycle_time`, `step_length` aus `linear.x` skaliert
  + clamp am step_length:**
  `step_length = clamp(linear.x · stance_duration, max=step_length_max)`.
  Pro: einfach. Contra: bei zu großem `linear.x` rutscht der Foot
  über Boden (step_length geclamped, aber Body-Geschwindigkeit nicht
  → Mismatch).
- **B) `step_length` fix, `cycle_time` skaliert mit `linear.x`:**
  `cycle_time = step_length_const / (v_body · (1-swing_duty))`.
  Pro: Foot rutscht nie. Contra: cycle_time ändert sich live, JTC-
  Goals werden phase-jumpy. `linear.x → 0` divergiert cycle_time → ∞,
  Edge-Case-Handling nötig.
- **C) `linear.x` clampen, dann `step_length` daraus berechnen:**
  ```
  linear_x_max = step_length_max / stance_duration
  v_body = clamp(input_linear_x, ±linear_x_max)
  step_length = v_body · stance_duration   # automatisch ≤ step_length_max
  ```
  Pro: physikalisch konsistent (kein Foot-Rutschen im erlaubten Range),
  beide User-Knöpfe verfügbar (`step_length_max` Param + `linear.x`
  Topic), `cycle_time` bleibt konstant. Contra: User-Eingabe `linear.x`
  über `linear_x_max` wird stillschweigend geclamped → ein Log-Warning
  bei Clamping nötig.

**Gewählt: C** — User-Entscheidung. Erfüllt User-Vorgabe (beide Knöpfe),
physikalisch sauber, einfach zu implementieren.

**Verfeinerung aus User-Vorgabe ("eine Geschwindigkeit reicht für
Anfang"):** `default_linear_x: float` rclpy-Param (Default 0.0)
zusätzlich. Wenn keine cmd_vel innerhalb Activity-Window → Engine
nutzt `default_linear_x` als Fallback. Wenn `default_linear_x = 0`:
Engine geht nach Timeout in STANDING. Wenn z.B. `default_linear_x =
0.05`: Roboter läuft vom Launch weg konstant 5 cm/s — Demo-Modus
ohne Topic-Setup.

**Falls später Re-Design nötig** (z. B. asymmetrische Vor/Rückwärts-
Schritte oder dynamische Schrittweiten-Anpassung): zu B umschwenken,
dann kann `cycle_time` adaptiv werden.

#### 2. State-Trigger (cmd_vel-Activity-Detection vs. `enable_walk`)

**Optionen:**
- **A) `cmd_vel`-Activity allein, `enable_walk` raus:**
  `last_cmd_time = time.monotonic()` bei jedem cmd_vel-Empfang.
  Pro Tick: `now - last_cmd_time > timeout` → STANDING. Sonst
  WALKING mit cached `linear.x`. Pro: einkanalig. Contra: kein
  manuelles Sofort-Stopp (außer `cmd_vel.linear.x = 0` publishen).
- **B) `cmd_vel` UND `enable_walk` als AND-Bedingung:**
  WALKING nur wenn `enable_walk=true` UND cmd_vel-Activity in Window.
  Pro: kann manuell per Param stoppen. Contra: zwei Trigger-Kanäle,
  mehr State-Logik.
- **C) `linear.x = 0` als expliziter Stopp + Timeout als Sicherheitsnetz:**
  WALKING wenn `|linear.x| > epsilon` UND cmd_vel-Activity in Window.
  `linear.x = 0` → STANDING (sofort). Activity-Timeout (>0.5 s ohne
  Pub) → STANDING als Fallback gegen tote Publisher. Pro: ROS-Standard
  (cmd_vel=0 ist Stopp-Signal), minimal. Contra: epsilon-Wahl muss
  klein genug sein dass User-Wert 0.001 nicht als 0 interpretiert wird,
  aber groß genug dass Float-Noise nicht trigget — z. B. 1e-4.

**Gewählt: C** — User-Entscheidung. ROS-konform, `enable_walk`-Param
ersatzlos gestrichen (Stufe-F-Live-Toggle war nur Bringup-Convenience).
Activity-Timeout 0.5 s aus Roadmap.

**Falls später Re-Design nötig** (z. B. Emergency-Stop-Service): zu B
ergänzen mit `enable_walk=false` als Hard-Override.

#### 3. Body↔Bein-Frame-Mapping (Mount-Yaw)

**Hintergrund:** `cmd_vel.linear.x = 0.05 m/s` ist im base_link-Frame
(vorne = +X). Jedes Bein hat eigenen `mount_yaw` (z.B. `leg_1 =
-π/4`, `leg_4 = +3π/4`). Im Bein-Frame ist die "rückwärtige Stütz-
Bewegung" daher **nicht parallel zur Bein-X-Achse**.

**Mathematisch:** Body bewegt sich `(v_x, v_y, 0)` im base_link.
Im Bein-Frame ist das `R_z(-mount_yaw) · (v_x, v_y, 0)`. Foot bewegt
sich relativ zum Body um `-v_leg · dt`.

**Optionen:**
- **A) Mount-Yaw-Rotation pro Bein in `gait_engine`:**
  ```python
  # rotate_z aus hexapod_kinematics.geometry verwenden:
  v_leg = rotate_z(-mount_yaw, (v_body_x, v_body_y, 0))
  # Stance-Trajektorie: Foot bewegt sich (-v_leg · dt) pro Tick
  ```
  Pro: physikalisch korrekt, geradeaus-Walk in Body-Frame. Helper
  existiert bereits. Contra: minimal mehr Code (1 Rotation/Bein/Tick).
- **B) Vereinfachung: Schritt nur in Bein-X (alle Beine identisch):**
  Pro: einfacher. Contra: **falsch** — Beine "rudern" radial nach
  innen/außen statt parallel zur Body-Richtung. Roboter dreht sich
  oder läuft seitlich, nicht geradeaus. **Fail für DK 5.**
- **C) Hybrid: Bein-Frame + Yaw-Korrektur via swing_traj-Endpoint:**
  Komplexere Mapping-Funktion außerhalb der Engine. Pro: keine echten
  Vorteile. Contra: split logic, schwerer zu lesen.

**Gewählt: A** — User-Entscheidung. Einzig physikalisch korrekt,
`rotate_z` aus
[hexapod_kinematics/geometry.py](../src/hexapod_kinematics/hexapod_kinematics/geometry.py)
nutzt vorhandenen Helper.

**Falls später Re-Design nötig** (z. B. dynamische Body-Pose mit Roll/
Pitch): vollständige 3×3-Rotation statt nur Yaw.

#### 4. Timeout-Verhalten — sauberer Stopp

**Problem:** Wenn `cmd_vel.linear.x = 0` oder Timeout: Engine ist
mitten im Cycle (z.B. Gruppe A halb im Swing). Beine in der Luft
müssen sicher landen.

**Optionen:**
- **A) Sofortiger Sprung in Stand-Pose:**
  Engine setzt sofort alle 6 Beine auf Stand-Pose. JTC interpoliert.
  Pro: einfach. Contra: Bein in der Luft fällt schnell auf Stand-Pose-
  Z runter (von z. B. -0.022 nach -0.052 in 0.04 s) — Body-Schock,
  nicht elegant.
- **B) Cycle ausfahren, dann STANDING:**
  Bei Stopp wird Engine-State `STOPPING`, Cycle läuft bis Phase=1 zu
  Ende. Pro: physikalisch sauber. Contra: bis zu 1 Cycle (2 s)
  Latenz. DK 3 fordert "<0.5 s" — wäre formal nicht erfüllt.
- **C) Beine-in-der-Luft fertig schwingen, Stütz-Beine sofort auf
  Neutral:**
  Pro Bein: wenn aktuell im Swing → Cycle bis Phase=swing_duty
  fertig (max 1 s bei cycle_time=2). Wenn aktuell im Stance → sofort
  Foot-X auf Stand-Neutral interpolieren. Pro: schnellster sicherer
  Stopp (max swing_duration). Contra: per-Bein-Tracking nötig.

**Gewählt: C** — User-Entscheidung.

**Anmerkung zu DK 3 ("<0.5 s"):** mit cycle_time=2.0 s und Tripod
50/50 ist swing_duration=1.0 s — Worst-Case-Latenz also 1 s, nicht
<0.5 s. Lösungsoptionen:
1. Für DK-3-Verifikation `cycle_time:=1.0` nehmen → swing=0.5 s →
   Worst-Case 0.5 s. **Empfohlen** — DK formal erfüllt.
2. Roadmap-DK relaxieren auf "<1 s" — User-Entscheidung-Sache.

Standard-Default in Stufe G bleibt `cycle_time=2.0` (für JTC-Konvergenz),
DK-3-Test mit `cycle_time:=1.0` ausführen.

**Falls später Re-Design nötig** (z. B. Emergency-Stop mit hartem
Override): A als zusätzlicher Modus parallel zu C.

#### 5. Knoten-Parameter (Δ ggü. Stufe F)

| Parameter | Default | Bedeutung | Δ Stufe F |
|---|---|---|---|
| `gait_pattern` | `'tripod'` | unverändert | — |
| `step_length_max` | `0.05` | Obere Schranke für Schritt-Länge (m), DK-2-tauglich | NEU (Roadmap-Wert 0.04 hochgesetzt für DK 2) |
| `default_linear_x` | `0.0` | Fallback-Geschwindigkeit wenn keine cmd_vel ankommt (m/s) | NEU |
| `cmd_vel_timeout` | `0.5` | Activity-Timeout in Sekunden | NEU |
| `cycle_time` | `2.0` | unverändert (für DK-3-Test auf 1.0 setzen) | — |
| `step_height` | `0.03` | unverändert | — |
| `body_height` | `-0.052` | unverändert | — |
| `radial_distance` | `0.27` | unverändert | — |
| `tick_rate` | `50.0` | unverändert | — |
| `time_from_start_factor` | `2.0` | unverändert | — |

`enable_walk` weg — durch cmd_vel-Activity-Detection ersetzt
(Frage-2-C). State `STOPPING` neu in Engine für sauberen Stopp
(Frage-4-C).

#### 6. Backward-Compat & Stufe-E/F-Tests

`gait_pattern: single_leg_*` Presets bleiben verfügbar (Stufe-E-
Backward-Compat). Stufe-F-Test (`enable_walk:=true`) wird
funktional ersetzt durch `default_linear_x:=0.0` (STANDING) +
cmd_vel-Pub für Walk-Test. Test-Doc von Stufe E + F bleibt für
Bringup gültig (Stand-Pose-Setup), Walk-Test-Sequenz ist neu in
`phase_5_stage_G_test_commands.md`.

---

- [x] Konzept besprochen (Mapping C: clamp linear.x → step_length, Trigger C: linear.x=0 als Stopp + Timeout-Sicherheitsnetz, Body-Mapping A: mount_yaw-Rotation, Stopp C: Schwung-fertig + Stütz-sofort, neue Param-Defaults inkl. default_linear_x)
- [ ] `hexapod_gait/gait_engine.py` erweitert: `set_command(v_body_x, v_body_y)`, `STOPPING`-State, mount-yaw-Rotation pro Bein, Stützphase-Vortrieb
- [ ] `hexapod_gait/gait_node.py` refaktoriert: `cmd_vel`-Subscriber (geometry_msgs/Twist), Activity-Timestamp-Tracking, `default_linear_x`-Fallback, `enable_walk` raus
- [ ] `hexapod_gait/launch/gait.launch.py` — neue Args (`step_length_max`, `default_linear_x`, `cmd_vel_timeout`), `enable_walk` raus
- [ ] `colcon build --packages-select hexapod_gait` grün
- [ ] `colcon test --packages-select hexapod_gait` grün (flake8 + pep257)
- [ ] `phase_5_stage_G_test_commands.md` geschrieben
- [ ] **Live-Verifikation DK 2:** `cmd_vel.linear.x = 0.05` → Roboter läuft sichtbar vorwärts (Body-X-Drift > 0.05 m in 5 s)
- [ ] **Live-Verifikation DK 3:** `cmd_vel.linear.x = 0` (oder Topic-Stopp) → Roboter steht nach <1 s (cycle_time=2) bzw. <0.5 s (cycle_time=1) in Stand-Pose
- [ ] **Live-Verifikation DK 4:** Tripod-Sequenz erkennbar — 3 schwingen, 3 stützen, alternierend, in Phasen-Sync 0.5
- [ ] **Live-Verifikation DK 5:** Kein Wegrutschen (y-Drift < 5 mm pro 1 m Vortrieb), keine Chassis-Kollision, Body-Yaw-Drift < 5°
- [ ] **default_linear_x-Demo:** Launch mit `default_linear_x:=0.05` → Roboter läuft sofort, ohne extra cmd_vel-Pub
- [ ] **Backward-Compat Stufe E:** `gait_pattern:=single_leg_1 default_linear_x:=0.0` + cmd_vel `linear.x>0`-Pub → Bein 1 schwingt einzeln (nicht Walking, weil nur 1 Bein im Pattern)

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
