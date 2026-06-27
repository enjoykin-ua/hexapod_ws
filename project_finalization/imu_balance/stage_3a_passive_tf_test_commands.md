# TF-1 — Test-Befehle (interaktiv)

> Du führst die Tests aus, knappe Status-Meldung zurück. **Jeder Testfall ist
> eigenständig** — eigene Terminals + Befehle, setzt **nicht** voraus, dass aus
> einem vorherigen Test noch etwas läuft.
>
> **Ziel TF-1:** den Roboter Hänge **passiv** hochlaufen lassen (Nominal-Stance,
> `leveling_enable:=false` — kein aktives Leveln, Körper folgt dem Boden) und
> die slope-bewusste Kipp-Erkennung verifizieren (kein Fehlalarm auf der gewollten
> Hang-Neigung). **Charakterisieren:** wie steil kommt er passiv hoch, ab wann
> kippt/rutscht er (Grenze = Schwerpunkt/Traktion, **nicht** Bein-Reichweite).

## Konventionen

- **Pro Test:** Terminals frisch öffnen; jeder Block beginnt mit dem Sourcing.
- **Zwischen zwei Tests:** alle Terminals mit **`Strg-C`** beenden.
- **Sourcing-Zeile** (steht in jedem Block):
  ```bash
  source /opt/ros/jazzy/setup.bash && source ~/hexapod_ws/install/setup.bash
  ```
- **`leveling_enable` bleibt in TF-1 `false`** (passiv). TF-1 baut **keinen**
  Stellpfad — nur Hang-Schätzung + slope-bewusster Tip. Aktive Stabilisierung
  (roll→0, pitch→folgen, Gyro-D) ist **TF-2**.
- **Flach spawnen** ist Pflicht (gz-IMU ist spawn-referenziert) — die `ramp.launch.py`
  spawnt per Default flach auf dem ebenen Anlauf (`spawn_x:=-0.7`) und läuft in den Hang.

---

## Einmalig vorab: bauen

**Terminal (einmalig):**
```bash
cd ~/hexapod_ws
source /opt/ros/jazzy/setup.bash
colcon build --packages-select hexapod_kinematics hexapod_gait hexapod_bringup hexapod_gazebo --symlink-install
```

---

## Was du beobachtest

### `/imu/monitor` (rohe IMU-Lage) — `geometry_msgs/Vector3`

| Feld | Bedeutung | Einheit |
|---|---|---|
| `x` | **roll** | Radiant (× 57.3 = Grad) |
| `y` | **pitch** | Radiant (× 57.3 = Grad) |
| `z` | yaw | Radiant (driftet, ignorieren) |

Auf der um Y geneigten Rampe interessiert **`y` (pitch)**: `y ≈ 0.14` ≈ 8°.

### `/imu/slope` (NEU TF-1, Hang-Schätzung) — `std_msgs/Float64MultiArray`

```bash
ros2 topic echo /imu/slope
```
→ `data: [slope_roll_deg, slope_pitch_deg]`. Die **langsame** Schätzung des
Untergrunds. Beim Hineinlaufen in die Rampe soll `slope_pitch` dem echten
Hangwinkel nachlaufen (τ=0.5 s → ~1 s Lag) und sich dort einpendeln. Das ist die
Größe, gegen die der Tip das Residual bildet.

---

## TU — Unit-Tests (ohne Sim)

**Terminal 1:**
```bash
cd ~/hexapod_ws
source /opt/ros/jazzy/setup.bash && source ~/hexapod_ws/install/setup.bash
colcon test --packages-select hexapod_kinematics hexapod_gait \
  --pytest-args -k "slope or tip" \
  --event-handlers console_direct+
colcon test-result --verbose
```

**Erwartung:** grün — `test_slope_estimator` (Snap-Init, Konvergenz/Lag, Clamp,
τ-Sonderfälle, Residual, residual-gefütterter TipMonitor) + `test_leveling_node`
TF-1-Block (Params, Schätzung im STANDING, slope-aware Tip ignoriert konstanten
Hang, Gegenprobe roh feuert, Live-Tuning, Reject invalid).

---

## T1 — Hang-Schätzung trackt den echten Hang (8°)

> ⚠️ **Startreihenfolge strikt einhalten.** `/imu/slope` (und `/imu/monitor`)
> existieren **erst, wenn der gait_node läuft** — er erzeugt den Publisher. Ein
> Echo-Terminal, das **vor** dem gait_node gestartet wird, meldet „topic does not
> appear to be published yet / Could not determine the type". Darum:
> **erst Sim → dann gait_node (aufstehen abwarten) → dann Echo → dann fahren.**

