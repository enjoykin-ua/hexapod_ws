# Interface-Contract — App ↔ Roboter (Block I)

> **DIE geteilte Naht.** Die Liste der rosbridge-Topics/Services/Message-Felder, gegen die
> **beide Seiten** bauen (ROS in `hexapod_ws`, App im Android-Repo). **Single Source of
> Truth** — der App-Repo *referenziert* diese Datei, kopiert sie nie ([D9](decisions.md)/[D10](decisions.md)).
>
> **Wächst pro Phase.** Was heute existiert, ist unten belegt; was neu zu bauen ist, ist als
> `[TBD-Phase N]` markiert und wird beim Bau der Phase hier festgezurrt (Typen/Felder).
>
> **Regel:** Ändert sich hier etwas, **Version hochzählen + Changelog-Zeile** → die App-
> Seite weiß, dass sie nachziehen muss.

---

## Version + Changelog

| Version | Was |
|---|---|
| **v0.1** | Gerüst. Bestandsaufnahme der wiederverwendbaren ROS-Schnittstellen + Platzhalter für die neu zu bauenden. Noch nichts implementiert. |
| **v0.2** | §1 festgezurrt: konkrete Kishi-V2→PS4-`/joy`-Index-Tabelle (Achsen + Buttons + Transforms) aus dem Phase-1-Deliverable (gemessen am S22+) **+ 2 Kishi-Extra-Slots (L4/R4 = `buttons[13]`/`[14]`), damit alle physischen Tasten erfasst und ROS-seitig später bindbar sind.** Vorzeichen-Endverifikation via `ros2 topic echo /joy` = Phase 2. |
| **v0.3** | §0 gepinnt (Phase-2-Live-Test): `/joy`-QoS = **RELIABLE Pflicht** (`joy_to_twist` subscribt RELIABLE → BEST_EFFORT wäre inkompatibel), Durability egal; Zwei-Modi-Adressierung (Sim `Desktop-IP`, real `Pi-IP`), Port 9090 + Netz-Erreichbarkeit vom Handy verifiziert. |
| **v0.4** | §1 D-Pad-Vorzeichen verifiziert (echte App): D-Pad-Y invertiert → App negiert `AXIS_HAT_Y` (`axes[7]`). Fix app-seitig, NICHT `sign_dpad_y` (PS4-Fallback bleibt korrekt). Rest der Achsen/Buttons bestätigt. |
| **v0.5** | Phase 3 (Lifecycle) festgezurrt: 4 Launcher-Services `/hexapod_bringup_start`/`_stop`/`_status`/`/hexapod_pi_shutdown` (§2a) + latched `/hexapod/bringup_running` (§3), alle `std_srvs/Trigger`. Bauch-Start (`auto_standup_on_start:=false`) → Aufstehen per `/hexapod_stand_up`. §6/§7 Phase-3-Punkte erledigt. |
| **v0.6** | §7.4 geklärt (aus rosbridge-2.7.0-Quellcode): latched Topics kommen über rosbridge zur App — Auto-QoS-Match an `transient_local`-Publisher, deterministisch via explizitem `qos`-subscribe-Frame. **Kein ROS-Change.** Betrifft nur den **optionalen** Live-Push von `/hexapod/bringup_running` (Primärquelle bleibt `bringup_status`-Polling). |
| **v0.7** | §5 (Video) festgezurrt für Phase 4: MJPEG via `web_video_server` :8080, `/camera/image_raw`, URL-Schema, 16:9 ~720p@15 + center-crop, `camera_enable` reserviert (Pi). §6 ergänzt: `/hexapod/alerts` (WARN+ aus `/rosout`), Set-Stance-direkt, Status-Publisher-Felder (verfügbare Tempos; Batterie gestrichen) — alle `[TBD-Phase 5]`. |
| **v0.8** | §5 präzisiert nach Phase-4-**ROS-Live-Verifikation**: **Host** = gleiche IP wie rosbridge (§0), nur Port 8080; **Verfügbarkeit** = Stream-Server läuft **im On-Demand-Stack** → Port 8080 erst **nach `/hexapod_bringup_start`** offen, App koppelt die Kamera-View an `/hexapod/bringup_running`; live gemessen **~11 Hz** (Render-Jitter, v1-ok). **Kein ROS-Change, kein neues Interface** — Klarstellung für den App-Bau (P4.7–P4.9). |
| **v0.9** | §6a festgezurrt für Phase 5 (**ROS-Seite live-verifiziert**): Status/Config/Alerts als **JSON-String** (`std_msgs/String`) — `/hexapod/status` (5 Hz, gait_node, State/Stance/Gangart/Safety/Tip + dyn. H1/H2-Caps), `/hexapod/tempo` (latched, joy_to_twist), `/hexapod/capabilities` + `/hexapod/config_manifest` (latched, Always-On `hmi_status`, 39 Params), `/hexapod/alerts` (latched Historie 50, WARN+ aus `/rosout`). **Set-Stance direkt** = App cyclet `/hexapod_cycle_stance` (kein neues Interface). Config-Panel = natives rosbridge get/set_parameters + Manifest. §7.3 damit geschlossen. |
| **v0.9.1** | §2/§6a: neuer **`/hexapod_cycle_tempo`** (`std_srvs/SetBool`, Host `joy_to_twist`) — schließt die von der App-Session gemeldete Lücke „kein direkter Tempo-Setz-Weg" (Tempo lief nur über D-Pad). App-Tempo-Dropdown = **cycle-to-target** via `tempo_idx` aus `/hexapod/tempo`, symmetrisch zu Set-Stance. Kein neuer Message-Typ; standing_only serverseitig. |
| **v0.10** | §2/§6 festgezurrt für Phase 6 (**ROS-Seite implementiert + unit-getestet**): **`/hexapod_estop`** (`std_srvs/Trigger`, **gait_node**) = der App-Not-Halt, wirkt **Sim UND HW** (gated den gait-Tick latched + ruft intern den Plugin-`/hexapod_safety_freeze`); ersetzt `/hexapod_safety_freeze` als App-Ziel (§4.2: neuer Name statt Plugin-Namen spiegeln → keine Zwei-Server-Kollision auf HW). **`/hexapod_recover`** (`std_srvs/Trigger`, gait_node) = Ein-Klick-Recovery ([D6]): Plugin-Freeze lösen + gait-Latches/Monitore reset + **Joint-Space-Ramp** in den Stand (ursachen-agnostisch, kein IK). `safety_frozen` im Status wird jetzt durch Recovery zurückgesetzt (nicht mehr „bis Stack-Neustart"). |
| **v0.11** | §3/§4/§6b festgezurrt für Phase 7A (**ROS-Seite implementiert + unit-getestet**): **`/hexapod/play_sound`** (`std_msgs/String`, App→Roboter) = Soundboard (`sound_01..03`, spielt immer); **`/hexapod/sound_enabled`** (`std_msgs/Bool`, latched, Roboter→App) = Auto-Sound-Mute-Status; Param **`sound_enable`** auf `/hexapod_audio` (App setzt via `set_parameters`). Auto-Sounds bei Aufstehen/Hinsetzen/Höhenwechsel/Freeze (**Recovery stumm**); Sound nur am Roboter-Speaker ([D5]). `/hexapod/audio_cue` = intern (gait_node→hexapod_audio). |
| **v0.11.1** (aktuell) | §6b für die App-Session präzisiert: **kopierbare rosbridge-Frames** (advertise/publish `play_sound`, `set_parameters` für den BOOL `sound_enable`, latched `subscribe` auf `sound_enabled`) + App-Pflichten (Buttons erst wenn Stack läuft, Toggle spiegelt `sound_enabled`). `sound_enabled` in die §3-Latched-QoS-Note aufgenommen. **Kein Interface-Change** — reine Klarstellung für den Android-Bau. |

---

## 0. Transport

- **Kanal 1 (Steuerung/Status):** WebSocket → `rosbridge_server` (Port **9090**, verifiziert),
  JSON. App-Client: `OkHttp`-WebSocket + rosbridge-Protokoll (`op: publish/subscribe/
  call_service`), analog roslibjs.
- **Kanal 2 (Video):** eigener Stream-Server (MJPEG/RTSP/WebRTC), **nicht** hier — nur ein
  Verweis unter §5.
- **Adressierung (zwei Modi, code-identisch, [D4](decisions.md)):**
  - **Sim:** `Desktop-IP:9090` (Dev-PC + Handy am Router).
  - **Real HW:** feste `Pi-IP:9090` im Hotspot-Range.
  - rosbridge bindet `0.0.0.0` → vom Handy übers Netz erreichbar (Phase-2-T2.6 verifiziert).
- **`/joy`-QoS (Pflicht):** Die App muss `/joy` mit **Reliability = RELIABLE** advertisen —
  `joy_to_twist` subscribt RELIABLE, ein BEST_EFFORT-Publisher wäre **inkompatibel** (kommt
  nicht an). Durability egal (Subscriber VOLATILE → TRANSIENT_LOCAL oder VOLATILE beide ok).
  Der rosbridge-Advertise-Default liefert das bereits (RELIABLE + TRANSIENT_LOCAL, in Phase 2
  verifiziert).

---

## 1. Steuerung — `sensor_msgs/Joy` (Reuse, [D3](decisions.md))

Die App publisht `sensor_msgs/Joy` auf **`/joy`**, normalisiert auf das **PS4-Layout**
(`ps4_usb.yaml`). `joy_to_twist` konsumiert es unverändert.

| Feld | Inhalt |
|---|---|
| Topic | `/joy` |
| Typ | `sensor_msgs/Joy` |
| Richtung | **App → Roboter** |
| Rate | **~30 Hz stetig** (auch bei neutral — NF1 Comms-Loss-Safety) |
| `axes[]` | PS4-Achsen-Reihenfolge (Sticks + D-Pad als Achsen) |
| `buttons[]` | PS4-Button-Reihenfolge |

**Verbindliches Layout (festgezurrt v0.2, Phase-1-Deliverable):** Die App misst die Kishi-Roh-
Eingaben über Android `InputManager` und emittiert `sensor_msgs/Joy` mit den **8 PS4-Achsen +
13 PS4-Buttons** (Indizes exakt wie in
[`ps4_usb.yaml`](../../src/hexapod_teleop/config/ps4_usb.yaml)) **plus 2 Kishi-Extra-Slots
(L4/R4, `buttons[13]`/`[14]`)**, damit **alle** physischen Kishi-Tasten erfasst und ROS-seitig
später bindbar sind (ohne App-Änderung). Gemessen am S22+ (Kishi V2, Vendor `0x1532` /
Product `0x071b`).

**Achsen `axes[]`:**

| Idx | PS4-Rolle | Kishi (Android) | App-Transform |
|---|---|---|---|
| 0 | `axis_lx` linker Stick X | `AXIS_X` | `−AXIS_X` |
| 1 | `axis_ly` linker Stick Y | `AXIS_Y` | `−AXIS_Y` |
| 2 | `axis_l2` L2 (idle +1 / gedrückt −1) | `AXIS_LTRIGGER` (0..1) | `1 − 2·LTRIGGER` |
| 3 | `axis_rx` rechter Stick X | `AXIS_Z` | `−AXIS_Z` |
| 4 | `axis_ry` rechter Stick Y (Show) | `AXIS_RZ` | `−AXIS_RZ` |
| 5 | `axis_r2` R2 | `AXIS_RTRIGGER` (0..1) | `1 − 2·RTRIGGER` |
| 6 | `axis_dpad_x` D-Pad ←/→ | `AXIS_HAT_X` (−1/0/+1) | `AXIS_HAT_X` (P2 ok: Gangart wechselt) |
| 7 | `axis_dpad_y` D-Pad ↑/↓ | `AXIS_HAT_Y` (−1/0/+1) | **`−AXIS_HAT_Y`** (P2: Kishi hoch=−1, PS4 erwartet +1=schneller) |

**Buttons `buttons[]` (positionsbasiert, nicht labelbasiert):**

| Idx | PS4 | Funktion (`joy_to_twist`) | Kishi-Keycode (Position) |
|---|---|---|---|
| 0 | Cross | Show-Toggle¹ | `KEYCODE_BUTTON_A` (unten) |
| 1 | Circle | Shutdown (lang) | `KEYCODE_BUTTON_B` (rechts) |
| 2 | Triangle | Sit/Stand-Toggle | `KEYCODE_BUTTON_Y` (oben) |
| 3 | Square | — (unbelegt, ROS bindet später) | `KEYCODE_BUTTON_X` (links) |
| 4 | L1 | Slow/präzise | `KEYCODE_BUTTON_L1` |
| 5 | R1 | **Dead-Man** | `KEYCODE_BUTTON_R1` |
| 6 | L2 | — (Höhe via `axes[2]`) | `KEYCODE_BUTTON_L2` |
| 7 | R2 | — (via `axes[5]`) | `KEYCODE_BUTTON_R2` |
| 8 | Share | — (unbelegt, ROS bindet später) | `KEYCODE_BUTTON_SELECT` |
| 9 | Options | — (unbelegt, ROS bindet später) | `KEYCODE_BUTTON_START` |
| 10 | PS/Guide | — (unbelegt, ROS bindet später) | `KEYCODE_BUTTON_MODE` |
| 11 | L3 | — (unbelegt, ROS bindet später) | `KEYCODE_BUTTON_THUMBL` (linker Stick-Klick) |
| 12 | R3 | — (unbelegt, ROS bindet später) | `KEYCODE_BUTTON_THUMBR` (rechter Stick-Klick) |
| 13 | *(Kishi-Extra)* | — (unbelegt, ROS bindet später) | `KEYCODE_BUTTON_C` = **L4** |
| 14 | *(Kishi-Extra)* | — (unbelegt, ROS bindet später) | `KEYCODE_BUTTON_Z` = **R4** |

**Erfasst vs. konsumiert:** `joy_to_twist` **konsumiert** aktuell Achsen 0–7 und Buttons
**0, 1, 2, 4, 5**. **Alle übrigen physischen Kishi-Tasten werden trotzdem gesendet**, nur noch
nicht konsumiert → jederzeit ROS-seitig bindbar **ohne App-Änderung**: Square=`3`, L2/R2=`6`/`7`,
Share/Options/Home=`8`/`9`/`10`, L3/R3=`11`/`12`, L4/R4=`13`/`14`. Damit trägt **jeder** Slot eine
echte Kishi-Taste (keine leeren Slots). Alle Slots müssen im Array existieren, sonst Index-Fehler.

**Regeln:**
- **Sticks negiert** (Kishi hoch/links = −1, PS4-`/joy` erwartet +1).
- **Trigger `1 − 2·t` jeden Frame** (auch idle → +1), sonst steht L2/R2 beim Start
  fälschlich „gedrückt". Kishi meldet Trigger doppelt (`AXIS_BRAKE`/`AXIS_GAS`) → **ignorieren**,
  nur `LTRIGGER`/`RTRIGGER`.
- **Keine App-Deadzone** — `joy_to_twist` filtert (`deadzone 0.10`), App publisht roh ([D3]).
- **Positionsbasierte Face-Buttons:** Kishi ist Xbox-beschriftet (A unten / B rechts / X links /
  Y oben); Zuordnung nach **physischer Position** → Kishi-Y = Triangle (idx 2), Kishi-A = Cross (idx 0).
- ¹ Cross/Show ist roboterseitig aktuell inert (`show_enabled: false` in `ps4_usb.yaml`) —
  Mapping bleibt korrekt für später.
- **Kishi-Extra-Buttons:** L4/R4 = `KEYCODE_BUTTON_C` / `_Z` (nativ HID lesbar, entgegen der
  Web-Vorcheck-Annahme) → **gesendet in `buttons[13]`/`[14]`**, aktuell von `joy_to_twist`
  unkonsumiert, ROS-seitig jederzeit bindbar **ohne App-Änderung**. Konsumenten, die 13/14
  lesen, müssen deren Fehlen tolerieren (PS4-Fallback [NF7] hat sie nicht). Screenshot-Taste
  = Android-System-Taste → out of scope.

**Phase-2-Verifikation (erledigt, echte App + Sim):** (1) Stick-Vorzeichen ok (alle vier
negiert) · (2) D-Pad-X ok (pass-through) · (3) Trigger idle = +1 ok · (4) **D-Pad-Y war
invertiert → App negiert `AXIS_HAT_Y`** (Fix in der App, NICHT `sign_dpad_y`, damit der
PS4-Fallback [NF7] korrekt bleibt). Bewegen + Höhe + Stance end-to-end verifiziert.

> Damit sind Fahren/Drehen/Dead-Man/Slow/Sit-Stand/Stance/Gait/Tempo/Show automatisch
> abgedeckt (alles hängt an `/joy` → `joy_to_twist`).

---

## 2. Bestehende Services (Reuse) — `[E]`

Alle über rosbridge `call_service` aufrufbar. Verifiziert gegen `gait_node.py` /
`hexapod_system.cpp`.

| Service | Typ | Wirkung |
|---|---|---|
| `/hexapod_sit_stand_toggle` | `std_srvs/Trigger` | Sit↔Stand nach State (UI-Intent) |
| `/hexapod_sit_down` | `std_srvs/Trigger` | Hinsetzen (nur STANDING) |
| `/hexapod_stand_up` | `std_srvs/Trigger` | Aufstehen |
| `/hexapod_cycle_stance` | `std_srvs/SetBool` | `data=true` höher / `false` tiefer (nur STANDING) |
| `/hexapod_cycle_gait` | `std_srvs/SetBool` | `true` next / `false` prev Gangart |
| `/hexapod_cycle_tempo` | `std_srvs/SetBool` | `true` schneller / `false` langsamer Tempo-Preset (nur STANDING). **Host = `joy_to_twist`** (Tempo lebt dort). App-Tempo-Dropdown = cycle-to-target via `tempo_idx` aus `/hexapod/tempo`. `[N Ph.5]` |
| `/hexapod_adjust_step_length` | `std_srvs/SetBool` | `true` größer / `false` kleiner (H2: modus-gedeckelt) |
| `/hexapod_show_toggle` | `std_srvs/Trigger` | Show-Pose rein/raus |
| `/hexapod_shutdown` | `std_srvs/Trigger` | Kontrolliertes Hinsetzen + Shutdown-Kette (Block F) |
| `/hexapod_estop` | `std_srvs/Trigger` | **NOT-HALT (App-Ziel, Phase 6)** — gait_node, wirkt **Sim UND HW**: gated den Tick **latched** (kein joint_trajectory-Publish) + ruft intern den Plugin-`/hexapod_safety_freeze` (HW-PWM-Hold). Resumt NICHT von selbst → nur `/hexapod_recover`. `[N Ph.6]` |
| `/hexapod_recover` | `std_srvs/Trigger` | **RECOVERY (App-Ziel, Phase 6)** — gait_node: Plugin-Freeze lösen + gait-Latches/Monitore reset + **Joint-Space-Ramp** aus der eingefrorenen Pose in den Stand ([D6]), ursachen-agnostisch. `[N Ph.6]` |
| `/hexapod_safety_freeze` | `std_srvs/Trigger` | Plugin-Not-Halt (nur HW, hält letzte PWM). **Intern** von `/hexapod_estop` gerufen — **nicht** direkt aus der App (wirkt nicht in Sim). |
| `/hexapod_safety_reset` | `std_srvs/Trigger` | Plugin-Freeze lösen (nur HW). **Intern** von `/hexapod_recover` gerufen. |
| `/hexapod_relay_set` | (Plugin) | Relay schalten (i. d. R. nicht aus der App) |

> **App-Nutzung:** **Not-Halt-Button → `/hexapod_estop`** (NICHT `/hexapod_safety_freeze` —
> das ist der Plugin-Service, wirkt nur auf HW; `/hexapod_estop` wirkt Sim+HW und triggert den
> Plugin intern). **Recover-Button → `/hexapod_recover`** (aktiv wenn `status.safety_frozen`).
> Explizit Sit/Stand-Buttons → die Trigger. Stance/Gait/Tempo laufen **primär über `/joy`**
> (Controller), die direkten Services sind für On-Screen-Buttons optional.

### 2a. Launcher-Services (Block I Phase 3, neu) — `[N Ph.3]`

Vom `bringup_launcher` (Always-On-Schicht in `hexapod_supervisor`, neben rosbridge +
`shutdown_supervisor`). Alle `std_srvs/Trigger` (leerer Request), über rosbridge `call_service`.

| Service | Typ | Wirkung |
|---|---|---|
| `/hexapod_bringup_start` | `std_srvs/Trigger` | schweren Stack starten (Gazebo/HW + gait + `joy_to_twist(app)`); **idempotent** (läuft schon → `success`). Roboter kommt **auf dem Bauch** hoch (SAT, `auto_standup_on_start:=false`) → danach `/hexapod_stand_up`. |
| `/hexapod_bringup_stop` | `std_srvs/Trigger` | Stack sauber stoppen (SIGINT→TERM→KILL, keine Zombies); rosbridge lebt weiter. |
| `/hexapod_bringup_status` | `std_srvs/Trigger` | `message` = `running (pid=…)` / `stopped`. |
| `/hexapod_pi_shutdown` | `std_srvs/Trigger` | **Pi ausschalten** — Stack läuft: kontrolliertes Hinsetzen (Block-F-Kette via internem `/hexapod_request_shutdown`) + guarded Poweroff; idle: direkter guarded Poweroff. **Dev-Host = nur Dry-Run** (dreifacher Guard). App zeigt **Bestätigungs-Dialog**. |

> **App-Lifecycle-Flow:** Verbinden → `/hexapod/bringup_running` + `/hexapod_bringup_status`
> lesen → „Hexapod starten" (`bringup_start`) → „Aufstehen" (`/hexapod_stand_up`) → fahren →
> „Hinsetzen" (`/hexapod_sit_down`) → „stoppen" (`bringup_stop`) → „Pi ausschalten" (Bestätigung
> → `pi_shutdown`).

