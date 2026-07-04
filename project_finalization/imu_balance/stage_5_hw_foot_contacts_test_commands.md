# Stufe 5 — Test-Befehle (HW-Fußkontakte am Servo2040)

> Du führst die Tests aus, knappe Status-Meldung zurück. **Ziel:** dieselben 6 `/leg_<n>/foot_contact`
> (`std_msgs/Bool`) wie in der Sim, aber aus echten Fuß-Tastern am Servo2040 (Firmware GET_INPUTS →
> Host-Plugin publisht). `gait_node` + die gesamte S4-Pipeline bleiben **unverändert**.
>
> **Sicherheit:** Alle Tests hier sind **read-only** — kein Servo-Enable, kein Relay. Bare-USB reicht,
> der Roboter darf aufgebockt oder stromlos sein. Die Firmware sampelt die Inputs jeden Tick, egal ob
> Host verbunden oder Servos aus.

## Verdrahtung (verbindlich)

- Fuß-Taster **normally-open**, 2 Kabel an den Servo2040-Sensor-Header:
  - Kabel 1 → **`IN`** des Kanals (SENSOR_n)
  - Kabel 2 → **`GND`** (Header-GND, gemeinsam)
- Interner Pull-Up (Firmware). Fuß in der Luft → offen → HIGH → **kein Kontakt (0)**;
  Fuß am Boden → Taster geschlossen gegen GND → LOW (< 1,65 V) → **Kontakt (1)**.
- Mapping: `SENSOR_1 = leg_1`, … `SENSOR_6 = leg_6`.

---

## 0. Firmware flashen (Firmware-Repo)

Der Firmware-Build ist bereits erzeugt (`build/Hexapod_servo_driver.uf2`, baut sauber). Flashen:

```bash
cd ~/hexapod_servo_driver
# Board in BOOTSEL versetzen ODER laufende FW rebooten lassen:
picotool load build/Hexapod_servo_driver.uf2 && picotool reboot
# Alternativ (BOOTSEL gedrückt einstecken): .uf2 aufs RPI-RP2-Volume kopieren.
```

Neu bauen (falls nötig):
```bash
cd ~/hexapod_servo_driver/build && make -j
```

---

## HW5.8 — FW-Bench: leg 1 an SENSOR_1 (Firmware-Bitmaske)

Ein Bein verdrahtet (SENSOR_1 `IN`+`GND`, NO). Das Probe-Tool pollt GET_INPUTS ~10 Hz und zeigt die
Bitmaske live:

```bash
cd ~/hexapod_servo_driver
python3 tools/probe_inputs.py /dev/ttyACM0
```

Erwartung (Ctrl-C beendet):
- Taster **los** → Zeile zeigt `L1○ … raw=0x00`.
- Taster **gedrückt** → `L1● … raw=0x01` (Bit 0), mit `<-- change`-Marker bei der Flanke.
- **Nur Bit 0** bewegt sich, L2..L6 bleiben `○`.
- Kurzes Prellen wird von der FW-Entprellung (2 Ticks / ~20 ms) geschluckt — kein Flackern.

> Melde: folgt `L1` sauber dem Taster? Bleiben L2..L6 ruhig?

Optional Kabelbruch-Check (fail-safe): Kabel abziehen → `L1○` (0, kein Kontakt) — sichere Fehlrichtung.

---

## HW5.9 — Host-Bench: /leg_1/foot_contact + gait_node-Naht

Firmware weiter verbunden. Jetzt der Host-Pfad — das Plugin publisht die 6 Bool-Topics. Loopback
**aus** (echte HW):

```bash
# Terminal A — HW-Bringup (aufgebockt/stromlos ok, wir enablen nichts):
source /opt/ros/jazzy/setup.bash && source ~/hexapod_ws/install/setup.bash
ros2 launch hexapod_bringup real.launch.py loopback_mode:=false serial_port:=/dev/ttyACM0
```

```bash
# Terminal B — Bool-Topic beobachten:
source /opt/ros/jazzy/setup.bash && source ~/hexapod_ws/install/setup.bash
ros2 topic echo /leg_1/foot_contact
```

Erwartung:
- Topic tickt dauerhaft (~50 Hz), `data: false` los / `data: true` gedrückt.
- Alle 6 Topics existieren:
  ```bash
  ros2 topic list | grep foot_contact
  # → /leg_1/foot_contact … /leg_6/foot_contact
  ```

**Naht-Check (gait_node unverändert):** Läuft der `gait_node` (z.B. via `ramp_walk.launch.py` oder
`gait.launch.py use_sim_time:=false`), spiegelt er die Kontakte in `/foot_contacts`:
```bash
ros2 topic echo /foot_contacts   # Float64MultiArray, Index 0 = leg_1
```

---

## Alle 6 Beine (nach HW5.9)

Restliche 5 Taster verdrahten (SENSOR_2..6). Firmware-Bitmaske:
```bash
cd ~/hexapod_servo_driver && python3 tools/probe_inputs.py
```
→ jeder Taster bewegt genau sein `Ln`-Flag (L1..L6), `raw` zeigt die kombinierte Maske
(z.B. leg 1+3 gedrückt → `raw=0x05`).

Host-Seite pro Bein:
```bash
for n in 1 2 3 4 5 6; do echo "leg $n:"; ros2 topic echo /leg_${n}/foot_contact --once; done
```

---

## Optionale Overrides

- **Mapping umverdrahtet?** Falls die physische Zuordnung von SENSOR_n=leg_n abweicht, ohne umlöten:
  ```bash
  ros2 launch hexapod_bringup real.launch.py loopback_mode:=false \
      publish_foot_contacts:=true
  # sensor_leg_map ist ein hardware_parameter (URDF); CSV der 6 Sensor-Kanäle je Bein 1..6,
  # z.B. "6,5,4,3,2,1". Default Identität. (Setzen via xacro-Arg/URDF, nicht als Launch-Arg.)
  ```
- **Fußkontakte aus** (Board ohne Taster): `real.launch.py … publish_foot_contacts:=false`
  → Plugin fragt GET_INPUTS nicht ab, legt die Topics nicht an; gait_node läuft ohne adaptive
  Features (nominal).

---

## Was NICHT getestet wird (scope-out)

- **S4-Closed-Loop auf HW** (adaptiver Touchdown/Stand mit echten Kontakten am laufenden Roboter) →
  eigener HW-Bring-up-Schritt (Phase 13, aufgebockt zuerst).
- **USER_SW (Bit 6):** wird mitgeführt (`SW●/○` in der Probe), aber vom Host ignoriert (kein Consumer).
- **Analoge Kraftsensoren** (0x41) — reserviert, nicht geplant.
