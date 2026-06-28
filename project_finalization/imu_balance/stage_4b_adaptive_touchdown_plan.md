# Stufe 4 / S4-2 — Adaptiver Touchdown (kontrollierte Senk-Rate)

> Zweite Teil-Stufe von [Stufe 4 Terrain-adaptiv](stage_4_terrain_adaptive_plan.md) (Block A5).
> **Ziel:** das **sichtbare** Deliverable — jeder Fuß setzt auf seiner **echten** Bodenhöhe auf
> (statt fester Höhe), via **kontrollierter Senk-Rate bis Kontakt**. Löst moderate Unebenheit +
> den **Knick-Übergang**. Methode = **fixed-timing** (Gait-Uhr unverändert; nur die Fuß-z-
> Komponente wird kontakt-adaptiv).
>
> **Status: ⚪ offen — Plan zum Review.** §4: Plan → **User-Freigabe** → Code → Test → Self-Review.
> Voraussetzung: **S4-1 🟢** (Kontakt-Signal verifiziert). Methode: [Umbrella §0.5](stage_4_terrain_adaptive_plan.md).

---

## 0. Kontext + die entscheidenden S4-1-Befunde (Handoff-Basis)

**S4-1 (abgeschlossen) hat das Kontakt-Signal verifiziert und den Schlüssel-Befund geliefert** —
das hier ist die fachliche Grundlage für S4-2:

1. **Der Kontakt-Sensor ist zuverlässig + korrekt.** `miss 0`; er feuert **exakt, wenn die
   Fußkugel den Boden berührt** (gemessen: `act_z` bei Kontakt-RISE = `body_height + Kugelradius
   8 mm`; FK gibt das Kugel-Zentrum, Kontakt = Kugel-Unterseite am Boden).
2. **Die ~13-Tick-„Latenz" war reiner Ausführungs-Lag** (kommandiert vs. tatsächlich, **Sim**):
   der heutige **schnelle Halbsinus-Aufsetzer** (`swing_traj`: max. Senk-Geschwindigkeit genau
   beim Touchdown) wird vom JTC ~8.8 mm hinterhergetrackt → der tatsächliche Fuß hinkt dem
   Kommando nach → der Kontakt erscheint „spät" gegen die kommandierte Phase. **Kein Sensor-/
   Pipeline-Defekt.**
3. **Konsequenz (datenbelegt):** senkt man den Fuß **langsam/kontrolliert** statt im schnellen
   Halbsinus, trackt der tatsächliche Fuß eng (kleiner Lag) → der Kontakt feuert **prompt**, wenn
   der echte Fuß den Boden erreicht. **Das ist der Kern von S4-2.**

**Mess-Werkzeug aus S4-1 (bleibt, für Tuning/Verifikation):** `gait_node._debug_leg1_contact`
loggt bei jeder Kontakt-Flanke von Bein 1 `cmd_z` vs. `act_z` (FK aus `/joint_states`) +
`ContactDiagnostic` (Latenz/Apex/Gap). Mit S4-2 muss **`lat` deutlich sinken + `apex` → ~0**.

---

## 1. Logik-Skizze + Pseudocode

### 1.1 Grundidee (nur die z-Komponente wird adaptiv)
- **x, y bleiben unverändert** (normaler `swing_traj`/`stance_traj`-Vortrieb). **Nur das
  Fuß-z** wird in einem **Senk-/Such-Fenster** kontakt-adaptiv.
- **Senk-/Such-Fenster** spannt von der **späten Schwungphase** über das Schwung-Ende **bis in
  die frühe Stance** (damit der Fuß auch *tiefer* als `body_height` suchen kann → Löcher /
  abfallendes Terrain hinter einem Knick).
- Im Fenster sinkt das kommandierte z **linear/kontrolliert** (langsam) von der Höhe-bei-Fenster-
  Start hinab bis zur **Envelope-Grenze** `body_height − max_extra_depth`.
  - **Kontakt** (Bein) → das aktuelle z als **`touchdown_z` einfrieren**; Rest der Stance hält
    `touchdown_z` (per-Fuß-Terrain-Höhe). Höherer Boden (Buckel) → früher Kontakt → höheres
    `touchdown_z`. Tieferer Boden → später, tieferes `touchdown_z`.
  - **kein Kontakt** bis Fenster-Ende → bei der Grenze halten (Open-Loop-Fallback, kein Hängen).
