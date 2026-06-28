# Stufe 4 / S4-6 — Stufen-/Knick-Welten (Demo des adaptiven Touchdowns)

> Teil-Stufe von [Stufe 4 Terrain-adaptiv](stage_4_terrain_adaptive_plan.md) (Block A5).
> **Vorgezogen** (User-Entscheid): erst eine echte **Stufen-/Knick-Welt** bauen, damit das
> selektive Nachreichen aus **S4-2 (Option A)** sichtbar wird. Auf dem sanften 8°-Hang verlangte
> das Terrain nur ~6 mm Nachreichen → optisch kaum vom Tripod-Wackeln zu trennen. Eine **Stufe ab
> / Knick mit echtem Höhensprung** zeigt das Nachreichen klar.
>
> **Status: 🟢 Sim-verifiziert (Graben zeigt den per-Fuß-Reach).** §4: Plan → User-Freigabe ✅ →
> SDF/Launch ✅ → Sim-Verify (User) ✅ → Self-Review ✅. **Kein Engine-/Node-Code** — nur Welt
> (SDF/xacro) + Launch + Test-Doku. Done-Vertrag + Befund: [progress S4-6-Block](imu_balance_progress.md).
> **Befund:** Graben `cmd_z` −0.105 vs −0.080 (~2.5 cm Reach), Roll ±1.3° vs ±2.7°; Stufe vom Pitch
> geschluckt (~3 mm). Welten: `step.sdf.xacro` (signiert) + `trench.sdf.xacro` (die klare Demo).

---

## 0. Kontext + Reichweiten-Budget (was die Welt-Maße begrenzt)

- **S4-2 Option A reicht NUR nach unten**, bis maximal `body_height − touchdown_max_extra_depth`
  = `−0.08 − 0.02 = −0.10` (Floor, envelope-GREEN). D.h. ein Fuß findet beim **Stufe-ab** echten
  Boden nur, wenn der Höhensprung **≤ ~`max_extra_depth` (2 cm)** ist (plus die kleine
  pitch-bedingte Extrareichweite, wenn die Vorderbeine über die Kante kippen). Größerer Sprung →
  Fuß erreicht nur den Floor, findet keinen Boden → **Open-Loop-Fallback** (Bein hängt am Floor,
  die anderen 5 tragen, Körper kippt nach vorn bis Boden/Bauch) — das ist die **fixed-timing-
  Grenze** und motiviert später S4-3 (free-gait).
- **Konsequenz für die Demo:** eine **kleine Stufe (~1.5–2 cm) ab** = im Reach → sichtbares,
  sauberes Nachsetzen. Eine **größere Stufe (~3–4 cm)** = zeigt die Grenze (Fuß am Floor, kein
  Boden) — didaktisch wertvoll, aber „kommt nicht sauber drüber".
