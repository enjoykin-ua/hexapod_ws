# Stage S1 — Modell-Werte eintragen (plan.md Schritt 3 + 4)

> Detail-Sub-Plan gemäß CLAUDE.md §4. **Anker für Review + Done-Vertrag.**
> Übergeordnet: [`plan.md`](plan.md) · Werte-Quelle: [`handover.md`](handover.md) §1.
> Branch `leg_changes`. **Nur Roboter-Modell-Schicht** (Geometrie/Massen/rad-Limits) —
> die Servo-Cal (`servo_mapping.yaml`) ist **Stage S2**, bewusst getrennt (anderes
> Paket, orthogonaler Test).

---

## 1. Logik-Skizze / was geändert wird (mit Begründung)

Fünf Dateien, reine Werte-/Struktur-Edits, keine Logik. Reihenfolge so, dass der
xacro-Build nach jedem Schritt konsistent bleibt.

### 1.1 `hexapod_physical_properties.xacro`
| Property | alt → neu | warum |
|---|---|---|
| `femur_length` | `0.07994` → **`0.060`** | gemessen (handover §1) |
| `tibia_length` | `0.200` → **`0.134`** | gemessen (handover §1) |
| `segment_mass` (1 Wert) | **ersetzt** durch 3 Properties: `coxa_mass`=`0.1167`, `femur_mass`=`0.102`, `tibia_mass`=`0.118` | leg.xacro nutzt die Masse 3× (coxa/femur/tibia); Coxa bleibt 0.1167, nur Femur/Tibia ändern sich → ein gemeinsamer Wert geht nicht mehr |
| `tibia_lower` | `-1.00` → **`-0.28`** | neuer, viel engerer Überstreck-Anschlag (handover §1); `tibia_upper 2.50` bleibt |

**Unverändert:** Coxa (Länge/Limits), Femur-Limits `±1.57`, Foot, body-Maße,
effort/velocity. Kommentar an `tibia_lower` neu (Begründung Bein-Umbau statt
Stage-1-Unlock).

### 1.2 `leg.xacro` (Massen-Referenzen umhängen — Folge von 1.1)
- Coxa-`box_inertia` `mass="${segment_mass}"` → `"${coxa_mass}"`
- Femur-`box_inertia` `mass="${segment_mass}"` → `"${femur_mass}"`
- Tibia-`box_inertia` `mass="${segment_mass}"` → `"${tibia_mass}"`

Inertien propagieren danach automatisch ([`inertials.xacro`](../../src/hexapod_description/urdf/inertials.xacro)
Box-Formel + 1e-5-Clamp) — **nicht von Hand rechnen**.

### 1.3 `hexapod.urdf.xacro` (per-Bein rad-Limit, 6×)
- In allen 6 `<xacro:leg …>`: `tibia_lower="-1.00"` → `"-0.28"`.
- `femur_lower/upper`, `coxa_lower/upper`, `tibia_upper` **unverändert**.
- Kommentarblock (Stage-1-Unlock-Historie) um den Bein-Umbau-Eintrag ergänzen.

### 1.4 `hexapod.ros2_control.xacro` (per-Bein command_interface-Clamp, 6×) — **NICHT in der Handover-Checkliste**
- In allen 6 `<xacro:joint_iface name="leg_*_tibia_joint" …>`: `lower="-1.00"` → `"-0.28"`.
- **Begründung:** der `command_interface`-`<param min>` ist das Sicherheitsnetz im
  controller_manager. Bliebe er auf `-1.00`, ließe der Stack Überstreck-Kommandos bis
  `-1.00` durch → Servo gegen den neuen `-0.28`-Anschlag → Stall/Trip auf HW. Belegt:
  [`ai_navigation.md`](../../project_architecture/ai_navigation.md) §1 + `01_hardware_change_workflow.md` Szenario 2.
- **`initial="…"`-Werte (Sim-Spawn-Pose) NICHT** anfassen → 🟡 Stage S4 (hängen an der
  neuen Cal, separat neu zu rechnen).

### 1.5 `config.py` (IK-Mirror, manuell)
- `_L_FEMUR` `0.07994` → **`0.060`**
- `_L_TIBIA` `0.200` → **`0.134`**
- `_TIBIA_LIMITS` `(-1.00, 2.50)` → **`(-0.28, 2.50)`**
- Kommentar aktualisieren.

---

## 2. Design-Entscheidungen (mit verworfenen Alternativen)

