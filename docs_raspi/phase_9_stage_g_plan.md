# Phase 9 — Stufe G — Plan

> **Status:** Plan, noch nicht implementiert. **Code/Doku-Edits beginnen
> erst nach User-Freigabe** (CLAUDE.md §4).
>
> **Parent-Plan:** [`phase_9_hexapod_hardware.md`](phase_9_hexapod_hardware.md)
> Stufe G — `real.launch.py` (HW-Pfad-Bringup, Pendant zu Phase-4
> `sim.launch.py`).
>
> **Test-Anleitung:** wird nach Implementations-Freigabe finalisiert
> (`phase_9_stage_g_test_commands.md`).

---

## Ziel der Stufe

Den **HW-Pfad-Bringup** als Launch-File aufbauen, sodass ein einziger
Befehl (`ros2 launch hexapod_bringup real.launch.py …`) den vollen
ros2_control-Stack ohne Gazebo startet:

- `robot_state_publisher` mit dem HW-URDF (`use_sim:=false`)
- `ros2_control_node` (controller_manager) mit `controllers.real.yaml`
  und dem geladenen `hexapod_hardware`-Plugin
- `joint_state_broadcaster` + 6× `leg_<n>_controller` via Spawner-Chain
  (OnProcessExit-Pattern, analog `sim.launch.py`)