---

## 3. Bestehende Topics (Reuse) — `[E]`

| Topic | Typ | Richtung | Inhalt |
|---|---|---|---|
| `/imu/data` | `sensor_msgs/Imu` | Roboter → App | Orientierung + Drehraten (Tip-Warnung) |
| `/imu/monitor` | (roll/pitch, Grad-Umrechnung) | Roboter → App | fertige roll/pitch (Overlay-freundlich) |
| `/imu/slope` | `std_msgs/Float64MultiArray` | Roboter → App | Hang-Schätzung [roll°, pitch°] |
| `/foot_contacts` | `std_msgs/Float64MultiArray` | Roboter → App | 6× 0/1 Fußkontakt |
| `/hexapod/shutdown_request` | `std_msgs/Bool` (latched, `transient_local`) | Roboter → App | HW-Shutdown-Schalter gedrückt |
| `/hexapod/shutdown_complete` | `std_msgs/Bool` (latched) | Roboter → App | Shutdown-Sequenz fertig |
| `/hexapod/bringup_running` | `std_msgs/Bool` (latched, `transient_local`) | Roboter → App | läuft der schwere Stack? (Connect-/Start-Screen) `[N Ph.3]` |
| `/cmd_body_height` | (Float) | App → Roboter | Körperhöhe (On-Screen-Slider) |
| `/cmd_show` | `std_msgs/Float64MultiArray[6]` | App → Roboter | Show-Pose-Offsets (falls On-Screen) |
| `/hexapod/play_sound` | `std_msgs/String` | **App → Roboter** | **Soundboard (Phase 7A):** Sound-Key (`sound_01`/`sound_02`/`sound_03`) → spielt sofort auf dem Roboter-Speaker (immer, unabhängig von `sound_enable`). §6b |
| `/hexapod/sound_enabled` | `std_msgs/Bool` (latched, `transient_local`) | **Roboter → App** | **Auto-Sound-Mute-Status (Phase 7A):** aktueller `sound_enable`-Zustand für die „mit/ohne Audio"-Anzeige. §6b |
| `/hexapod/audio_cue` | `std_msgs/String` | gait_node → hexapod_audio | **intern** (nicht App): Bewegungs-Audio-Events. Der Vollständigkeit halber. |