- **DS1-1 — Massen-Split in 3 benannte Properties** (`coxa/femur/tibia_mass`).
  _Verworfen:_ nur `femur_mass`+`tibia_mass` anlegen und `segment_mass` für die Coxa
  behalten → inkonsistente Benennung, irreführend („segment" wäre dann nur noch Coxa).
- **DS1-2 — `tibia_lower` in 4 Dateien** (properties + urdf 6× + ros2_control 6× + config.py).
  _Verworfen:_ die Handover-Variante mit nur 3 (ohne ros2_control) → löchriges
  Sicherheitsnetz, s. 1.4.
- **DS1-3 — Startwert `tibia_lower = -0.28`** (engste/sicherste, Leg-2-bound).
  _Aufgeschoben:_ Weitung auf ~`-0.36` erst, falls der Envelope (S3) zeigt, dass eine
  Pose den Streck-Bereich braucht (unwahrscheinlich, Streckung wird nie aktiv genutzt).
  Konservativ zuerst = garantiert kein Anschlag auf HW.
- **DS1-4 — per-Bein-URDF-Limits nur manuell (grep) geprüft, nicht automatisiert.**
  _Vorschlag/offen (4.):_ ein kleiner Test, der die generierte URDF parst und alle 6
  Bein-Limits prüft, würde das Test-Loch (s.u.) dauerhaft schließen. Für S1 erstmal
  manuell, um den Scope nicht zu sprengen.

---

## 3. Tests / Done-Kriterium (mit Begründung)

> ⚠️ **Zentraler Punkt:** `test_config.py` prüft `config.py` **nur gegen die
> Properties** in `hexapod_physical_properties.xacro`, **nicht** gegen die 6 per-Bein-
> Werte in urdf/ros2_control ([`test_config.py:71-84`](../../src/hexapod_kinematics/test/test_config.py#L71-L84)).
> Es fängt also Längen-/Property-Drift und config↔properties-Drift, **aber NICHT**, wenn
> einer der 12 per-Bein-`tibia_lower` (6 urdf + 6 ros2_control) auf `-1.00` vergessen
> wird. Deshalb ist T3 (generierte URDF) der **einzige Wächter** dieser 12 Stellen — Pflicht.

| # | Test | fängt | Begründung |
|---|---|---|---|
| T1 | `xacro hexapod.urdf.xacro > /tmp/hexapod.urdf` ohne Fehler | undefined `segment_mass` nach Refactor | beweist 1.1↔1.2 konsistent |
| T2 | `check_urdf /tmp/hexapod.urdf` ok | kaputter Tree | Standard-Gate |
| T3 | **generierte URDF: 6× tibia-`<limit lower>` + 6× tibia-`command_interface <param min>` = neuer Wert, kein `-1.00` mehr; Längen in origins; Massen in inertials** | vergessene per-Bein-Stelle | **einziger Wächter der 12 per-Bein-Werte** (s. Warnung) |
| T4 | `colcon build --packages-select hexapod_description hexapod_kinematics` | Build-Bruch | — |
| T5 | `colcon test --packages-select hexapod_kinematics` grün | config↔properties-Drift (Längen, Limits, Mounts, 6-Bein-identisch) | zentrales Cross-Check-Gate |
| T6 | Lint grün (`ament_flake8`/`ament_pep257` auf config.py) | Style | vor-Commit-Pflicht (ai_navigation §0.4) |

### Bewusst NICHT in S1 getestet (scope-out, kommt später)
- Servo-Cal / Calibration-Roundtrip → **S2**.
- Envelope / Reichweite / out-of-reach → **S3** (Mathe vor Sim).
- Sim-Spawn / RViz / visuell / `initial`-Pose-Werte → **S4**.
- Gait / Walking / Stance-Modi / real-engine → **S5**.
- HW (aufgehängt/Boden) → **S6+**.

---

## 4. Progress-Checkliste (Done-Vertrag — fließt in plan.md §5 zurück)

```
### Schritt 3 — Geometrie
- [x] 3.2a physical_properties.xacro: femur_length 0.060, tibia_length 0.134
- [x] 3.2b physical_properties.xacro: segment_mass → coxa_mass/femur_mass/tibia_mass (0.1167/0.102/0.118)
- [x] 3.2c leg.xacro: 3 box_inertia-mass-Referenzen umgehängt
- [x] 3.3  config.py: _L_FEMUR 0.060, _L_TIBIA 0.134 gespiegelt

### Schritt 4 — rad-Limits (Tibia-Unterkante -1.00 → -0.28)
- [x] 4.2a hexapod.urdf.xacro: tibia_lower 6× = -0.28
- [x] 4.2b hexapod.ros2_control.xacro: tibia lower 6× = -0.28  (Handover-Lücke, DS1-2)
- [x] 4.1  physical_properties.xacro: tibia_lower = -0.28 (Property/Default)
- [x] 4.3  config.py: _TIBIA_LIMITS = (-0.28, 2.50) gespiegelt
- [x] 4.4  DS1-4: automatisierter Wächter test_per_leg_limits.py angelegt (Symmetrie + URDF-Sync + IK-Anker)

### Schritt 5.1 (Teil-Gate für S1)
- [x] T1 xacro-Parse grün · [x] T2 check_urdf · [x] T3 generierte URDF verifiziert (12 Stellen, Sim+HW-Pfad)
- [x] T4 build grün · [x] T5 colcon test hexapod_kinematics grün (35 passed) · [x] T6 Lint grün
- [x] Self-Review-Tabelle (§6), dann Fertig-Meldung
```

---

## 5. Offene Punkte für User-Review (vor Code-Beginn)

1. **`tibia_lower = -0.28` als Startwert** (DS1-3) — ok, Feinwert später aus Envelope? (Handover §4 sieht genau das vor.)
2. **DS1-4:** den per-Bein-URDF-Limit-Check jetzt schon als kleinen automatisierten Test anlegen, oder vorerst manuell (grep) lassen und in S5/Abschluss automatisieren? → **entschieden: A (automatisiert)**, `test_per_leg_limits.py` angelegt.
3. Sonst keine — alle Zahlenwerte sind in der Handover vorgegeben; S1 ist mechanisch.

---

## 6. Ergebnis + Self-Review (S1 fertig)

**Alle 6 Test-Gates grün** (T1–T6), zusätzlich der **HW-Pfad** (`use_sim:=false`)
gegengeprüft (Plugin `HexapodSystemHardware`, 6× Tibia-Clamp `-0.28`, kein
velocity-State). `colcon test hexapod_kinematics`: **35 passed, 1 skipped, 0
failures**. Neuer Wächter `test_per_leg_limits.py`: 4 Tests grün.

| Punkt | Status |
|---|---|
| Massen-Split coxa 0.1167 / femur 0.102 / tibia 0.118 (Σ femur+tibia = 0.220 = Handover), gen. URDF bestätigt | OK |
| Längen femur 0.060 / tibia 0.134 in Joint-Origins; Reichweite innen 0.074 / außen 0.194 = Handover | OK |
| 12 per-Bein `tibia_lower=-0.28` (6 `<limit>` + 6 command-Clamp), **Sim- UND HW-Pfad** bestätigt, kein `-1.0`-Rest | OK |
| ros2_control.xacro (Handover-Lücke) mitgezogen + automatisierter Wächter dagegen | OK |
| config.py-Mirror (Längen + Limits), Cross-Check `test_config` grün | OK |
| Tibia-`ixx` trifft den 1e-5-Inertia-Clamp (dünner Stab, 12×12 mm) — wie vorher (war auch bei 200-mm-Tibia so), §11.5-Design, **kein Regress** | OK |
| **Coxa-Abweichung: `config.py _COXA_LIMITS=±1.57` vs. per-Bein-URDF `±0.415`** — VORBESTEHEND. **User-Kontext:** ±1.57 war die alte Datenblatt-Verifikations-Cal (±90°-Test), die echte doppelt-geprüfte Grenze (rad+PWM) ist ±0.415. → config.py sollte ±0.415 sein. **Plan: in S3 korrigieren** (`_COXA_LIMITS=(-0.415, 0.415)`) + Envelope-Reach-Folge prüfen, nicht blind in S1. | 🟡 → S3 |
| Sim-`initial`-Pose-Werte (ros2_control, 18×) noch aus der ALTEN Cal abgeleitet | 🟡 S4 (mit neuer Cal neu rechnen) |
| effort/velocity (5.0/2.0 Nm) trotz leichterer Segmente unverändert | 🟢 S5 (falls Re-Param nötig) |
| `tibia_lower` Feinwert -0.28 vs -0.36 | 🟢 S3/S5 (aus Envelope) |

**Keine 🔴.** S1 erfüllt den Done-Vertrag — Modell-Schicht (Geometrie/Massen/
Limits) ist eingetragen, konsistent über alle 4 Dateien, und durch einen
dauerhaften Wächter gegen künftigen per-Bein-Drift abgesichert.
