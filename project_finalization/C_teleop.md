# Block C — Teleop / Steuerungs-UX (Handover-Plan + Fortschritt)

> **Zweck:** Sammel-Plan für Block C (PS4-Steuerung). Hält die **Steuerungs-Belegung**, die
> Stage-Aufteilung (C1 erweitern → C2 Param/Intent-Bridge → C4 Bluetooth), abhakbare Punkte,
> Tests und offene Fragen — so dass ein **neuer Chat/Agent nahtlos übernehmen** kann.
>
> **Lese-Reihenfolge für neuen Chat:** `CLAUDE.md` §4/§5/§9 · `project_architecture/ai_navigation.md` ·
> DIESE Datei · der Teleop-Code (`src/hexapod_teleop/`) + `gait_node.py` (Services aus B1).
> Block-Kontext Lokomotion: [`B_lokomotion_kern.md`](B_lokomotion_kern.md). Backlog: [`00_backlog.md`](00_backlog.md).
> Status: ⚪ offen — 🟡 aktiv — 🟢 fertig — ⏸️ pausiert — 💤 deferiert.

## Status-Übersicht (für Handover)
| Stage | Titel | Status | Test-Datei |
|---|---|---|---|
| C1 | PS4 USB Grund-Steuerung (Fahren/Höhe/Dead-Man) | 🟢 vorhanden (Phase 6); wird in **C1+** erweitert | `docs/phase_6_stage_A_test_commands.md` |
| **C1+** | Sticks omnidirektional + Sit/Stand-Toggle + Shutdown + Show-Pose-Hook | 🟢 **fertig** (SIM+HW 2026-06-03) | [`C1plus_test_commands.md`](C1plus_test_commands.md) |
| C2 | Live-Param/Intent-Bridge (Gangart-Wechsel + Schrittweite) | 🟢 **fertig** (SIM 2026-06-03; HW via B3+C1+) | [`C2_test_commands.md`](C2_test_commands.md) |
| C4 | Bluetooth (`ps4_bt.yaml` + Pairing) | ⚪ nach USB | (später) |

> **Reihenfolge (User 2026-06-03):** erst **USB** komplett (C1+), dann **C2** (Param-Bridge),
> dann **C4 Bluetooth**. Show-Pose-Verhalten hängt an **Block B4** (pausiert) — hier nur Hook.

---

## 0. Design-Prinzip (verbindlich): Teleop = reines UI, `gait_node` = Logik

**Der Teleop kennt KEINEN Engine-State und enthält KEINE Entscheidungslogik.** Er übersetzt
Controller-Eingaben in **Intents** und schickt sie weg; was damit passiert (abhängig von
STANDING/SAT/WALKING, Limits, Param-Clamps), entscheidet der `gait_node`. Begründung (User
2026-06-03): saubere Trennung, Teleop bleibt dumm/austauschbar (USB/BT/PS5/Tastatur), die
Sicherheits-/State-Logik lebt an EINER Stelle.

Daraus folgt:
- **Sit/Stand:** Teleop ruft **einen** Toggle-Intent; `gait_node` löst nach State auf.
- **Gangart-Wechsel:** Teleop ruft „nächste Gangart"-Intent; `gait_node` cyclet + prüft STANDING.
- **Schrittweite:** Teleop ruft „größer/kleiner"-Intent; `gait_node` clampt.
- **Höhe:** bleibt das bestehende `/cmd_body_height`-Topic (gait_node clampt + ignoriert ≠STANDING).
- **Fahren:** `/cmd_vel` (Engine clampt/State-gated). **Shutdown:** bestehender B1-Service.

---

## 1. Volle Steuerungs-Belegung (Ziel-Mapping, PS4)