**▶ Terminal 1 — Sim + Rampe 8° (zuerst):**
```bash
cd ~/hexapod_ws
source /opt/ros/jazzy/setup.bash && source ~/hexapod_ws/install/setup.bash
ros2 launch hexapod_bringup ramp.launch.py slope_deg:=8.0
```
⏳ **Warten,** bis Gazebo geladen ist und der Roboter (flach, auf dem Anlauf) sichtbar ist.

**▶ Terminal 2 — gait_node, Leveling AUS = passiv TF (als Zweites):**
```bash
source /opt/ros/jazzy/setup.bash && source ~/hexapod_ws/install/setup.bash
ros2 launch hexapod_gait gait.launch.py use_sim_time:=true leveling_enable:=false \
  robot_description_file:=$(ros2 pkg prefix hexapod_description)/share/hexapod_description/urdf/hexapod.urdf.xacro
```
⏳ **Warten,** bis der Roboter **aufgestanden** ist (Auto-Standup; im Gazebo steht
er auf allen 6 Beinen). Ab jetzt publiziert der Node `/imu/slope`.

**▶ Terminal 3 — Hang-Schätzung beobachten (als Drittes, NACH dem Standup):**
```bash
source /opt/ros/jazzy/setup.bash && source ~/hexapod_ws/install/setup.bash
ros2 topic echo /imu/slope
```
→ jetzt erscheint `data: [slope_roll_deg, slope_pitch_deg]`. Auf der flachen
Anlauffläche ist `slope_pitch ≈ 0`.

**▶ Terminal 4 — vorwärts laufen, in den Hang (zuletzt):**
```bash
source /opt/ros/jazzy/setup.bash && source ~/hexapod_ws/install/setup.bash
ros2 topic pub -r10 /cmd_vel geometry_msgs/msg/Twist '{linear: {x: 0.05}}'
```

**Erwartung:** Roboter läuft in die Rampe; in Terminal 3 läuft `slope_pitch` von
~0 auf **~8°** hoch (kurzer Lag, ~1 s) und pendelt sich dort ein (Vorzeichen je
nach Hang-Richtung, Betrag zählt — z.B. `-7.98` ≈ 8°). **Kein** Safety-Freeze.
Körper sieht **hangparallel** aus (natürlich, kein Spreizen/Tieflegen).

---

## T2 — slope-bewusster Tip feuert NICHT auf der gewollten Hang-Neigung

> Wie T1, aber Fokus aufs gait_node-Log (Terminal 2) während des Hochlaufens.
> Optional Gegenprobe: in einem 5. Terminal `slope_aware_tip_enable` umschalten.

**Erwartung:** Beim sauberen Hochlaufen einer Rampe, deren Winkel **über** der
absoluten WARN-Schwelle (15°) liegt (z.B. `slope_deg:=16.0`), **kein** „Kipp-WARN"/
„Kipp-CRIT" im Log — das Residual (Ist − Hang-Schätzung) bleibt klein.

**Gegenprobe (zeigt, dass die Schwelle ohne slope-Awareness fälschlich feuert):**
```bash
# Terminal 5
source /opt/ros/jazzy/setup.bash && source ~/hexapod_ws/install/setup.bash
ros2 param set /gait_node slope_aware_tip_enable false
```
→ jetzt sollte auf der ≥16°-Rampe „Kipp-WARN" auftauchen (cmd_vel=0, Roboter
stoppt). Zurück auf `true` → läuft wieder.

---

## T3 — Charakterisierung: wie steil kommt er passiv hoch?

> **Kern-Deliverable TF-1.** Für jeden Winkel T1 frisch starten (gleiche
> **Startreihenfolge** 1→2→3→4 wie oben), jeweils `slope_deg` setzen. Beobachten:
> kommt er hoch? kippt/rutscht er? feuert der (slope-bewusste) Tip korrekt erst
> beim *echten* Kippen?

Winkel-Ladder: **8 → 12 → 16 → 20 → 25 → 35°**.

```bash
# Terminal 1 — je Lauf einen Winkel:
ros2 launch hexapod_bringup ramp.launch.py slope_deg:=8.0
ros2 launch hexapod_bringup ramp.launch.py slope_deg:=12.0
ros2 launch hexapod_bringup ramp.launch.py slope_deg:=16.0
ros2 launch hexapod_bringup ramp.launch.py slope_deg:=20.0
ros2 launch hexapod_bringup ramp.launch.py slope_deg:=25.0
ros2 launch hexapod_bringup ramp.launch.py slope_deg:=35.0
```
(Terminals 2–4 wie in T1: gait_node `leveling_enable:=false`, `/imu/slope`-Echo,
`/cmd_vel`-Vortrieb.)

