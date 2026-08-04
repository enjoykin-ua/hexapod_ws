# Block I Phase 11 — Längere Schritte — Test-Anleitung

> **Jeder Block ist eigenständig.** Eigener Bringup, eigene Erwartung, eigenes Melde-Format —
> du kannst mit T3 (Simulation über die App) anfangen, ohne T1/T2 gefahren zu sein.
> Vorher immer einmal: `cd ~/hexapod_ws && source install/setup.bash`.
>
> **Was geändert wurde (Kurzfassung):**
> - Stance-Deckel `step_length_max`: tief 0.060 → **0.065** · mittel 0.080 → **0.085** · hoch
>   0.050 → **0.055** (Fuß-Hub unverändert — geometrisch ausgereizt).
> - Tempo-Stufen: Zykluszeit **4.0 / 3.6 / 3.4 (Boot) / 1.7 s**, Stick-Skalen unverändert,
>   „aggressiv" gebremst (0.10/0.09/0.95).
> - `cmd_vel clamped` wird nur noch bei deutlicher Begrenzung als WARN gemeldet.
>
> **Erwartung in der Boot-Kombination (Stance „mittel" + Tempo „schnell"): 85 mm Schrittweite
> statt bisher 50 mm — bei unveränderter Fahrgeschwindigkeit (0.05 m/s).**

---

## T1 — Offline-Gates (kein ROS, ~1 Minute)

Belegt, dass die drei Deckel kinematisch valide sind. **Exit-Code auswerten, nie `grep`/`tail`** —
die Kopfzeile des Tools meldet nur das forward-Szenario und kann „GREEN" sagen, während
sidestep/diagonal rot sind.

```bash
cd ~/hexapod_ws && source install/setup.bash

# --- steady-state-Gate, alle 4 cmd_vel-Szenarien -------------------------
for CELL in "-0.065 0.040 0.065 tief" "-0.080 0.050 0.085 mittel" "-0.100 0.080 0.055 hoch"; do
  set -- $CELL
  python3 tools/walking_envelope_check.py check \
      --radial 0.160 --body-height $1 --step-height $2 --step-length $3 \
      --min-margin 0.10 --leveling-deg 4.0 --s4-floor 0.03 --scenario all > /dev/null
  echo "check  $4: exit=$?"
done

# --- engine-check: Start / Richtungswechsel / Stopp / Sitdown / Reposition
for CELL in "-0.065 0.040 0.065 tief" "-0.080 0.050 0.085 mittel" "-0.100 0.080 0.055 hoch"; do
  set -- $CELL
  python3 tools/walking_envelope_check.py engine-check \
      --radial 0.160 --body-height $1 --step-height $2 --step-length $3 \
      --min-margin 0.10 --s4-floor 0.03 > /dev/null
  echo "engine $4: exit=$?"
done

# --- alle vier Gangarten mit den finalen Deckeln -------------------------
for GP in tripod wave tetrapod ripple; do
  python3 tools/walking_envelope_check.py check --gait-pattern $GP \
      --radial 0.160 --body-height -0.080 --step-height 0.050 --step-length 0.085 \
      --min-margin 0.10 --leveling-deg 4.0 --s4-floor 0.03 --scenario all > /dev/null
  echo "gangart $GP: exit=$?"
done
```

**Erwartung:** alle Zeilen `exit=0`.
**Melde-Format:** „T1: alle exit=0" bzw. die Zeile(n), die ≠ 0 sind.

---

## T2 — Unit-Tests + Lint (~1 Minute)

```bash
cd ~/hexapod_ws
colcon build --packages-select hexapod_gait hexapod_teleop --symlink-install
source install/setup.bash
colcon test --packages-select hexapod_gait hexapod_teleop hexapod_kinematics hexapod_supervisor
colcon test-result --test-result-base build/hexapod_gait
colcon test-result --test-result-base build/hexapod_teleop
colcon test-result --test-result-base build/hexapod_kinematics
colcon test-result --test-result-base build/hexapod_supervisor
```

