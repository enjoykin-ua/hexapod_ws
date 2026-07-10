# Anforderungen — Mobile Teleop / HMI (Block I)

> **Das „was es können muss".** Funktionale Anforderungen gruppiert nach Ort der
> Bedienung (**Controller-Taste** / **Touch-Screen** / **Overlay-Anzeige**), mit
> Must/Nice-Priorität und der ROS-Anbindung (welches Topic/Service). Danach die
> nicht-funktionalen Anforderungen + explizite Nicht-Ziele.
>
> Spalte **ROS-Anbindung:** `[E]` = existiert bereits (wiederverwendet), `[N]` = neu
> zu bauen. Details/Typen in [`interface_contract.md`](interface_contract.md).

---

## 1. Steuerung — bleibt auf dem physischen Controller (Kishi)

> **Entscheidung (User):** die Roboter-**Bewegung** bleibt komplett auf dem Controller
> (wie heute PS4), inkl. Dead-Man-Schalter — NICHT auf den Touch-Screen. Alle diese
> Eingaben fließen über `sensor_msgs/Joy` → bestehendes `joy_to_twist` ([D3](decisions.md)).

| Funktion | Eingabe (Kishi) | Prio | ROS-Anbindung |
|---|---|---|---|
| Laufen (vor/zurück/seitlich) | linker Stick | Must | `/joy` → `/cmd_vel` [E] |
| Drehen (Yaw) | rechter Stick | Must | `/joy` → `/cmd_vel` [E] |
| **Dead-Man** (Bewegung nur bei gehalten) | Schulter-Taste (R1) | Must | `/joy` (Button) [E] |
| Langsam-Modus | Schulter-Taste (L1) | Must | `/joy` (Button) [E] |
| Stance-Höhe hoch/tief | L2/R2 (ohne R1) | Must | `/joy` → `/hexapod_cycle_stance` [E] |
| Gangart prev/next | D-Pad ←/→ | Should | `/joy` → `/hexapod_cycle_gait` [E] |
| Tempo schneller/langsamer (H2) | D-Pad ↑/↓ | Should | `/joy` (Tempo-Presets, H2) [E] |
| Sit/Stand-Toggle | Face-Button | Must | `/joy` → `/hexapod_sit_stand_toggle` [E] |
| Show-Pose-Toggle | Face-Button | Nice | `/joy` → `/hexapod_show_toggle` [E] |

> **Kern-Prinzip:** Die App **normalisiert** die Kishi-Eingaben auf das PS4-Achsen-/
> Button-Layout und publisht `sensor_msgs/Joy`. Damit bleibt die Roboter-Config
> (`ps4_usb.yaml`) **unverändert**, und die controller-spezifische Zuordnung lebt in der
> App (= wo auch die Portabilitäts-Profile liegen, [D8](decisions.md)).

---

## 2. Konfiguration — auf dem Touch-Screen (der Mehrwert ggü. PS4)

> Alles, was heute `ros2 param set` im Terminal ist, wird On-Screen (Slider/Toggle/Liste).
> Direkte rosbridge-Service-/Param-Calls, NICHT über `/joy`.

| Funktion | Bedienung (Screen) | Prio | ROS-Anbindung |
|---|---|---|---|
| Gangart aus Liste wählen | Dropdown/Liste | Should | Param `gait_pattern` (STANDING) [E] |
| Stance-Modus explizit wählen | Segment/Buttons | Nice | `/hexapod_cycle_stance` bzw. Param [E] |
| Tempo-Preset wählen | Segment (aggr/schnell/mittel/langsam) | Nice | H2-Tempo (cycle_time+scales) [E] |
| Körperhöhe fein | Slider | Nice | `/cmd_body_height` [E] |
| Leveling an/aus + Modus | Toggle + Segment | Should | Params `leveling_enable`/`leveling_mode` [E] |
| Adaptiver Touchdown an/aus | Toggle | Should | Param `adaptive_touchdown_enable` [E] |
| Slip-Schutz / Adaptive Stand an/aus | Toggle | Nice | Params `slip_detection_enable`/`adaptive_stand_enable` [E] |
| Preset laden (hw_terrain etc.) | Liste | Nice | (Launcher / Param-Batch) [N] |

> **Vorbedingung Phase 5:** viele dieser Params sind live setzbar (Block-C/H-Arbeit),
> andere sind `standing_only` — die App muss den State kennen (Status-Topic, §3) und
> `standing_only`-Steller nur im Stand aktiv schalten (sonst Reject).

---

## 3. Anzeige — Status-Overlay über dem Video

> Semi-transparent über dem Kamera-Bild (DJI-Style). Braucht Status-Topics, die teils
> noch nicht existieren → **Status-Publisher** (ROS-seitig, Phase 5).