> ⚠️ **Latched Topics** (`shutdown_request/complete`, **`bringup_running`**, **`sound_enabled`**)
> brauchen beim Lesen `reliable + transient_local` QoS ([[project_latched_topic_qos_reliable]]). Über
> rosbridge kommt der gelatchte Wert an — **rosbridge 2.7.0 auto-matcht** die QoS, deterministisch
> per explizitem `qos`-Feld im subscribe-Frame (Details + Frame-Beispiel: §7.4).

---

## 4. Parameter (Reuse via rosbridge param-Ops) — `[E]`

On-Screen-Toggles/Slider setzen `gait_node`-Parameter. Beispiele (vollständige Liste:
[`hexapod_gait/README.md`](../../src/hexapod_gait/README.md) + [`ai_navigation.md`](../../project_architecture/ai_navigation.md)):

- `leveling_enable` (bool), `leveling_mode` (`terrain|horizontal|auto`)
- `adaptive_touchdown_enable`, `adaptive_stand_enable`, `slip_detection_enable` (bool)
- `gait_pattern` (string, **standing_only**), `body_height`/`radial_distance` (**standing_only**)
- `step_height` (H1: modus-gedeckelt), `step_length_max` (H2: modus-gedeckelt)
- **`sound_enable`** (bool, Node **`/hexapod_audio`**, Phase 7A) — Auto-Sounds an/aus; Live-Anzeige
  latched auf `/hexapod/sound_enabled` (§6b)

