# A5 — IMU-Integration & Balance — Master-Plan

> **Block A5** aus dem [Finalisierungs-Backlog](../00_backlog.md). Aktiviert die in
> [`../peripherals_tests/imu_bno055.md`](../peripherals_tests/imu_bno055.md) als
> Hello-World verifizierte **BNO-055** als echtes ROS-Subsystem: Lage-Erkennung,
> Körper-Leveling, perspektivisch Hang-/Terrain-Lokomotion.
>
> **Branch:** `imu_balance`. **Arbeitsweise:** CLAUDE.md §4 — pro Stufe
> Plan → Freigabe → Implementierung → Tests → kritischer Self-Review. Dieser
> Master-Plan hält **Gesamtbild + Architektur-Entscheidungen + Risiko-Register**;
> die `stage_<n>_*_plan.md` halten die §4-Details je Stufe;
> [`imu_balance_progress.md`](imu_balance_progress.md) ist der Done-Vertrag.

---

## ⚠️ RICHTUNGSWECHSEL (Stand 2026-06-27) — Klettern: Leveln → Terrain-Following

Der Sim-Test von Stufe 3c-1 hat gezeigt, dass **Körper-Leveln zur Wasserwaage fürs Klettern
der falsche Ansatz ist** (sieht sprawlig aus, Plateau-Reset-Bug, Trippeln). **Neuer Ansatz:
Terrain-Following** — der Körper folgt dem Boden (flach → waagerecht, Hang → hangparallel);
der IMU dient für **Sicherheit + Wackel-Dämpfung + Hang-Wissen**, nicht zum Waagerecht-Zwingen.

- **Neuer Plan:** [`terrain_following_plan.md`](stage_3_terrain_following_plan.md) (TF-1/2/3).
- **Warum + was verworfen wurde:** [`terrain_following_pivot_retro.md`](terrain_following_pivot_retro.md).
- **Betroffen unten:** §1 „Stufe 3" (Leveling im Lauf / Weg-A-Geometrie-Tabelle) ist fürs
  **Klettern verworfen** — die 3c-Pläne (`stage_3c_*`) sind als VERWORFEN markiert. Stufe 0/1/2
  + `BalanceController`/Welten **bleiben** als Fundament (Regler wird für TF umgepolt). Die
  3b/3d-Ideen (Wackel-Dämpfung, Schlupf) leben im TF-Plan weiter. Das Folgende ist insoweit
  **historischer Kontext** des verworfenen Wegs.

---

## 0. Kontext-Befund (warum das billiger ist als es klingt)

Drei Dinge aus der Code-Analyse, die die Integration stark vereinfachen:

1. **Das System ist bereits live-parametrisch, nicht statisch.** Die Gangart ist
   kein abgespieltes Joint-Playback, sondern ein Generator, der jeden Tick
   (50 Hz) Fuß-Targets rechnet und durch **einen** zentralen IK-Punkt schickt
   (`GaitEngine.compute_joint_angles`,
   [`gait_engine.py`](../../src/hexapod_gait/hexapod_gait/gait_engine.py)).
   Leveling = diesen einen Punkt modulieren, kein Umbau.
2. **B4/Show-Pose hat den Base-Frame-Umweg schon gebaut** (`_show_foot`:
   `leg_to_base_frame` → im Body-Frame modifizieren → `base_to_leg_frame`).
   Heute als **Translation** (`body_shift_back`); Leveling ist dasselbe Muster
   als **Rotation** `R(roll, pitch)`.
3. **Die Fußkontakt-Pipeline existiert in Sim schon vollständig**
   (`hexapod.foot_contact.xacro` → Bridge → `foot_contact_publisher.py` → `Bool`
   auf `/leg_<n>/foot_contact`). Der IMU-Sim-Pfad spiegelt **exakt** dieses Muster.

---

## 1. Ziel & Abgrenzung — fünf Fähigkeiten, nicht eine

„IMU integrieren" zerfällt in fünf unterscheidbare Fähigkeiten mit sehr
unterschiedlicher Schwierigkeit und unterschiedlichem Sensorbedarf:

