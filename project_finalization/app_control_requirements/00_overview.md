# Block I — Mobile Teleop / HMI (Handy + Controller-Steuerung)

> **Master-/Einstiegs-Dokument.** Ersetzt die PS4-Bluetooth-Steuerung durch ein
> **Handy in einem Gamepad-Halter** (Razer Kishi V2) mit **Touch-Bildschirm + Kamera-
> Live-Bild** — Steuerung wie beim PS4, plus On-Screen-Konfiguration, Status-Overlay,
> Kamera-Stream, Sound und Lifecycle (Bringup/Shutdown/Recovery) aus der App.
>
> **Status: 🟡 Anforderungs-/Architektur-Phase.** Noch kein Code. Branch: separater
> Feature-Branch (User entscheidet). Arbeitsweise CLAUDE.md §4 (Plan → Freigabe → Code →
> Tests → Self-Review), §5 (Agent macht NIE git). Deutsch durchgehend.

---

## 0. Wozu das Ganze

Heute: PS4-DualShock über Bluetooth → `joy_node` am Pi → `/joy` → `joy_to_twist` → `/cmd_vel`.
Funktioniert (Block C), aber: **kein Bildschirm** → alle Feineinstellungen laufen über
`ros2 param set` im Terminal, kein Kamera-Bild, kein Status, kein Sound-Trigger, kein
Bringup/Shutdown aus der Hand.

Ziel: **ein Gerät in der Hand**, das den Roboter fährt (physische Sticks/Tasten wie PS4)
UND als Bildschirm alles zeigt/verstellt, was heute Terminal-Arbeit ist — Vorbild:
DJI-Drohne (Controller + Handy-Halter, Video-Vollbild, Menüs als Overlay).

**Zwei bereits verbaute, aber noch nicht integrierte Roboter-Komponenten** werden hier
angebunden:
- **Raspi-Cam v1.3** (HW-funktionsgeprüft) → Live-Video in die App.
- **Speaker** (HW-funktionsgeprüft, mp3 per CLI abgespielt) → Sound-Trigger aus der App
  (spätere ROS-Integration, hier zunächst zweitrangig).

---

## 1. Architektur-Übersicht (das Gesamtbild)

```
   ┌─────────────────────── Handy (Samsung S22+, SIM-los) ──────────────────────┐
   │                                                                             │
   │   Razer Kishi V2  ──USB-HID──►  Native Android-App (Kotlin)                 │
   │   (Sticks/Tasten)               ├─ liest Gamepad (InputManager)             │
   │                                 ├─ Touch-UI (Parameter, Menüs)              │
   │                                 ├─ Video-Vollbild + Status-Overlay          │
   │                                 └─ ist zugleich WLAN-HOTSPOT (Variante A)   │
   └───────────┬───────────────────────────────────────────┬─────────────────────┘
               │  WLAN (lokaler Hotspot, kein Internet)     │
    ┌──────────▼──────────────┐                   ┌─────────▼──────────────┐
    │ Kanal 1: STEUERUNG/STATUS│                   │ Kanal 2: VIDEO         │
    │ WebSocket → rosbridge     │                   │ eigener Stream-Server  │
    │ (JSON, Unicast-TCP)       │                   │ (MJPEG/RTSP/WebRTC)    │
    └──────────┬──────────────┘                   └─────────┬──────────────┘
   ┌───────────▼─────────────────────── Raspberry Pi 5 ─────▼──────────────────┐
   │  ALWAYS-ON (systemd, ab Boot):  rosbridge_server + Launcher-Node           │
   │  ON-DEMAND (per App gestartet): gait_node + hexapod_hardware + …           │
   │  App publisht sensor_msgs/Joy  →  joy_to_twist  →  /cmd_vel  (unverändert!) │
   └───────────────────────────────────────────────────────────────────────────┘
```

**Die fünf tragenden Entscheidungen** (Details in [`decisions.md`](decisions.md)):

1. **Native Android-App** (Kotlin), nicht Web-PWA — robuster Hardware-Zugriff
   (Gamepad/Video/Vollbild), passt zum Embedded-Hintergrund. (D1)