| Input | Funktion | Hinweis / Abhängigkeit | Stage |
|---|---|---|---|
| **Linker Stick** | Fahren omnidirektional: Y=vor/zurück (linear.x), X=seitwärts (linear.y), **analog** | nur mit Dead-Man | C1+ |
| **Rechter Stick X** | Drehen (angular.z) | nur mit Dead-Man | C1+ |
| **R1** (halten) | **Dead-Man** — Fahren nur während gehalten | Safety (Pflicht) | C1+ |
| **L1** (halten) | „Langsam/Präzise" — halbes Tempo (Skalierung) | rein lokal im Teleop | C1+ |
| **L2 / R2** (Druck) | Körper **senken / heben um 1 cm** | clampt auf `[body_height_min, body_height_max]`; nur STANDING | C1+ |
| **△ Triangle** (Druck) | **Toggle Hinsetzen/Aufstehen** | Intent `/hexapod_sit_stand_toggle`; gait_node löst nach State auf | C1+ |
| **○ Circle** (lang) | **Shutdown** (`/hexapod_shutdown`) | bewusst (Long-Press), terminal (Relay aus) | C1+ |
| **✕ Cross** (lang) | **Show-Pose** (Hinterteil runter, Vorderteil hoch, Vorderbeine wackeln per linkem Stick) | ⚠️ **B4-abhängig** — jetzt nur Hook/Stub | C1+ (Hook), B4 (Verhalten) |
| **D-Pad ←/→** | **Gangart** durchschalten (tripod→wave→tetrapod→ripple) | Intent `/hexapod_cycle_gait`; nur STANDING | C2 |
| **D-Pad ↑/↓** | **Schrittweite** (`step_length_max`) größer/kleiner | Intent; gait_node clampt; ändert Stride + Top-Speed | C2 |
| **□ Square** | reserviert (z.B. Gangart-Reset auf tripod) | — | später |
| Rechter Stick Y | reserviert (Body-Pitch, B4) | — | B4 |

**Tempo:** Dosierung über Stick-Auslenkung (analog) + L1=langsam; „weiter/schneller laufen" über
Schrittweite (D-Pad ↑/↓). Keine separate Tempo-Stufe nötig (User 2026-06-03).

---

## C1+ — USB-Steuerung erweitern (Sticks + Posture-Intents)  ⚪ als Nächstes

**Ziel:** Den vorhandenen USB-Teleop auf analoge Sticks (omnidirektional) heben und die B1-Aktionen
(Sit/Stand-Toggle, Shutdown) + Show-Pose-Hook auf den Controller legen — **alles über Topics +
discrete Intent-Services**, ohne Live-Param-Tuning (das ist C2).

**Logik-Skizze:**
- `joy_to_twist.py`:
  - **Linker Stick** → `cmd_vel.linear.x` (Achse Y) + `cmd_vel.linear.y` (Achse X), skaliert mit
    `linear_x_scale`/`linear_y_scale`, Deadzone gegen Stick-Drift. **Rechter Stick X** →
    `angular.z` (`angular_z_scale`). Alles **nur wenn Dead-Man (R1) gehalten**, sonst `cmd_vel=0`.
  - **L1 gehalten** → Skalen × `slow_factor` (z.B. 0.5).
  - **L2/R2** → wie bisher Edge-Detection, aber Schritt = **0.01 m**; lokales Ziel zusätzlich auf
    `[body_height_min, body_height_max]` clampen (Params spiegeln/lesen), dann `/cmd_body_height`.
  - **Triangle** (Edge) → Service-Call `/hexapod_sit_stand_toggle` (fire-and-forget).
  - **Circle** (Long-Press ≥ `longpress_sec`) → `/hexapod_shutdown`.
  - **Cross** (Long-Press) → **Show-Pose-Hook**: ruft (vorerst) einen Stub/Log „Show-Pose noch
    nicht implementiert (B4)" — KEIN Service, KEINE Pose. Binding + Long-Press-Erkennung stehen,
    damit B4 nur noch das Verhalten einhängt.
- `gait_node.py` (kleine Ergänzung, gehört logisch zu B1): neuer Service
  **`/hexapod_sit_stand_toggle`** (`std_srvs/Trigger`): STANDING → `_start_sitdown_sequence()`
  (Rest); SAT & nicht latched → Stand-up (wie `_on_stand_up`); sonst `success=False` + Meldung.
  Reuse der bestehenden B1-Interna.

**Dateien:** `hexapod_teleop/hexapod_teleop/joy_to_twist.py`, `hexapod_teleop/config/ps4_usb.yaml`
(neue Achsen/Buttons/Long-Press/Skalen/Deadzone), `hexapod_teleop/README.md` (Mapping-Tabelle),
`hexapod_gait/hexapod_gait/gait_node.py` (Toggle-Service).