**Erwartung:** `569 gait` / `69 teleop` / `43 kinematics` / `38 supervisor`, je **0 failures**
(je 1 skipped ist normal). Lint ist in diesen Zahlen enthalten.

---

## T3 — Simulation über die APP (der Hauptteil)

> **Ein Befehl im Terminal, alles Weitere in der App.** Kein `ramp_walk`, kein zweites
> Launch-File — das kollidiert auf Port 9090 mit der Always-On-Schicht.

### T3.0 — Start

```bash
cd ~/hexapod_ws && source install/setup.bash
ros2 launch hexapod_bringup always_on.launch.py
```

Dann **in der App**: verbinden → **„Hexapod starten"** → warten bis das Status-Overlay Werte zeigt
(der schwere Stack braucht ~12 s bis zum ersten `/hexapod/status`) → **„Aufstehen"**.

> Für Rauhterrain statt der flachen Welt: `ros2 launch hexapod_bringup always_on.launch.py scene:=rubicon`
> (dann sind Leveling + alle Terrain-Regelkreise ab Start scharf).

### T3.1 — Boot-Zustand prüfen (die Kernaussage der Phase)

In der App im Config-Panel ablesen (Gruppe „Lauf / Gang"):

| Anzeige | Erwartung |
|---|---|
| Schrittdauer (`cycle_time`) | **3.4 s** |
| Schrittweite (`step_length_max`) | **0.085 m**, Slider-Maximum ebenfalls 0.085 (dynamischer Cap) |
| Fuß-Hub (`step_height`) | 0.05 m, Slider-Maximum 0.05 |
| Stance im Overlay | `mittel` |

Gegenprobe im Terminal (optional, zweites Fenster):
```bash
source ~/hexapod_ws/install/setup.bash
ros2 param get /gait_node cycle_time
ros2 param get /gait_node step_length_max
ros2 topic echo /hexapod/status --once
```

### T3.2 — Schrittweite messen (85 mm statt 50 mm)

Mit dem Stick **voll** vorwärts fahren (ohne L1), dann messen:

```bash
# zweites Terminal
source ~/hexapod_ws/install/setup.bash
python3 tools/apex_meter.py --window 12   # Fuß-Hub je Bein (Fenster > 2 Zyklen)
```

Die Schrittweite selbst am einfachsten **visuell in Gazebo**: ein Bein im Blick behalten und
Aufsetzpunkt-zu-Aufsetzpunkt vergleichen — der Unterschied 50 → 85 mm ist deutlich sichtbar
(die Beine holen merklich weiter aus, der Zyklus ist gemächlicher).

Alternativ rechnerisch aus dem Log: `linear_max` steht in der `gait_node init:`-Zeile im
Terminal 1; die real gefahrene Schrittweite ist `min(Stick-Skala, linear_max) × cycle_time/2`.

**Erwartung:** deutlich längere Schritte, **gleiche Marschgeschwindigkeit** wie vorher,
Fuß-Hub unverändert.

### T3.3 — Stance-Modi durchschalten

Über das App-Dropdown (oder L2/R2 am Controller) tief → mittel → hoch und zurück.

| Stance | Slider-Max Schrittweite | Slider-Max Fuß-Hub |
|---|---|---|
| tief | **0.065** | 0.04 |
| mittel | **0.085** | 0.05 |
| hoch | **0.055** | 0.08 |

**Erwartung:** die Slider-Grenzen folgen dem Stance sofort; kein IKError, kein Freeze, kein
Ruck beim Umschalten. In jedem Modus einmal in alle Richtungen fahren (vor, zurück, seitwärts,
drehen, diagonal).

### T3.4 — Tempo-Stufen durchschalten

D-Pad ↑/↓ (oder Tempo-Dropdown in der App). Erwartete Werte:

| Stufe | Schrittdauer | Schritt @ mittel | subjektiv |
|---|---|---|---|
| langsam | 4.0 s | 60 mm | sehr ruhig |
| mittel | 3.6 s | 72 mm | |
| **schnell (Boot)** | 3.4 s | **85 mm** | volle Schritte |
| aggressiv | 1.7 s | 85 mm | zügig, gleiche Schrittlänge |

**Erwartung:** „schneller" fühlt sich in **jedem** Stance-Modus auch schneller an (Monotonie).
Im hoch-Modus ist „schnell" spürbar gemächlicher als früher — das ist beabsichtigt
(dort deckelt die kurze erlaubte Schrittweite die Geschwindigkeit); „aggressiv" holt es zurück.

### T3.5 — Alert-Liste kontrollieren (der B2b-Fix)

Während des Fahrens (besonders im hoch-Modus und mit Gangart wave/ripple) die **Alert-Liste in
der App** beobachten.

**Erwartung:** **keine** wiederkehrenden „cmd_vel clamped"-Warnungen. Ein leichter Clamp ist in
vielen Kombinationen normal (Stick-Skala über `linear_max`) und wird nur noch als debug geloggt;
eine WARN erscheint erst, wenn ein Kommando mehr als 4× über `linear_max` liegt.

### T3.6b — Bahn-Nachführung (`time_from_start_factor`) — der große Hebel

Im Config-Panel „Bahn-Nachführung" (Gruppe *Lauf / Gang*, 1.0…4.0, Default 2.0). Er bestimmt, wie
viel der **kommandierten** Schrittweite die Beine real ausführen. Messmethode: feste Strecke
abfahren und die Gait-Zyklen eines mittleren Beins zählen — **weniger Zyklen = längere Schritte**.

| Wert | Sim-Ergebnis bei 2 s Schrittdauer | Charakter |
|---|---|---|
| 1.0 | 7,0 Zyklen (**93 %**) | straff, volle Schrittweite, keine Zeitreserve |
| 2.0 (Default) | 9,2–9,5 Zyklen (~70 %) | Sicherheitsmarge gegen Tick-Jitter |
| 4.0 | 14,4 Zyklen (45 %) | sehr weich, kurze Schritte |

⚠️ Der Wert wirkt auf **alle** Bewegungen — also nach dem Umstellen auch Aufstehen, Hinsetzen und
den Stance-Wechsel einmal ansehen, nicht nur das Laufen. Bei Unruhe/Zappeln sofort zurück auf 2.0
(live umstellbar).

### T3.6 — Live-Tuning (optional, wenn dir 3.4 s zu träge ist)

Im Config-Panel „Schrittdauer" verstellen (nur im **Stand** möglich) und wieder losfahren:

| Schrittdauer | Schritt @ mittel | Fahrgeschwindigkeit |
|---|---|---|
| 3.4 s (Default) | 85 mm | 0.050 m/s |
| 3.0 s | 75 mm | 0.050 m/s |
| 2.6 s | 65 mm | 0.050 m/s |
| 2.0 s (alt) | 50 mm | 0.050 m/s |

> ⚠️ Ein manueller Zug am Schrittdauer-Slider verstellt den **Tempo-Index nicht** — der nächste
> Tempo-Wechsel springt auf den Tabellenwert zurück. Zum Vergleichen ist das egal; wenn du einen
> Wert dauerhaft willst, sag Bescheid, dann wandert er in die Tempo-Tabelle.

**Melde-Format T3:** je Unterpunkt „ok" oder was abwich; für T3.6 den Wert, der sich am besten
angefühlt hat.

---

## T4 — Hardware aufgebockt

> **Sicherheit (CLAUDE.md §9):** Roboter aufgebockt, Beine frei, Kill-Switch griffbereit.

Auf dem Pi (Always-On läuft als Dienst ab Boot — **nicht** zusätzlich manuell starten):

```bash
# nur falls Code neu deployed wurde:
#   Nur schwerer Stack geändert  -> in der App "stoppen" -> "starten"
#   Always-On-Schicht/Manifest geändert:
systemctl --user restart hexapod_always_on      # ⚠️ reisst einen laufenden Stack mit
```

Dann in der App: „Hexapod starten" → „Aufstehen" → T3.1/T3.3/T3.4 wiederholen.

Zusätzlich:
```bash
# auf dem Pi, zweites Terminal
source ~/hexapod_ws/install/setup.bash
python3 tools/apex_meter.py --window 12
```

**Zusätzlich — die Bahn-Nachführung auf HW gegenmessen** (der offene Punkt aus dem Sim-Test):
feste Strecke abstecken (Fliesen/Maßband), Schrittdauer 2 s, Stance mittel, Hub 50 mm, und je
einmal mit **2.0 → 1.5 → 1.2 → 1.0** die Zyklen zählen. Pro Messung nur diesen einen Wert ändern.

> ⚠️ Auf der Hardware ist die Kette anders als in der Sim: das Plugin liefert kein echtes
> Positions-Feedback (Echo-State). Die Dämpfung entsteht rechnerisch im Controller und sollte
> deshalb auch hier auftreten — was die **Servos** mechanisch umsetzen, sieht aber kein
> Regelkreis. Die Größenordnung aus der Sim ist also **nicht** übertragbar. Bleibt der Effekt
> aus, ist auch das ein sauberes Ergebnis (dann war es ein Gazebo-Artefakt).

**Erwartung:** Fuß-Hub wie vor Phase 11 (unverändert) — durch die längere Zykluszeit kommt
tendenziell **mehr** vom kommandierten Hub an, weil die Servos mehr Zeit haben. Keine
Slip-/Kontakt-Fehlalarme, keine Freezes.

**Melde-Format:** Hub je Modus (kommandiert vs. gemessen), aufgetretene WARNs.

---

## T5 — Hardware am Boden / im Gelände

1. **Erst Stopp-Verhalten prüfen:** in „schnell" losfahren, Stick loslassen, Nachlauf ansehen.
   **Erwartung:** ~8 cm Nachlauf (bis zu ein halber Zyklus = 1.7 s). Das ist neu und beabsichtigt.
   Der **E-Stop wirkt weiterhin sofort** — einmal bewusst auslösen und mit „Recover" zurückholen.
2. Dann normale Runde in „mittel" + „schnell": Schrittlänge subjektiv bewerten.
3. Dann Gelände im hoch-Modus: Terrain-Toggles an, Tempo „aggressiv" für zügiges Vorankommen.
4. Strom/Temperatur im Blick behalten (längere Standzeiten pro Bein).

**Erwartung:** keine False-Positive-Freezes („Stütz-Verlust"), kein IKError.

### Rückfall, falls doch Slip-Fehlalarme auftreten

```bash
# App-Config-Panel oder Terminal:
ros2 param set /gait_node slip_debounce_ticks 20
ros2 param set /gait_node slip_min_lost_legs 2
# Recovery nach einem Freeze: in der App "Recover" (oder /hexapod_recover)
ros2 service call /hexapod_recover std_srvs/srv/Trigger
```

Wenn das nötig war: melden, dann ziehen wir die Werte in `hw_terrain.yaml` nach.

---

## T6 — Deploy-Hinweise (Pi)

| Was geändert wurde | Was neu gestartet werden muss |
|---|---|
| gait_node / joy_to_twist (Phase-11-Werte) | nichts am Dienst — in der App **„stoppen" → „starten"** |
| `hmi_config_manifest.yaml` (Slider-Defaults, neuer Param „Bahn-Nachführung") | `systemctl --user restart hexapod_always_on` |

⚠️ **Der Always-On-Dienst startet ab Boot mit dem Code-Stand, der beim Booten installiert war.**
Wer den Pi hochfährt, dann `git pull` + `colcon build` macht, läuft danach **immer noch mit dem
alten Manifest** — der neue Slider fehlt. Weder ein Neustart der Android-App noch „Stack
stoppen/starten" ändert daran etwas, denn das Manifest lebt im `hmi_status`-Node der
Always-On-Schicht. Deshalb nach dem Build **zwingend**:

```bash
systemctl --user restart hexapod_always_on
```

(Alternativ den Pi nach dem Build ein zweites Mal neu starten.) Danach die App neu verbinden.

⚠️ Der Restart der Always-On-Schicht reißt einen laufenden schweren Stack mit (Relay fällt) —
also **vor** dem Aufstehen machen, nicht mittendrin.