2. **rosbridge als Naht:** die App spricht WebSocket+JSON mit `rosbridge_server`; **kein
   ROS auf dem Handy**. Diese Naht ist bei native ODER web identisch → Entscheidung
   isoliert. Bonus: Unicast-TCP umgeht das frühere DDS-Multicast-Problem am Hotspot. (D2)
3. **`/joy`-Reuse:** die App emuliert einen Joystick (publisht `sensor_msgs/Joy`) → die
   **komplette bestehende `joy_to_twist`-Kette** (Deadzone, Scaling, Dead-Man, Sit/Stand,
   Stance, Gait, Tempo, Show) läuft **unverändert**. Kein neuer Steuer-Code am Roboter. (D3)
4. **Video getrennt von rosbridge** (eigener Stream-Server) — rosbridge ist für Video
   ungeeignet (base64-JSON). (D2)
5. **Zweistufiger Start:** Always-On-Schicht (rosbridge + Launcher) ab Boot; der schwere
   Gait-/HW-Stack wird **on demand** aus der App gestartet. (D7)

---

## 2. Phasen-Roadmap

> **§4-Prinzip:** Detaillierte plan/progress/test_commands je Phase entstehen **direkt vor**
> der Umsetzung der Phase, nicht alles vorab. Hier nur die Roadmap.

| Phase | Titel | Kern | Seite |
|---|---|---|---|
| **1** | **Controller-Validierung** (Kishi Hello-World) | Beweisen, dass Android den Kishi als Gamepad liest (Web-Vorcheck + minimale native App zeigt Achsen/Buttons). Kein ROS. | App |
| **2** | **Steuer-Grundstrecke** (PS4-Parität) | rosbridge always-on + App verbindet + publisht `/joy` → Roboter läuft. **Der Meilenstein.** | App + ROS |
| **3** | **Bringup-/Shutdown-Lifecycle** | Launcher-Node (bringup start/stop, shutdown) + Connect-Screen + Start-/Shutdown-Buttons (Henne-Ei) | App + ROS |
| **4** | **Video-Vollbild + UI-Shell** | Stream-Server + Fullscreen-Video mit Overlay-Gerüst (DJI-Style), Kamera an/aus | App + ROS |
| **5** | **Touch-Parameter-UI + Status-Overlay** | On-Screen-Slider/Toggles (Params via rosbridge) + **Status-Publisher (ROS)** → Batterie/Tip/Modus/Safety im Overlay | App + ROS |
| **6** | **Recovery + Not-Halt** | E-Stop (`safety_freeze`) + Ein-Klick-Recovery-Service (Joint-Space-Ramp in den Stand) + App-Button | App + ROS |
| **7** | **Audio** *(zweitrangig, schwebt)* | `hexapod_audio`-Node + Soundboard + Mute-Param | App + ROS |
| **8** | **Politur** | Controller-Profile (Portabilität), Reconnect-Handling, Robustheit | App |

**Abhängigkeiten:** 1 → 2 → 3 sind linear (Input → Steuerstrecke → Lifecycle). 4/5/6 bauen
auf 2/3 auf, sind untereinander aber weitgehend unabhängig. 7 schwebt (jederzeit). 8 zum
Schluss.

---

## 3. Arbeits-Aufteilung: welche Arbeit lebt wo

| Bereich | Ort | Inhalt |
|---|---|---|
| **ROS-Seite** | `hexapod_ws` (dieser Workspace) | rosbridge-Config + systemd-Unit, `hexapod_launcher` (bringup/shutdown), `hexapod_status` (Status-Topic), `hexapod_audio`, Kamera-Stream-Setup, Recovery-Service. Alles echte ROS-Pakete/Configs. |
| **App-Seite** | **Separates Android-Studio-Repo** (außerhalb hexapod_ws, z. B. `hexapod_app`) | Kotlin-App: Gamepad-Read, WebSocket-Client (roslib-artig via OkHttp), Touch-UI, Video-Player, Overlay, Controller-Profile. |
| **Geteilt (die Naht)** | [`interface_contract.md`](interface_contract.md) **hier** (Single Source) | rosbridge Topics/Services/Message-Felder = die „API/ABI" zwischen beiden Welten. Versioniert + Changelog. Der App-Repo **referenziert** ihn (kopiert nie). |
| **Diese Doku** | `hexapod_ws/project_finalization/app_control_requirements/` | WAS + WARUM + Schnittstelle + Phasen. Der App-Repo bekommt nur dünne, mechanische Doku (Build/Emulator) + Zeiger hierher. |