**Progress-Checkliste:**
```
- [x] C1+.1  Teleop: linker Stick → cmd_vel x/y (omnidirektional) + rechter Stick X → omega; Deadzone
- [x] C1+.2  Teleop: Dead-Man (R1) gated; L1 = slow_factor-Skalierung
- [x] C1+.3  Teleop: L2/R2 → ±0.01 m Höhe, lokal auf [min,max] geclampt, /cmd_body_height
- [x] C1+.4  gait_node: Service /hexapod_sit_stand_toggle (State→sit/stand), Reuse B1
- [x] C1+.5  Teleop: Triangle→toggle, Circle-long→shutdown (Long-Press-Erkennung)
- [x] C1+.6  Teleop: Cross-long → Show-Pose-HOOK (Stub/Log, kein Verhalten; B4-ready)
- [x] C1+.7  Unit-Tests Teleop (15) + gait_node Toggle-Test (3); Lint grün (140 gait / 15 teleop)
- [x] C1+.8  SIM: Fahren omnidirektional, Höhe, Triangle-Toggle, Shutdown — sauber (User 2026-06-03)
- [x] C1+.9  HW aufgebockt → Boden (USB): sinnvoll gelaufen (User 2026-06-03)
- [x] C1+.10 README-Mapping-Tabelle + Test-Markdown (`C1plus_test_commands.md`); Self-Review
```

> **🟢 C1+ ABGESCHLOSSEN (2026-06-03):** Code + Tests + Lint grün, SIM + HW (USB) vom User
> bestätigt.
>
> ⏳ **Feinjustage am Ende von Block C (offen, User-Notiz 2026-06-03):**
> 1. Stick-Vorzeichen/Skalen, `longpress_sec`, `slow_factor`, Deadzone, Höhen-Schritt.
> 2. **WICHTIG — gültige Parameter-Kombinationen erzwingen:** Beim Live-Tuning (Höhe via L2/R2,
>    Schrittweite via D-Pad, Gangart) kann man in **ungültige (out-of-reach) Kombinationen** von
>    `(body_height, radial_distance, step_length_max, step_height, gait)` geraten → IKError/
>    safety_freeze-Meldungen (vom User beobachtet). Am Ende von C: der Controller darf nur in
>    **envelope-grüne** Kombinationen schalten. Lösungs-Optionen (Ende-C entscheiden):
>    (a) `gait_node` validiert eine vorgeschlagene Änderung vorab gegen das Envelope/IK
>    (`walking_envelope_check`-Logik) und lehnt ab, statt zu freezen; ODER
>    (b) nur zwischen **validierten Presets/Profilen** umschalten (überlappt Block E3
>    Preset-Management) — die „berechnete Höhe + die daran hängenden korrekten Parameter" als
>    gekoppeltes Set. Bezug: zwei Limit-Quellen + lenient-Sim (`ai_navigation` §0).
>
> Self-Review:

| # | Punkt | Status | Befund |
|---|---|---|---|
| 1 | Teleop = reines UI (kein State) | OK | Sit/Stand via Toggle-Intent; gait_node löst auf. |
| 2 | Dead-Man-Gate | OK | ohne R1 → Null-Twist (getestet). |
| 3 | Höhen-Clamp lokal + gait_node | OK | doppelt geclampt; läuft nicht über Grenze (getestet). |
| 4 | Long-Press gegen Versehen | OK | Circle/Cross erst nach `longpress_sec` (getestet, Zeit injiziert). |
| 5 | Show-Pose nur Hook | OK | Stub/Log; Verhalten = B4. |
| 6 | Stick-Vorzeichen/Indizes | 🟡 SIM-verify | Defaults gesetzt; live per `/joy` bestätigen (sign_*-Params). |
| 7 | Intent-Service fehlt (Sim ohne gait_node) | OK | `_call_intent` no-op + WARN (getestet). |

**Tests-Liste (C1+):**
- Teleop-Unit (rclpy-Node wie `test_param_callback`): Stick→Twist (x/y/omega + Vorzeichen + Deadzone);
  Dead-Man-Gate (ohne R1 → Twist 0); L1-Slow-Faktor; L2/R2-Edge + lokaler Höhen-Clamp; Long-Press-
  Erkennung (Zeit-gefakt); Triangle/Circle/Cross rufen die richtigen Clients (mocken/zählen).
- gait_node-Unit: `_on_sit_stand_toggle` aus STANDING → sit (REPOSITION), aus SAT → standup, aus
  WALKING/latched → success=False.
- **NICHT getestet:** echtes Controller-HID (live), Show-Pose-Verhalten (B4).

**Offene Punkte C1+:**
- Achsen-/Button-Indizes der Sticks (linker Stick X/Y, rechter Stick X) per `ros2 topic echo /joy`
  am realen Controller bestätigen (USB) — Default-Annahme: LX=0, LY=1, RX=3.