**Pro Winkel notieren:**
- Kommt er **hoch** (erreicht das Plateau)? ja / langsam / nein-rutscht / nein-kippt
- `/imu/slope` pitch stationär ≈ `slope_deg`?
- Tip: still (gut) / WARN / CRIT — und war das **berechtigt** (echtes Kippen)?
- Qualität: hangparallel & ruhig / wackelig / kippt nach hinten?

**Erwartung / Hypothese:** passiv-TF kommt **deutlich steiler** als die ~8° des
verworfenen Voll-Levelings (Bein ist nicht die Grenze). Die Grenze tritt als
**Kippen nach hinten** (Schwerpunkt) oder **Durchrutschen** (Traktion) auf — der
slope-bewusste Tip soll genau dort (und erst dort) CRIT melden. Das Ergebnis ist
der Input für TF-2 (aktive Stabilisierung) bzw. TF-3 (Schwerpunkt-Hilfe).

---

## T4 — Live-Tuning der TF-1-Params (Was bewirkt welcher Knopf?)

> Sim wie T1 (Startreihenfolge 1→2→3, fahren optional). T4 prüft, dass die drei
> TF-1-Parameter zur Laufzeit greifen — und macht **spürbar, was sie tun**. Setzen
> in einem zusätzlichen **Terminal 5**.

### Die drei TF-1-Parameter im Detail