| Anzeige | Quelle | Prio | ROS-Anbindung |
|---|---|---|---|
| Verbindungsstatus (rosbridge / Bringup) | App-intern + Launcher | Must | WebSocket-State + [N] |
| Kipp-Winkel / Tip-Warnung | IMU | Must | `/imu/data` bzw. `/imu/monitor` [E] |
| Aktueller Stance-Modus | gait_node-State | Should | Status-Topic [N] (heute nur intern `_stance_idx`) |
| Gangart / Tempo | gait_node-State | Should | Status-Topic [N] |
| Walking/Standing/Sitting-State | gait_node-State | Should | Status-Topic [N] |
| Safety-State (Freeze aktiv?) | Freeze-Latch | Must | Status-Topic [N] |
| Batterie (Spannung/%) | Block D3 (geplant) | Nice | Telemetrie-Topic [N, hängt an D3] |
| Fußkontakte (6×) | Kontakt-Pipeline | Nice | `/foot_contacts` [E] |

---

## 4. Lifecycle + Aktionen — On-Screen-Buttons

| Funktion | Bedienung | Prio | ROS-Anbindung |
|---|---|---|---|
| **Verbinden** (App → rosbridge) | Button (Startscreen) | Must | WebSocket-Connect [N-App] |
| **Hexapod starten** (Bringup) | Button | Must | Launcher `bringup_start` [N] |
| Hexapod stoppen (Bringup aus) | Button | Should | Launcher `bringup_stop` [N] |
| **Pi herunterfahren** (mit Bestätigung) | Button | Must | Launcher `shutdown` / `/hexapod_shutdown` [E/N] |
| **NOT-HALT** (prominent) | großer roter Button | Must | `/hexapod_safety_freeze` [E] |
| **Recovery** (Freeze → Stand) | Button | Should | Recovery-Service [N] |
| Aufstehen / Hinsetzen (explizit) | Buttons | Nice | `/hexapod_stand_up` / `/hexapod_sit_down` [E] |
| Kamera an/aus | Toggle | Should | Stream-Server-Steuerung [N] |
| Sound abspielen (Soundboard) | Buttons | Nice | `hexapod_audio` [N, Phase 7] |
| Auto-Sounds an/aus (Mute) | Toggle | Nice | Param `sound_enable` [N, Phase 7] |

---

## 5. Nicht-funktionale Anforderungen

| # | Anforderung | Begründung |
|---|---|---|
| NF1 | **Comms-Loss-Safety:** App publisht `/joy` **stetig** (~30 Hz), auch bei neutralen Sticks. Bricht App/WLAN/Screen weg → `/joy` stoppt → `cmd_vel_timeout` → B1-Fail-safe. | Screen-Lock/Absturz = Roboter stoppt (gewünscht). Nutzt bestehendes Timeout. |
| NF2 | **Dead-Man physisch:** Bewegung nur bei gehaltener Schulter-Taste. Kein Touch-Ersatz. | Sicherheit; Touch kann „halten" schlecht. |
| NF3 | **Latenz Steuerung:** `/joy` über WebSocket @ ~30 Hz, spürbar verzögerungsfrei. | Teleop eines laufenden Roboters. |
| NF4 | **Latenz Video:** akzeptabel zum Folgen (MJPEG ~100–200 ms Erstwurf; später RTSP/WebRTC < 100 ms). | Nicht kritisch wie Steuerung, aber nutzbar. |
| NF5 | **Portabilität Controller:** Controller-Wechsel = neues **Profil** (JSON, Achsen/Button-Indizes → abstrakte Actions), kein App-Umbau. | User-Anforderung: „nicht plug&play, aber geringer Aufwand". |
| NF6 | **Netz ohne Internet/Multicast:** funktioniert über Handy-Hotspot (SIM-los), rosbridge = Unicast-TCP. | Kein DDS-Multicast-Problem. |
| NF7 | **PS4-Fallback:** der PS4-Controller bleibt als alternative `/joy`-Quelle nutzbar (einer nach dem anderen, nicht gleichzeitig). | De-Risk während Umstellung. |
| NF8 | **Robustheit Reconnect:** WLAN-Aussetzer → App verbindet automatisch neu, Roboter bleibt sicher (NF1). | Feldtauglichkeit. |
| NF9 | **Interface stabil + versioniert:** Änderungen an der Naht laufen über `interface_contract.md` (Version/Changelog). | Zwei-Repo-Entwicklung ([D9](decisions.md)). |

---

## 6. Explizite Nicht-Ziele (out of scope)

- **Kein ROS auf dem Handy** (rosbridge statt rclandroid). [D2]
- **Kein RViz** — die App ersetzt den Debug-View für den Feldbetrieb; RViz bleibt Desktop-Werkzeug.
- **Kein Video über rosbridge** (eigener Stream-Kanal). [D2]
- **Keine Bewegungssteuerung auf dem Touch-Screen** (User-Entscheid: nur Controller). [§1]
- **Keine Autonomie/Navigation** — reine Teleop + Konfiguration + Anzeige.
- **Kamera-SW-Details (Bildverarbeitung)** — hier nur der Live-Stream; Vision separat, später.
- **Auth/Security härten** — privater Hotspot mit eigenen Geräten; nicht ins Internet hängen (bewusst simpel). [D2]