> ⚠️ **`standing_only`-Params** werden außerhalb STANDING **rejected** — die App muss den
> State kennen (Status-Topic §6) und solche Steller nur im Stand aktiv schalten. Sonst
> `Set parameter failed`.

---

## 5. Video (Kanal 2, separat) — festgezurrt v0.7, präzisiert v0.8 (Phase 4, ROS-Seite live-verifiziert)

**Nicht rosbridge** — eigener HTTP-Stream-Server.

| Feld | Wert |
|---|---|
| **Protokoll (Erstwurf)** | **MJPEG** über `web_video_server` (`ros-jazzy-web-video-server`, Stock-Paket). Latenz ~100–300 ms (NF4-Erstwurf); Upgrade RTSP/H.264/WebRTC später. |
| **Port** | **8080** (getrennt von rosbridge 9090). |
| **Host** | **Gleiche IP wie rosbridge** (§0), **nur Port 8080** statt 9090 (Sim `Desktop-IP:8080` / real `Pi-IP:8080`). Die App leitet die Video-URL aus derselben Host-Eingabe ab wie die WebSocket-URL. |
| **Image-Topic** | **`/camera/image_raw`** (`sensor_msgs/Image`). |
| **Bildquelle** | Sim = Gazebo-Kamera-Sensor (vorne oben am Body, geradeaus); **real** = Raspi-Cam v1.3 (Pi, Phase 7) → **gleiches Topic**, Stream-Server + App **unverändert**. |
| **URL-Schema** | `http://<host>:8080/stream?topic=/camera/image_raw&type=mjpeg` (Snapshot gestrichen). Das ist die **rohe** MJPEG-URL (`multipart/x-mixed-replace`), die die App direkt lädt — **live gegen den Server verifiziert**. Die Index-Seite `http://<host>:8080/` (Topic-Liste, `stream_viewer`) ist nur ein HTML-Wrapper zum manuellen Testen. |
| **Auflösung/FPS** | 16:9, 1280×720, Sensor `update_rate` 15; **live gemessen ~11 Hz** (Render-Jitter der gz-Sensors unter Last; für v1 „folgbar", NF4-ok, final justierbar). App zeigt **center-crop-to-fill** (Phone 19,5:9 → kein schwarzer Balken, minimaler Beschnitt; späterer In-App-Zoom optional). |
| **Verfügbarkeit** | Der Stream-Server (`web_video_server`) läuft **im On-Demand-Stack** (`sim.launch.py`, kommt mit `bringup_start`) → Port 8080 ist **erst nach `/hexapod_bringup_start`** offen (davor Connection-refused). **App: Kamera-View an `/hexapod/bringup_running` koppeln** — keinen Stream laden/anzeigen, solange `false` (sonst Fehlbild/Timeout beim Connect). |
| **Kamera an/aus** | **Phase 4 app-seitig** (App fordert Stream an / stoppt ihn = MJPEG-URL laden/entladen). ROS-Node-Start/Stop (Strom/Wärme) = **Pi/Phase 7** — `camera_enable`-Service/Param **reserviert** (§6). |

---

## 6. Neu zu bauende Schnittstellen — `[TBD]`

Diese werden beim Bau der jeweiligen Phase hier mit Typ/Feldern festgezurrt.

| Schnittstelle | Zweck | Phase |
|---|---|---|
| Launcher: `bringup_start`/`_stop`/`_status` | schweren Stack starten/stoppen/Status | **✅ erledigt (v0.5, §2a)** |
| Launcher: `pi_shutdown` + `/hexapod/bringup_running` | Pi ausschalten (guarded) + Stack-State | **✅ erledigt (v0.5, §2a/§3)** |
| **Status/Capabilities/Manifest/Alerts** | Overlay-Live-Daten + Config-Panel-Naht | **✅ erledigt (v0.9, §6a)** |
| **Set-Stance direkt** | Stance-Modus direkt wählen (Touch-Dropdown) | **✅ erledigt (v0.9, §6a)** — App cyclet `/hexapod_cycle_stance` zum Ziel |
| **Kamera an/aus** (`camera_enable`) | Kamera-Node am Pi starten/stoppen (Strom/Wärme); in Sim app-seitig | `[TBD-Phase 7]` |
| **E-Stop** (`/hexapod_estop`) | App-Not-Halt, latched Freeze Sim+HW | **✅ erledigt (v0.10, §2)** |
| **Recovery-Service** (`/hexapod_recover`) | Freeze → Joint-Space-Ramp → Stand ([D6](decisions.md)) | **✅ erledigt (v0.10, §2)** |
| Audio: `play_sound` + Param `sound_enable` | Sound-Trigger + Mute ([D5](decisions.md)) | **✅ erledigt (v0.11, §6b)** |

---

## 6a. Status / Config / Alerts (Block I Phase 5) — festgezurrt v0.9

**Alle vier Topics = `std_msgs/String` mit JSON-Payload** (einziger Consumer = App über rosbridge,
dort ohnehin JSON; kein neues Message-Paket, [D-neu]). Feld-Formen ROS-seitig **live-verifiziert**.

**`/hexapod/status`** — Live-Zustand fürs Overlay. Quelle **`gait_node`** (nur im laufenden Stack),
**~5 Hz**, nicht latched.
```json
{"state":"STANDING","stance_idx":1,"stance":"mittel","gait":"tripod",
 "safety_frozen":false,"tip":"none","step_height_cap":0.05,"step_length_cap":0.08}
```
| Feld | Typ | Werte |
|---|---|---|
| `state` | string | `STARTUP_RAMP`/`CARTESIAN_STANDUP`/`REPOSITION`/`STANDING`/`WALKING`/`STOPPING`/`SAT`/Sitdown-/Show-States |
| `stance_idx` / `stance` | int / string | 0/1/2 · `tief`/`mittel`/`hoch` |
| `gait` | string | `tripod`/`wave`/`tetrapod`/`ripple` |
| `safety_frozen` | bool | true nach Safety-Freeze/E-Stop; **latched** bis `/hexapod_recover` (Phase 6) |
| `tip` | string | `none`/`warn`/`crit` |
| `step_height_cap` / `step_length_cap` | float | **dynamischer H1/H2-Cap des aktuellen Stance** → App klemmt die Slider auf `min(manifest.max, cap)` |

**`/hexapod/tempo`** — aktives Tempo-Preset. Quelle **`joy_to_twist`**, **latched** (transient_local).
```json
{"tempo":"schnell","tempo_idx":2,"linear_x_scale":0.05,"linear_y_scale":0.05,"angular_z_scale":0.46}
```

**`/hexapod/capabilities`** — statische Enums für die Dropdowns. Quelle **`hmi_status`** (Always-On),
**latched**.
```json
{"gaits":["tripod","wave","tetrapod","ripple"],"stance_modes":["tief","mittel","hoch"],
 "tempo_presets":["langsam","mittel","schnell","aggressiv"]}
```

**`/hexapod/config_manifest`** — die kuratierte Whitelist der verstellbaren Params (Config-Panel).
Quelle **`hmi_status`** (Always-On), **latched**. Die App rendert das Panel **generisch**; get/set der
Werte über die **nativen rosbridge-Parameter-Services** (`/<node>/get_parameters` /`set_parameters`).
```json
{"version":1,"params":[
  {"node":"/gait_node","param":"step_height","group":"Lauf / Gang","label":"Fuß-Hub",
   "hint":"größer = höher","widget":"slider","type":"double","default":0.05,"min":0.01,
   "max":0.09,"step":0.005,"unit":"m","dynamic_cap":"step_height_cap"}, … ]}
```
Feld je Param: `node`,`param`,`group`,`label`,`hint`,`widget`(`slider`/`toggle`/`dropdown`),`type`,
`default`; slider zusätzlich `min`/`max`/`step`(+`unit`); dropdown `options`; optional `gating:"standing"`
(App disabled außerhalb STANDING), `dynamic_cap:"<status-feld>"`, `advanced:true` (eingeklappt). v1 =
**39 Params** (23 sichtbar + 16 Balance-Gains advanced).
> **App-Pflichten:** (1) `gating:"standing"` → Slider aus wenn `status.state != STANDING`; (2)
> `dynamic_cap` → max auf `status[cap]` klemmen; (3) `set_parameters`-Antwort `successful=false` →
> `reason`-String als Fehler zeigen (der gait_node liefert Klartext, z.B. Cap-/Standing-Reject).

**`/hexapod/alerts`** — WARN/ERROR/FATAL aus `/rosout`. Quelle **`hmi_status`** (Always-On), **latched
mit Historie** (Default 50, `alerts_history`-Param) → späte Subscriber bekommen die letzten N. Ein
Alert pro Nachricht:
```json
{"stamp":1784399508.45,"level":"WARN","name":"gait_node","msg":"…"}
```

**Set-Stance direkt** — **kein neues ROS-Interface**: die App liest `status.stance_idx` und ruft das
bestehende **`/hexapod_cycle_stance`** (`std_srvs/SetBool`, `data=true` höher / `false` tiefer) so oft,
bis der Ziel-Index erreicht ist (standing_only bleibt serverseitig geprüft).

**Set-Tempo direkt** (v0.9.1) — analog: die App liest `tempo.tempo_idx` (aus `/hexapod/tempo`) und
ruft **`/hexapod_cycle_tempo`** (`std_srvs/SetBool`, `true` schneller / `false` langsamer) bis zum
Ziel-Index. `success=false` = blockiert (läuft noch / nicht STANDING) → nächsten Schritt erst nach
`/hexapod/tempo`-Update. Der Tempo-Wechsel ist standing_only (setzt `cycle_time`) → außerhalb STANDING
lehnt der gait_node ab, `_cycle_tempo` bricht sauber ab.

> **Verfügbarkeit:** `capabilities`/`config_manifest`/`alerts` laufen in der **Always-On-Schicht**
> (`hmi_status`) → schon **beim App-Connect** da, vor dem On-Demand-Stack. `status`/`tempo` kommen aus
> dem Stack (gait_node/joy_to_twist) → erst nach `bringup_start`.

---

## 6b. Audio (Block I Phase 7A) — festgezurrt v0.11

**Sound spielt NUR auf dem Roboter-Speaker** (MAX98357A), nie am Handy ([D5]). Der `hexapod_audio`-Node
(Pi, im On-Demand-Stack) spielt kurze mp3s. Zwei App-relevante Nähte + ein interner Cue:

**Manuelle Sounds (Soundboard)** — `/hexapod/play_sound` (`std_msgs/String`, App → Roboter):
die App **publisht** einen Key, der Node spielt die gemappte mp3 **sofort** (ein neuer Sound bricht den
laufenden ab). Keys v1: `sound_01` / `sound_02` / `sound_03`. Spielen **immer** — unabhängig von
`sound_enable`.
```json
// rosbridge publish auf /hexapod/play_sound:
{"op":"publish","topic":"/hexapod/play_sound","msg":{"data":"sound_01"}}
```

**Auto-Sounds + Mute** — bei Bewegungs-Ereignissen spielt der Node automatisch:
`sound_aufstehen` (Aufstehen vom Boden) · `sound_hinsetzen` (Hinsetzen) · `sound_repositioning`
(Höhenwechsel/Stance-Switch) · `sound_freeze` (Safety-Freeze/E-Stop). **Recovery-Aufstehen ist
stumm.** Diese Auto-Sounds werden über den **Param `sound_enable`** (bool) auf dem Node
**`/hexapod_audio`** gemutet:
- **Setzen** (App): native rosbridge-`set_parameters` auf `/hexapod_audio` (wie das Config-Panel §6a) —
  die zwei Buttons „**Fahren mit Audio**" (`true`) / „**Fahren ohne Audio**" (`false`) beim Übergang
  Verbinden→Fahren, plus ein Zuschalt-Toggle im Fahr-Modus.
- **Lesen** (App): **`/hexapod/sound_enabled`** (`std_msgs/Bool`, **latched** `transient_local`) —
  der aktuelle Mute-Zustand für die Toggle-Anzeige (kommt sofort beim Subscribe).

**Intern (nicht App):** `/hexapod/audio_cue` (`std_msgs/String`, gait_node → hexapod_audio) trägt die
Bewegungs-Events; die App nutzt es nicht.

> **Verfügbarkeit:** `hexapod_audio` läuft im **On-Demand-Stack** (mit `gait_node`) → `play_sound` +
> `sound_enabled` sind **nach `/hexapod_bringup_start`** da (wie `/hexapod/status`; **nicht** schon
> beim Connect wie die Always-On-Config-Topics). `sound_enable` live-toggelbar. In Sim läuft der Node
> **log-only** (kein Speaker) — die App-Nähte sind identisch.

**rosbridge-Frames (kopierbar):**
```jsonc
// (a) Soundboard-Button — advertise EINMAL, dann publish je Tap (RELIABLE-Default genügt):
{"op":"advertise","topic":"/hexapod/play_sound","type":"std_msgs/msg/String"}
{"op":"publish","topic":"/hexapod/play_sound","msg":{"data":"sound_01"}}

// (b) "Fahren mit/ohne Audio" + Toggle — sound_enable (BOOL) setzen (type 1 = PARAMETER_BOOL):
{"op":"call_service","service":"/hexapod_audio/set_parameters",
 "type":"rcl_interfaces/srv/SetParameters",
 "args":{"parameters":[{"name":"sound_enable",
   "value":{"type":1,"bool_value":false}}]}}
// Antwort: results[0].successful == true.

// (c) Mute-Status lesen — latched Bool (deterministisch mit explizitem qos):
{"op":"subscribe","topic":"/hexapod/sound_enabled","type":"std_msgs/msg/Bool",
 "qos":{"history":"keep_last","depth":1,"durability":"transient_local","reliability":"reliable"}}
// -> msg.data (true = Auto-Sounds an). Kommt sofort beim Subscribe (gelatcht), sofern der
//    On-Demand-Stack läuft.
```
> **App-Pflichten:** (1) Audio-Buttons erst aktiv, wenn der Stack läuft (`bringup_running`), sonst
> gibt es `/hexapod_audio` noch nicht. (2) Der Zuschalt-Toggle spiegelt `sound_enabled` (nicht den
> eigenen Button-State raten) — der Roboter ist die Wahrheit. (3) `set_parameters`-Antwort
> `successful=false` → Fehler zeigen (sollte hier nicht vorkommen; `sound_enable` ist immer setzbar).

---

## 7. Offene Interface-Fragen (bei Phasen-Bau zu klären)

1. **`/joy`-Index-Tabelle** Kishi-Roh → PS4-Layout — **erledigt (v0.2, §1)**. Offen bleibt nur
   die Vorzeichen-Endverifikation via `ros2 topic echo /joy` in Phase 2.
2. **rosbridge-Auth/Port** — Default 9090, unauth; für Hotspot ok.
3. **Status-Topic-Format** — **entschieden (v0.9): JSON-String** (`std_msgs/String`). Einziger
   Consumer = App über rosbridge (dort ohnehin JSON), kein neues Message-Paket, leicht erweiterbar.
   Config/min-max lebt im Parameter-System (Manifest + native Param-Services), 3D-Viz an
   `/joint_states` — die drei Kanäle sind getrennt (§6a). Upgrade auf Custom-`.msg` möglich, falls
   je ein ROS-nativer Consumer dazukommt.
4. **Latched/QoS über rosbridge** — **geklärt (v0.6, aus rosbridge-2.7.0-Quellcode; kein
   ROS-Change nötig).** rosbridge **auto-matcht** die Subscriber-QoS an einen
   `transient_local`-Publisher (`subscribers.py::_get_default_qos_profile`: findet es einen
   TRANSIENT_LOCAL-Publisher, subscribed es selbst TRANSIENT_LOCAL+RELIABLE) → der **gelatchte
   Wert kommt beim (späten) Subscribe sofort**, sofern der Publisher schon existiert (bei uns:
   `bringup_launcher` always-on ⇒ immer gegeben). Die QoS wird pro Topic **einmalig beim ersten
   Subscriber** fixiert (Timing-Abhängigkeit nur im Auto-Modus). **Deterministisch + empfohlen:**
   explizites `qos` im subscribe-Frame:
   `{"op":"subscribe","topic":"/hexapod/bringup_running","type":"std_msgs/msg/Bool","qos":{"history":"keep_last","depth":1,"durability":"transient_local","reliability":"reliable"}}`
   (`subscribe.py` liest das `qos`-Feld → `qos_extraction.extract_qos_profile`). Empirische
   Bestätigung folgt in der ersten Integration.
5. **Bringup-Lifecycle-Rückmeldung** — **erledigt (v0.5)**: `bringup_start/stop` liefern
   Trigger-`success`+`message` (synchron), der laufende Zustand kommt zusätzlich als latched
   `/hexapod/bringup_running` (Bool) für den Connect-Screen. „Roboter steht" (vs. nur „Stack
   läuft") kommt später über das Status-Topic (Phase 5).
