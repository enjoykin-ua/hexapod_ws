# Phase 2 — Steuer-Grundstrecke (PS4-Parität) — ROS-Seite §4-Plan

> **Der Meilenstein.** rosbridge läuft, die App publisht `/joy` → bestehende `joy_to_twist`-
> Kette → `/cmd_vel` → gait → **Sim-Roboter läuft**. Diese Phase beweist die komplette
> Steuerstrecke — **in der Simulation**, bevor der Pi angefasst wird.
>
> **Seite:** ROS (dieses Dokument) + App (parallel, andere Session). **Status: 🟡 Plan.**
> Master: [`00_overview.md`](00_overview.md) · Contract: [`interface_contract.md`](interface_contract.md).

---

## 0. Ziel + Abgrenzung

**Ziel (ROS-Seite):** die Always-On-`/joy`-Aufnahmeschicht bereitstellen —
`rosbridge_server` + ein Teleop-Modus, in dem die **App die einzige `/joy`-Quelle** ist
(kein `joy_node`). Danach kann ein WebSocket-Client (Test-Client *oder* die echte App)
`sensor_msgs/Joy` publishen und der Sim-Roboter fährt.

**Netz (neu):** Dev-PC hat jetzt ein WLAN-Modul → Dev-PC **und** Handy hängen am **Router**.
Das Handy erreicht die Desktop-rosbridge unter `Desktop-IP:9090`. Kein Hotspot nötig für den
Sim-Test. Die Hotspot-/Pi-AP-Varianten ([D4]) bleiben ein **Feld-/Phase-7-Thema**.

**Zwei Netz-Modi (bewusst code-identisch):** rosbridge über WebSocket ist **transport-agnostisch** —
die App verbindet sich auf `<host>:9090`, egal wie der Host erreichbar ist. Der `/joy`-Pfad
ändert sich zwischen den Modi **null** (Unicast-TCP, kein DDS-Multicast → funktioniert über
Router *und* Hotspot gleich, [D2]).

| | **Sim (diese Phase)** | **Real HW (spätere HW-Netz-Stage)** |
|---|---|---|
| rosbridge auf | Dev-PC | Raspi |
| Netz | Handy + Dev-PC am Router | Handy = Hotspot, Raspi tritt bei ([D4] A) |
| App zielt auf | `Desktop-IP:9090` | `Pi-IP:9090` |
| Steuer-Code | **identisch** | **identisch** |

Die **HW-Netz-Stage** (eigene, spätere Stage beim Pi-Port) enthält nur *Netz-Konfiguration*,
keinen neuen Steuer-Code: Pi tritt Handy-Hotspot bei (nmcli/netplan) bzw. Pi-AP (Variante B),
rosbridge-systemd-Unit scharf schalten (das Artefakt entsteht schon hier), feste Pi-IP in der
App. **Risiken geklärt:** Hotspot ohne SIM am S22+ **funktioniert** (verifiziert); Akku-Last
unkritisch (Handy hält länger durch als der Hexapod).

**Bewusst NICHT in Phase 2 (Abgrenzung):**
- **Kein** Launcher/`bringup_start` (das On-Demand-Starten des schweren Stacks aus der App =
  **Phase 3**). Der Gait-/Sim-Stack wird in Phase 2 **manuell** gestartet.
- **Kein** Video (Phase 4), **kein** Status-Topic (Phase 5), **kein** Recovery (Phase 6).
- **Kein** Pi — reiner **Desktop-Sim**-De-Risk. Die systemd-Always-On-Unit wird als
  **Artefakt** geschrieben, aber auf dem Dev-Host **nicht** scharf geschaltet (Boot-Validierung
  = Pi/Phase 7).
- **Nicht** die App selbst — die baut die parallele Android-Session. Der ROS-seitige Test nutzt
  einen **WebSocket-Test-Client** als App-Ersatz.

---

## 1. Logik-Skizze / Vorgehen

### 1a. rosbridge bereitstellen
- Paket `ros-jazzy-rosbridge-suite` installieren (ROS-Paket → CLAUDE.md §5 erlaubt).
- Neues `rosbridge.launch.py` in `hexapod_bringup/launch/`: startet `rosbridge_websocket`
  (Port **9090**, bindet default alle Interfaces) + `rosapi` (für Topic-/Service-Discovery
  aus der App). Param `use_sim_time:=true` (Sim-Default), als Arg überschreibbar.
- **Design-Begründung:** eigenes Launch statt Stock-Aufruf, damit `use_sim_time`, Port und
  spätere Params (Fragment-Größe, Auth) an *einer* Stelle liegen und in den Pi-Bringup
  wiederverwendbar sind.

### 1b. App als alleinige `/joy`-Quelle
- [`joy_teleop.launch.py`](../../src/hexapod_teleop/launch/joy_teleop.launch.py) um Arg
  **`joy_source`** (`controller` | `app`) erweitern:
  - `controller` (Default, unverändert): `joy_node` + `joy_to_twist` (PS4-USB wie bisher, NF7-Fallback).
  - `app`: **nur** `joy_to_twist` — kein `joy_node`. Die App publisht `/joy` über rosbridge.
