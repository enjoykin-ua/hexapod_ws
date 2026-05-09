# Phase 5 Stufe D — Test-Befehle

Live-Verifikation der Foot-Bodenkontakt-Sensoren aus Stufe D. User
führt die Befehle in den jeweiligen Terminals aus, meldet knapp den
Status pro Schritt zurück.

> Sim-Output nach `/tmp/sim.log`, Memory-Eintrag
> `feedback_interactive_stage_test_doc.md`.

Drei Test-Pfade:
1. **Toggle ON** (Default): Sensoren aktiv, Topics da, Stand-Pose alle 6 = `True`.
2. **Funktional**: Bein 1 manuell anheben → Sensor wechselt auf `False`.
3. **Toggle OFF**: keine Topics, keine Bridge-Aktivität.

---

## Vorbereitung in jedem Terminal

```bash
cd ~/hexapod_ws
source install/setup.bash
```

Falls noch nicht gebaut:

```bash
colcon build --packages-select hexapod_description hexapod_sensors hexapod_bringup hexapod_kinematics hexapod_gait
source install/setup.bash
```

---

## Pfad 1 — Toggle ON: Sensoren aktiv

### Schritt 1.1 — Sim mit Foot-Contact starten (Terminal 1)

```bash
ros2 launch hexapod_bringup sim.launch.py enable_foot_contact:=true > /tmp/sim.log 2>&1 &
```

(`enable_foot_contact:=true` ist Default, kann auch weggelassen werden.)

**Erwartet:**
- Gazebo-Fenster öffnet sich, Hexapod fällt auf den Bauch.
- `/tmp/sim.log`: 7 Spawner-Meldungen (wie Phase 4) plus Logs vom
  `foot_contact_publisher` ("init: 6 legs, in /leg_<n>/foot_contact_raw -> out /leg_<n>/foot_contact (Bool)").

**Status-Meldung:** „Sim läuft, foot_contact_publisher init logged."

### Schritt 1.2 — Topic-Liste prüfen (Terminal 2)

```bash
ros2 topic list | grep foot_contact
```

**Erwartet:** 12 Topics insgesamt:
- 6× `/leg_<n>/foot_contact` (Bool, Output für Konsumenten).
- 6× `/leg_<n>/foot_contact_raw` (Contacts, Bridge-Output).

**Status-Meldung:** „12 foot_contact-Topics da" oder „X von 12 da, fehlen: ...".

### Schritt 1.3 — Stand-Pose anfahren (Terminal 2)

```bash
ros2 launch hexapod_gait stand.launch.py
```

**Erwartet:** wie Stufe-C-Test — Roboter steht nach ~5 s auf 6 Foot-Kugeln.

### Schritt 1.4 — Foot-Contact alle = True verifizieren (Terminal 3)

Sequenziell pro Bein, dauert insgesamt ~30 s:

```bash
for n in 1 2 3 4 5 6; do
  echo "--- leg_$n ---"
  timeout 2 ros2 topic echo "/leg_${n}/foot_contact" std_msgs/msg/Bool --once
done
```

**Erwartet:** alle 6 zeigen `data: true`.

**Hinweis zur Typangabe:** wieder mit explizitem `std_msgs/msg/Bool`,
weil frische Terminals mit DDS-Discovery-Race kämpfen (siehe
Stufe-C-Notiz).

**Status-Meldung:** „Alle 6 = True" oder „Bein X = False (unerwartet)".

---

## Pfad 2 — Funktional: Bein anheben

Sim weiterhin laufen lassen (Pfad 1 nicht beenden).

### Schritt 2.1 — Bein 1 manuell aus dem Boden heben (Terminal 2)

```bash
ros2 topic pub --once /leg_1_controller/joint_trajectory \
  trajectory_msgs/msg/JointTrajectory \
  '{joint_names: ["leg_1_coxa_joint", "leg_1_femur_joint", "leg_1_tibia_joint"],
    points: [{positions: [0.0, -1.2, 0.5], time_from_start: {sec: 2}}]}'
```

(femur=-1.2 hebt Bein deutlich an, tibia=0.5 reduziert das Knicken,
Foot kommt sicher vom Boden weg.)

**Erwartet:** Bein 1 hebt sich sichtbar in der Luft.