- **Reset** `touchdown_z = None` beim Start jeder neuen Schwungphase.

### 1.2 Warum „langsam" den Lag löst (S4-1-Befund)
Der Lag ≈ proportional zur Senk-Geschwindigkeit. Halbsinus: ~200 mm/s am Touchdown → ~8.8 mm Lag.
Kontrollierte Senkung über ein breites Fenster: z.B. ~70 mm/s → ~3× kleinerer Lag → Kontakt
feuert nahe am tatsächlichen Bodenkontakt → präziser Touchdown.

### 1.3 Pseudocode (Engine — pro Bein, WALKING, wenn adaptiv aktiv)
```
# Phase wie gehabt: cycle_phase < swing_duty → swing(0..1), sonst stance(0..1)
# Parameter: probe_start_phase (Schwung-Phase, ab der die kontrollierte Senkung beginnt),
#            search_end_stance_phase (Stance-Phase, bis zu der gesucht wird),
#            max_extra_depth (max. Tiefe unter body_height), descent ist linear über das Fenster.

x, y = swing_traj/stance_traj(...)   # UNVERÄNDERT (Vortrieb)

if not adaptive_enabled or not contact_pipeline_live:
    z = nominal_z (swing_traj.z bzw. body_height)        # Fallback = heutiges Verhalten
else:
    if in_swing and swing_phase < probe_start_phase:
        z = swing_traj.z                                  # normaler Schwungbogen
        touchdown_z[leg] = None                           # noch nicht gelandet (Reset-Zone)
    elif touchdown_z[leg] is not None:
        z = touchdown_z[leg]                              # schon gelandet → halten (Stance-Höhe)
    else:
        progress = fraction through the Senk-Fenster (probe_start_phase .. swing-Ende .. search_end_stance_phase)
        z_search = lerp(z_at_window_start, body_height - max_extra_depth, progress)
        if contact[leg]:
            touchdown_z[leg] = z_search                   # Kontakt → einfrieren
            z = z_search
        else:
            z = z_search                                  # weiter suchen (langsam sinken)
    # Fenster vorbei ohne Kontakt → touchdown_z bleibt None → z bei der Grenze gehalten
    # (im Code: nach search_end z = body_height - max_extra_depth halten)

target[leg] = (x, y, z)
```

### 1.4 ROS-Glue (Node)
- gait_node reicht die 6 Kontakt-States pro Tick an die Engine: `engine.set_foot_contacts(self._foot_contact)`
  (Engine bleibt ROS-frei). Bereits gecacht (S4-1).