**Zwei Modi via Launch-Args:**
- `loopback_mode:=true` — Plugin öffnet keinen seriellen Port (CI-/Dry-Run-
  Modus, vorgezogen aus Stage F's verschobenem F-T9-Smoke)
- `loopback_mode:=false` (Default) — Plugin öffnet `serial_port`
  (`/dev/ttyACM0` Default), echte Servo2040-Kommunikation

Stage G beweist die **Bringup-Verdrahtung** im Loopback-Modus
(G-T1-Smoke, der direkte Nachfolger des verschobenen F-T9). Die echte
Servo2040-Anbindung — auch ohne echte Hexapod-Servos, nur Servo2040
am USB — ist Stage H.

---

## Was Stufe G NICHT macht

- **Kein echter Servo2040-Anschluss** (Stage H bringt das, plus PWM-
  Verifikation am Output-Pin mit Oszi/Logic-Analyzer)
- **Kein gait + teleop im real.launch.py** — Konsistenz zu `sim.launch.py`,
  das beides auch nicht inline startet. Modulare Bringup-Topologie
  (gait/teleop separat) bleibt erhalten
- **Kein RViz im real.launch.py** — beim echten Roboter steht das physische
  Modell vor einem; RViz-Visualisierung ist optional und kann separat
  via `rviz2 -d view.rviz` gestartet werden falls gewünscht
- **Keine URDF-Switch-Logik** — die ist Stage F (xacro-`<xacro:if>`)
- **Kein Plugin-Code-Change** — das Plugin ist nach Stage E + F unverändert

---

## Logik-Skizze

### G.1 `hexapod_bringup/launch/real.launch.py`

Vorlage: `/tmp/f_t9_smoke.launch.py` aus Stage-F-Verschiebung (siehe
`phase_9_stage_f_plan.md` Plan-Korrektur Punkt 5). Ergänzungen vs.
Vorlage:

- `DeclareLaunchArgument('loopback_mode', default_value='false')`
- `DeclareLaunchArgument('serial_port', default_value='/dev/ttyACM0')`
- `LaunchConfiguration('loopback_mode')` und `LaunchConfiguration('serial_port')`
  in den `Command(['xacro ', xacro_path, ' loopback_mode:=', LaunchConfiguration(...), …])`-
  Aufruf einsetzen, damit der xacro-Output je nach Launch-Arg-Wert das
  HW-Plugin mit dem richtigen `<param>`-Block produziert
- File-Top-Doku-Block analog `sim.launch.py` (was tut die Datei,
  Architektur-Notiz, OnProcessExit-Begründung)

```python
# Skizze (final-Kompletter Code dann in Implementation):
def generate_launch_description() -> LaunchDescription:
    pkg_desc = FindPackageShare('hexapod_description')
    pkg_ctrl = FindPackageShare('hexapod_control')
    xacro_path = PathJoinSubstitution([pkg_desc, 'urdf', 'hexapod.urdf.xacro'])
    real_yaml = PathJoinSubstitution([pkg_ctrl, 'config', 'controllers.real.yaml'])

    declare_loopback = DeclareLaunchArgument(
        'loopback_mode', default_value='false',
        description='true: Plugin öffnet keinen seriellen Port (CI/Dry-Run). '
                    'false (default): echte Servo2040-Anbindung über serial_port.')
    declare_port = DeclareLaunchArgument(
        'serial_port', default_value='/dev/ttyACM0',
        description='USB-CDC-Device der Servo2040. Nur relevant wenn loopback_mode=false.')

    robot_description = {
        'robot_description': ParameterValue(
            Command([
                'xacro ', xacro_path,
                ' use_sim:=false',
                ' loopback_mode:=', LaunchConfiguration('loopback_mode'),
                ' serial_port:=', LaunchConfiguration('serial_port'),
            ]),
            value_type=str,
        ),
        'use_sim_time': False,
    }

    rsp = Node(package='robot_state_publisher', executable='robot_state_publisher',
               name='robot_state_publisher', output='screen',
               parameters=[robot_description])
    cm = Node(package='controller_manager', executable='ros2_control_node',
              name='controller_manager', output='screen',
              parameters=[robot_description, real_yaml])

    spawn_jsb = Node(package='controller_manager', executable='spawner',
                     name='spawn_joint_state_broadcaster',
                     arguments=['joint_state_broadcaster',
                                '--controller-manager', '/controller_manager'],
                     output='screen')

    leg_spawners = [
        Node(package='controller_manager', executable='spawner',
             name=f'spawn_leg_{i}_controller',
             arguments=[f'leg_{i}_controller',
                        '--controller-manager', '/controller_manager'],
             output='screen')
        for i in range(1, 7)
    ]

    return LaunchDescription([
        declare_loopback, declare_port,
        rsp, cm, spawn_jsb,
        RegisterEventHandler(event_handler=OnProcessExit(
            target_action=spawn_jsb, on_exit=leg_spawners)),
    ])
```

### G.2 `hexapod_bringup/package.xml` — `<exec_depend>hexapod_hardware</exec_depend>`

Der Launch lädt das HW-Plugin via pluginlib. Damit `colcon build` das
Paket korrekt einreiht (`hexapod_hardware` muss vor `hexapod_bringup`
gebaut sein) und damit `ros2 launch` zur Laufzeit die `.so` findet:
`<exec_depend>hexapod_hardware</exec_depend>` ergänzen.

### G.3 `hexapod_bringup/CMakeLists.txt` — kein Edit nötig

`install(DIRECTORY launch config DESTINATION ...)` installiert
`real.launch.py` automatisch. Analog Stage F's F.5.

### G.4 `hexapod_bringup/README.md` — Aufruf-Doku

Neuer Abschnitt mit:
- Aufruf-Beispielen für Loopback (CI / Bringup-Dry-Run) und HW-Mode
  (echte Servo2040)
- Tabelle der Launch-Args mit Defaults und Auswirkungen
- Hinweis auf Sim-Pendant `sim.launch.py`
- Hinweis auf `ros2 control list_*`-Verifikations-Befehle

---

## Tests / Verifikation

| # | Test | Was geprüft wird |
|---|---|---|
| G-T1 | `colcon build --packages-up-to hexapod_bringup` grün, keine Warnings | Paket-Reihenfolge stimmt (hexapod_hardware vor hexapod_bringup), launch-File installiert |
| G-T2 | `ros2 launch hexapod_bringup real.launch.py --print-description` (oder `--show-args`) | Launch-Syntax valide, Args sichtbar — fängt Tippfehler in den `DeclareLaunchArgument`-Aufrufen frühzeitig |
| G-T3 | `xacro hexapod.urdf.xacro use_sim:=false loopback_mode:=true serial_port:=/dev/null` strukturell korrekt | Sicherstellung dass die LaunchArg→xacro-Substitution korrekt aufgelöst wird (das ist genau Stage F's F-T4 erweitert um den serial_port-Override) |
| G-T4 | **Vorgezogenes-F-T9-Äquivalent**, jetzt G-T4: `ros2 launch hexapod_bringup real.launch.py loopback_mode:=true` startet sauber → `ros2 control list_hardware_components` zeigt Plugin als `active`, `ros2 control list_controllers` zeigt 1× JSB + 6× JTC alle `active`. Kein `[ERROR]`/`[FATAL]` im Log | End-to-End-Bringup-Verdrahtung im Loopback-Modus. **Stage-G-Hauptbeweis.** |
| G-T5 | Override-Smoke: `ros2 launch ... loopback_mode:=true serial_port:=/dev/null` startet auch sauber (Plugin sieht `/dev/null` als Param-Wert, öffnet aber wegen loopback nichts) | Args werden sauber durchgereicht |
| G-T6 | Bestehende Stage-A–F-Tests (208 hexapod_hardware-Tests) weiter 0 failures | Keine Regression durch die Bringup-Änderungen |
| G-T7 | **Sim-Regression-Smoke (analog F-T8):** `ros2 launch hexapod_bringup sim.launch.py` läuft weiter wie gehabt — der bestehende Sim-Pfad darf NICHT durch Stage-G-Änderungen broken werden | hexapod_bringup hat jetzt zwei Launch-Files; Stage G berührt nur den neuen, aber paket-weit sollte nichts zerbrechen |
| G-T8 | **Sim-Walking-Regression-Smoke (analog F-T10):** sim + gait + teleop + PS4 → Tripod-Gait läuft. Per Memory-Konvention `feedback_urdf_refactor_full_smoke.md` — auch wenn Stage G nicht direkt URDF anfasst, ist es eine Bringup-Änderung am gleichen Paket | Sim-Pfad voll funktional regression-frei |

**Was bewusst NICHT getestet wird in Stage G:**
- echter Servo2040-Anschluss + PWM am Output-Pin (Stage H)
- Trajectory-Publishen + JTC-Reaktion testen (Stage H/I — braucht echten oder Sim-Stack hinter dem Plugin)
- gait/teleop integriert in real.launch.py (bewusst modular gehalten, siehe „Was Stufe G NICHT macht")

---

## Progress-Checkliste (geht 1:1 in `phase_9_progress.md`)

Done-Vertrag — alle `[x]` = Stage fertig:

- [x] G.1 Vorab-User-Antworten zu den 4 offenen Fragen (siehe „User-Entscheidungen"-Tabelle oben, am 2026-05-16; alle 4 Antworten = A)
- [ ] G.2 `hexapod_bringup/launch/real.launch.py` neu (basierend auf `/tmp/f_t9_smoke.launch.py`-Vorlage), mit `DeclareLaunchArgument` für `loopback_mode` + `serial_port`, xacro-Args über `LaunchConfiguration` durchgereicht
- [ ] G.3 `hexapod_bringup/package.xml`: `<exec_depend>hexapod_hardware</exec_depend>` ergänzt
- [ ] G.4 `hexapod_bringup/README.md`: neuer „Real-Hardware-Bringup (Stufe G)"-Abschnitt mit Aufruf-Beispielen, Args-Tabelle, Verifikations-Befehlen
- [ ] G.5 `colcon build` (alle betroffenen Pakete) grün, keine Warnings
- [ ] G.6 Test G-T2 (`--show-args` zeigt loopback_mode + serial_port mit korrekten Defaults)
- [ ] G.7 Test G-T3 (xacro-Args via LaunchArgs durchgereicht — strukturell korrekt)
- [ ] G.8 Test G-T4 (Loopback-Bringup-Smoke: `list_hardware_components` zeigt active, `list_controllers` zeigt 7 active — User-ausgeführt)
- [ ] G.9 Test G-T5 (Args-Override-Smoke `serial_port:=/dev/null` — User-ausgeführt zusammen mit G-T4)
- [ ] G.10 Test G-T6 (hexapod_hardware-Tests weiter 0 failures)
- [ ] G.11 Test G-T7 (sim.launch.py-Regression-Smoke — User-ausgeführt)
- [ ] G.12 Test G-T8 (Sim-Walking-Regression — User-ausgeführt mit gait + teleop + PS4)
- [ ] G.13 Kritischer Self-Review-Tabelle in `phase_9_progress.md`
- [ ] G.14 Eventuelle Post-Review-Fixes
- [ ] G.15 `phase_9_stage_g_test_commands.md` finalisiert
- [ ] G.16 README-Updates: `hexapod_bringup/README.md` (siehe G.4) + `hexapod_hardware/README.md` Status-Zeile (Stufe G ✅)
- [ ] G.17 progress.md: G-Sektion mit Bullets + Notizen + Post-Review-Tabelle
- [ ] G.18 `/tmp/f_t9_smoke.launch.py` löschen oder mit `# SUPERSEDED by hexapod_bringup/launch/real.launch.py`-Kommentar markieren (cleanup)

---

## User-Entscheidungen (2026-05-16)

| Frage | Antwort | Auswirkung |
|---|---|---|
| G-Q1 loopback_mode-Default | **A** — `false` (echte HW als Default) | `DeclareLaunchArgument('loopback_mode', default_value='false')`. Stage H profitiert ohne Args-Override; Loopback-Smoke G-T4 setzt explizit `loopback_mode:=true`. |
| G-Q2 RViz im real.launch.py | **A** — nicht mitstarten | Kein RViz-Code im Launch. Diagnose bei Bedarf via separatem `rviz2 -d view.rviz`. |
| G-Q3 gait + teleop im real.launch.py | **A** — modular separat | Konsistenz zu `sim.launch.py`. Bringup-Tests in Stage H + Phase 10 brauchen bewusst kein gait (sonst zappelt der aufgebockte Roboter). |
| G-Q4 G-T4-Smoke-Style | **A** — User-Run | Konsistent zu Stage F's F-T8/T10. CI bleibt pure gtests + `--show-args`-Headless-Check. End-to-End-Smoke ist User-ausgeführt. |

---

## Was offen war und User-Feedback gebraucht hat (vor Plan-Freigabe)

### Frage 1 — `loopback_mode`-Default in `real.launch.py`?

- **A (mein Vorschlag): `loopback_mode:=false` (echte HW als Default).**
  Begründung: der Name „real.launch.py" suggeriert Real-Hardware-Bringup.
  Wer Loopback testen will, muss explizit `loopback_mode:=true` setzen —
  was in der README dokumentiert ist und im G-T4-Smoke explizit so
  aufgerufen wird. Stage H (echte Servos) profitiert vom Default ohne
  weitere Args.
- B: `loopback_mode:=true` (sicherer Default, nichts geht kaputt wenn
  jemand „auf gut Glück" launched). Aber: Stage H braucht dann immer
  `loopback_mode:=false`-Override, was den Default-Vorteil neutralisiert.

### Frage 2 — RViz im `real.launch.py` mitstarten?

- **A (mein Vorschlag): nein, nicht mitstarten.** Beim echten Roboter
  steht das Modell physisch da; RViz-Visualisierung bringt operativ
  wenig. Wer joint_states + commanded vs. measured plotten will,
  startet `rviz2 -d view.rviz` separat (das funktioniert gegen
  `/robot_description` aus dem RSP).
- B: optional über LaunchArg `enable_rviz:=true|false` (default false).
  Plus paar Zeilen Code, plus Test-Aufwand. Bringt aber für Stage H
  (Servo2040 ohne Servos) und Phase 10 (Single-Leg-Bringup) ein paar
  Diagnose-Vorteile (Trajektorie sichtbar machen).

### Frage 3 — `gait` + `teleop` im `real.launch.py` mitstarten?

- **A (mein Vorschlag): nein, nicht mitstarten.** Konsistenz zu
  `sim.launch.py`, das beides auch nicht inline startet (User ruft
  `ros2 launch hexapod_gait gait.launch.py` + `joy_teleop.launch.py`
  separat). Modular bleibt es flexibler — Bringup-Tests in Stage H
  brauchen bewusst kein gait, sonst zappelt der Roboter beim Aufbocken.
- B: über LaunchArg `enable_gait:=true|false`, `controller:=ps4_usb`
  optional einbauen. Mehr Convenience für End-User, aber Phase 10/11/12
  würden die meiste Zeit `enable_gait:=false` setzen wegen Bench-Tests.

### Frage 4 — `--show-args`-Test (G-T2) reicht oder zusätzlicher launch_testing?

- **A (mein Vorschlag): `--show-args` reicht.** Verifiziert dass die
  Launch-Datei syntaktisch evaluierbar ist und die Args richtig
  deklariert sind. Plus G-T4 als End-to-End-Smoke.
- B: zusätzlich eine `launch_testing`-Test-Suite (Python-test-File mit
  ProcessIsRunning-Asserts). Cooles CI-Goodie aber +~150 Zeilen
  Boilerplate für eine Stage die schon einen User-ausgeführten
  End-to-End-Smoke hat.

### Frage 5 — Loopback-Smoke G-T4 in CI oder rein User-Run?

- **A (mein Vorschlag): rein User-Run.** Konsistenz zu Stage F's F-T8/T10:
  Bringup-Smokes sind manuell, weil sie GUI-Komponenten (Gazebo/RViz)
  starten könnten und in CI-Containern ohne Display fragil werden. Bei
  G-T4 ist es zwar headless (kein Gazebo, kein RViz), aber der saubere
  Weg ist einheitlich: alle Live-Stack-Smokes sind User-Runs, alle CI-
  Tests sind reine gtests. (G-T2 `--show-args` ist Headless-CI-fähig.)
- B: G-T4 als launch_testing (siehe Frage 4-B), läuft headless in CI.
  Aber nur Bringup-Wert (kein controller-manager-Antwort-Verhalten),
  und der manuelle Smoke kommt auch ohne CI dazu.

---

## Reihenfolge nach Plan-Freigabe

1. ☐ User reviewt Plan + 5 Fragen → Antworten
2. ☐ Bei Bedarf Plan anpassen
3. ☐ `hexapod_bringup/launch/real.launch.py` schreiben (mit Args + xacro-Substitution)
4. ☐ `hexapod_bringup/package.xml` `<exec_depend>` ergänzen
5. ☐ `colcon build` grün
6. ☐ G-T2 (`--show-args`) + G-T3 (xacro-Override) + G-T6 (hexapod_hardware-Regression)
7. ☐ User-Smokes G-T4 + G-T5 + G-T7 + G-T8
8. ☐ Kritischer Self-Review (Pflicht CLAUDE.md §4)
9. ☐ Doku-Updates (`hexapod_bringup/README.md`, `hexapod_hardware/README.md`-Status)
10. ☐ `/tmp/f_t9_smoke.launch.py` cleanup
11. ☐ Fertig-Meldung für User-Commit

Mit Stage G ist der **HW-Bringup im Loopback-Modus produktiv lauffähig**.
Danach Stage H (echter Servo2040 am USB ohne Hexapod-Servos, PWM-
Verifikation), dann Stage I (volle Tests + Doku-Polish), dann Stage J
(Phase-9-Abschluss).

---

## Plan-Korrekturen während Implementation (2026-05-16)

Drei kleinere Abweichungen vom Vorab-Plan, keine fachlichen Diffs:

1. **AskUserQuestion-Limit von 4 Fragen.** Plan-Doku hatte ursprünglich
   5 offene Fragen aufgelistet. Da `AskUserQuestion` max. 4 Fragen pro
   Aufruf erlaubt, wurden G-Q4 (`--show-args` vs. launch_testing) und
   G-Q5 (G-T4-Smoke User-Run vs. CI) zu einer Frage „G-Q4 Smoke-Style"
   zusammengefasst, da beide dieselbe Trade-off-Dimension haben (Test-
   Granularität in CI vs. Manual). User-Antwort A deckt beide
   ursprünglichen Punkte ab.

2. **G-T1 Build-Test nur hexapod_bringup statt „alle betroffenen
   Pakete".** Da hexapod_description / hexapod_control / hexapod_hardware
   nach Stage F bereits gebaut + symlink-installiert waren, reichte
   `colcon build --packages-select hexapod_bringup` für G-T1 — keine
   anderen Pakete sind in Stage G angefasst. Plan-Wording „alle
   betroffenen Pakete" war defensiver formuliert; in der Praxis
   1 Paket = hexapod_bringup. Bei einem clean rebuild würde der Plan-
   Befehl trotzdem stimmen.

3. **`<ros2_control name="GazeboSimSystem">` semantischer Mismatch
   sichtbar in G-T4-Output.** `ros2 control list_hardware_components`
   wird in Stage H einen Eintrag mit `name: GazeboSimSystem` und
   `plugin name: hexapod_hardware/HexapodSystemHardware` zeigen — das
   ist verwirrend aber funktional korrekt. Stage-J-Vormerk zum
   Rename-Refactor besteht weiter (Stage F Plan-Korrektur Punkt 2 +
   F-Self-Review-Zeile). Die G-T4-Test-Anleitung erklärt es jetzt
   explizit, damit der User bei der Verifikation nicht stutzt.
