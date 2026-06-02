# Block A / Stage A1 — Torque-/Hitze-Viz-Tool (Plan)

> **STATUS: ⚪ PLAN — erstellt 2026-06-02. Zu reviewen + freigeben VOR Code (CLAUDE.md §4).**
> Ziel: die statische **Gelenk-Auslastung** (Drehmoment, % der Servo-Nennleistung) pro Pose
> sichtbar machen — **live in RViz** (aktuelle Pose) **und** als **Sweep** (radial×Höhe) für
> die last-optimale Pose. Beantwortet: „wo überlastet der Tibia, bei welcher Fuß-Nähe/Höhe
> verteilt sich die Last gleichmäßig?" Backlog: [`00_backlog.md`](00_backlog.md) A1.

## 0. Vorgaben (aus der Diskussion 2026-06-02)
- **Kraft-Modell: CoG-basiert (Weg B)** — Stützkräfte aus statischem Gleichgewicht (Gewicht
  + Momente um den Schwerpunkt). Reduziert sich im symmetrischen Stand auf Even-Split.
- **Eigengewicht der Beine mitrechnen** — Beine = ~83 % der Masse (2,5/3 kg), nicht
  vernachlässigbar (auch ein Schwingbein hält sein eigenes Segment-Gewicht).
- **Masse als Tool-Param** (KEINE `physical_properties`-Änderung): Default = URDF-Link-Summe;
  Körper-Extra (~0,37 kg Akku, mittig) + Gesamt-Override (3,0 kg) per CLI/Param.
- **Coxa ~0** für Vertikallast (vertikale Achse) — erwartet, dient als Sanity-Check.
- **% gegen Nennmoment** (Femur/Tibia 35 kg·cm ≈ **3,43 N·m**, Coxa 20 kg·cm ≈ **1,96 N·m**),
  **konservativ** (bei 8,4 V real etwas mehr Reserve). Echt-Eichung später via A4 (Strom).
- **Beides:** Live-RViz-Overlay **+** Offline-Sweep, gemeinsames Modell-Modul.

## 1. Logik-Skizze / Pseudocode

### 1.1 Gemeinsames Modell (pure Python, kein ROS) — `joint_load.py`
Eingabe: alle 6 Bein-Winkel (coxa/femur/tibia), Massen, `g`, Stütz-Set (welche Füße am Boden), Servo-Nennmomente.
```
# 1) Roboter-Schwerpunkt (base_link-Frame)
for each link (Körper+Akku mittig, je Bein coxa/femur/tibia-Segment via FK):
    akkumuliere mass·pos  → CoG = Σ(m·p)/Σm ;  M = Σm
# 2) Stütz-Füße (base_link) via FK + mount-Transform; Stütz-Polygon = konvexe Hülle (xy)
# 3) Vertikale Stützkräfte F_i ≥ 0 lösen (statisches Gleichgewicht):
#    Σ F_i = M·g ;  Σ F_i·x_i = M·g·x_cog ;  Σ F_i·y_i = M·g·y_cog
#    n=3 → exakt; n>3 → least-norm (Pseudo-Inverse). F_i<0 → Fuß würde abheben → clampen + Instabilität flaggen.
# 4) Pro Bein Gelenk-Momente:
#    τ_react = J_legᵀ · (0,0,F_i)   (nur Stützbeine; J = Bein-Jacobi am Fuß)
#    τ_self  = Σ über die 3 Segmente: Segment-Gewicht × Momentarm zu jedem Gelenk (immer)
#    τ_joint = τ_react + τ_self     → (coxa, femur, tibia) je Bein
# 5) % = |τ_joint| / Nennmoment(servo) ;  Farbe nach %
# 6) Stabilität: horizontaler CoG vs Stütz-Polygon → Marge (Abstand zur nächsten Kante)
return {per-leg τ + %}, CoG, support_polygon, stability_margin, F_i
```

### 1.2 Live-RViz-Node — `torque_viz` (hexapod_gait, analog `reachability_viz`)
- Subscribe `/joint_states` → aktuelle 6×3 Winkel.
- **Stütz-Erkennung:** Füße deren z (base) ≈ Minimum (am Boden) = Stütz; angehobene = Swing
  (Schwellwert-Param). Im reinen Stand: alle 6 Stütz.
- Rechnet 1.1 → publisht `MarkerArray`:
  - **Pro Gelenk ein `TEXT_VIEW_FACING`-Marker DIREKT an der Gelenk-Position** (via FK der
    Gelenk-Origins: Coxa-Mount, Hüfte, Knie) mit **„N·m / %"**, eingefärbt nach %-Schwelle
    (grün/gelb/rot) → die Zahl schwebt am Modell beim jeweiligen Gelenk.
  - optional zusätzlich ein farbiger Kugel-Marker am Gelenk (Schnell-Überblick).
  - **CoG-Marker**, **Stütz-Polygon** (LINE_STRIP), **Stabilitäts-Marge** als Text.
- Reagiert live auf jsp-Slider / Sim / HW — „sehen während Pose/Lauf". (Eine separate
  RViz-Panel-Anzeige im Fenster wäre ein eigenes Qt-Plugin = mehr Aufwand → verworfen,
  der In-Szene-Text am Gelenk ist einfacher und genau das Gewünschte.)

### 1.3 Sweep-CLI — `torque_sweep.py` (tools/, analog `walking_envelope_check`)
- Für eine Stütz-Konfiguration (z.B. 6er-Stand, oder Tripod-Mid-Stance) Sweep über
  (radial, body_height): pro Punkt **Peak-%**, **Femur-%**, **Tibia-%**, **Balance |Femur−Tibia|**,
  **Stabilitäts-Marge**. Tabelle → last-minimale / best-balancierte Pose finden.