- `longpress_sec` (Vorschlag 0.8 s), `slow_factor` (0.5), Deadzone (0.1) — beim Sim-Test final.
- Dead-Man auch für Show-Pose? → mit B4 entscheiden.

---

## C2 — Live-Param/Intent-Bridge (Gangart + Schrittweite)  ⚪ (komplexer, getrennt)

**Ziel:** Gangart-Wechsel und Schrittweite **live vom Controller** — über **Intents** (Teleop bleibt
UI), die der `gait_node` umsetzt (Cyclen, Clampen, STANDING-Schutz). Bewusst von C1+ getrennt, weil
Param-Mutation + State-Guards + Persistenz die komplexere Hälfte sind.

**Logik-Skizze:**
- `gait_node.py`:
  - **`/hexapod_cycle_gait`** (`std_srvs/Trigger`): cyclet die aktive Gangart durch eine feste Liste
    `[tripod, wave, tetrapod, ripple]` (Wrap), nur wenn STANDING (sonst reject) — nutzt das
    bestehende `_load_gait_pattern` + den `standing_only`-Mechanismus. Optional Rückmeldung welche
    Gangart nun aktiv ist (Log + response.message).
  - **Schrittweite:** `/hexapod_adjust_step_length` (`std_srvs/SetBool`: true=+, false=−) ODER
    `/hexapod_step_length_delta` (`std_msgs/Float64`, relativ). gait_node addiert `±step`, clampt auf
    sinnvolle Grenzen (z.B. [0.03, 0.12]) und auf das Envelope-/URDF-Limit. (Design-Entscheidung im
    C2-Plan festlegen: SetBool vs Float-Topic.)
- `joy_to_twist.py`: **D-Pad ←/→** → cycle_gait (Edge); **D-Pad ↑/↓** → step-length-Intent (Edge).
- Optional: aktive Gangart / step_length als String/Float publishen (HUD/Diagnose).

**Dateien:** `gait_node.py` (2 Services + Param-Clamp-Logik), `joy_to_twist.py` + `ps4_usb.yaml`
(D-Pad-Bindings), READMEs.

**Progress-Checkliste:**
```
- [x] C2.1  gait_node: /hexapod_cycle_gait (SetBool next/prev, Wrap, STANDING-only)
- [x] C2.2  gait_node: /hexapod_adjust_step_length (SetBool +/-, Clamp [intent_min,max])
- [x] C2.3  Teleop: D-Pad ←/→ → cycle_gait, D-Pad ↑/↓ → step-length-Intent (Rising-Edge)
- [x] C2.4  Unit-Tests: cycle wrappt + STANDING-Guard; step clampt; Teleop D-Pad → Intents (gait 144 / teleop 20)
- [x] C2.5  SIM: Gangart per D-Pad durchschalten (User 2026-06-03: schaltet sauber durch alle 4)
- [x] C2.6  HW: Gangart-Cyclen via B3 (HW-verifiziert) + Controller-Bindings via C1+ (HW) abgedeckt
- [x] C2.7  Self-Review + Test-Markdown (`C2_test_commands.md`)
```

> **🟢 C2 ABGESCHLOSSEN (2026-06-03):** Code + Tests + Lint grün, SIM bestätigt (Gangart
> cyclt sauber durch alle 4 nach D-Pad-Debounce-Fix). HW-Risiko gering (Gangarten schon in B3
> HW-verifiziert, Controller-Bindings in C2/C1+ HW-getestet). Self-Review:
>
> | # | Punkt | Status | Befund |
> |---|---|---|---|
> | 1 | Teleop = reines UI | OK | D-Pad → SetBool-Intents; cyclen/clampen/STANDING-Guard im gait_node. |
> | 2 | cycle_gait STANDING-only + Wrap | OK | nur [tripod,wave,tetrapod,ripple], single_leg ausgenommen (getestet). |
> | 3 | step_length-Clamp | OK | [0.02, 0.10] (Params), schützt grob vor out-of-reach (getestet). |
> | 4 | D-Pad Rising-Edge | OK | ein Druck = ein Schritt, Halten feuert nicht nach (getestet). |
> | 5 | Restliche Kombi-Validierung | 🟡 Ende-C | Höhe×Schrittweite×Gangart kann noch ungültig werden → Feinjustage Ende C. |
> | 6 | D-Pad-Vorzeichen | 🟡 SIM-verify | `sign_dpad_x/y`; live bestätigen. |

