# Stufe 5 — HW-Fußkontakte (Taster am Servo2040)

> Teil-Stufe von Block A5. **Ziel:** die in der Sim verifizierte Fußkontakt-/S4-Pipeline (S4-1 Kontakt-
> Consumer, S4-2 adaptiver Touchdown, S4-5 Plausibilität, S4-7 Adaptive Stand) auf **echte Hardware**
> bringen — 6 Fuß-Taster am Servo2040, gelesen per Firmware, in ROS gespiegelt.
>
> **Status: 🟡 Kern-Implementierung (FW + Host) fertig + alle Software-Tests grün — nur HW-Bench (HW5.8/5.9) offen.**
> Voraussetzung Stufe 4 (S4-x) 🟢 Sim-verifiziert. **Bench-Schritt 1 (LED) bestätigt** (2026-07-04): leg-1
> an SENSOR_1 → Lese-Kette (Pull-Up gegen GND, Mux, Schwelle 1,65 V) auf HW verifiziert. **Firmware:**
> `GET_INPUTS`/`INPUTS` implementiert (poll_inputs im on_tick, alle 6 Kanäle Pull-Up, entprellt), Temp-
> LED-Code entfernt, PROTOCOL.md → 1.1, `probe_inputs.py` Bench-Tool; baut sauber. **Host:**
> `encode_get_inputs`/`decode_inputs`, Reader-Cache `InputsSnapshot(bits,stamp)`, 6 Bool-Publisher,
> GET_INPUTS pro write()-Zyklus, freshness-gated Publish; `real.launch.py`-Arg `publish_foot_contacts`.
> Tests grün (hexapod_hardware 252, hexapod_gait 402, bringup real-launch 3). **Nächstes: User flasht die
> FW + verdrahtet leg 1 → HW5.8/5.9 am Bench** ([Test-Doku](stage_5_hw_foot_contacts_test_commands.md)).
>
> **Die Naht (macht alles einfach):** Der `gait_node` abonniert 6× `/leg_<n>/foot_contact`
> (`std_msgs/Bool`) — **identisch für Sim und HW** ([gait_node.py:972-978](../../src/hexapod_gait/hexapod_gait/gait_node.py#L972-L978),
> Callback [1279-1291](../../src/hexapod_gait/hexapod_gait/gait_node.py#L1279-L1291), Live-Guard 0.5 s
> [:574](../../src/hexapod_gait/hexapod_gait/gait_node.py#L574)). In der Sim erzeugt
> `hexapod_sensors/foot_contact_publisher.py` diese Topics aus Gazebo. **Auf HW erzeugen wir dieselben
> 6 Bool-Topics aus dem Servo2040 → `gait_node` + gesamte S4-Pipeline bleiben unverändert.**

---

## 0. Kontext + Ist-Zustand

- **Protokoll ist vorbereitet:** `GET_INPUTS (0x40)` → `INPUTS (0xC0)`, 1-Byte-Bitmaske für 6 Sensor-
  Kanäle (SENSOR_1..6 über Analog-Mux, geteilt via GP29) + `USER_SW` (Bit 6). Opcodes definiert in
  `hexapod_servo_driver/src/config.hpp:112-114` und `hexapod_hardware/include/hexapod_hardware/servo2040_protocol.hpp:26-27`.
- **Firmware: `GET_INPUTS` NICHT implementiert** — wird mit `NACK/UNKNOWN_OPCODE` abgewiesen
  (`hexapod_servo_driver/src/main.cpp:397-398`). `analog_reader.hpp` liest die Sensoren aktuell als
  **analoge Spannung** mit **Pull-Down** (`:28,:33`).
- **Host-Plugin: nutzt `GET_INPUTS` nicht** — exportiert nur Position-State/Command je Joint, keine
  Sensor-Interfaces. Hat aber schon ein Topic-Publish-Muster (`/hexapod/shutdown_request`,
  `hexapod_system.cpp:433`) + COBS/CRC/Frame-Protokoll.
- **Bringup: `real.launch.py` hat keine Fußkontakt-Quelle** (kein `hexapod_sensors`, kein Gazebo).

## 1. Verdrahtung (verbindlich)

- **Pro Fuß-Taster (normally-open), 2 Kabel** zum Servo2040-Sensor-Header:
  - Kabel 1 → **`IN`** des Kanals (SENSOR_n)
  - Kabel 2 → **`GND`** (Header-GND; GND ist gemeinsam)
- **Konvention:** interner **Pull-Up** auf `IN`. Fuß in der Luft → offen → `IN` HIGH → **kein Kontakt (0)**.
  Fuß am Boden → Taster geschlossen → `IN` gegen GND → LOW → **Kontakt (1)** (Firmware negiert bzw.
  Schwelle „Spannung < Mitte = Kontakt").
- **Mapping:** `SENSOR_1 = leg_1`, `SENSOR_2 = leg_2`, … `SENSOR_6 = leg_6`.
- **Fail-safe:** Kabelbruch/abgezogen → `IN` per Pull-Up HIGH → liest 0 (kein Kontakt) — sichere
  Fehlrichtung; S4-5 fängt einen „toten" (immer-0) Taster ab.
- **Optional gegen Rauschen** bei langen Bein-Kabeln: kleiner Kerko (10–100 nF) `IN`↔`GND` am Header;
  zusätzlich greift die Firmware-Entprellung.
- **`3V3`-Pin des Headers bleibt frei** (wird für passive Taster nicht gebraucht).

## 2. Logik-Skizze / Pseudocode

### 2.1 Firmware (`hexapod_servo_driver`)

**Init (Pull-Up + Snapshot-State):**
```
// analog_reader: Sensor-Kanäle auf Pull-Up statt Pull-Down
for i in 0..NUM_SENSORS: mux.configure_pulls(SENSOR_1_ADDR + i, /*pull_up=*/true, /*pull_down=*/false)
// neue State: entprellter Snapshot + pro-Kanal Stabilitäts-Zähler
uint8_t inputs_stable = 0            // Bit i = Kontakt Bein (i+1); Bit 6 = USER_SW
uint8_t inputs_raw_last[7], stable_count[7]
```

**Sampling im on_tick() (100 Hz) — Muster wie `poll_switch` (main.cpp:426):**
```
for ch in 0..5:
    mux.select(SENSOR_1_ADDR + ch)
    raw = (sen_adc.read_voltage() < THRESHOLD_V)   // Pull-Up + gg. GND → gedrückt = LOW = Kontakt
    debounce(ch, raw) -> commit in inputs_stable Bit ch
raw6 = gpio_get(USER_SW)                            // Bit 6 (Onboard, unbenutzt vom Host)
debounce(6, raw6) -> inputs_stable Bit 6
// Voltage/Current-Sense weiter alle 5 Ticks (Mux teilen — select vor jedem Read, schon so)
```

**Handler `handle_get_inputs(seq)` + Dispatch:**
```
case cmd::GET_INPUTS:
    if len != 0: send_error(PAYLOAD_LEN); return
    send_frame(seq, INPUTS_RESPONSE, [inputs_stable])   // 1 Byte
// (aus der NACK-Gruppe main.cpp:394-398 herausnehmen)
```

### 2.2 Host-Plugin (`hexapod_hardware`)

**on_configure() — 6 Publisher (Muster shutdown_request):**
```
for n in 1..6: foot_pub[n] = node->create_publisher<std_msgs::Bool>("/leg_" + n + "/foot_contact", 10)
declare param publish_foot_contacts (default true), sensor_leg_map (default identity)
```

**Protokoll:**
```
encode_get_inputs(seq) -> Frame(GET_INPUTS, len=0)
reader-thread: bei INPUTS_RESPONSE (0xC0, 1 B) -> inputs_cache = payload[0]; inputs_stamp = now
```

**write() — pro Zyklus (~50 Hz) mitsenden:**
```
... encode_set_targets(...) senden ...
encode_get_inputs(seq++) senden     // jeden Zyklus (Kontakt-Timing zählt für adaptiven Touchdown)
```

**read() (oder 50-Hz-Timer) — spiegeln:**
```
if publish_foot_contacts:
  for n in 1..6:
      ch = sensor_leg_map[n]                       // default n
      foot_pub[n].publish(Bool{ (inputs_cache >> (ch-1)) & 1 })
// Staleness braucht KEINEN Extra-Code: bleibt inputs_cache stehen (FW antwortet nicht mehr),
// greift der 0.5-s-Live-Guard im gait_node → adaptive Features aus (Fallback nominal).
```

**→ `gait_node` unverändert** (abonniert genau diese 6 Bool-Topics).

## 3. Tests-Liste (mit Begründung)

| Test | Prüft | Ort |
|---|---|---|
| **FW: GET_INPUTS Bitmaske** | gedrückter Kanal → Bit gesetzt; LEN≠0 → `ERR_PAYLOAD_LEN`; Antwort-Opcode 0xC0 | Bench-Tool (`probe.py`/`test_servo2040.py`) |
| **FW: Pull-Up + Schwelle** | offen → 0, gegen GND → 1 (Negation korrekt) | Bench (Jumper IN↔GND) |
| **FW: Entprellung** | prellender Kontakt → stabiler Snapshot (kein Flattern) | Bench (Taster mehrfach) |
| **Host: Frame-Roundtrip** | `encode_get_inputs` + Parse `INPUTS_RESPONSE` (COBS/CRC) | Unit (falls Protokoll-Test existiert) |
| **Host: Bool-Topics** | 6× `/leg_<n>/foot_contact` publizieren ~50 Hz; Bit→Bool; Mapping SENSOR_n=leg_n | Bench (`ros2 topic echo`) |
| **Naht: gait_node unverändert** | `/leg_1/foot_contact` toggelt mit dem Taster; `gait_node`-Cache folgt | Bench (leg 1) |
| **Bench leg 1** | Taster an SENSOR_1 → `/leg_1/foot_contact` true/false; dann alle 6 | Live (aufgebockt) |
| build/lint | FW-Build + host `colcon build/test` grün | — |

**Bewusst NICHT (→ scope-out / später):**
- **Analoge Kraftsensoren** (`0x41 GET_SENSORS_ANALOG`) — reserviert, nicht geplant.
- **S4-Closed-Loop-Verhalten auf HW** (adaptiver Touchdown/Stand mit echten Kontakten am fahrbereiten
  Roboter) — eigener HW-Bring-up-Schritt (Phase 13, aufgebockt zuerst, §9-Sicherheit).
- **`USER_SW` (Bit 6)** — mitgeführt, aber vom Host ignoriert (kein Consumer).
- **Per-Taster-Kalibrierung / analoge Schwelle pro Kanal** — feste globale Schwelle reicht für
  mechanische Taster.

## 4. Progress-Checkliste (→ Progress-File, Done-Vertrag)

```
HW5 (HW-Fußkontakte):
- [x] HW5.0 Bench-Vorabtest (temporärer LED-Test): leg-1 an SENSOR_1 → LED 6 folgt → Pull-Up/Mux/Schwelle auf HW verifiziert (2026-07-04). ⚠️ Temp-Code entfernt (HW5.2).
- [x] HW5.1 FW: alle 6 Sensor-Kanäle auf internen Pull-Up (main.cpp configure_pulls true/false); digitale Schwelle SENSOR_THRESHOLD_V=1,65 V
- [x] HW5.2 FW: entprellter 7-Bit Input-Snapshot poll_inputs() im on_tick (6 Sensoren + USER_SW), Muster poll_switch; Temp-poll_foot_led/FOOT_THRESHOLD_V entfernt
- [x] HW5.3 FW: handle_get_inputs (0x40 → 0xC0, LEN-Check), aus der NACK-Gruppe herausgenommen
- [x] HW5.4 FW: PROTOCOL.md §3.2 auf Pull-Up/gegen-GND/Schwelle/Entprellung + Version 1.1 + Änderungshistorie; probe_inputs.py + CMD_GET_INPUTS/CMD_INPUTS_RESP
- [x] HW5.5 Host: encode_get_inputs + decode_inputs; Reader INPUTS_RESPONSE (0xC0) → InputsSnapshot(bits, stamp) + latest_inputs()
- [x] HW5.6 Host: 6× /leg_<n>/foot_contact (Bool) Publisher (Muster shutdown_request) + sensor_leg_map (identity-default) + publish_foot_contacts hardware_parameter
- [x] HW5.7 Host: GET_INPUTS pro write()-Zyklus (~50 Hz); read() publisht freshness-gated (100 ms → gait-Live-Guard bleibt wirksam)
- [ ] HW5.8 Verdrahtung leg 1 (SENSOR_1 IN+GND, NO) + Bench-Verify FW (probe_inputs.py, Bitmaske Bit0 toggelt)  ← HW, User
- [ ] HW5.9 Bench-Verify Host (/leg_1/foot_contact toggelt, gait_node /foot_contacts folgt) → dann alle 6  ← HW, User
- [x] HW5.10 real.launch.py: publish_foot_contacts Launch-Arg (default an) + xacro-Arg + <param>; Naht-Check gait_node unverändert
- [x] HW5.11 FW-Build (make -j sauber) + host colcon build/test + Lint grün (hexapod_hardware 252 / hexapod_gait 402 / bringup real-launch 3)
- [x] HW5.12 kritische Self-Review-Tabelle (→ imu_balance_progress.md Stufe-5-Post-Review)
```

## 5. Design-Entscheidungen (mit Alternativen)

| Entscheidung | Gewählt | Verworfen | Warum |
|---|---|---|---|
| Verdrahtung | **IN + GND, Pull-Up, NO** | IN + 3V3, Pull-Down | GND am Bein reichlich vorhanden, kein live-Rail zum Fuß; idiomatische Taster-Beschaltung; fail-safe→0; macht PROTOCOL.md §3.2 korrekt |
| Host-Anbindung | **Plugin publisht Bool-Topics** | ros2_control Sensor-Interface + Broadcaster | hält die Naht **identisch** zur Sim (gait_node unverändert); nutzt vorhandenes shutdown_request-Muster; Sensor-Interface wäre „sauberer", aber invasiv (gait_node müsste umgestellt werden) |
| Sensor-Read | **digital (Schwelle)** | analog (Kraft) | mechanische Taster; analog ist im Protokoll (0x41) reserviert, nicht geplant |
| Poll | **GET_INPUTS pro Zyklus (~50 Hz)** | seltener / piggyback in STATE | Kontakt-Timing zählt für adaptiven Touchdown; Last unkritisch; dedizierter Opcode statt STATE-Payload-Änderung |
| Debounce | **Firmware (on_tick)** | Host-seitig | nah an der Quelle, entkoppelt von Poll-Rate; Muster poll_switch existiert |

## 6. Offene Punkte für User-Review

1. **Verdrahtung** IN+GND / Pull-Up / NO / `SENSOR_n=leg_n` — **freigegeben** (2026-07-… User). ✅
2. **GET_INPUTS pro write()-Zyklus** mitsenden (piggyback) — ok, oder lieber jeden 2. Zyklus (25 Hz)?
3. **Debounce-Zeit** ~20–30 ms (2–3 Ticks @ 100 Hz) — ok fürs Gait-Timing? (Sim hält Kontakt 0.1 s;
   S4-1 zeigte Ausführungs-Lag dominiert → kurze Entprellung unkritisch.)
4. **Schwelle** THRESHOLD_V ~1.65 V (halbe 3V3) — Implementierungs-Detail, ok als Default?
5. **Firmware-Repo:** eigener Branch/Commit (User macht git); PROTOCOL-Version 1.1 + Tag beim Umsetzen.

## 7. Handoff / Code-Anker

- **Firmware (`hexapod_servo_driver`):**
  - `src/main.cpp`: `:397` (GET_INPUTS-NACK → Handler), `:426` `poll_switch` (Debounce-Vorlage),
    `:466` `on_tick` (Sampling einhängen), `:366` `dispatch`.
  - `src/utils/analog_reader.hpp`: `:28` (Pull-Config → Pull-Up), `:33` `readSensor` (Schwelle).
  - `src/config.hpp`: `:112-114` (Opcodes vorhanden), Sensor-/USER_SW-Pins.
  - `PROTOCOL.md §3.2` (Pull-Richtung angleichen), §8 (Version 1.1).
  - `tools/probe.py` / `tools/test_servo2040.py` (GET_INPUTS-Test).
- **Host (`hexapod_ws`):**
  - `hexapod_hardware/include/hexapod_hardware/servo2040_protocol.hpp:26-27` (Opcodes), Frame/COBS/CRC.
  - `hexapod_hardware/src/hexapod_system.cpp`: `:376-514` on_configure (Publisher anlegen),
    `:886-955` read (publishen), `:957-1099` write (GET_INPUTS mitsenden), `:433` shutdown_request-Muster.
  - `hexapod_bringup/launch/real.launch.py` (publish_foot_contacts-Param).
  - **Consumer unverändert:** `hexapod_gait/hexapod_gait/gait_node.py:972-978/1279-1291/574`.
  - **Sim-Vorbild:** `hexapod_sensors/hexapod_sensors/foot_contact_publisher.py` (gleiche Topic/Message).

## 8. Bench-Log + Cleanup des Vorabtests

**Bench-Schritt 1 (LED-Test) 🟢 — 2026-07-04:** leg-1-Taster (NO) an SENSOR_1 `IN`+`GND`; interner
Pull-Up auf SENSOR_1; `poll_foot_led()` spiegelt gedrückt→LED 6 grün, los→aus. Auf HW **sauber
bestätigt**. Damit ist verifiziert: Pull-Up gegen GND + Mux-Select + `read_voltage()`-Schwelle (1.65 V)
erkennt den Taster zuverlässig. Firmware baut (`build/Hexapod_servo_driver.uf2`).

**Temporärer Code, der bei der GET_INPUTS-Umsetzung entfernt/überführt werden muss** (alles
`hexapod_servo_driver/src/main.cpp`, mit `HW5` markiert):
- `g_sen_sense`-Global + `static Analog sen_sense(SHARED_ADC)` → **bleibt** (wird für GET_INPUTS gebraucht).
- Sensor-/Mux-Init **vor die USB-Warteschleife** gezogen → **kann bleiben** (harmlos; ADC-Init ohne Host).
- `poll_foot_led()` + `FOOT_THRESHOLD_V` + die Aufrufe in `on_tick()` **und** in der Warteschleife →
  **entfernen** (LED-Test), ersetzt durch den entprellten Input-Snapshot (HW5.2) + `handle_get_inputs` (HW5.3).
- `configure_pulls(SENSOR_1_ADDR, true, false)` (nur SENSOR_1) → **erweitern** auf alle 6 Kanäle (HW5.1).
- LED 6 wird danach wieder frei (kein Foot-LED mehr).

> **Für den nächsten Chat:** Der Bench-Test beweist die HW-Lese-Kette. Ab hier ist es reine Software:
> FW `GET_INPUTS` (HW5.1–5.4) → am Bench mit einem Probe-Tool gegen leg 1 verifizieren → Host-Plugin
> publisht die 6 Bool-Topics (HW5.5–5.7) → `gait_node` unverändert → Bench alle 6 → Doku-Hygiene.

## 9. Doku-Hygiene bei Abschluss
- **Firmware-Repo:** `PROTOCOL.md` (§3.2 Pull-Up-Konvention, Version 1.1), Firmware-README/Progress.
- **hexapod_ws:** `imu_balance_progress.md` (HW5-Checkliste + Post-Review), diese Plan-Datei → 🟢.
- **`project_architecture/ai_navigation.md`:** neuer Eintrag „HW-Fußkontakt-Quelle" (Sim =
  `hexapod_sensors`, HW = `hexapod_hardware`-Plugin publisht die gleichen 6 Bool-Topics; „ich ändere
  die Kontakt-Topics → beide Quellen + gait_node-Sub anfassen").

---

## 10. Zusatz: RViz-Fußkontakt-Viz (Bench-Sichtprüfung, „B1")  — 🟡 Plan, Freigabe offen

> **Ziel:** Taster drücken → der zugehörige Fuß wird in **RViz** grün. Rein visuelle Bestätigung der
> Sensor-Kette (Taster → FW → Bool-Topic), unabhängig von Gait/Sim-Kontaktphysik. **Reine Zusatz-
> Politur** — der funktionale Nachweis läuft bereits über HW5.8/5.9 (`probe_inputs.py` + `ros2 topic
> echo`). **Entscheidung „B1":** nur ein neuer, quellen-agnostischer Viz-Node + RViz-Anzeige,
> **null Änderung an Firmware oder Plugin.**
>
> **Betrieb ohne Servo-Power (bewusst so):** Läuft gegen `real.launch.py loopback_mode:=false` **ohne**
> angeschlossene Servo-Power. Die FW meldet ~1 s nach dem Activate **einmal** einen Undervoltage-Trip
> (Rail liest ~0 V), latcht ihn und ist dann still. Das disabled nur die ohnehin stromlosen Servos und
> berührt `poll_inputs`/GET_INPUTS/Foot-Contact-Publish **nicht** — die Controller bleiben aktiv, die
> Bools fließen weiter. Also: ein kosmetischer Undervoltage-Log, **kein** Blocker. Bewusst akzeptiert
> (kein „sensors-only"-Modus — im Realbetrieb ohne Mehrwert, verworfen).

### 10.1 Design-Entscheidungen (fixiert mit User)

| Entscheidung | Gewählt | Verworfen | Warum |
|---|---|---|---|
| Kontakt-Quelle | **`real.launch.py loopback:=false`** (Plugin publisht die Bools) | Standalone-Serial-Node (A) | A wäre Wegwerf-Code; der Viz-Node ist quellen-agnostisch und **dauerhaft** nutzbar (Sim + HW) |
| Marker-Platzierung | **(a) `leg_<n>_foot_link`-TF-Frame** | (b) FK aus `/joint_states` im base_link | (a) = **kein** Kinematik-Code im Node, RViz platziert per TF; eine Quelle der Wahrheit (URDF). (b) dupliziert FK (2. Wahrheit), nur nötig wenn man die Fuß-Zahlen bräuchte (torque_viz) — hier nicht |
| Marker-Größe | **Ø ~0,020 m (Overlay der echten Fußkugel)** | RobotModel-Link direkt umfärben | RViz kann eine RobotModel-Link-Farbe **nicht** aus einem Topic umfärben. `foot_link` hat schon eine Visual-Kugel (`foot_radius = 0,008 m`, Material „black"); ein Marker am selben Frame, minimal größer (Ø 0,020 > 0,016), **überdeckt** sie → Fuß „wird" farbig, ohne 2. Ball und ohne URDF-Eingriff |
| Farbe | **grün = Kontakt / neutralgrau = offen** (+ dunkel/transparent = stale) | Bein-Label-Text | Farbe reicht, Fuß ist optisch eindeutig; stale-Farbe deckt „Pipeline tot" ehrlich ab |
| USER_SW (Bit 6) | **weglassen** | 7. Status-Marker | kein Consumer; „lebt die Kette?"-Check hat `probe_inputs.py` |
| Publish-Rate | **5 Hz (Timer-Republish)** | 50 Hz / Publish-pro-Callback | Marker gehen **nur** nach RViz (kein Logik-Consumer) → niedrige Rate reicht; 200 ms Update ist fürs Auge sofort, spart Last |
| RViz-Config | **`view_hw.rviz` erweitern** | eigene `view_foot_contact.rviz` | ein HW-View, kein Config-Wildwuchs |
| Convenience-Launch | **keiner (3-Terminal-Handbetrieb)** | `foot_contact_viz.launch.py` | `real.launch.py` liefert TF/RobotModel schon; klein halten |
| Paket | **`hexapod_gait`** (bei `torque_viz`/`reachability_viz`) | hexapod_sensors | Viz-Präzedenz + rclpy-Setup dort; hängt an nichts gait-Spezifischem, aber Konsistenz |

### 10.2 Logik-Skizze / Pseudocode

**Neuer Node `hexapod_gait/hexapod_gait/foot_contact_viz.py`** (Muster `torque_viz.py`):
```
class FootContactViz(Node):
  params: stale_timeout=0.5 (s), marker_scale=0.020 (m Ø, überdeckt die 0.016er Fußkugel), publish_rate=5.0 (Hz)
  _contact[1..6] = False
  _last_t[1..6]  = 0.0            # time.monotonic() der letzten Bool-Msg (wall, wie foot_contact_publisher)
  pub = create_publisher(MarkerArray, 'foot_contact_markers', 1)
  for n in 1..6: sub /leg_<n>/foot_contact (Bool) -> _cb(n)
  timer(1/publish_rate) -> _publish     # RViz-schonend aus dem Cache re-publishen

  _cb(n)(msg): _contact[n] = msg.data; _last_t[n] = monotonic()

  _publish():
    now = monotonic()
    arr = MarkerArray()
    for n in 1..6:
      m = Marker()
      m.header.frame_id = f'leg_{n}_foot_link'   # (a): RViz transformiert per TF
      m.header.stamp    = clock.now()            # wie torque_viz; Fallback stamp=0 (latest-TF) falls Extrapolations-Warnings
      m.ns='foot_contact'; m.id=n; m.type=SPHERE; m.action=ADD
      m.pose.position = (0,0,0); m.pose.orientation.w=1
      m.scale = marker_scale (x=y=z)
      if now - _last_t[n] > stale_timeout: m.color = DARK (a=0.4)   # keine/tote Pipeline → nicht als „offen" tarnen
      elif _contact[n]:                    m.color = GREEN (a=1.0)
      else:                                m.color = GREY  (a=0.9)
      arr.markers.append(m)
    pub.publish(arr)
```
**Begründung je Entscheidung:**
- **Timer-Republish (5 Hz) statt Publish-pro-Callback:** stetiger, RViz-schonender Marker-Strom (identisch torque_viz); entkoppelt von der ~50-Hz-Bool-Rate.
- **`frame_id = leg_<n>_foot_link`, Position 0:** RViz platziert den Marker über den TF-Baum (vom
  `robot_state_publisher` in `real.launch.py`). `foot_link` ist im HW-Pfad ein normaler Fixed-Joint-
  Frame (Gazebo-Contact-Sensorik ist sim-only) → immer im TF-Baum.
- **Overlay statt Umfärben:** `foot_link` hat bereits eine schwarze Visual-Kugel (`foot_radius=0.008`).
  Die RobotModel-Anzeige ist nicht per Topic umfärbbar; der Marker (Ø 0.020 > 0.016) sitzt am selben
  Frame und **überdeckt** die Fußkugel → der Fuß „wird" grün/grau, ohne 2. Ball, ohne URDF-Eingriff.
- **stale→dunkel:** wenn das Plugin bei FW-Stille aufhört zu publishen (Freshness-Gate aus HW5.7),
  soll der Fuß **nicht** fälschlich „offen/grau" zeigen, sondern „keine Daten" — ehrlich + billig.
- **`time.monotonic()` für Staleness:** wall-clock, robust ohne `/clock` (HW, `use_sim_time=false`);
  gleiche Wahl wie `foot_contact_publisher.py`.

**Kein Launch-Zwang:** Betrieb = 3 Terminals (`real.launch.py` / `ros2 run hexapod_gait foot_contact_viz`
/ `rviz2 -d view_hw.rviz`). Eine optionale Convenience-`foot_contact_viz.launch.py` (nur Node + RViz,
da `real.launch.py` TF/RViz-Model schon liefert) ist offener Punkt (§10.5).

**`view_hw.rviz`:** ein `MarkerArray`-Display auf `/foot_contact_markers` ergänzen (Fixed Frame
`base_link` bleibt; TF verbindet `base_link ↔ leg_<n>_foot_link`).

### 10.3 Tests-Liste (mit Begründung)

| Test | Prüft | Ort |
|---|---|---|
| **Unit: build_markers Farbe** | Kontakt-Beine → GREEN, offene → GREY; 6 Marker, `ns/id/type` korrekt | pytest (Muster `test_foot_contact_node`) |
| **Unit: frame_ids** | Marker n hat `frame_id == leg_<n>_foot_link` (Platzierungs-Vertrag) | pytest |
| **Unit: stale → DARK** | Bein ohne Msg > `stale_timeout` → DARK-Farbe (nicht GREY) | pytest (`_last_t` alt setzen) |
| **build/lint** | `colcon build/test hexapod_gait` + flake8/pep257/copyright grün | — |
| **Live-RViz-Bench (User)** | `real.launch.py` + Node + RViz → Taster N drücken → Fuß N grün; loslassen → grau | Live (aufgebockt/stromlos) |

**Bewusst NICHT (→ scope-out):**
- **RViz-Rendering selbst** (visuell, Handprüfung am Bench — nicht automatisierbar).
- **TF-Verfügbarkeit / Integration** mit `real.launch.py` (durch bestehende rsp-/broadcaster-Tests
  abgedeckt; hier kein Neu-Test).
- **Serieller/Plugin-Pfad** (bereits HW5.5–5.11); der Viz-Node ist reiner Bool→Marker-Adapter.
- **Firmware/Plugin** — **unverändert** (B1).

### 10.4 Progress-Checkliste (→ Progress-File, Done-Vertrag)

```
HW5v (RViz-Fußkontakt-Viz, B1):
- [ ] HW5v.1 foot_contact_viz Node (6 Bool-Subs, MarkerArray auf /foot_contact_markers, foot_link-Frame, grün/grau/stale-dunkel, 5-Hz-Timer-Republish)
- [ ] HW5v.2 Entry-Point in hexapod_gait/setup.py (console_scripts foot_contact_viz)
- [ ] HW5v.3 view_hw.rviz um MarkerArray-Display (/foot_contact_markers) erweitern
- [ ] HW5v.4 Unit-Tests (build_markers: Farben, frame_ids, stale→dunkel) + colcon test/lint grün
- [ ] HW5v.5 Test-Doku ergänzen (stage_5_..._test_commands.md: RViz-Bench real.launch.py + node + rviz)
- [ ] HW5v.6 kritische Self-Review-Tabelle (→ imu_balance_progress.md)
- [ ] HW5v.7 Live-RViz-Bench (User): Taster N → Fuß N grün, loslassen → grau  ← HW, User
```

### 10.5 Offene Punkte für User-Review — **geklärt (User, 2026-07-04)**

1. **Marker-Größe:** ✅ Ø 0,020 m als **Overlay der vorhandenen Fußkugel** (`foot_radius=0.008`);
   RobotModel-Link ist nicht per-Topic umfärbbar → Marker am selben `foot_link`-Frame überdeckt sie.
2. **stale→dunkel:** ✅ mit reinnehmen (FW-Stille → „keine Daten", nicht „offen").
3. **Convenience-Launch:** ✅ **keiner** — 3-Terminal-Handbetrieb reicht.
4. **Marker-Topic:** ✅ `/foot_contact_markers`.
5. **Republish-Rate:** ✅ **5 Hz** (display-only, kein Logik-Consumer → niedrige Rate genügt).