- **Design-Begründung:** ein Arg statt zweitem Launch-File hält die Controller-Config an einer
  Stelle und macht NF7 (genau eine `/joy`-Quelle) explizit. `joy_to_twist` bleibt **unverändert**
  ([D3]) — es weiß nicht, ob `/joy` von `joy_node` oder rosbridge kommt.
- `joy_to_twist` im app-Modus mit `use_sim_time:=true` (für Long-Press-Timing gegen `/clock`).

### 1c. Komfort-Bringup (optional, ein Aufruf)
- `app_teleop.launch.py`: bündelt `joy_teleop(joy_source:=app)` + `rosbridge.launch.py`. Damit
  bringt **ein** Befehl die app-zugewandte Schicht neben einem laufenden Sim-Walk hoch.

### 1d. systemd-Artefakt (für später, Pi)
- `hexapod_bringup/systemd/hexapod_rosbridge.service` schreiben (User-Unit-Template) + im
  README dokumentieren (`systemctl --user enable`). **Auf dem Dev-Host NICHT enablen** — nur
  Artefakt. Läuft in Phase 2 alles über manuellen Launch.

### 1e. Contract-Touchpoints
- §0 (Transport) präzisieren: rosbridge-Adresse (`Desktop-IP` im Sim, feste Pi-IP im Feld),
  Port 9090, **`/joy`-QoS** (default reliable, depth 10) — falls Anpassung nötig → Contract
  **v0.3 + Changelog**. §1 (`/joy` @ 30 Hz) steht schon.

---

## 2. Tests-Liste (mit Begründung) + was NICHT getestet

| Test | Prüft | Warum |
|---|---|---|
| **T2.1** rosbridge kommt hoch (`ros2 node list` zeigt `rosbridge_websocket`+`rosapi`, Port 9090 lauscht) | Aufnahmeschicht | Grundlage |
| **T2.2** WebSocket-Test-Client sendet rosbridge-`advertise`+`publish` `/joy` (R1-Dead-Man + linker Stick vor) → **Sim-Roboter fährt** | ganze Kette rosbridge→`/joy`→`joy_to_twist`→`/cmd_vel`→gait→Sim | Meilenstein-Beweis, **unabhängig von der App** |
| **T2.3** im app-Modus läuft **kein** `joy_node` (genau ein `/joy`-Publisher) | NF7 / kein Konflikt | zwei Publisher = Zucken |
| **T2.4** `/joy`-QoS App↔`joy_to_twist` kompatibel (rosbridge-Publish kommt an) | QoS-Matching | rosbridge/DDS-Fallstrick |
| **T2.5** NF1: `/joy`-Publish stoppen → `cmd_vel_timeout` → Roboter stoppt | Comms-Loss-Failsafe | Screen-Lock/Absturz = Stopp |
| **T2.6** Handy erreicht `Desktop-IP:9090` (ping/Port offen, ggf. ufw) | Netz über Router | Vorbedingung Integration |

**Bewusst offen / später:**
- **Echter End-to-End mit der App** (Handy → Desktop-rosbridge → Sim) = **Integration
  (Schritt 6, User + Android-Session)**, nicht Teil des ROS-seitigen Done. Der ROS-Test nutzt
  den Test-Client als App-Ersatz.
