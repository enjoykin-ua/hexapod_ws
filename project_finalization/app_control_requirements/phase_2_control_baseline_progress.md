# Phase 2 — Steuer-Grundstrecke (PS4-Parität) — Progress (ROS-Seite)

> **Done-Vertrag** (CLAUDE.md §4). Bullets 1:1 aus
> [`phase_2_control_baseline_plan.md`](phase_2_control_baseline_plan.md) §3.
> Pro erledigtem Bullet sofort abhaken. Self-Review + Contract-§0-Pin nach dem Live-Test.

```
Phase 2 (Steuer-Grundstrecke, ROS-Seite):
- [x] P2.1 ros-jazzy-rosbridge-suite installiert; rosbridge.launch.py bringt rosbridge_websocket + rosapi auf :9090 hoch (T2.1)
- [x] P2.2 joy_teleop.launch.py um joy_source:=controller|app erweitert (app-Modus = joy_to_twist OHNE joy_node)
- [x] P2.3 app_teleop.launch.py (Komfort): joy_to_twist(app) + rosbridge in einem Aufruf, use_sim_time konfigurierbar
- [x] P2.4 T2.2 gruen: WebSocket-Test-Client-/joy-Publish bewegt den Sim-Roboter (Dead-Man R1 + Stick)
- [x] P2.5 T2.3+T2.4: kein Doppel-/joy-Publisher; /joy-QoS kompatibel (RELIABLE<->RELIABLE, TRANSIENT_LOCAL>=VOLATILE)
- [x] P2.6 T2.5: NF1 Comms-Loss (Publish-Stop -> cmd_vel_timeout -> Stopp) verifiziert; Gegentest --no-deadman = keine Fahrt
- [x] P2.7 systemd-Unit-Artefakt hexapod_rosbridge.service geschrieben + dokumentiert (Pi-Always-On; Dev NICHT enabled)
- [x] P2.8 Contract §0 gepinnt (Adresse/Port/QoS -> v0.3): /joy = RELIABLE Pflicht
- [x] P2.9 Self-Review-Tabelle + Doku (hexapod_bringup README rosbridge-Abschnitt, test_commands final)
- [x] P2.10 [Integration] echte App bewegt Sim-Roboter + Höhe end-to-end; Vorzeichen verifiziert (nur D-Pad-Y invertiert -> App negiert AXIS_HAT_Y, Contract v0.4; Rest ok)
```

## Stand — ROS-Seite fertig (Sim-verifiziert), nur P2.10 (App-Integration) offen

**Live-Sim-Test bestanden** (rosbridge + python3-websocket installiert; Test nach
[`phase_2_control_baseline_test_commands.md`](phase_2_control_baseline_test_commands.md)):
T2.1 rosbridge up · T2.2 Roboter fährt vorwärts · T2.3 eine /joy-Quelle · T2.4 QoS kompatibel ·
T2.5 NF1-Stopp · T2.6 Handy erreicht `:9090` · Gegentest (--no-deadman) = keine Fahrt.

**Phase 2 komplett** (Sim). Die echte Android-App bewegt den Roboter + verstellt die Höhe
end-to-end. Vorzeichen-Verifikation: alle Richtungen korrekt **außer D-Pad-Y (Tempo)** — war
invertiert, Fix = **App negiert `AXIS_HAT_Y`** (Contract v0.4, app-seitig damit PS4-Fallback
korrekt bleibt). Diese eine Zeile zieht die Android-Session noch nach; kein ROS-Change nötig.

## Self-Review (P2.9)

| # | Punkt | Status |
|---|---|---|
| 1 | T2.1 rosbridge up, Port 9090 auf `0.0.0.0`/`[::]` | OK |
| 2 | T2.2 Sim-Roboter fährt vorwärts auf /joy-Publish | OK |
| 3 | T2.3 kein joy_node, 1 Publisher / 1 Subscriber (NF7) | OK |
| 4 | T2.4 QoS kompatibel (RELIABLE↔RELIABLE; TRANSIENT_LOCAL ≥ VOLATILE) | OK |
| 5 | T2.5 NF1: Publish-Stop → cmd_vel_timeout → Roboter hält | OK |
| 6 | T2.6 Handy erreicht `Desktop-IP:9090` (Router) | OK |
| 7 | Gegentest `--no-deadman` → keine Fahrt (Dead-Man-Gating) | OK |
| 8 | Contract §0 `/joy`-QoS = RELIABLE gepinnt (v0.3) — kritisch für App | OK |
| 9 | systemd-Unit nur Artefakt, Dev-Host nicht scharf | OK |
| 10 | colcon build grün, 3 Launch-Files parsen | OK |
| 11 | P2.10 App-Integration + Vorzeichen-Verifikation | 🟢 Android-Session + User |

Keine 🔴/🟡. Die ROS-Seite von Phase 2 ist Sim-verifiziert abgeschlossen.

## Design-Entscheidungen (mit Alternativen)

- **`joy_source`-Arg statt zweitem Launch-File:** hält die Controller-Config an einer Stelle,
  macht NF7 (genau eine /joy-Quelle) explizit. Verworfen: separates `app_teleop_only`-Launch
  (dupliziert joy_to_twist-Setup) und „joy_node immer an, App überschreibt" (zwei Publisher → Zucken).
- **rosbridge als eigenes Launch (nicht Stock-XML-Include):** eigener Ort für Port/use_sim_time/
  Thread-Params, wiederverwendbar im Pi-Bringup. Verworfen: XML-Stock-Include (schwer, use_sim_time
  je Node schlecht setzbar).
- **systemd-Unit jetzt als Artefakt (nicht scharf):** dokumentiert die Always-On-Absicht, kostet
  nichts, wird in der HW-Netz-Stage aktiviert. Verworfen: ganz nach Phase 7 verschieben (Absicht
  ginge im Doku-Rauschen unter).
- **Python-Test-Client (websocket-client) als App-Ersatz:** macht T2.2 handy-frei reproduzierbar
  (CI-/Regressions-tauglich). Verworfen: nur mit der echten App testen (blockiert ROS-Fortschritt
  an der Android-Session).
