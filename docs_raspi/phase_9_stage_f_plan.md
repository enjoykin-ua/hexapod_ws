# Phase 9 — Stufe F — Plan

> **Status:** Plan, noch nicht implementiert. **Code/YAML-Edits beginnen
> erst nach User-Freigabe** (CLAUDE.md §4).
>
> **Parent-Plan:** [`phase_9_hexapod_hardware.md`](phase_9_hexapod_hardware.md)
> Stufe F — URDF-Anpassung & `controllers.real.yaml` (Architektur-
> Entscheidung A: xacro-Conditional Sim ↔ HW).
>
> **Test-Anleitung:** wird nach Implementations-Freigabe finalisiert
> (`phase_9_stage_f_test_commands.md`).

---

## Ziel der Stufe

Den **Sim/HW-Switch** in der URDF und den dazugehörigen Controller-
Configs verdrahten, damit der gleiche Robot-Description-Stack mit
`use_sim:=true` weiterhin in Gazebo läuft (wie seit Phase 4) **und** mit
`use_sim:=false` das in Stage A–E gebaute `hexapod_hardware`-Plugin
verwendet.

Stufe F selbst startet **noch keinen** controller_manager mit dem HW-
Plugin — das macht Stage G (`real.launch.py`). Stage F beweist nur,
dass:
1. die URDF in beiden Modi xacro-evaluierbar ist (kein Syntax-Fehler,
   keine ungebundene Variable),
2. das Plugin im HW-Mode korrekt mit allen Hardware-Parametern aus dem
   URDF instanziierbar wäre,
3. eine `controllers.real.yaml` existiert, die zum HW-Plugin-Interface-
   Vertrag passt (nur `position`-State, kein `velocity`).

---

## Was Stufe F NICHT macht

- **Kein `real.launch.py`** — kommt in Stage G.
- **Kein laufender controller_manager** — Stage G.
- **Kein echter Servo2040-Anschluss** — Stage H.
- **Keine Plugin-Code-Änderungen.** Plugin bleibt 1:1 wie nach Stage E
  (außer einem evtl. State-Interface-Refactor falls Frage 1 das verlangt
  — siehe unten).
- **Kein gait/teleop-Refactor.** Die existierenden Sim-Pfade (Phase 4–6)
  müssen unberührt bleiben — Phase 9 baut den HW-Pfad NEBEN dem Sim-Pfad
  auf, ersetzt ihn nicht.

---

## Logik-Skizze

### F.1 URDF-Refactor in `hexapod.ros2_control.xacro`

Aktueller Zustand (post-Phase-4): hartkodiert auf `gz_ros2_control`,
state_interfaces sind `position` + `velocity`, am Ende ein `<gazebo>`-
Block der das gz_ros2_control-System-Plugin lädt mit
`controllers.yaml`.

Geplanter Zustand: gleiche Datei, drei xacro-Conditional-Bereiche.

```xml
<?xml version="1.0"?>
<robot xmlns:xacro="http://www.ros.org/wiki/xacro">

  <!-- Sim/HW-Switch (Stufe F). Default true = Gazebo (bestehender
       Sim-Pfad bleibt unverändert). false = Servo2040-Plugin. -->
  <xacro:arg name="use_sim" default="true"/>
  <xacro:property name="use_sim" value="$(arg use_sim)"/>

  <!-- Hardware-Parameter (nur für use_sim=false relevant). Per Default
       /dev/ttyACM0; Bench-Wechsel ohne URDF-Edit per Launch-Override
       (Stage G ruft xacro mit serial_port:=... auf). -->
  <xacro:arg name="serial_port" default="/dev/ttyACM0"/>
  <xacro:arg name="loopback_mode" default="false"/>

  <ros2_control name="HexapodSystem" type="system">
    <hardware>
      <xacro:if value="${use_sim}">
        <plugin>gz_ros2_control/GazeboSimSystem</plugin>
      </xacro:if>
      <xacro:unless value="${use_sim}">
        <plugin>hexapod_hardware/HexapodSystemHardware</plugin>
        <param name="serial_port">$(arg serial_port)</param>
        <param name="calibration_file">$(find hexapod_hardware)/config/servo_mapping.yaml</param>
        <param name="loopback_mode">$(arg loopback_mode)</param>
      </xacro:unless>
    </hardware>

    <xacro:macro name="joint_iface" params="name lower upper">
      <joint name="${name}">
        <command_interface name="position">
          <param name="min">${lower}</param>
          <param name="max">${upper}</param>
        </command_interface>
        <state_interface name="position"/>
        <!-- Velocity-State nur in Sim. Servo2040 liefert kein echtes
             Velocity-Feedback, das Plugin exportiert nur position. -->
        <xacro:if value="${use_sim}">
          <state_interface name="velocity"/>
        </xacro:if>
      </joint>
    </xacro:macro>

    <!-- 18 joint-Aufrufe wie bisher … -->
  </ros2_control>

  <!-- Gazebo-System-Plugin nur in Sim. In HW-Mode wird der Controller
       von ros2_control_node geladen (Stage G), nicht von Gazebo. -->
  <xacro:if value="${use_sim}">
    <gazebo>
      <plugin filename="gz_ros2_control-system"
              name="gz_ros2_control::GazeboSimROS2ControlPlugin">
        <parameters>$(find hexapod_control)/config/controllers.yaml</parameters>
      </plugin>
    </gazebo>
  </xacro:if>

</robot>
```