- **Stufe AUF** demonstriert S4-2 **nicht** (Option A reicht nicht nach oben): der Fuß trifft die
  höhere Kante früh, wird bei `body_height` verankert = Open-Loop. Gut als **Gegenprobe** („adaptiv
  tut hier korrekt nichts"), aber kein Payoff-Bild.
- **Maßstab:** Hexapod klein (radial 0.16, Schritt ≤ 0.05/Cycle, `body_height` 0.08). Eine 2-cm-
  Stufe ist relativ zur Beinlänge bereits ein deutlicher Knick. Welt entsprechend kompakt halten.

## 1. Logik-Skizze (Welt-Geometrie, parametrisch)

**`step.sdf.xacro`** — analog zu `ramp.sdf.xacro` (gleiche Plugin-Liste: physics, user-commands,
scene-broadcaster, **contact**, **imu**; mu=mu2=1.2; Welt-Name `empty`). Geometrie für eine **Stufe
ab** in +x-Richtung:

```
Arg: step_drop (m, Default 0.02)   # Höhensprung der Stufe (positiv = ab)
     step_x    (m, Default 0.0)    # x-Position der Kante

- Obere Plattform (Start, wo der Roboter FLACH spawnt):
    statische Box, Oberseite bei z = +step_drop, reicht von weit −x bis x = step_x.
    (Roboter spawnt darauf bei spawn_x < step_x, spawn_z = step_drop + Δ.)
- Untere Ebene (Ziel):
    der bestehende infinite ground_plane bei z = 0, ab x = step_x sichtbar/betretbar.
    → Höhensprung an der Kante = step_drop (obere Box-Oberkante step_drop über ground_plane).
- Kante bei x = step_x: scharfe konvexe Kante (Box-Vorderfläche vertikal).
```

Begründung der Wahl „obere Box + infinite ground_plane unten":
- **IMU bleibt welt-referenziert** (flach spawnen auf der oberen Box, Memory
  [[project_gz_imu_spawn_referenced]]).
- Minimale Geometrie (eine Box + vorhandener ground_plane), exakte Kante, kein Box-Box-Junction-
  Versatz wie bei der Rampe.
- Reibung/Plugins 1:1 wie `ramp.sdf.xacro` → keine neuen Sim-Variablen.

**Optional (separater Arg / zweite Welt) — Knick statt Stufe:** statt vertikaler Kante eine kurze
**steile Abfahrt** (z.B. 30–45° über wenige cm) für einen „weicheren" Knick. **Vorschlag: erst die
scharfe Stufe** (klarstes Bild), Knick nur falls gewünscht.

**Launch (analog ramp):**
- `step.launch.py` — expandiert `step.sdf.xacro` mit `step_drop`/`step_x` → Tempfile → `sim.launch.py`,
  spawnt flach auf der oberen Box (`spawn_x` < `step_x`, `spawn_z` = `step_drop` + Δ).
- `step_walk.launch.py` — Ein-Befehl-Bringup (wie `ramp_walk`): Sim + Spawn + Auto-Standup + verzögerter
  `gait_node`. Reicht `step_drop`/`step_x`/`gait_pattern`/`leveling_enable` durch.

## 2. Tests-Liste (mit Begründung)

| Test | Prüft | Done-Idee |
|---|---|---|
| **xacro expandiert** (`step_drop` 0.02 / 0.04) | Welt baut, Properties korrekt | py/launch-Konstruktion |
| **`gz sdf --check` Valid** | SDF syntaktisch + physikalisch gültig (wie ramp) | exit 0 |
| **Launches konstruieren** (`step.launch.py`, `step_walk.launch.py`) | `--show-args` / Konstruktion ohne Fehler | grün |
| **Reach-Budget dokumentiert** | `step_drop ≤ max_extra_depth` (+pitch) = „im Reach"; größer = Grenze | Tabelle in Test-Doku |
| **Sim-Verify (User) — Stufe 2 cm ab** | adaptiv AN: Vorderbeine setzen sauber auf die untere Ebene (`cmd_z` < −0.08 an der Kante), Körper folgt; adaptiv AUS: Fuß „landet" in der Luft → Stampfen/Ruck | A/B + `_debug_leg1` |
| **Sim-Verify (User) — Stufe 4 cm ab** | zeigt die fixed-timing-**Grenze** (Fuß am Floor −0.10, kein Boden) | qualitativ |
| **Sim-Verify (User) — Stufe auf (Gegenprobe)** | adaptiv tut korrekt **nichts** (`cmd_z` bleibt −0.08), Open-Loop nimmt die Stufe | A/B |

**Bewusst NICHT (→ später):**
- Treppe/mehrere Stufen, Buckel, schräge Kanten, Heightmap/Fuel → später (erst eine Stufe).
- Automatischer „kommt-drüber"-Erfolgstest (bräuchte Pose-Tracking) → visuell durch User.
- Kombination mit IMU/TF-Leveling → erst isoliert (`leveling_enable:=false`).
- Slip an der Kante (S4-4), Plausibilität (S4-5) — eigene Stufen.

## 3. Progress-Checkliste (→ Progress-File, Done-Vertrag)

```
S4-6:
- [ ] S4-6.1 step.sdf.xacro (obere Box @ +step_drop + ground_plane unten, scharfe Kante @ step_x; Plugins/Reibung wie ramp), Args step_drop/step_x
- [ ] S4-6.2 step.launch.py (xacro-Expand + flach spawnen auf der oberen Box) + step_walk.launch.py (Ein-Befehl-Bringup wie ramp_walk)
- [ ] S4-6.3 gz sdf --check Valid (step_drop 0.02 + 0.04) + Launches konstruieren
- [ ] S4-6.4 CMake/install: Welt + Launches installiert (colcon build grün)
- [ ] S4-6.5 Test-Doku stage_4c_step_worlds_test_commands.md (A/B Stufe-ab 2cm/4cm + Stufe-auf Gegenprobe; Reach-Budget-Tabelle) + Sim-Verify durch User
- [ ] S4-6.6 README/Doku-Querverweis (hexapod_gazebo Welten, ai_navigation Stufe-4-Eintrag, Umbrella S4-6 → 🟢)
- [ ] S4-6.7 kritische Self-Review-Tabelle (OK/🔴/🟡/🟢)
```

## 4. Offene Punkte für User-Review (vor Bau)

1. **Welt-Form:** scharfe **Stufe ab** (Vorschlag, klarstes Bild) vs. weicher **Knick** (kurze steile
   Abfahrt) vs. **beides** (zwei Welten/Args). **Vorschlag: scharfe Stufe ab zuerst.**
2. **Stufenhöhen für die Demo:** primär **~0.02 m** (im Reach → sauberes Nachsetzen) **+ ~0.04 m**
   (zeigt die fixed-timing-Grenze). **Vorschlag: 0.02 als Default, 0.04 als zweiter Lauf.** Ggf.
   `max_extra_depth` für die 2-cm-Demo leicht erhöhen (z.B. 0.025) für Marge?
3. **Stufe-auf-Gegenprobe** mit ins Paket (zeigt „adaptiv tut korrekt nichts")? **Vorschlag: ja**,
   über negativen `step_drop` oder einen zweiten Arg — billig + lehrreich.
4. **Naming/Struktur:** `step.sdf.xacro` + `step.launch.py` + `step_walk.launch.py` (analog
   ramp/ramp_walk). Plan-Datei `stage_4c_…` (= dritte bearbeitete Teil-Stufe nach 4a=S4-1, 4b=S4-2;
   Inhalt = **S4-6**). **OK so?**
5. **Einzelstufe vs. Treppe:** erst **eine** Stufe (Vorschlag); Treppe/Buckel später. **OK?**

## 5. Design-Entscheidungen (mit Alternativen)

| Entscheidung | Gewählt (Vorschlag) | Verworfen / Alternative | Warum |
|---|---|---|---|
| Welt-Form | **scharfe Stufe ab** | Knick (steile Abfahrt) / Rampe | klarster Höhensprung → Nachreichen sichtbar; Rampe (sanft) ist schon erledigt |
| Geometrie | **obere Box + infinite ground_plane** | zwei Boxen (oben/unten) | minimal, exakte Kante, IMU welt-referenziert, kein Junction-Versatz |
| Höhe | **2 cm (im Reach) + 4 cm (Grenze)** | nur eine Höhe | 2 cm = Payoff sichtbar, 4 cm = ehrliche fixed-timing-Grenze (motiviert S4-3) |
| Richtung | **Stufe ab** (+ optional auf als Gegenprobe) | nur auf / nur ab | ab = der S4-2-Reach; auf = Open-Loop-Gegenprobe |
| Scope | **eine Stufe** | Treppe/Buckel/Heightmap | klein anfangen (wie bei TF/S4-1/S4-2); Rest später |
| Code | **nur Welt+Launch+Doku** | Engine/Node anfassen | S4-2 ist fertig+verifiziert; S4-6 ist reine Welt-Arbeit |

## 6. Doku-Hygiene bei Abschluss
- `imu_balance_progress.md`: S4-6-Checkliste + Post-Review; Umbrella-Statuszeile.
- `stage_4_terrain_adaptive_plan.md`: S4-6 → 🟢.
- `hexapod_gazebo` README (falls vorhanden) + `ai_navigation.md` (Stufe-4-Eintrag: Welten).
- Memory `project_a5_stage4_adaptive_touchdown`: S4-6 erledigt, nächster (S4-4/S4-5).