- **Vorzeichen-Endverifikation** (`ros2 topic echo /joy`, Stick/D-Pad/Trigger) läuft im
  Integrations-Schritt mit der echten App (Contract §1 „Phase-2-Verifikation").
- **systemd-Boot-Start** = Pi/Phase 7 (in Phase 2 nur Artefakt).
- **Latenz-Messung** grob/qualitativ (NF3), keine harte Zahl in Phase 2.

---

## 3. Progress-Checkliste (→ `phase_2_..._progress.md`, Done-Vertrag)

```
Phase 2 (Steuer-Grundstrecke, ROS-Seite):
- [ ] P2.1 ros-jazzy-rosbridge-suite installiert; rosbridge.launch.py bringt rosbridge_websocket + rosapi auf :9090 hoch
- [ ] P2.2 joy_teleop.launch.py um joy_source:=controller|app erweitert (app-Modus = joy_to_twist OHNE joy_node)
- [ ] P2.3 app_teleop.launch.py (Komfort): joy_to_twist(app) + rosbridge in einem Aufruf, use_sim_time konfigurierbar
- [ ] P2.4 T2.2 gruen: WebSocket-Test-Client-/joy-Publish bewegt den Sim-Roboter (Dead-Man R1 + Stick)
- [ ] P2.5 T2.3+T2.4: kein Doppel-/joy-Publisher; /joy-QoS kompatibel
- [ ] P2.6 T2.5: NF1 Comms-Loss (Publish-Stop -> cmd_vel_timeout -> Stopp) verifiziert
- [ ] P2.7 systemd-Unit-Artefakt hexapod_rosbridge.service geschrieben + dokumentiert (Pi-Always-On; Dev NICHT enabled)
- [ ] P2.8 Contract §0 gepinnt (rosbridge Adresse/Port/QoS); Version-Bump falls noetig
- [ ] P2.9 Self-Review-Tabelle + Doku (hexapod_bringup README rosbridge-Abschnitt, test_commands final)
- [ ] P2.10 [Integration, User+App] End-to-End Handy -> Desktop-rosbridge -> Sim; Vorzeichen-Verifikation (Contract §1)
```

---

## 4. Offene Punkte für User-Review (vor Code-Beginn)

1. **systemd jetzt schon?** Ich schreibe die Unit als **Artefakt** (nicht enablen). Ok, oder
   ganz nach Phase 7 verschieben? (Empfehlung: Artefakt jetzt, es kostet fast nichts und
   dokumentiert die Always-On-Absicht.)
2. **rosbridge-Auth:** Default **ohne** Auth. Für privaten Router/Hotspot ok ([requirements §6]/[D2])?
   Ich baue keine Auth (bewusst simpel), nur an privates Netz binden.
3. **Komfort-Launch `app_teleop.launch.py`** bauen, oder reicht dir `rosbridge.launch.py` +
   `joy_teleop.launch.py joy_source:=app` als zwei Aufrufe? (Empfehlung: Komfort-Launch, ein Befehl.)
4. **Test-Client:** ich schreibe ein kleines Python-WebSocket-Skript (`tools/`), das rosbridge-
   `/joy` publisht (Dead-Man + Stick), damit T2.2 **ohne Handy** reproduzierbar ist. Ok?
5. **Firewall:** falls `ufw` aktiv ist, muss Port 9090 im lokalen Netz auf sein — ich gebe den
   Befehl vor (du führst ihn aus), stelle das aber nicht selbst um.

---

## 5. Arbeits-Aufteilung + App-Seiten-Brief (self-contained für die Android-Session)

**ROS-Seite (dieses Dokument — erledigt):** rosbridge-Launch, `joy_source`-Arg, Komfort-Launch,
systemd-Artefakt, Test-Client, Contract-§0-Pin, README/test_commands.

**App-Seite (Android-Session) — die Phase-2-Aufgabe.** Alles Interface-Nötige steht im
[`interface_contract.md`](interface_contract.md); dieser Abschnitt ist die Aufgaben-/Akzeptanz-
Fassung. Handoff = „lies den Contract + diesen Abschnitt", nichts aus dem Chat.

- **Transport (§0):** OkHttp-WebSocket auf `ws://<host>:9090` (Sim: `Desktop-IP` via
  `hostname -I` am Dev-PC; real: `Pi-IP`). rosbridge-Protokoll (`op: advertise` → `op: publish`).
- **`/joy` advertisen mit `reliability: reliable`** — **PFLICHT** (§0). BEST_EFFORT ⇒
  `joy_to_twist` bekommt nichts (QoS-inkompatibel).
- **Publizieren:** `sensor_msgs/Joy`, **~30 Hz stetig** (auch bei neutral — NF1), volle Länge
  (**8 Achsen, 15 Buttons**) mit den Kishi→PS4-Transforms aus **§1**: Sticks negiert, **D-Pad-Y
  negiert** (`−AXIS_HAT_Y`, v0.4 — sonst Tempo invertiert), Trigger `1−2t` (idle→+1),
  positionsbasierte Face-Buttons, Dead-Man = `buttons[5]` (R1).
- **Referenz-Implementierung (exaktes Nachrichten-Format):**
  [`tools/joy_ws_test_client.py`](../../tools/joy_ws_test_client.py) — funktionierender
  rosbridge-`/joy`-Publisher (advertise → publish-Schleife, Idle-Trigger, Dead-Man). In Kotlin
  nachbauen; identisch getestet in Phase 2.
- **Akzeptanz (P2.10):** Handy im Kishi → App verbindet → **Sim-Roboter fährt** wie beim
  Test-Client (R1 halten + Stick). Dann **Vorzeichen-Verifikation** via `ros2 topic echo /joy`
  (Contract §1 „Phase-2-Verifikation"): Stick hoch=vorwärts / links=links, Trigger idle=+1,
  D-Pad-Richtung korrekt. Abweichung → Transform bzw. `sign_*`-Params justieren.
- **Bewusst noch NICHT (spätere Phasen):** Touch-UI, Video, Status-Overlay, Controller-Profil-System.

**Integration (User):** startet Sim-Walk + `app_teleop`, öffnet die App, prüft die Akzeptanz.

---

## 6. Doku-Nachzug (nach Umsetzung)
- `phase_2_..._progress.md` (Done-Vertrag) + `phase_2_..._test_commands.md` (Kontext-Tags:
  ▶ ROS / ▶ App / ▶ Handy) — Letzteres **vor** dem Live-Test final schreiben.
- `hexapod_bringup/README.md`: rosbridge-Abschnitt + `joy_source`-Erklärung.
- Contract §0/§7 aktualisieren (Version + Changelog), falls gepinnt.
- Design-Entscheidungen (joy_source-Arg vs. zweites Launch; systemd-Artefakt-Timing) im
  progress-File als „Design-Entscheidungen"-Abschnitt.