- **Contact-Live-Guard (Sicherheit):** der Node verfolgt, ob *überhaupt* Kontakt-Messages
  ankommen (z.B. „zuletzt irgendein `True` < N s her" oder Subscriber hat schon mal empfangen).
  **Pipeline tot/abwesend → adaptiv AUS** (Fallback nominal), damit der Fuß **nicht** jeden
  Schritt auf `max_extra_depth` durchsackt. Param `adaptive_touchdown_enable` (Default **false**,
  Opt-in wie `leveling_enable`).
- **Isoliert testen:** `leveling_enable:=false` (IMU getrennt), wie in S4-1.

### 1.5 Stance-Höhe / per-Fuß-Terrain
`touchdown_z[leg]` wird für den Rest der Stance gehalten → der Körper „sitzt" auf dem per-Fuß-
Höhenprofil (nicht durch eine einzelne Kippung beschreibbar — komplementär zur IMU/TF).

## 2. Tests-Liste (mit Begründung)

| Test | Prüft | Done-Idee |
|---|---|---|
| **Unit: Senk-Logik (ROS-frei)** | im Fenster sinkt z kontrolliert; Kontakt friert `touchdown_z`; kein Kontakt → Grenze; Reset bei Swing-Start; Stance hält `touchdown_z` | konstruierte (phase, contact)-Sequenzen |
| **Unit: höher/tiefer Boden** | früher Kontakt (Buckel) → höheres `touchdown_z`; später (Loch) → tieferes, gekappt bei Grenze | Werte korrekt |
| **Engine: x,y unverändert** | nur z adaptiv; Vortrieb (x,y) identisch zu nominal | abs-Vergleich |
| **Engine: Fallback = nominal** | adaptiv aus ODER Pipeline tot → exakt heutiges `swing_traj`-Verhalten | Regression |
| **Engine: Envelope/IK** | tiefster Touchdown bleibt in-limit (IKError-Fallback Backstop) | kein Freeze |
| **Node: Kontakt→Engine + Live-Guard** | States durchgereicht; Pipeline-tot → adaptiv aus | rclpy-Smoke |
| colcon + Lint | alle bestehenden + neue grün | 0 Fehler |
| **Sim (User) flach** | läuft normal, `touchdown_z ≈ body_height`; **`lat` sinkt deutlich, `apex` → ~0** (S4-1-Diagnose); kein Durchsacken | Diagnose-Log + `_debug_leg1` |
| **Sim (User) Knick (ramp)** | Vorderbeine senken am Plateau-Scheitel **weiter bis Plateau** → kommt sichtbar **besser über den Knick** als ohne | qualitativ |

**Bewusst NICHT (→ später):**
- Free-gait / kontakt-getriggertes Timing → **S4-3** (nur falls fixed-timing nicht reicht).
- Slip / Kontaktverlust (fallende Flanke, `contact_timeout`-Latenz) → **S4-4**.
- Sensor-Fault-Plausibilität + Reaktion → **S4-5**.
- Stufen-/Buckel-Welten (Heightmap) → **S4-6** (S4-2 nutzt flach + bestehende ramp-Knick-Welt).
- Kombination mit IMU/TF-Leveling → nach Stage-4-Kern (erst isoliert).

## 3. Progress-Checkliste (→ Progress-File, Done-Vertrag)

```
S4-2:
- [ ] S4-2.1 Engine: set_foot_contacts() + per-Bein touchdown_z-State + adaptive-Params; z-adaptiv NUR in _compute_walking_targets (x,y unverändert)
- [ ] S4-2.2 Kontrollierte Senk-Logik (ROS-frei testbar): Senk-Fenster (späte Schwung→frühe Stance), lineare Senkung bis Kontakt/Grenze, Reset bei Swing-Start
- [ ] S4-2.3 gait_node: Kontakt-States an Engine durchreichen + adaptive_touchdown_enable (Default false, live) + Contact-Live-Guard (Pipeline tot → adaptiv aus)
- [ ] S4-2.4 Params: adaptive_touchdown_enable, touchdown_probe_phase, touchdown_search_end_stance_phase, touchdown_max_extra_depth (alle live, dokumentiert)
- [ ] S4-2.5 Unit-Tests (Senk-Logik, höher/tiefer Boden, Fallback=nominal, x,y unverändert) + Engine-/Node-Tests
- [ ] S4-2.6 colcon test + Lint grün
- [ ] S4-2.7 README/Konzept (adaptiver Touchdown, Senk-Fenster, per-Fuß-Höhe, Fallback, Params)
- [ ] S4-2.8 Test-Doku stage_4b_adaptive_touchdown_test_commands.md (flach: lat↓/apex→0; ramp-Knick: kommt drüber) + Sim-Verify durch User
- [ ] S4-2.9 kritische Self-Review-Tabelle (OK/🔴/🟡/🟢)
```

## 4. Offene Punkte für User-Review (vor Code)

1. **Senk-Fenster-Lage:** `probe_start_phase` (Schwung-Phase, z.B. **0.6**) und
   `search_end_stance_phase` (Stance-Phase, z.B. **0.3**). Breiter = langsamer = kleinerer Lag,
   aber längeres „Suchen" in die Stance hinein. **Vorschlag: 0.6 / 0.3**, in Sim nachtunen
   (Ziel: `lat` ≤ ~3 Ticks, `apex` ~0).
2. **`touchdown_max_extra_depth`:** wie tief unter `body_height` maximal suchen (Loch/Knick),
   z.B. **0.02 m**. Muss envelope-/IK-sicher sein (Backstop IKError-Fallback). **Vorschlag: 0.02**,
   ggf. via Reachability prüfen.
3. **Default:** `adaptive_touchdown_enable` Default **false** (Opt-in) — bestätigen.
4. **Contact-Live-Guard-Form:** „Subscriber hat schon empfangen + zuletzt `True` < N s" reicht?
   **Vorschlag: ja** (einfacher Staleness-Check; voller Sensor-Fault-Schutz = S4-5).
5. **Senk-Profil:** **linear** (einfach, Vorschlag) vs. weich (ease-in). Linear reicht für den
   kleinen Lag; ease-in nur falls nötig.

## 5. Design-Entscheidungen (mit Alternativen)

| Entscheidung | Gewählt (Vorschlag) | Verworfen / Alternative | Warum |
|---|---|---|---|
| Touchdown-Mechanik | **kontrollierte Senk-Rate bis Kontakt** (nur z) | schneller Halbsinus (heute) | S4-1: schneller Aufsetzer = ~8.8 mm Lag; langsam → prompter Kontakt |
| Penetration (Hebel 3) | **nicht nötig** | Fuß bewusst tiefer | S4-1: Sensor feuert exakt bei Bodenberührung; Penetration auf starrem Boden hebt eh nur den Körper |
| Senk-Fenster | **späte Schwung → frühe Stance** | nur im Schwung | erlaubt Suche **tiefer** als body_height (Löcher/Knick-Abfall) |
| Was adaptiv | **nur z** | x,y,z | Vortrieb (x,y) bleibt korrekt; minimaler Eingriff |
| Timing | **fixed-timing** (Gait-Uhr unverändert) | free-gait | Umbrella §0.5; free-gait erst falls nötig (S4-3) |
| Fallback | **nominal `swing_traj`** wenn aus / Pipeline tot | immer adaptiv | „Optimierung, nie load-bearing"; kein Durchsacken auf max_depth |
| State-Ort | **Engine (ROS-frei) + Node reicht Kontakt** | alles im Node | testbar wie tip/balance; Engine = Single Source der Phase/Targets |

## 6. Handoff / Code-Anker (für frischen Chat)

**Wo S4-2 andockt:**
- Engine Swing/Stance: [`gait_engine.py`](../../src/hexapod_gait/hexapod_gait/gait_engine.py)
  `_compute_walking_targets` (~Z.646–680) ruft `swing_traj`/`stance_traj`. **Hier** die z-adaptive
  Logik + per-Bein `_touchdown_z` + `set_foot_contacts()` + Params. `leg_gait_states()` (S4-1)
  gibt die per-Bein-Phase.
- Trajektorien: [`trajectory_gen.py`](../../src/hexapod_gait/hexapod_gait/trajectory_gen.py)
  `swing_traj` (z = body_height + step_height·sin(π·phase)), `stance_traj` (z = body_height).
- Node-Glue: [`gait_node.py`](../../src/hexapod_gait/hexapod_gait/gait_node.py) — `_foot_contact`
  (Cache, S4-1), `_update_foot_contacts` (Tick), `_debug_leg1_contact` (Mess-Werkzeug),
  `_apply_param`/`_on_param_change` (Params live). Kontakt an Engine im Tick durchreichen.
- Kontakt-Pipeline (Sim, **existiert**): `hexapod.foot_contact.xacro` → `bridge_foot_contact.yaml`
  → `foot_contact_publisher.py` → `/leg_<n>/foot_contact` (Bool). `enable_foot_contact:=true`
  Default (auch in `ramp_walk.launch.py`).
- FK fürs Mess-Werkzeug: `from hexapod_kinematics import leg_fk`; tatsächliche Joints im Node:
  `self._latest_joints` (Dict {leg_name: (coxa,femur,tibia)}, vom bestehenden `/joint_states`-Sub).

**Welten:** `ramp_walk.launch.py slope_deg:=0.0` (flach) bzw. `ramp.launch.py`/`ramp_walk` mit
slope (Knick). Stufen-/Buckel-Welt = S4-6.

**Verifikation:** S4-1-Diagnose-Log (`foot_contact [...] | L1 td.. lat.. apex.. gap..`) muss mit
S4-2 **`lat` deutlich kleiner + `apex` → ~0** zeigen; `_debug_leg1_contact` (`dz` zwischen cmd_z
und act_z) muss schrumpfen. Knick: sichtbar drüberkommen.

**S4-1-Tests als Vorlage:** `test_contact_diagnostic.py`, `test_leg_gait_states.py`,
`test_foot_contact_node.py`. Regler-/Logik-Klassen ROS-frei wie `tip_monitor`/`slope_estimator`.

## 7. Doku-Hygiene bei Abschluss
- `imu_balance_progress.md`: S4-2-Checkliste abhaken + Post-Review.
- `hexapod_gait/README.md`: adaptiver Touchdown.
- `ai_navigation.md`: Eintrag „Fußkontakt/Terrain (Stufe 4) ändern".
- Umbrella [`stage_4_terrain_adaptive_plan.md`](stage_4_terrain_adaptive_plan.md): S4-2 → 🟢.
