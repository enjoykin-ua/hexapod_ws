# Phase 13 — Erster echter HW-Start am Pi (Plan)

> **Test-Anleitung:** [`phase_13_pi_hw_bringup_test_commands.md`](phase_13_pi_hw_bringup_test_commands.md)
> **Vorbedingung:** Phase 12 ✅ (Stack baut + läuft am Pi, Loopback grün,
> Servo2040 erkannt als `/dev/servo2040`).
> **Ziel:** Den kompletten Stack auf dem Pi mit **echter** Servo2040 fahren —
> dieselbe Sequenz wie am Desktop erprobt, jetzt Pi-getrieben.

---

## ⚠️ Safety zuerst (CLAUDE.md §9) — gilt für ALLE Stufen

- **Aufgebockt zuerst.** Beine in der Luft, kein Bodenkontakt, bis aufgebockt
  alles sauber war (Stages B–E). Erst dann an den Boden (Stage F).
- **PSU-Kill-Switch in der Hand.** Bei jedem Stall, unerwarteten Ruck,
  `OVERCURRENT`/`WATCHDOG`/`SAFETY FREEZE` → **sofort Strom trennen**.
- **Erste Bewegung langsam**, Stromanzeige der PSU beobachten.
- **Power-On-Zentrieren ist HW-bedingt unvermeidbar** (Miuzei/Diymore-Servos
  zucken beim Enable zur Mitte). Deshalb aufgebockt booten + Relay-Gate +
  smooth aus der Mitte rampen — Strategie aus dem `servo_real_cal`-Thread.
- **Sauberes Runterfahren:** Launches per `Strg+C` (Rail wird stromlos →
  Servos limp), dann erst PSU aus. Pi via `sudo shutdown -h now`.

---

## Was diese Phase macht (Logik-Skizze)

Die Sequenz ist **dieselbe, die am Desktop bereits erprobt wurde** (HW-Standup
Stage 0.7, Walking aufgebockt E2, Teleop USB+BT C1–C4). Neu ist **nur**, dass
sie jetzt **am Pi** läuft. Damit ist das Hauptrisiko nicht die Logik, sondern:
Pi-Performance/Timing, der serielle Port (`/dev/servo2040`), und das erstmalige
echte HW-Enable über den Pi.

Vier funktionale Schritte (so wie vom User vorgegeben), jeder **erst aufgebockt**:

1. **Init** — `real.launch.py loopback_mode:=false serial_port:=/dev/servo2040`
   → robot_state_publisher + controller_manager lädt `hexapod_hardware`-Plugin,
   öffnet `/dev/servo2040`, Relay-gated Power-On, alle 18 Servos rampen smooth
   auf `power_on_mid` (1500 µs). Danach: JSB + 6 leg-JTC active.
2. **Aufstehen** — `gait.launch.py use_sim_time:=false robot_description_file:=$HEX_URDF`
   → `gait_node` startet, triggert nach `/joint_states`-Flow das **kartesische**
   Aufstehen (~8 s, 2-phasig). `robot_description_file` aktiviert den
   Joint-Limit-Check (sonst lenient — auf HW gefährlich, s. Memory zwei
   Limit-Quellen). Ab hier ist der Roboter bewegungsbereit (`/cmd_vel`).
3. **Teleop USB** — `joy_teleop.launch.py controller:=ps4_usb` → `joy_node` +
   `joy_to_twist` erzeugen `/cmd_vel` (Dead-Man R1 + Sticks). PS4 per USB am Pi
   (`/dev/input/js0`).
4. **Teleop BT** — DS4 via `bluetoothctl` am Pi koppeln (bonded+trusted, MAC
   `D0:27:88:3D:68:9A`), dann `joy_teleop.launch.py controller:=ps4_bt`.

**Pi-spezifische Unterschiede zum Desktop:**
- `serial_port:=/dev/servo2040` (statt `/dev/ttyACM0`) — udev-Symlink steht.
- `use_sim_time:=false` ist auf dem Pi Pflicht (kein `/clock`) — ist bereits
  gait.launch.py-Default, wird aber explizit gesetzt.