**Was auf Sim-Seite erhalten bleibt:** `xacro hexapod.urdf.xacro` ohne
Args = exakt der bisherige Sim-Output (Default `use_sim=true`,
`enable_foot_contact=true`). `sim.launch.py` braucht keine Änderung.

### F.2 `hexapod.urdf.xacro` — durchreichen der drei neuen Args

Damit `xacro hexapod.urdf.xacro use_sim:=false serial_port:=...` greift,
müssen die Top-Level-Argumente bekannt sein. Aktuell hat das Top-File
nur `enable_foot_contact`. Optionen:
- **A:** xacro-Args werden auch ohne explizite `<xacro:arg>`-Deklaration
  im Top-File durchgereicht (xacro 2-Verhalten). Dann reicht es, die
  `<xacro:arg>`s in `hexapod.ros2_control.xacro` zu deklarieren — das
  ist die Datei, die sie konsumiert.
- **B:** Sicherheitshalber auch im Top-File deklarieren, falls ein
  künftiges xacro-Update strikter wird.

**Mein Vorschlag:** A (minimal-invasiv), aber im Plan dokumentiert dass
B die fallback-sichere Variante ist.

### F.3 `controllers.real.yaml` (neu in `hexapod_control/config/`)

Kopie von `controllers.yaml` mit drei Diffs:

| Setting | sim.yaml | real.yaml | Begründung |
|---|---|---|---|
| `update_rate` | 100 Hz | 50 Hz | Plugin-Tickrate per Stage D.5/D.6-Design (50 Hz `SET_TARGETS`); 100 Hz würde den Servo2040-USB-Bus verdoppeln, kein operativer Mehrwert weil Servos selber nicht schneller PWM-updaten |
| `use_sim_time` | true | false | Wallclock am Pi/Desktop (Phase-6-Übergabe-Notiz in `PHASE.md`) |
| `state_interfaces` (per leg_X_controller) | `[position, velocity]` | `[position]` | Plugin exportiert nur position (Echo-State, kein Velocity-Feedback). `velocity` in der yaml + nicht-exportiert vom Plugin = JTC-Spawner-Failure |

**Keine Vel/Accel-Limit-Reduktion in der yaml** — die existing yaml hat
keine Vel/Accel-`constraints` drin. Das „drastisch reduziert"-Wording
in der Mutter-Plan-Doku trifft nicht zu, da die JTCs aktuell ohne Limits
laufen. Falls für HW-Bringup gewünscht, wäre das ein eigenes Feature
(`constraints` + per-joint Vel-/Accel-Limits) — separat besprechen.

### F.4 Doku-Updates

- `hexapod_description/README.md`: kurzer Hinweis zum xacro-Switch
  (`use_sim:=false` wechselt auf das hexapod_hardware-Plugin)
- `hexapod_control/README.md`: `controllers.real.yaml` erklären, Diff
  zur sim-yaml dokumentieren
- `hexapod_hardware/README.md`: schon Stage E-aktualisiert; Konzept-
  Sektion „Pluginlib-Registrierung" verweist auf URDF-`<param>`-Block,
  also passt es