**Entwicklungs-Setup (Zwei-Sessions-Muster, [D9](decisions.md)):** Diese Session (hexapod_ws)
= ROS + Architekt/Contract-Autorschaft. Eine **zweite Claude-Code-Session im Android-Repo** =
App-Seite, liest denselben `interface_contract.md` (read-only). **Koordination = der Contract-
File (asynchron, versioniert), nicht Live-Agent-Verhandlung.** Integration + End-to-End-Test =
User.

---

## 4. Doku-Konventionen dieses Blocks

- **Kontext-Tags in allen test_commands** (weil ein Phasen-Test end-to-end über beide Welten
  läuft, die Datei aber in hexapod_ws liegt):
  - **▶ ROS (hexapod_ws)** — `colcon build`, `ros2 launch …` (Desktop/Pi-Terminal)
  - **▶ App (Android Studio)** — Gradle-Build, `adb install`, App-Code
  - **▶ Handy** — „App öffnen, Verbinden drücken, Taster …" (Bedienung am Gerät)
- **`interface_contract.md` = Single Source**, nie duplizieren; Version/Changelog macht
  Änderungen für die App-Seite explizit.
- **Kein App-Source in hexapod_ws** (eigenes Repo).
- Sonst gelten die Projekt-Konventionen (CLAUDE.md §4/§5, [`ai_navigation.md`](../../project_architecture/ai_navigation.md)).

---

## 5. Navigations-Index

| Datei | Zweck |
|---|---|
| [`00_overview.md`](00_overview.md) | dieses Dokument (Einstieg) |
| [`requirements.md`](requirements.md) | Funktions-/Anforderungsliste (Controller/Screen/Overlay, Must/Nice, nicht-funktional) |
| [`decisions.md`](decisions.md) | Architektur-Entscheidungen mit verworfenen Alternativen |
| [`interface_contract.md`](interface_contract.md) | die App↔Roboter-API (versioniert) — geteilte Naht |
| [`phase_1_controller_validation_plan.md`](phase_1_controller_validation_plan.md) | Phase 1 Plan (Kishi Hello-World) |
| [`phase_1_controller_validation_progress.md`](phase_1_controller_validation_progress.md) | Phase 1 Done-Vertrag |
| [`phase_1_controller_validation_test_commands.md`](phase_1_controller_validation_test_commands.md) | Phase 1 Ausführ-Schritte |
| Phase 2–8 | plan/progress/test_commands je Phase, angelegt bei Umsetzungsbeginn |

---

## 6. Hardware-Kontext (Stand)

- **Controller:** Razer Kishi V2 (USB-C, präsentiert sich als Standard-HID-Gamepad).
  ⚠️ Eignung wird in **Phase 1** verifiziert (5-Min-Web-Vorcheck + native App). Trigger
  vermutlich digital (nicht analog) — für uns unkritisch (L2/R2 = Buttons).
- **Handy:** Samsung S22+ (bevorzugt, SIM-los = reines WLAN/Hotspot-Gerät) oder S26+
  (Ersatz). Beide moderne USB-C-Flagships.
- **Netz:** Variante A (Handy-Hotspot, Pi tritt bei) zuerst; Variante B (Pi-AP, feste IP)
  falls A sich nicht bewährt. Kein Internet nötig ([D4](decisions.md)).
- **Roboter-Recheneinheit:** Raspberry Pi 5, Ubuntu Server 24.04 arm64 (siehe CLAUDE.md).
- **Kamera:** Raspi-Cam v1.3 (verbaut, geprüft). **Speaker** (verbaut, geprüft).