- Launches in **tmux** oder am Pi-Bildschirm (SSH-Abbruch killt sonst den
  Stack — in Phase 12 passiert).
- **Watchdog-Heartbeat:** Frame-Stille > 200 ms in blockierender on_activate-
  Sequenz → FW-Watchdog trippt + Relay-Drop. Falls der Pi langsamer ist als der
  Desktop, hier genau hinschauen (Memory `project_phase13_onactivate_watchdog_heartbeat`).

---

## Stufen

| Stage | Inhalt | aufgebockt? |
|---|---|---|
| **A** | Vorbereitung & Safety-Setup (HW, Strom, FW-Limit, Build, `/dev/servo2040`) | — |
| **B** | Init: `real.launch.py` echter Zugriff → power_on_mid, Relay, JTCs active | ✅ |
| **C** | Kartesisches Aufstehen via `gait.launch.py` | ✅ |
| **D** | Teleop USB (`ps4_usb`) — Bewegung in der Luft | ✅ |
| **E** | Teleop BT (`ps4_bt`) — Pairing + Bewegung in der Luft | ✅ |
| **F** | **Am Boden**: Aufstehen + fahren, **Strom messen** (Done-Kriterium) | Boden |

---

## Tests-Liste (was markiert „fertig", mit Begründung)

**Stage A — Vorbereitung**
- A-T1: `/dev/servo2040` zeigt auf den Servo2040-ttyACM (udev steht). *Warum:* der Launch öffnet genau diesen Port.
- A-T2: Workspace am Pi aktuell gebaut (`colcon build`), gesourct. *Warum:* sonst alte Binaries.
- A-T3: FW-Strom-Limit = 10 A total (FW-seitig, `cfg::TOTAL_CURRENT_MAX_MA`). *Warum:* legt die Trip-Schwelle fest; Kill-Switch bleibt primäre Sicherung.

**Stage B — Init aufgebockt** (= der erste echte HW-Zugriff am Pi)
- B-T1: Alle 6 Beine kommen smooth in `power_on_mid`, Relay an, **kein** Trip/Freeze/Watchdog. *Warum:* das ist der kritischste Erstkontakt; beweist, dass Plugin↔Servo2040 über den Pi sauber spricht.
- B-T2: `ros2 control list_controllers` = 1× JSB + 6× JTC active.

**Stage C — Aufstehen aufgebockt**
- C-T1: Kartesisches Aufstehen läuft über ~8 s (Phase 1 strecken, Phase 2 beugen), **kein** Stall/`IKError`/`SAFETY FREEZE`/`OVERCURRENT`.
- C-T2: Endpose stabil, kein Zittern; `/joint_states` plausibel (coxa~0 / femur −0.240 / tibia +0.758).

**Stage D — Teleop USB aufgebockt**
- D-T1: `/dev/input/js0` vorhanden, `/joy` ändert sich bei Stick/Button.
- D-T2: Mit **R1 gehalten** + linker Stick → Beine bewegen sich in der Luft (cmd_vel wirkt); ohne R1 → Neutral (Dead-Man greift).

**Stage E — Teleop BT aufgebockt**
- E-T1: DS4 via `bluetoothctl` gekoppelt, `/dev/input/js0` über BT, `/joy` aktiv.
- E-T2: Bewegung in der Luft wie D-T2, jetzt drahtlos.

**Stage F — Am Boden (Done-Kriterium)**
- F-T1: Aufstehen am Boden **schürffrei**, Strom-Peak nahe Stand-Niveau (nicht >3,5 A mit Voltage-Drop). *Warum:* das ist der eigentliche Beweis, dass der HW-Start am Pi unter Last funktioniert.
- F-T2: Fahren per Teleop am Boden (langsam, Tripod, kurze Strecke) ohne Trip/Freeze.