- Optional `--gait`/Stütz-Set, `--total-mass`, `--voltage`-Hinweis.

## 2. Tests-Liste mit Begründung
### 2.1 Unit (pure Python)
| Test | Prüft |
|---|---|
| Bekannte Einfach-Pose von Hand nachgerechnet (1 Bein, Fuß-Kraft F → τ_tibia = F·Hebelarm) | Jᵀ·F korrekt |
| Symmetrischer 6er-Stand → alle F_i ≈ M·g/6 | **CoG-Modell reduziert sich auf Even-Split** (B⊇A) |
| Kräfte-/Momenten-Bilanz: ΣF=M·g, Momentengleichgewicht erfüllt | Solver korrekt |
| Coxa-τ ≈ 0 unter reiner Vertikallast | Achsen-Geometrie, deine Intuition |
| Schwingbein (angehoben) → τ_femur/τ_tibia ≠ 0 aus Eigengewicht, coxa ~0 | Eigengewicht-Term |
| CoG mittig → Stabilitäts-Marge > 0; CoG aus Polygon geschoben → Marge < 0, F_i<0 geflaggt | Stabilität + Clamping |
| Sweep-Sanity: Fuß weiter draußen → höheres Tibia-τ (monoton) | Plausibilität |
| `--total-mass`-Override skaliert τ linear | Massen-Param |
### 2.2 Live (Sim/HW)
| Live-Node: jsp-Slider bewegen → τ/%/Farbe + CoG/Polygon ändern sich plausibel | Integration |
### 2.3 Bewusst NICHT
- Dynamische/Beschleunigungs-Momente (nur quasi-statisch), Reibung, **echter Strom** (→ A4),
  exakte Servo-Moment-vs-Spannung-Kurve (% ist konservativ gegen Nennwert).

## 3. Progress-Checkliste
```
### Stage A1 — Torque-/Hitze-Viz-Tool
- [ ] A1.1  Modell-Modul joint_load.py: CoG, Stützkraft-Solver (CoG-basiert, n=3 exakt / n>3 least-norm, F≥0), Jᵀ·F + Eigengewicht, %/Nennmoment, Stabilitäts-Marge
- [ ] A1.2  Massen als Param (URDF-Summe default; Körper-Extra/Akku + Gesamt-Override), KEINE physical_properties-Änderung
- [ ] A1.3  Live-Node torque_viz + launch: /joint_states → MarkerArray (τ+%+Farbe je Gelenk, CoG, Polygon, Marge); Stütz-Erkennung
- [ ] A1.4  Sweep-CLI torque_sweep.py: radial×Höhe → Peak/Femur/Tibia/Balance/Marge-Tabelle
- [ ] A1.5  Unit-Tests (§2.1) + Lint grün; Build grün
- [ ] A1.6  Live in Sim/RViz: Slider/Lauf → plausible Anzeige; Sweep liefert last-optimale Pose
- [ ] A1.7  Self-Review + Design-Log; Eintrag in tools_catalog.md + ai_navigation.md
- [ ] A1.8  (nach Messung) %-Werte gegen echten Servo-Strom (A4) plausibilisieren — optional/später
```

## 4. Offene Punkte für User-Review (vor Code)
| # | Frage | Vorschlag |
|---|---|---|
| 4.1 | n>3-Stützkraft-Verteilung (6er-Stand, 5er-Wave): least-norm (Pseudo-Inverse)? | **ja** — glatte, eindeutige Verteilung; im symmetrischen Fall = Even-Split |
| 4.2 | Negativ-Kraft (Fuß würde abheben) → clampen + Instabilität flaggen? | **ja** (rote Marge/Warnung) |
| 4.3 | Segment-Schwerpunkt: URDF-Inertial-Origin nutzen, sonst Segment-Mitte? | **URDF-Origin falls vorhanden, sonst geometrische Mitte** |
| 4.4 | Paket-Ort: Live-Node in `hexapod_gait` (wie reachability_viz), Sweep in `tools/`? | **ja** (gemeinsames `joint_load.py` importierbar) |
| 4.5 | Farb-Schwellen %: grün <50 / gelb 50–80 / rot >80? | **ja**, anpassbar |
| 4.6 | Stütz-Erkennung live: Fuß-z-Schwelle ggü. Boden? | **ja** (Param); reiner Stand = alle 6 |
| 4.7 | Gesamtmasse-Default: URDF-Summe (~2,63) oder gleich auf 3,0 (mit Akku)? | **URDF-Summe als Default + Akku-Extra-Param**, du fährst mit `--total-mass 3.0` echte Zahlen |

## 5. Cross-References
- Backlog/Block A: [`00_backlog.md`](00_backlog.md) · Referenz: [`../project_architecture/ai_navigation.md`](../project_architecture/ai_navigation.md)
- Vorbild-Muster: `hexapod_gait/reachability_viz.py` (RViz-Marker), `tools/walking_envelope_check.py` (Sweep-CLI), `hexapod_kinematics/leg_ik.py`/`leg_fk` + `config.py`
- Servo-/Massen-Kontext: Memory `project_hexapod_servo_models`; Masse ~3 kg (0,5 Körper + ~2,1 Beine + ~0,37 Akku mittig), 8,4 V PSU
- Folge-Nutzen: A2 (Pose-Opt), A3 (Geometrie-Entscheidung), C3 (Wave senkt Last), C4 (Body-/Show-Pose nutzt CoG + Polygon)
