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
| **v0.1** (aktuell) | Gerüst. Bestandsaufnahme der wiederverwendbaren ROS-Schnittstellen + Platzhalter für die neu zu bauenden. Noch nichts implementiert. |

---

## 0. Transport

- **Kanal 1 (Steuerung/Status):** WebSocket → `rosbridge_server` (Standard-Port **9090**),
  JSON. App-Client: `OkHttp`-WebSocket + rosbridge-Protokoll (`op: publish/subscribe/
  call_service`), analog roslibjs.
- **Kanal 2 (Video):** eigener Stream-Server (MJPEG/RTSP/WebRTC), **nicht** hier — nur ein
  Verweis unter §5.
- **Adressierung:** feste Pi-IP im Hotspot-Range ([D4](decisions.md)) + Port 9090.

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

**Verbindliches Layout:** die exakten Achsen-/Button-Indizes = die aus
[`ps4_usb.yaml`](../../src/hexapod_teleop/config/ps4_usb.yaml) (`axis_*`, `*_button`,
`axis_dpad_x/y`). Die App muss die **Kishi-Rohindizes** (in Phase 1 ermittelt) auf **diese
PS4-Indizes** abbilden. → Wird in **Phase 2** als konkrete Index-Tabelle hier eingetragen
`[TBD-Phase 2]`.

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
| `/hexapod_adjust_step_length` | `std_srvs/SetBool` | `true` größer / `false` kleiner (H2: modus-gedeckelt) |
| `/hexapod_show_toggle` | `std_srvs/Trigger` | Show-Pose rein/raus |
| `/hexapod_shutdown` | `std_srvs/Trigger` | Kontrolliertes Hinsetzen + Shutdown-Kette (Block F) |
| `/hexapod_safety_freeze` | `std_srvs/Trigger` | **NOT-HALT** — Plugin hält letzte PWM |
| `/hexapod_safety_reset` | `std_srvs/Trigger` | Plugin-Freeze lösen (Teil von Recovery) |
| `/hexapod_relay_set` | (Plugin) | Relay schalten (i. d. R. nicht aus der App) |

> **App-Nutzung:** Not-Halt-Button → `/hexapod_safety_freeze`. Explizit Sit/Stand-Buttons →
> die Trigger. Stance/Gait/Tempo laufen **primär über `/joy`** (Controller), die direkten
> Services sind für On-Screen-Buttons optional.

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
| `/cmd_body_height` | (Float) | App → Roboter | Körperhöhe (On-Screen-Slider) |
| `/cmd_show` | `std_msgs/Float64MultiArray[6]` | App → Roboter | Show-Pose-Offsets (falls On-Screen) |

> ⚠️ **Latched Topics** (`shutdown_request/complete`) brauchen beim Lesen
> `reliable + transient_local` QoS ([[project_latched_topic_qos_reliable]]) — rosbridge/
> App-Subscribe entsprechend konfigurieren.

---

## 4. Parameter (Reuse via rosbridge param-Ops) — `[E]`

On-Screen-Toggles/Slider setzen `gait_node`-Parameter. Beispiele (vollständige Liste:
[`hexapod_gait/README.md`](../../src/hexapod_gait/README.md) + [`ai_navigation.md`](../../project_architecture/ai_navigation.md)):

- `leveling_enable` (bool), `leveling_mode` (`terrain|horizontal|auto`)
- `adaptive_touchdown_enable`, `adaptive_stand_enable`, `slip_detection_enable` (bool)
- `gait_pattern` (string, **standing_only**), `body_height`/`radial_distance` (**standing_only**)
- `step_height` (H1: modus-gedeckelt), `step_length_max` (H2: modus-gedeckelt)

> ⚠️ **`standing_only`-Params** werden außerhalb STANDING **rejected** — die App muss den
> State kennen (Status-Topic §6) und solche Steller nur im Stand aktiv schalten. Sonst
> `Set parameter failed`.

---

## 5. Video (Kanal 2, separat) — `[TBD-Phase 4]`

**Nicht rosbridge.** Ein Stream-Server auf dem Pi (Kandidaten: MJPEG als Erstwurf, später
RTSP/H.264 oder WebRTC). Festzulegen in Phase 4:
- Protokoll + Port + URL-Schema
- Steuerung Kamera an/aus (rosbridge-Service ODER Stream-Server-Endpoint)
- Auflösung/FPS/Codec

---

## 6. Neu zu bauende Schnittstellen — `[TBD]`

Diese werden beim Bau der jeweiligen Phase hier mit Typ/Feldern festgezurrt.

| Schnittstelle | Zweck | Phase |
|---|---|---|
| Launcher: `bringup_start` / `bringup_stop` | schweren Gait-/HW-Stack starten/stoppen | `[TBD-Phase 3]` |
| Launcher: `shutdown` | Pi herunterfahren (mit Guard, Block F) | `[TBD-Phase 3]` |
| Launcher: Status (läuft der Stack?) | für den Connect-/Start-Screen | `[TBD-Phase 3]` |
| **Status-Topic** (`hexapod_status`) | kompakt: State, Stance-Modus, Gangart, Tempo, Safety-State, (Batterie) fürs Overlay | `[TBD-Phase 5]` |
| Recovery-Service | Freeze → Joint-Space-Ramp → Stand ([D6](decisions.md)) | `[TBD-Phase 6]` |
| Audio: `play_sound` + Param `sound_enable` | Sound-Trigger + Mute ([D5](decisions.md)) | `[TBD-Phase 7]` |

> **Design-Hinweis Status-Topic:** heute liegt z. B. der Stance-Modus nur als `_stance_idx`
> **intern** im gait_node (nicht publiziert). Das Overlay braucht ein **kompaktes, eigenes
> Status-Topic** — die zentrale neue ROS-Arbeit für die Anzeige.

---

## 7. Offene Interface-Fragen (bei Phasen-Bau zu klären)

1. **`/joy`-Index-Tabelle** Kishi-Roh → PS4-Layout (Phase 1 liefert die Roh-Indizes, Phase 2
   fixiert die Abbildung).
2. **rosbridge-Auth/Port** — Default 9090, unauth; für Hotspot ok.
3. **Status-Topic-Format** — ein Custom-Msg-Typ vs. `DiagnosticArray` vs. JSON-String.
   Custom-Msg ist sauberer, aber ein neues Message-Paket; JSON-String pragmatischer für die
   App. In Phase 5 entscheiden.
4. **Latched/QoS über rosbridge** — verifizieren, dass `transient_local` sauber durch
   rosbridge zur App kommt.
5. **Bringup-Lifecycle-Rückmeldung** — wie meldet der Launcher „Stack läuft / gestartet /
   Fehler" an die App (Service-Response vs. Status-Topic).