| Stufe | Fähigkeit | Signal | Schwierigkeit | Taster? |
|---|---|---|---|---|
| **0** | IMU in ROS (`/imu/data`, Sim-gz-Sensor + HW-Treiber, Viz) | – | niedrig (Plumbing) | nein |
| **1** | **Kipp-/Sturz-Erkennung → Safe-State** | roll/pitch + Gyro-Rate | niedrig, **hoher Wert** | nein |
| **2** | **Körper-Leveling statisch** (am Hang horizontal stehen) | fused roll/pitch | mittel | nein |
| **3** | **Leveling im Laufen** + Wackel-Dämpfung (B3-Fix) + Hang-Parameter | fused roll/pitch + Gyro-Rate | mittel-hoch | nein |
| **4** | **Terrain-adaptive Lokomotion** (Touchdown nach Kontakt, Schlupf) | IMU + **Fußkontakt** | hoch (Forschung) | **ja** |

> **Konsequenz:** Stufe 0–3 brauchen die Fußtaster **nicht** — Leveling und
> Kipp-Erkennung laufen rein über den Schwerkraftvektor. Die Taster (Block E2)
> werden erst in **Stufe 4** (echtes unebenes Terrain) tragend. Reihenfolge daher:
> IMU als **aktiver** Strang jetzt; die Fußkontakt-Pipeline darf in Sim **passiv
> mitlaufen** (visualisieren/loggen), aktiver Consumer erst Stufe 4.

---

## 2. Terrain-Entscheidung: progressiv (A-Fundament → erweiterbar zu B)

Zwei Wege, einen Hang zu meistern:

- **Weg A — parametrische Familie offline validieren, online evaluieren:**
  offline **einmal** die sichere Parameter-Hülle als Funktion des Hangwinkels θ
  rechnen (`θ → body_height, step_height, radial, Gangart` + Max-θ); zur Laufzeit
  IMU-θ in die vorab-bewiesene Kurve einsetzen. Adaptiert kontinuierlich an
  **jeden** (auch wechselnden) Hang, nie außerhalb der bewiesenen Hülle. Löst
  **glatte Schrägen** vollständig, ohne Fußtaster.
- **Weg B — Voll-Online-Planung + Live-Feasibility:** Parameter zur Laufzeit
  from scratch + live verifizieren (IK/CoG) + replan. Nötig erst bei **echt
  unebenem** Terrain (per-Fuß unvorhersehbare Bodenhöhe) → braucht Fußtaster.

> **Entscheidung (User): progressiv.** A-Fundament zuerst (glatte Hänge,
> Stufe 2–3), Architektur so schneiden, dass B (online + Fußkontakte) für
> unebenes Terrain später **aufgesetzt** werden kann, ohne A wegzuwerfen. Die
> finale A/B/Hybrid-Wahl fällt in **Stufe 3 mit echten Gazebo-Daten**.
>
> Begründung: Stufe 0–2 sind A/B-**unabhängig** (identischer Code); „der Hang
> ändert sich" unterscheidet A und B **nicht** (beide werten live das *momentane*
> θ aus); B hängt zwingend an den noch nicht verbauten Tastern + am 50-Hz-
> Echtzeitbudget. Ein vernünftiges B replant zudem nicht jeden Tick, sondern bei
> θ-Änderung + cached → konvergiert praktisch gegen A.

---

## 3. Stufen-Roadmap

| Stufe | Ziel | Kern-Output | Done-Idee |
|---|---|---|---|
| **0** | IMU-Plumbing/Viz | `hexapod.imu.xacro`, `bridge_imu.yaml`, `imu_monitor`-Node, RViz | `/imu/data` getraut, Ground-Truth-Abgleich grün |
| **1** | Kipp-Erkennung | Schwellen-Logik + Safe-State im `gait_node`, State-Gating | über Schwelle → Reaktion; kein Fehlalarm beim Laufen |
| **2** | Statisches Leveling | `BalanceController` (austauschbar) + Rotations-Stellpfad + Envelope-Clamp | auf Schräg-Welt body level, in-Limit, kein Freeze |
| **3** | Leveling im Laufen + Hang-Params | Gyro-Dämpfung, θ→Parameter-Familie (Weg A), Gangart-Auto-Switch | Hang hoch/runter in Gazebo, ruhiges Nicht-Tripod |
| **4** | Terrain (Weg B) | Fußkontakt-Consumer, adaptiver Touchdown, Schlupf | unebenes Terrain — **viel später, eigene Planung** |