### Schritt 2.2 — `/leg_1/foot_contact` jetzt False (Terminal 3)

```bash
timeout 3 ros2 topic echo /leg_1/foot_contact std_msgs/msg/Bool --once
```

**Erwartet:** `data: false`.

### Schritt 2.3 — Andere 5 Beine immer noch True (Terminal 3)

```bash
for n in 2 3 4 5 6; do
  echo "--- leg_$n ---"
  timeout 2 ros2 topic echo "/leg_${n}/foot_contact" std_msgs/msg/Bool --once
done
```

**Erwartet:** alle 5 zeigen `data: true`.

**Status-Meldung:** „Bein 1 = False, andere 5 = True." Damit ist
funktional verifiziert dass die Sensoren je Bein unabhängig
reagieren.

### Schritt 2.4 — Bein 1 zurück auf Boden (Terminal 2, optional)

```bash
ros2 topic pub --once /leg_1_controller/joint_trajectory \
  trajectory_msgs/msg/JointTrajectory \
  '{joint_names: ["leg_1_coxa_joint", "leg_1_femur_joint", "leg_1_tibia_joint"],
    points: [{positions: [0.0, -0.510, 1.012], time_from_start: {sec: 2}}]}'
```

Dann erneut `ros2 topic echo /leg_1/foot_contact std_msgs/msg/Bool --once`
sollte wieder `data: true` zeigen.

### Schritt 2.5 — Sim beenden (Terminal 1)

```bash
kill %1
```

---

## Pfad 3 — Toggle OFF: Sensoren komplett aus

### Schritt 3.1 — Sim mit Toggle-OFF starten (Terminal 1)

```bash
ros2 launch hexapod_bringup sim.launch.py enable_foot_contact:=false > /tmp/sim.log 2>&1 &
```

**Erwartet:**
- Sim startet wie immer.
- `/tmp/sim.log` enthält **keine** `foot_contact_publisher`-Init-Logs.
- Auch keine `ros_gz_foot_contact_bridge`-Meldungen.

**Status-Meldung:** „Sim läuft, kein foot_contact-Init in Logs."

### Schritt 3.2 — Topic-Liste verifizieren (Terminal 2)

```bash
ros2 topic list | grep foot_contact
```

**Erwartet:** **leere Ausgabe** (keine Topics matchen). `grep` exit
status ist 1, das ist erwartetes Verhalten.

**Status-Meldung:** „Keine foot_contact-Topics in topic list."

### Schritt 3.3 — Sim weiter funktional, ohne Sensoren (Terminal 2)

```bash
ros2 launch hexapod_gait stand.launch.py
```

**Erwartet:** Roboter steht trotzdem in Stand-Pose. Toggle-OFF
beeinflusst nur die Sensor-Pipeline, nicht den Stand-Pose-Anfahr-
Prozess.

**Status-Meldung:** „Roboter steht, Sim funktional ohne Sensoren."

### Schritt 3.4 — Aufräumen (Terminal 1)

```bash
kill %1
```

---

## Optionale Diagnose-Variationen

### Bridge-Direct-Topic prüfen (statt durchgereichtem Bool)

Bei Toggle ON, Stand-Pose:

```bash
timeout 2 ros2 topic echo /leg_1/foot_contact_raw ros_gz_interfaces/msg/Contacts --once
```

**Erwartet:** Eine Message mit `contacts:` als Array, mindestens 1
Eintrag (Foot-Kugel berührt Boden). Felder pro Contact:
`collision1`, `collision2`, `position[]`, `normal[]`, `wrench[]`.

Verifiziert die Bridge-Schicht zwischen Gazebo und ROS, unabhängig
vom Konversionsknoten.

### Gazebo-Topic direkt prüfen

```bash
gz topic -e -t /foot_contact_leg_1
```

(Strg+C zum Beenden, sonst läuft endlos.)

**Erwartet:** Gazebo-native Contacts-Messages mit Pose, Wrench,
Depth-Daten. Verifiziert die unterste Schicht (Sensor in Gazebo).

Wenn dieser Topic leer ist, aber `/leg_<n>/foot_contact` fehlt:
Bridge-Mapping-Problem. Wenn auch dieser Topic leer ist:
Sensor-Definition im URDF/xacro hat ein Problem.