**Offene Fragen C2:**
- Schrittweiten-Intent als `SetBool` (up/down) vs `Float64`-Delta? (Vorschlag: SetBool, 1 Schritt
  = z.B. 0.005 m, einfacher Controller-seitig.)
- Cyclen über ALLE Gangarten inkl. `single_leg_*`? (Vorschlag: nur [tripod, wave, tetrapod, ripple];
  single_leg bleibt Debug-only.)
- Sollen Gangart/Schrittweite über Reboots **persistiert** werden? (Vorschlag: nein in C2; Preset-
  Management ist Block E3.)

---

## C4 — Bluetooth  ⚪ (nach USB)
`ps4_bt.yaml` (BT-Achsen/Button-Indizes weichen ab → per `ros2 topic echo /joy` bestätigen) +
Pairing-Anleitung. Comms-Loss → bestehender **B1-Fail-safe** (`comms_loss_sitdown_timeout`).
`joy_teleop.launch.py` hat schon `controller:=`-Argument (Default `ps4_usb`) → `ps4_bt` ergänzen.

**Was sich bei BT bzw. Pi-Wechsel ändert (geklärt 2026-06-03) — Teleop-Logik bleibt gleich:**
- **BT (C4):** nur das **Index-/Vorzeichen-Mapping** (DS4 meldet über BT ein anderes HID-Layout
  als USB) → eigenes `ps4_bt.yaml`, kein Code. Plus Pairing.
- **Pi-Wechsel (Phase 12):** (a) **DDS** — Knoten reden maschinenunabhängig; Teleop+joy_node
  können auf dem Desktop bleiben, nur `gait_node`+`hexapod_hardware` auf dem Pi (gleiches
  `ROS_DOMAIN_ID`/Netz). (b) **Servo2040-Serial-Port** = Launch-Arg `serial_port` (Pi-USB-
  Device-Pfad, evtl. ≠ /dev/ttyACM0), kein Code. (c) **Controller-Anbindung:** am Pi → joy_node
  am Pi (Pi-BT-Stack + Pairing); am Desktop → über DDS. Teleop/Gait-Code portiert 1:1.

---

## Handover-Notizen (für einen Fortsetzungs-Agent)

> Falls dieser Block nicht in einer Session fertig wird — hier der Anker.

- **Was es schon gibt (C1, Phase 6):** `joy_to_twist.py` mappt D-Pad→cmd_vel (digital, nur vx+omega)
  + L2/R2→Höhe + R1=Dead-Man. Sauber YAML-konfiguriert (`ps4_usb.yaml`). Publisht `/cmd_vel` +
  `/cmd_body_height`. Launch: `joy_teleop.launch.py` (`controller:=ps4_usb`).
- **Was B1/B3 schon bereitstellen (nur noch anzubinden):** Services `/hexapod_sit_down`,
  `/hexapod_stand_up`, `/hexapod_shutdown` (B1); Gangarten + `gait_pattern`-Param (standing_only, B3);
  Live-Params `step_length_max`/`body_height`/`cycle_time` (alle im `gait_node`).
- **Reihenfolge:** C1+ (USB, Topics+discrete Services) **fertig machen & testen** → erst dann C2
  (Param/Intent-Bridge) → dann C4 (BT). Jede Stage: Plan→Code→Tests(grün+Lint)→SIM→HW, Commits macht
  der User.
- **Design-Prinzip beachten:** Teleop = reines UI (Intents), `gait_node` = State/Logik (s. §0).
  Neue Aktionen → als Intent-Service im `gait_node`, nicht als Logik im Teleop.
- **Gotchas:**
  - `joy_to_twist` publisht beim Start einmal `/cmd_body_height = body_height_init` → muss ==
    Gait-`body_height` sein, sonst sackt der Stand ab (ai_navigation §1). Bei Höhen-Änderung nachziehen.
  - Stick-Achsen-Indizes USB vs BT verschieden → immer `ros2 topic echo /joy` verifizieren.
  - Sit/Stand/Shutdown nie auf eine leicht verrutschende Achse; Shutdown = Long-Press (terminal).
  - Tests: Teleop-Node-Tests brauchen `rclpy.init()` (Modul-Fixture wie in `test_sitdown_node.py`);
    Service-Clients in Unit-Tests mocken/zählen statt echt aufrufen.
- **Validierungs-Gates:** Build → Unit/Lint → SIM (RViz+Gazebo) → HW aufgebockt → Boden. Sim VOR HW.