**Stufen-Pläne:** [Stufe 0](stage_0_imu_plumbing_plan.md) · [Stufe 1](stage_1_tip_detection_plan.md) ·
[Stufe 2](stage_2_static_leveling_plan.md) · [Stufe 3](discarded/stage_3_walking_slope_plan.md) ·
[Stufe 4](stage_4_terrain_adaptive_plan.md). Stufe 0+1 = 🟢 (Sim). Pläne 2–4 sind
**vorausgeplant** (Logik/Tests/offene Punkte) zum Nachlesen — **implementiert wird
pro Stufe nach §4** (Plan-Review → Freigabe → Code); die „Offene Punkte" je Stufe
werden vor dem Code entschieden. Test-Markdowns entstehen erst am Ende jeder Stufe.

---

## 4. Architektur-Entscheidungen (Design-Log mit verworfenen Varianten)

### D1 — Ort der Balance-Logik

- **Gewählt (dreischichtig, analog Engine=wertneutral / Strategie=Config):**
  1. **Regler** = reine Python-Klasse `BalanceController` (keine ROS-Dependency,
     unit-testbar wie `hexapod_kinematics`), Schnittstelle
     `update(roll, pitch, gyro, dt, state) → (corr_roll, corr_pitch)`.
  2. **Stellpfad** = in der `GaitEngine`: neue Methode
     `set_body_orientation_offset(corr_roll, corr_pitch)` + Anwendung der Rotation
     mit Envelope-Clamp **zentral** in `compute_joint_angles`.
  3. **ROS-Glue** = im `gait_node`: `/imu/data`-Subscriber → roll/pitch/gyro →
     `BalanceController.update` → `engine.set_body_orientation_offset`.
- **Verworfen:** (a) alles im `gait_node` — schlecht testbar, koppelt Sensor +
  Logik + Stellgröße; (b) alles in der Engine — Engine wird sensor-stateful,
  Algorithmus nicht mehr austauschbar; (c) komplett externer Balance-Node nur
  per Topic — modular, aber Zusatz-Latenz + Topic mehr im 50-Hz-Pfad. Die
  gewählte Variante erfüllt **„austauschbarer Algorithmus" (1)** *und* **„zentraler
  Clamp am Limit" (2)**.

### D2 — Stellpfad (Körper-Rotation)

- **Gewählt:** `R(roll, pitch)` um den base_link-Ursprung auf **alle 6 Fuß-Targets**
  im Base-Frame — exakt das B4-Round-Trip-Muster (`leg_to_base_frame` → rotieren →
  `base_to_leg_frame`), zentral in `compute_joint_angles`, **vor** der IK auf die
  **URDF-Joint-Limits / Reichweite geclampt** (siehe Risiko 1 + 6).
- **Verworfen:** (a) nur per-Bein-Z-Offset (kann nur Höhe, kein echtes Leveling um
  eine gekippte Achse); (b) Rotation in jeden Trajektorien-Generator
  (`swing_traj`/`stance_traj`/…) — verstreut, mehrere Stellen synchron zu halten.

### D3 — Austauschbares Regler-Interface + v1-Gesetz

- **Gewählt:** schmale `BalanceController`-Schnittstelle; v1-Implementierung =
  **Totband-PI + Slew-Rate-Limit am Ausgang + Anti-Windup-Clamp** (gekoppelt an den
  erreichbaren Kippwinkel). Langsamer Winkel-Loop (gegen den Hang) + optional
  schneller **Gyro-Raten-Term** (Wackel-Dämpfung, Stufe 3).