**Bewusst NICHT getestet (scope-out):**
- Gangarten außer Tripod (Wave/Tetra/Ripple) — deferiert, separat.
- Show-Pose / Stance-Modi-Umschaltung am Pi — separat (sind in Sim fertig).
- Untethered / 2S-LiPo — das ist Phase 8 (Elektronik), hier noch Bench-PSU.
- OLED / GPIO-Button / Autostart — Block D4/D5, eigenes Doc.
- Lange Boden-Lokomotion / Terrain — später (A5 IMU).

---

## Progress-Checkliste (Done-Vertrag)

```
### Stage A — Vorbereitung & Safety
- [ ] A.1 /dev/servo2040 verifiziert (udev-Symlink → ttyACM)
- [ ] A.2 Workspace am Pi aktuell gebaut + gesourct
- [ ] A.3 FW-Strom-Limit = 10 A total bestätigt (FW-seitig); PSU 8,4 V / 10 A
- [ ] A.4 Aufgebockt, Kill-Switch griffbereit, PSU mit Stromanzeige

### Stage B — Init aufgebockt (erster echter HW-Zugriff am Pi)
- [ ] B.1 power_on_mid: alle 6 Beine smooth, Relay an, kein Trip/Watchdog
- [ ] B.2 list_controllers = 1× JSB + 6× JTC active

### Stage C — Aufstehen aufgebockt
- [ ] C.1 Kartesisches Aufstehen ~8 s sauber (kein Stall/Freeze/IKError)
- [ ] C.2 Endpose stabil, /joint_states plausibel

### Stage D — Teleop USB aufgebockt
- [ ] D.1 /dev/input/js0 + /joy aktiv (USB)
- [ ] D.2 R1+Stick → Bewegung in der Luft; ohne R1 → Neutral (Dead-Man)

### Stage E — Teleop BT aufgebockt
- [ ] E.1 DS4 via bluetoothctl gekoppelt, /joy über BT
- [ ] E.2 Bewegung in der Luft drahtlos wie D.2

### Stage F — Am Boden (Done-Kriterium)
- [ ] F.1 Aufstehen am Boden schürffrei, Strom-Peak nahe Stand-Niveau
- [ ] F.2 Fahren per Teleop am Boden (langsam) ohne Trip/Freeze
- [ ] F.3 Self-Review + Progress-File + ggf. PHASE.md aktualisiert
```

---

## Geklärte Punkte (User-Review)

1. **Stromversorgung:** Bench-PSU **8,4 V / max 10 A** (Best-Case mit Reserve
   fürs erste Testen; Umstellung auf niedrigere Akku-Spannung später). User kann
   jederzeit alles abschalten.
2. **FW-Strom-Limit:** **10 000 mA (10 A) total**, FW-seitig
   (`cfg::TOTAL_CURRENT_MAX_MA`; verifiziert in
   `hexapod_servo_driver/tools/test_stage_e.py`: `PROD_CURRENT_LIMIT_MA = 10000`).
   Das **Plugin setzt das Limit nicht** — `SET_CURRENT_LIMIT` (0x11) dient nur
   Stage-E-Tests zum temporären Absenken. Im Produktivbetrieb gilt das FW-Default.
   ⚠️ **PSU-Max (10 A) = FW-Trip (10 A):** bei einem Stall kann die PSU einbrechen,
   *bevor* die FW trippt → **Kill-Switch ist die primäre Sicherung**, nicht das
   FW-Limit. (Aufgebockt zieht der Roboter ohnehin weit < 10 A.)
3. **Relay:** direkt am Servo2040 verdrahtet, vom **Plugin** ein-/ausschaltbar
   (je nach ROS2-Befehl) → Power-On-Gate greift.
4. **Stage F (Boden):** erst nach B–E **aufgebockt/aufgehängt** sauber, dann
   Wechsel zum Boden (User-Vorgabe).
5. **Terminals statt tmux** (User-Präferenz). Bei Pi-Absturz sind die Launches
   ohnehin weg; die SSH-Terminals hängen nur als tote Verbindungen → einfach
   schließen + neue öffnen (hängende Session sofort killen: `Enter` `~` `.`).
