# Phase 8b — Sim+HW Visual-Mirror (optional)

**Dauer-Schätzung:** 0,5–1 Tag (Tag der „lust drauf"-Sprint, nicht zwingend)
**Maschine:** Desktop
**Vorbedingung:** Phase 7 abgeschlossen (Servo2040-Firmware läuft),
Phase 8 nicht zwingend (Mirror funktioniert auch ohne komplettes Bench)
**Status:** **OPTIONAL** — kein Done-Kriterium für Phase 12 oder spätere
Phasen

---

## Ziel

Ein eigenständiger Python-Knoten, der parallel zur laufenden Gazebo-
Simulation die echten Servo2040-Servos mit den **gleichen Sollwerten**
versorgt wie die Sim. Aufgebockt am Bench. Pädagogisch / Demo-Zweck:
„Schau, der Roboter macht was die Sim sagt."

---

## Architektur-Abgrenzung

Wichtig: dieser Knoten ist **kein** Teil von `ros2_control` und greift
**nicht** in den Stack ein, der in Phase 9 gebaut wird. Er hängt rein
passiv an `/joint_states` und schickt unabhängig USB-Frames an Servo2040.

```
                          ┌──────────────────────────────┐
                          │ ros2_control + Gazebo (Sim)  │
                          │  gz_ros2_control = master    │
                          └────────────┬─────────────────┘
                                       │ /joint_states (publisht JSB)
                                       │
                                       ▼
              ┌─────────────────────────────────────────┐
              │   servo2040_mirror_node (Python)        │
              │   - subscribt /joint_states             │
              │   - rad → pulse_us mit shared cal-YAML  │
              │   - schickt SET_TARGETS-Frame an /dev/  │
              │     ttyACM0                             │
              │   - kein Feedback in den Sim-Stack      │
              └────────────┬────────────────────────────┘
                           │ USB-CDC
                           ▼
                      [Servo2040 + Servos aufgebockt]
```

**Konsequenz:** Wenn Phase 8b nachträglich gebaut wird, müssen Phase 9–12
**nicht** angefasst werden. Es ist eine reine Ergänzung.

---

## Wann ist 8b sinnvoll?

- Verkabelungs-Bugs sehen: Wenn Sim ein Bein anhebt, der echte aber das
  Gegenüber, ist die Servo-Mapping-Tabelle falsch.
- Kalibrierungs-Fehler sehen: Wenn Sim Endlage X zeigt, der echte Servo
  aber gegen den Anschlag fährt → `pulse_min/max` neu kalibrieren.
- Demo: dem Zuschauer „Hardware folgt Sim" zeigen, ohne komplettes
  ROS2-on-Pi-Setup.

## Wann ist 8b **nicht** sinnvoll?

- Echte Walking-Tests am Boden — dafür ist Option A (Sim↔HW-Switch) gemacht.
- Closed-Loop-Validierung „macht der Roboter wirklich was er soll?" —
  geht **nicht**, weil die Servos kein Position-Feedback liefern. Mirror
  zeigt nur was er gesendet hat, nicht was wirklich passiert.

---

## Done-Kriterien (falls man es macht)

1. Eigenes Python-Paket `hexapod_servo2040_mirror` im `hexapod_ws`
2. Subscriber auf `/joint_states`
3. Konversion Joint-rad → Pulse-µs mit Kalibrierungs-YAML (gleiches Schema
   wie in Phase 9's `hexapod_hardware/config/servo_mapping.yaml`)
4. Frame-Encoder identisch zu Phase 9 (idealerweise als gemeinsame
   Python-Lib, damit Drift vermieden wird)
5. Launch-File startet Sim + Mirror parallel
6. Aufgebockter Test: in Gazebo ein Bein heben per `cmd_vel`, echtes Bein
   hebt mit
7. Dead-Man-Logik im Mirror: ohne aktives `/cmd_vel` für > 500 ms →
   Servo2040 in Disabled-Modus

---

## Stufen

### Stufe A — Paket-Skelett

```bash
cd ~/hexapod_ws/src
ros2 pkg create --build-type ament_python --license Apache-2.0 \
  --dependencies rclpy sensor_msgs hexapod_servo2040_mirror
```

Struktur:
```
hexapod_servo2040_mirror/
├── package.xml
├── setup.py
├── hexapod_servo2040_mirror/
│   ├── __init__.py
│   ├── mirror_node.py
│   └── servo2040_protocol.py   # ggf. shared mit hexapod_hardware
├── config/
│   └── servo_mapping.yaml       # symlink oder kopiert aus hexapod_hardware
└── launch/
    └── sim_with_mirror.launch.py
```

### Stufe B — Mirror-Node

`mirror_node.py`:

- Subscribe `/joint_states` (sensor_msgs/JointState)
- Pro Eintrag: Joint-Name → Servo2040-Output-Index nachschlagen
- Pulse-µs berechnen: `pulse = pulse_zero[i] + direction[i] * pulse_per_rad[i] * position[i]`
- Clamp auf `[pulse_min[i], pulse_max[i]]`
- Frame zusammenbauen (CMD `SET_TARGETS`) + CRC + COBS
- Über `/dev/ttyACM0` schreiben
- 50 Hz Tick-Rate (Timer-basiert), pulse-Werte werden zwischen Joint-State-
  Callbacks gepuffert

### Stufe C — Dead-Man-Logik

- Letzter `/cmd_vel`-Empfang trackt
- Wenn Zeit seit letztem `/cmd_vel` > 500 ms: Mirror schickt weiter Stand-
  Pose, **nicht** disable (Servo2040 hat eigenen Watchdog, der zusätzlich
  läuft)
- Bei Start: Mirror schickt erstmal nur Stand-Pose, bis erste
  `/joint_states` reinkommen

### Stufe D — Launch-File

`sim_with_mirror.launch.py`:
- Bringt `hexapod_bringup/sim.launch.py` rein
- Startet zusätzlich `mirror_node`
- LaunchArg `mirror_enabled:=true|false`

### Stufe E — Aufgebockter Test

- Roboter aufgebockt, Servo2040 + ein paar Servos angeschlossen (so viele
  wie aktuell verfügbar sind)
- `ros2 launch hexapod_servo2040_mirror sim_with_mirror.launch.py`
- Per PS4 fahren — Sim bewegt sich, echte Servos folgen
- Visuell vergleichen

---

## Shared-Code-Hinweis

Der Frame-Encoder und die Kalibrierungs-YAML werden **in Phase 9** für
`hexapod_hardware` (C++) sowieso gebraucht. Wenn 8b nach Phase 9 gebaut
wird, sollte die Python-Frame-Encoder-Logik die **gleiche
Protokoll-Spec** umsetzen, idealerweise generiert aus einer gemeinsamen
Definition.

Empfehlung: das Protokoll wird im Phase-7-Firmware-Repo als `PROTOCOL.md`
final fixiert. Beide Implementierungen (Python in 8b, C++ in 9) lesen
gegen das Doc.

---

## Was in dieser Phase **NICHT** gemacht wird

- Kein Eingriff in `hexapod_hardware` oder in den Phase-9-Stack
- Keine Closed-Loop-Validierung (Servos haben kein Feedback)
- Kein eigenes ros2_control-Plugin

---

## Phasenabschluss-Checkliste (optional)

- [ ] Alle Stufen-Done-Kriterien erfüllt **falls Phase 8b gemacht wird**
- [ ] Falls verworfen: in `phase_8b_progress.md` vermerken warum
- [ ] Kein `phase-8b-done`-Tag nötig (optional bleibt optional)