- **Offen gehalten (Alternative):** das **Dual-Tiefpass/Dual-Fenster-Schema** des
  Users als zweite Implementierung hinter derselben Schnittstelle. Gegenüberstellung
  + Auswahl in Gazebo (Stufe 2). Der **kurze Filter** bleibt als Parameter (auch
  „quasi aus" stellbar) — schützt gegen Einzel-Spikes.
- **Begründung Totband:** verhindert, dass 18 Servos dem IMU-Rauschen/Gang-Ripple
  hinterherjagen (Hitze/Verschleiß/Strom). **Timescale-Trennung:** langsamer Filter
  trennt „Hang" (langsam, korrigieren) von „Gang-Ripple" (schnell, ignorieren) —
  *nicht* Rausch-Filterung, sondern Eigenbewegungs-Unterdrückung.

### D4 — IMU-Modus & Signale

- **Gewählt:** BNO-055 im **„IMU"-Fusionsmodus (ACC+GYRO, ohne MAG)**. Konsumiert:
  **roll/pitch** (schwerkraft-referenziert, robust) + **Gyro-Rate** (Dämpfung).
  **Absolutes Yaw/Heading ignoriert** (Mag nahe Servos unbrauchbar, ~230 µT). Die
  **Bergab-Richtung** kommt aus der roll/pitch-Projektion — braucht kein Yaw.
- **Verworfen:** NDOF-Modus (braucht Mag-Cal, Rohmag liest 0, Heading verseucht).
  Gyro-Yaw-Rate bleibt verfügbar (Drehung-am-Hang-Erkennung später).

### D5 — A/B für Hang-Lokomotion

→ **progressiv** (siehe §2). Entscheidung auf **Stufe 3** vertagt, mit Gazebo-Daten.

### D6 — Sim-Sensor-Realismus

- **Gewählt:** gz-IMU-Sensor analog `hexapod.foot_contact.xacro`; **realistisches
  Rauschen** parametrieren ODER Sim bewusst als reine **Logik-/Geometrie-Validierung**
  behandeln, Loop-Gains auf HW nachziehen.
- **Begründung (B2-Befund):** Gazebo hat keine Servo-Dynamik/-Nachgiebigkeit; gilt
  sinngemäß für die Sensor-Seite (gz-IMU ist per Default rausch-/vibrationsfrei).
  **Sim = Logik/Geometrie/Envelope. HW = Gains.**

---

## 5. Risiko-Register

| # | Risiko | Wirkung | Mitigation | greift ab |
|---|---|---|---|---|
| **1** | 🔴 IKError→Safety-Freeze | Leveling schiebt Fuß out-of-envelope → **ganzer Roboter friert ein** (`_trigger_safety_freeze` bei IKError) | Körper-Rotation **VOR der IK** auf URDF-Limits clampen; IKError nie als Leveling-Grenze | Stufe 2 |
| **2** | 🔴 CoG-auf-Hang + Selbst-Kollision (A4) | Kippen trotz gültiger IK; per-Bein-IK kennt **keine** Inter-Bein-Kollision | CoG-auf-Hang-Modell (wie `show_pose_cog_check`); **A4 reaktivieren**, sobald Body-Rotation scharf | Stufe 2–3 |
| **3** | 🟡 Closed-Chain / Fuß-Scrubbing | Body-Rotation mit aufgesetzten Füßen → Scrubben/innere Kräfte | kleine Winkel direkt abfangen; Schwelle überschritten → **Reposition** (lift-and-reset, `REPOSITION`-Muster, User-Punkt 3) | Stufe 2 |
| **4** | 🟡 IMU-Vibration + sauberer Sim-Sensor | fused roll/pitch zappelt auf HW; Sim zu optimistisch | **Stufe-0-Check mit aktiven Servos**; starre Montage; gz-Rauschen / Sim=Logik | Stufe 0 |
| **5** | 🟡 use_sim_time-Falle | Balance/IMU-Node tickt auf HW ohne `/clock` **still nicht** | `use_sim_time` sauber durchreichen (bekannte `gait.launch`-Pendenz) | Stufe 0 |
| **6** | 🟡 Zwei Limit-Quellen | Clamp mit stale `config.py` erlaubt HW-Freeze-Posen | Clamp nutzt die **URDF-geparsten `joint_limits`** (die die IK schon nutzt) | Stufe 2 |

---

## 6. Test-Strategie (drei Schichten)

1. **Offline-Batch (Dev-Rechner, ohne Gazebo):** validiert **Planer/Mathe** —
   produziert Stufe 2/3 für N Hangwinkel in-Limit + CoG-stabile Posen? Plan:
   20 lineare + 20 wechselnde Hänge als pytest/Skript. Billig, viele Fälle. Beweist
   **nicht** das dynamische Ergebnis.
2. **Gazebo (Teilmenge):** Dynamik/Stabilität — kippt/rutscht er auf der Rampe?
   **Ground-Truth-Körperlage** gegen IMU-Schätzung gegenchecken.
3. **HW aufgebockt → Boden:** Realität + Loop-Gain-Nachtuning (CLAUDE.md §9).

---

## 7. Doku-/Querverweis-Plan (bei Live-Schaltung nachziehen — NICHT jetzt)

- [`../00_backlog.md`](../00_backlog.md): A5 → 🟡 (+ E2-Bezug notieren).
- [`../../project_architecture/architecture.md`](../../project_architecture/architecture.md):
  `/imu/data`-Zeile real, `hexapod_sensors`-Inhalt, neuer IMU-Node/-Sensor.
- [`../../project_architecture/ai_navigation.md`](../../project_architecture/ai_navigation.md):
  neuer Eintrag „Ich ändere Balance/IMU → …".
- [`../../PHASE.md`](../../PHASE.md): A5 aktiv.
- READMEs: `hexapod_sensors` (IMU-Adapter), `hexapod_description` (imu-xacro),
  `hexapod_bringup` (`enable_imu`).

---

## 8. Datenfluss Sim ↔ HW (IMU-Quelle + RViz-Viz)

| | IMU-Quelle | Topologie | RViz |
|---|---|---|---|
| **Sim (Stufe 0–3, jetzt)** | gz-IMU-Sensor → Bridge | alles lokal am Dev-Rechner, kein Pi/Netz | lokal |
| **HW (später)** | `bno055`-Node **am Pi** (I2C) | Pi publisht `/imu/data` → **ROS2-DDS im LAN** → Dev | Dev abonniert via DDS |

- Der Sensor sitzt **am Pi** — nur der Pi liest ihn. Der bisherige Bench-Workflow
  (Dev ↔ Servo2040 per USB, **ohne Pi**) hat **keinen** IMU; IMU-auf-HW braucht den
  laufenden Pi-Node.
- DDS ist **netzwerk-transparent**: gleiche `ROS_DOMAIN_ID` + LAN → `/imu/data`
  erscheint am Dev automatisch. ⚠️ **Cross-Machine-DDS/RViz ist im Projekt deferiert**
  (PHASE.md) — Mechanismus Standard, LAN-Setup noch offener Schritt. Für Stufe 0–3
  irrelevant (alles Sim/lokal).
- **RViz-Modell-Neigung** (via `imu_monitor` `world→base_link`-tf aus roll/pitch)
  funktioniert **gleich in Sim und HW**. Heute bridged ihr nur `/clock` → RViz zeigt
  die Körperneigung aktuell NICHT; das liefert erst dieser tf.

---

## 9. Offene Punkte (Block-Ebene)

- **θ→Parameter-Familie:** wo lebt das Offline-Modell (eigenes Tool in `tools/`,
  wie `reachability_viz`/`torque_viz`)? — Detail in Stufe 3.
- **Welten / gz-imu-system:** `hexapod_gazebo/worlds/` ist **leer** und `empty.sdf`
  (Harmonic) hat **kein `gz-sim-imu-system`** (verifiziert) → schon Stufe 0 braucht
  `worlds/empty_imu.sdf` (= empty.sdf + imu-system). Für Stufe 2/3 darauf aufbauend:
  gekippte Ebene (gleichmäßiger Hang, mehrere Winkel) **+** Keil/Rampe
  (flach→Hang→flach) — alle mit imu-system. `world:=`-Arg existiert schon.
- **Hang-Reibung:** am Hang steigt Tangential/Normal → Schlupf; erst **hohe µ**
  (Leveling sauber bekommen), dann Sweep. Stufe 2/3.
- **Offset-Komposition:** Stufe-2-Rotation + B4-Show-Pose + Stance-Switch nutzen
  alle den Base-Frame-Umweg. Reihenfolge/Priorität der Offsets klären, bevor sie
  gleichzeitig aktiv sein können.
- **HW-IMU-Treiber:** fertiger `bno055`-Node (flynneva) vs. eigenes ros2_control-
  SensorInterface-Plugin — Entscheidung in der HW-Stufe.
- **A4-Kollisions-Check:** Reaktivierung terminieren, sobald Body-Rotation scharf
  ist (Risiko 2).