Erinnerung an die Mechanik: ein **langsamer Tiefpass** schätzt aus der IMU-Neigung
den **Hang** (= „der Untergrund, dem der Körper folgt"). Die Kipp-Erkennung schaut
dann nicht auf die *absolute* Neigung, sondern auf das **Residual = Ist − Hang**.
Stetiger Hang → Residual ≈ 0 (kein Alarm); schneller Kipp → der Filter „hinkt nach",
Residual wächst → Alarm.

| Parameter | Default | Was er steuert | **größer** → | **kleiner** → |
|---|---|---|---|---|
| `slope_estimate_tau_s` | `0.5` s | Wie **träge** die Hang-Schätzung der Neigung folgt (Tiefpass-Zeitkonstante). | Schätzung folgt **langsamer**. Trennt Hang/Sturz **schärfer** (mehr Lag → ein echter Kipp wird im Residual deutlicher). **Aber:** am Knick flach→Hang hinkt sie länger nach → kurz größeres Residual → Tip kann am Übergang eher anschlagen. | Schätzung folgt **schneller** (weniger Lag am Hang-Eintritt). **Aber:** nähert sich der Sturz-Zeitskala → ein echter Sturz wird teils „mit-getrackt" → Residual bleibt klein → Tip kann einen Kipp **verpassen**. `0` = Filter aus (Schätzung = Ist sofort → Residual immer ~0 → nur noch die Kipp**rate** fängt). |
| `slope_clamp_deg` | `40°` | **Obergrenze**, wie steil die Schätzung den Hang annehmen darf. | Folgt auch **steileren** Hängen. Muss **≥ steilster echter Hang** sein, sonst sättigt die Schätzung unter dem echten Hang → Residual bleibt dauerhaft ≈ (Hang−Clamp) → **Fehlalarm**. | Schützt stärker gegen **langsames Wegkippen** (Schätzung darf nicht beliebig „mitwandern" → Residual wächst beim Umkippen → Tip schlägt an). **Zu klein** → auf gewolltem Steilhang sättigt sie → Fehlalarm. Faustregel: Clamp = „wie steil ist ein noch *plausibler* Hang". |
| `slope_aware_tip_enable` | `true` | Schalter: Tip gegen **Residual** (hang-relativ) oder gegen **absolute** Neigung. | (nur true/false) `true` = hang-bewusst (kein Fehlalarm am Hang). | `false` = Stufe-1-Verhalten (absolute Schwelle 15°/25°) → feuert am Hang ≥15° fälschlich. |

### Live-Probe

**▶ Terminal 5:**
```bash
source /opt/ros/jazzy/setup.bash && source ~/hexapod_ws/install/setup.bash
# τ größer → /imu/slope folgt sichtbar TRÄGER beim Hang-Eintritt:
ros2 param set /gait_node slope_estimate_tau_s 1.5
# τ kleiner → folgt schneller (näher am Ist, weniger Lag):
ros2 param set /gait_node slope_estimate_tau_s 0.2
# Clamp enger:
ros2 param set /gait_node slope_clamp_deg 30.0
# Schalter umlegen (siehe T2-Gegenprobe):
ros2 param set /gait_node slope_aware_tip_enable false
ros2 param set /gait_node slope_aware_tip_enable true
ros2 param get /gait_node slope_estimate_tau_s
# Reject-Probe (MUSS fehlschlagen):
ros2 param set /gait_node slope_estimate_tau_s -1.0
ros2 param set /gait_node slope_clamp_deg 0.0
```

**Erwartung:** die gültigen Sets melden `successful`; mit `tau 1.5` folgt die
`/imu/slope`-Schätzung beim Hineinlaufen **sichtbar träger**, mit `0.2`
**zackiger**. Die beiden Reject-Proben schlagen mit Begründung fehl
(`must be >= 0` / `must be > 0`), der Node läuft normal weiter.

---

## Befund (Sim-Verify): die Grenze ist der KNICK, nicht der Hang

> Erste Sim-Charakterisierung (8/16/35°) — der zentrale Befund. **Die Hang-Schätzung
> funktioniert** (`/imu/slope` trackt den echten Hang, hangparallel, kein Fehlalarm).
> Die Kletter-Grenze liegt **nicht** beim Laufen *auf* dem Hang, sondern beim
> **Übergang über den Knick** (flach↔Hang / Hang↔Plateau).

| Winkel | Befund |
|---|---|
| **8°** | Läuft sauber hoch + runter. `slope_pitch` ≈ 8°. Übergänge minimal wackelig. |
| **16°** | Kommt hoch, aber am **Plateau-Scheitel** (Hang→eben, *konvexe* Kante) bleiben die **mittleren Beine auf der Kante hängen**, die **vorderen** stehen schon übers Plateau und **finden keinen Boden** (zu hoch), die **hinteren** haben am Hang kaum Last. Wackelig. |
| **35°** | Schafft den **Knick flach→Hang nicht** — der ist quasi eine **Stufe/Bordstein**, keine glatte Schräge. *Auf* dem Hang könnte er laufen, aber **drauf zu kommen** geht passiv nicht. |

**Scope-Abgrenzung — zwei verschiedene Probleme, nicht eins:**

- **Wackeln / Schwingen / Seitneigung** (dynamische Stabilität) → löst **TF-2**
  (Gyro-D-Dämpfung + roll→0). Das ist Balance.
- **„Bein findet keinen Boden" an einer Kante / Stufe** (Terrain-Wissen) → löst
  **TF-2 NICHT**. Dafür braucht es **Fußkontakt-Taster (Stufe 4)**: der Roboter muss
  *merken*, dass ein Fuß ins Leere greift, und tiefer tasten (adaptiver Touchdown).
  Das ist kein Balance-, sondern ein Terrain-Adaptions-Problem.
- **35°-Knick = Stufe, nicht Schräge:** passives glattes Hang-Laufen ist dafür der
  falsche Maßstab. Reaktiv lösbar mit Fußkontakten (Stufe 4); vorausschauend bräuchte
  es eine Tiefenkamera/Lidar — **außerhalb des aktuellen Projekt-Scopes** (das Projekt
  setzt auf IMU + geplante Fußtaster, nicht auf Perception).

→ **Konsequenz für TF-2:** Fokus = Wackel-Dämpfung + roll→0 (die Übergänge ruhiger
machen). Die Kanten-/Stufen-Limits sind ein **Stufe-4-Thema** und werden bewusst
NICHT in TF-2 gelöst.

## Hinweise / bekannte Vereinfachungen

- **Passiv (kein Stellpfad):** TF-1 levelt nicht — der Körper folgt dem Boden von
  allein. Sieht der Körper bei steileren Winkeln **wackelig** aus, ist das erwartet
  (Open-Loop) und genau das, was **TF-2** (Gyro-D + roll→0) glättet.
- **Auto-Standup vor dem Hineinlaufen:** der Roboter spawnt flach und steht über den
  Cartesian-Standup auf, dann erst `/cmd_vel`. Während des Standups ist der Tip
  ausgesetzt (State-Gating).
- **Ground-Truth-Pose** alternativ direkt aus Gazebo:
  `gz topic -et /world/empty/dynamic_pose/info` (Modell „hexapod"-Orientierung).