---

## Tests / Verifikation

Stage F ist **kein C++-Code**, also keine neuen gtest-Cases. Stattdessen
folgende Verifikations-Schritte (alle in `phase_9_stage_f_test_commands.md`
am Ende detailliert):

| # | Test | Was geprüft wird |
|---|---|---|
| F-T1 | `colcon build --packages-up-to hexapod_bringup` grün | URDF-Refactor bricht keinen bestehenden Build |
| F-T2 | `xacro hexapod.urdf.xacro` (default = sim) liefert ein URDF, das **byte-identisch** zum Pre-Stage-F-Output ist (modulo strukturell-irrelevante Whitespace-Diffs) | Sim-Pfad bleibt regression-frei (Phase 4–6 unverändert) |
| F-T3 | `xacro hexapod.urdf.xacro use_sim:=false` produziert valides URDF-XML mit `hexapod_hardware/HexapodSystemHardware` als plugin und ohne `<gazebo>`-Block | HW-Pfad funktioniert auf URDF-Generation-Ebene |
| F-T4 | `xacro hexapod.urdf.xacro use_sim:=false loopback_mode:=true serial_port:=/dev/null` produziert URDF mit den überschriebenen `<param>`-Werten | Argument-Durchreiche durch hexapod.urdf.xacro klappt |
| F-T5 | Beide URDF-Outputs (T2, T3) durchlaufen `check_urdf` (von liburdfdom-tools) ohne Fehler | URDF-Schema-Validity |
| F-T6 | `controllers.real.yaml` ist valide YAML (`python3 -c "import yaml; yaml.safe_load(...)"`) | YAML-Syntax-Check |
| F-T7 | Bestehende `colcon test --packages-select hexapod_hardware` weiter 0 failures | Stage-A–E-Plugin-Tests bleiben grün (kein Regression durch `make_joint`-Helper falls dort Änderungen nötig — vermutlich nicht, weil Test-Helper bauen synthetische HardwareInfo unabhängig von URDF) |
| F-T8 | `ros2 launch hexapod_bringup sim.launch.py` startet sauber: Gazebo öffnet mit Hexapod-Modell, **RViz zeigt das Modell ohne Fehler-Marker**, alle 6 JTCs + JSB werden active, Roboter steht stabil im Stand-Pose (Phase 4 DK4-Verhalten) | Sim-Pfad URDF-Output regression-frei UND visuell-funktional regression-frei (Mesh-Pfade, tf2-Frames, joint_state_broadcaster, robot_state_publisher → RViz-Pipeline) |
| F-T9 | **Manueller Quick-Smoke** `ros2_control_node` mit der `use_sim:=false`-URDF + `controllers.real.yaml` + `loopback_mode:=true` startet → `ros2 control list_hardware_components` zeigt das Plugin als `active` | End-to-End Plug-Verdrahtung im Loopback (vorgezogenes Stage-G/H-Setup, hier nur als bestätigender Smoke) |
| F-T10 | **End-to-End Walking-Smoke (NEU, nach User-Rückfrage 2026-05-16):** sim.launch.py + `ros2 launch hexapod_gait gait.launch.py` + `ros2 launch hexapod_teleop joy_teleop.launch.py` + PS4-Controller — Roboter läuft mindestens 5 Sekunden mit erkennbarem Tripod-Gait vorwärts, dreht auf der Stelle, hebt/senkt Body-Höhe (L2/R2). Foot-Contact-Plot in `/leg_*/foot_contact` zeigt erwartetes Tripod-Pattern | Phase-4-bis-Phase-6 voll-funktional regression-frei. Begründung: bei dem URDF-Refactor-Umfang (xacro-Conditionals, neue `<xacro:arg>`s, velocity-state-Ausnahme) reicht ein "alle JTCs active"-Test nicht — wir wollen den vollen IK + Gait + Teleop-Pfad einmal durchlaufen sehen, sonst können subtile Regressions (z.B. JointState-Velocity-Konsumenten die wir nicht gegrep'd haben, oder ein subtle URDF-Diff der erst beim Walking sichtbar wird) bis zur Inbetriebnahme verborgen bleiben. |

**Was bewusst NICHT getestet wird in Stage F:**
- echte Servo2040-Anbindung (Stage H)
- volle `real.launch.py` mit Spawner-Skripten (Stage G)
- Joint-Trajectory durch JTC pumpen + Servos bewegen (Stage H)
- launch_testing-Suite (überzogen für die XML-Refactor-Frage; manueller
  Smoke F-T9 reicht für Sub-Stage-F)

---

## Progress-Checkliste (geht 1:1 in `phase_9_progress.md`)

Done-Vertrag — alle `[x]` = Stage fertig:

- [x] F.1 Vorab-User-Antworten zu den 5 offenen Fragen (siehe „User-Entscheidungen"-Tabelle oben, am 2026-05-16)
- [ ] F.2 `hexapod.ros2_control.xacro` refactored: drei xacro-Args (`use_sim`, `serial_port`, `loopback_mode`), `<xacro:if>`-Conditional um Plugin-Wahl, `<xacro:if>` um velocity-state_interface, `<xacro:if>` um `<gazebo>`-Block
- [ ] F.3 `hexapod.urdf.xacro` Top-Level zusätzlich um die drei neuen `<xacro:arg>`s erweitert (Variante B per F-Q2-Antwort)
- [ ] F.4 Neue Datei `hexapod_control/config/controllers.real.yaml` mit Diffs zu `controllers.yaml`: `update_rate=50`, `use_sim_time=false`, `state_interfaces=[position]` pro leg_X_controller; **Top-Comment mit `# TODO Phase 10: Vel/Accel-Limits aus Bench-Trajektorie ableiten`**
- [ ] F.5 `hexapod_control/CMakeLists.txt`: `controllers.real.yaml` zur `install(FILES ...)`-Liste ergänzt
- [ ] F.6 `colcon build` (alle betroffenen Pakete) grün, keine Warnings
- [ ] F.7 Test F-T2 (Sim-URDF byte-equal zum Pre-F-Output) — Snapshot vor Refactor + Diff nach Refactor
- [ ] F.8 Test F-T3 + F-T4 (HW-URDF strukturell korrekt, Args durchgereicht)
- [ ] F.9 Test F-T5 (`check_urdf` für beide Modes)
- [ ] F.10 Test F-T6 (yaml validate)
- [ ] F.11 Test F-T7 (hexapod_hardware-Tests weiter 0 failures)
- [ ] F.12 Test F-T8 (sim.launch.py + RViz + Roboter steht stabil — User-ausgeführt; verstärkt nach User-Rückfrage 2026-05-16)
- [ ] F.13 Test F-T9 (HW-Loopback-Smoke mit ros2_control_node — User-ausgeführt)
- [ ] F.13b Test F-T10 (End-to-End Walking-Smoke: sim + gait + teleop + PS4 → Tripod-Gait läuft 5 s — User-ausgeführt; NEU nach User-Rückfrage 2026-05-16)
- [ ] F.14 Kritischer Self-Review-Tabelle in `phase_9_progress.md`
- [ ] F.15 Eventuelle Post-Review-Fixes
- [ ] F.16 `phase_9_stage_f_test_commands.md` finalisiert
- [ ] F.17 README-Updates: `hexapod_description/README.md`, `hexapod_control/README.md` (siehe F.4 oben)
- [ ] F.18 progress.md: F-Sektion mit Bullets + Notizen + Post-Review-Tabelle + **Pendenz-Eintrag „Vel/Accel-Limits in real.yaml" für Phase 10** (per F-Q4-Antwort)
- [ ] F.19 Memory-Eintrag schreiben: Cross-Session-Reminder „In Phase 10: Vel/Accel-Limits in `controllers.real.yaml` aus Bench-Trajektorie ableiten" (per F-Q4-Antwort)

---

## User-Entscheidungen (2026-05-16)

| Frage | Antwort | Auswirkung |
|---|---|---|
| F-Q1 velocity-State-Mismatch | **A** — URDF + yaml conditional | `<state_interface name="velocity"/>` per `<xacro:if value="${use_sim}">`, `controllers.real.yaml` ohne velocity. Kein Plugin-Refactor. |
| F-Q2 Top-Level-Arg-Deklaration | **B (Korrektur)** — auch im Top-File deklarieren | Bestehende `enable_foot_contact`-Konvention konsistent fortführen. 3 zusätzliche `<xacro:arg>`-Zeilen in `hexapod.urdf.xacro`. Robust gegen xacro-Strikt-Mode-Updates, Include-Refactors, Diagnose-Sucharbeit. (Erste Empfehlung im Plan war A — beim Erklären der drei Failure-Modes für 6-Monate-Sicht ist die Empfehlung gekippt.) |
| F-Q3 HW-Param-Style | **A** — per xacro-Arg mit Default | `<param name="serial_port">$(arg serial_port)</param>` etc. USB-Port-Wechsel ohne URDF-Edit. |
| F-Q4 Vel/Accel-Limits jetzt? | **A** — jetzt nicht | Pendenz an drei Stellen festgehalten: (1) `controllers.real.yaml` Top-Comment `# TODO Phase 10: Vel/Accel-Limits aus Bench-Trajektorie ableiten`, (2) progress.md F-Sektion „verschoben", (3) Memory-Eintrag als Cross-Session-Reminder. |
| F-Q5 Stage-F-Smoke F-T9 | **A → B (revidiert 2026-05-16)** | Original-Antwort A („F-T9 jetzt schon, ein einzelner `ros2 run`-Aufruf reicht") basierte auf falscher Aufwands-Schätzung. Real: inline `-p robot_description:="$(xacro ...)"` bricht den rcl-arg-parser → Launch-File nötig → Launch-File deckt schon Stage-G-Done-Kriterium 1+2 ab. Doppel-Arbeit-Risiko. → **F-T9 nach Stage G verschoben**, Vorlage `/tmp/f_t9_smoke.launch.py` bleibt als Stage-G-Seed. Stage F endet nach CI-Tests + F-T8 + F-T10. |

---

## Was offen ist und User-Feedback braucht (vor Plan-Freigabe)

Bitte einmal kurz absegnen vor Implementations-Start:

### Frage 1 (zentral) — Wie lösen wir den `velocity`-State-Interface-Mismatch?

Sim hat `position` + `velocity` (Gazebo liefert echtes Velocity-Feedback).
HW-Plugin exportiert nur `position` (Echo-State; Servo2040 hat kein
Velocity-Feedback).

- **A (mein Vorschlag): URDF + yaml conditional.** `<state_interface name="velocity"/>` per `<xacro:if value="${use_sim}">` weglassen für HW. `controllers.real.yaml` listet `state_interfaces: [position]`. Sauber, kein Plugin-Refactor nötig, kein „lying about velocity".
- B: Plugin exportiert dummy velocity = 0. URDF + yaml bleiben unverändert. Vorteil: kleinerer URDF/yaml-Diff. Nachteil: Plugin lügt subtile (velocity wäre konstant 0, was downstream zu Verwirrung führen kann; Tests müssten dummy-velocity mitprüfen).
- C: URDF + yaml conditional UND obendrein gait/teleop-Code prüft Verfügbarkeit von velocity. Aber: keine downstream-Konsumenten gefunden (`grep` über kinematics/gait/teleop liefert keine velocity-Subscriber). Damit fällt der downstream-Aspekt weg → C ≈ A.

Stand jetzt grep-bestätigt: kein gait/teleop-Code abhängig von velocity-Feld.

### Frage 2 — `hexapod.urdf.xacro` Top-Level — neue `<xacro:arg>` deklarieren oder durchreichen lassen?

- **A (mein Vorschlag): nur in `hexapod.ros2_control.xacro` deklarieren.** xacro 2-Verhalten reicht Args durch. Minimaler Diff im Top-File.
- B: Sicherheitshalber auch in `hexapod.urdf.xacro` als `<xacro:arg>` deklarieren. Ein paar Zeilen mehr Diff, aber zukunftssicher gegen striktere xacro-Versionen.

### Frage 3 — Hardware-Parameter (`serial_port`, `loopback_mode`): per `<xacro:arg>` oder hartkodiert im URDF?

- **A (mein Vorschlag): per `<xacro:arg>` mit Defaults.** USB-Port-Wechsel + Loopback-Toggle ohne URDF-Edit, einfach `xacro ... serial_port:=/dev/ttyACM1 loopback_mode:=true`. Stage G kann diese Args dann sauber als Launch-Argument exposeen.
- B: Hardcoded `<param name="serial_port">/dev/ttyACM0</param>`. URDF ist „single source of truth", Wechsel = Edit. Striktere Architektur, aber unhandlich für Bench-Szenarien.

### Frage 4 — Vel/Accel-Limits in `controllers.real.yaml`: jetzt schon einbauen oder später?

Mutter-Plan-Doku spricht von „drastisch reduzierten Limits (~30 % der
Sim-Werte)". Aber: existing `controllers.yaml` hat keine Vel/Accel-
Limits drin. Optionen:

- **A (mein Vorschlag): jetzt nicht.** controllers.yaml ist limit-frei,
  also auch real.yaml limit-frei. Limits einführen = neuer Konfig-
  Parameter über alle 6 leg_X_controller mit unklarem Wert (was sind
  „Sim-Werte" wenn keine drinstehen?). Das gehört in eine separate
  Bench-Tuning-Phase (Phase 10) wenn man echte Trajektorien hat.
- B: Konservative Limits jetzt schon einbauen (z.B. `max_velocity: 1.0
  rad/s` pro Joint), damit der erste HW-Versuch in Stage H sicherer ist.
  Wert bleibt arbiträr ohne Bench-Daten.

### Frage 5 — Stage-F-Smoke F-T9: jetzt schon oder erst Stage G?

F-T9 startet `ros2_control_node` mit der HW-URDF + real.yaml +
loopback_mode=true und checkt `ros2 control list_hardware_components`.
Das ist ein vorgezogener Stage-G-Smoke.

- **A (mein Vorschlag): jetzt schon machen.** Vorteil: Stage F endet mit
  einem belastbaren End-to-End-Beweis dass die Verdrahtung wirklich
  passt, nicht nur „URDF parsed sauber". Aufwand minimal: ein einzelner
  `ros2 run controller_manager ros2_control_node`-Aufruf manuell.
- B: erst in Stage G mit voll-launchen. Dann ist Stage F ausschließlich
  „URDF parsed + yaml valid", was schwächer ist als gewünscht.

---

## Reihenfolge nach Plan-Freigabe

1. ☐ User reviewt Plan + 5 Fragen → Antworten
2. ☐ Bei Bedarf Plan anpassen
3. ☐ Snapshot des aktuellen Sim-URDF-Outputs (für T2-Diff)
4. ☐ `hexapod.ros2_control.xacro` refactored
5. ☐ (Frage 2 = B) `hexapod.urdf.xacro` Top-Level erweitert
6. ☐ `controllers.real.yaml` neu
7. ☐ `hexapod_control/CMakeLists.txt` install-Liste erweitert
8. ☐ `colcon build` grün
9. ☐ Tests F-T1 bis F-T9 grün
10. ☐ Kritischer Self-Review (Pflicht CLAUDE.md §4)
11. ☐ Doku-Updates (3 READMEs)
12. ☐ Fertig-Meldung für User-Commit

Mit Stage F ist der **URDF-Sim/HW-Switch produktiv verdrahtet**.
Danach Stage G (`real.launch.py` zusammen mit Spawner-Skripten), dann
Stage H (echte Servo2040-Anbindung mit Oszi-Verifikation).

---

## Plan-Korrekturen während Implementation (2026-05-16)

Vier Abweichungen vom Vorab-Plan, alle dokumentiert:

1. **Test-Erweiterung F-T8 + neuer F-T10 nach User-Rückfrage.** Der
   Plan hatte F-T8 ursprünglich als „sim.launch.py startet, alle 6 JTCs
   active" formuliert. Auf User-Frage „macht es Sinn am Ende auch zu
   schauen ob die Simulation in Gazebo und RViz immer noch startet und
   der Roboter immer noch laufen kann" wurden zwei Tests verstärkt:
   - **F-T8 verstärkt:** zusätzlich „Gazebo-Modell sichtbar + RViz ohne
     Fehler-Marker + Stand-Pose stabil" (drei Verifikations-Punkte
     statt einem)
   - **F-T10 NEU:** End-to-End Walking-Test (sim + gait + teleop + PS4 →
     Tripod-Gait läuft 5 s, drehen, Body-Höhe). Begründung: bei diesem
     URDF-Refactor-Umfang reicht „Build grün + URDF parsed sauber"
     nicht — subtile Mesh-Pfad-/tf2-/Velocity-Konsumenten-Bugs zeigen
     sich erst beim Walking. Konvention für künftige
     URDF-/Description-Refactors: Memory-Eintrag siehe progress.md.

2. **`<ros2_control name="...">` weiter `GazeboSimSystem` (nicht
   umbenannt auf `HexapodSystem`).** Mutter-Plan-Doku
   `phase_9_hexapod_hardware.md` Z.36 zeigt `name="HexapodSystem"` als
   semantisch sauberer Wert nach Stage F (System ist nicht mehr
   Gazebo-only). Behalten habe ich `GazeboSimSystem` aus zwei Gründen:
   (a) F-T2-Byte-Equal-Ziel hätte sich gebrochen (Sim-URDF-Output
   unterscheidet sich um eine Attribut-Zeile), (b) der `name`-Attribut
   ist nur ein Logging-Tag in `ros2 control list_hardware_components`,
   kein funktional aktiver Lookup-Schlüssel. Renaming ist offener Punkt
   für Stage J (Phase-9-Final-Review).

3. **F.5 (CMakeLists.txt-Edit) nicht nötig.** Plan ging von einer
   `install(FILES ...)`-Liste in `hexapod_control/CMakeLists.txt` aus,
   die um `controllers.real.yaml` erweitert werden müsste. Das Paket
   benutzt aber `install(DIRECTORY config DESTINATION ...)` — neue
   yaml-Dateien werden ohne CMake-Edit automatisch mitinstalliert.
   F.5 → kein Code-Diff, nur Doku-Vermerk.

4. **F-T2-„byte-identisch"-Ziel präzisiert.** Plan hatte „byte-identisch
   zum Pre-Stage-F-Output (modulo strukturell-irrelevante Whitespace-
   Diffs)". Real-Output zeigt zusätzlich **3 XML-Kommentar-Diffs**
   (erweiterte Doku im ros2_control-Header + Gazebo-Block-Kommentar +
   Limits-Kommentar). Strukturell (nach Comment-Stripping +
   Whitespace-Normalize) ist die Gleichheit bestätigt — was die
   eigentliche Aussage des Tests ist. Plan-Kriterium informell um
   „Comment-Diffs sind OK solange semantisch keine Änderung" erweitert.

5. **F-T9 nach Stage G verschoben (F-Q5-Antwort revidiert).** Ursprüngliche
   F-Q5-Antwort A ging davon aus dass F-T9 mit „einem einzelnen
   `ros2 run controller_manager ros2_control_node`-Aufruf manuell"
   gemacht werden kann. Real beim Durchführen: `-p robot_description:="$(xacro ...)"`
   bricht den rcl-arg-parser (`Couldn't parse parameter override rule`),
   weil das xacro-Output `=`, `<`, `>` und Newlines enthält. Saubere
   Lösung verlangt eine Launch-Datei mit `Command(['xacro ', ...])` +
   `ParameterValue` — und genau diese Launch-Datei mit RSP +
   ros2_control_node + JSB-Spawner + 6 leg-Spawner ist **Stage-G-
   Deliverable Done-Kriterium 1+2** laut Mutter-Plan-Doku
   `phase_9_hexapod_hardware.md`. Ein Wegwerf-Launch in `/tmp/` zu
   schreiben + danach in Stage G denselben Inhalt nochmal final =
   Doppel-Arbeit ohne Gewinn.

   **Vorlage** `/tmp/f_t9_smoke.launch.py` bleibt als Stage-G-Seed
   bestehen (RSP + ros2_control_node + Spawner-Chain mit OnProcessExit).
   Stage G fügt hinzu: (a) Launch-Args (`loopback_mode:=true|false`,
   `serial_port:=...`), (b) finalen Ort
   `hexapod_bringup/launch/real.launch.py`, (c) README-Doku-Block.
   Stage F endet inhaltlich nach den CI-Tests F-T1–F-T7 + den
   User-Smokes F-T8 (Sim+RViz+Stand) + F-T10 (End-to-End Walking).
   Lesson: bei Aufwands-Schätzungen für „einzelner CLI-Aufruf reicht"-
   Tests prüfen, ob das in der Praxis ein Launch-File braucht — wenn
   ja, ist der Test wahrscheinlich schon Stage-N+1-Substanz.
