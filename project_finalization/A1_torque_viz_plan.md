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
  **konservativ** (bei 8,4 V real etwas mehr Reserve).
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
- Dynamische/Beschleunigungs-Momente (nur quasi-statisch), Reibung, exakte
  Servo-Moment-vs-Spannung-Kurve (% ist konservativ gegen Nennwert). Servo-Hitze
  selbst ist nur am laufenden Roboter beobachtbar.

## 3. Progress-Checkliste
```
### Stage A1 — Torque-/Hitze-Viz-Tool
- [x] A1.1  Modell-Modul joint_load.py: CoG, Stützkraft-Solver (CoG-basiert, least-norm via lstsq, F≥0 clamp+flag), Jᵀ·F + Eigengewicht, %/Nennmoment, Stabilitäts-Marge (konvexe Hülle)
- [x] A1.2  Massen als Param (MassModel: URDF-Summe default; Körper-Extra/Akku via total_mass-Override), KEINE physical_properties-Änderung
- [x] A1.3  Live-Node torque_viz + torque_viz.launch.py + view_torque.rviz: /joint_states → MarkerArray (TEXT am Gelenk N·m+%+Farbe, CoG, Polygon, Marge); Stütz-Erkennung via Fuß-z
- [x] A1.4  Sweep-CLI tools/torque_sweep.py: radial×Höhe → Peak/Femur/Tibia/Balance/Marge + last-min/best-balance-Empfehlung
- [x] A1.5  Unit-Tests test_joint_load.py (9) + Lint grün; Build grün (80 Gait-Tests, 0 Fail)
- [ ] A1.6  Live in Sim/RViz: Stand-Pose/Slider/Lauf → plausible Anzeige (User) — Anleitung: [`A1_torque_viz_test_commands.md`](A1_torque_viz_test_commands.md)
  - Marker-Klarheit (User-Feedback): farbige **Kugel am Gelenk** als Anker + **„L<n> Femur/Tibia"**-Label im Text (Zuordnung); `pose_publisher` startet RViz in der **feet-closer Stand-Pose** (pose:=stand default), `pose:=slider` zum Erkunden.
- [x] A1.7  Self-Review + Design-Log (s.u. §6); tools_catalog.md + ai_navigation aktualisiert

> **Stand 2026-06-02: Desktop-Anteil A1 ✅** (A1.1–A1.5, A1.7). Offen: A1.6 Live-Sicht (User).
> **Erster Sweep-Befund (3,0 kg):** Peak-Auslastung niedrig (~15–30 %); **statisch trägt der
> FEMUR mehr als der Tibia** (z.B. feet-closer 0.215/−0.120: Femur ~20 % vs Tibia ~14 %).
> Last steigt mit radial (Hebelarm); body_height-Effekt klein. Last-minimal: kleines radial
> (0.18). Wenn der **Tibia in der Praxis heißer** wird, liegt es an Dynamik/Lauf (nicht
> statischem Halten) oder Servo-/Kühlungs-Unterschied → am laufenden Roboter beobachten.
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
- Folge-Nutzen: A2 (Pose-Opt), A3 (Geometrie-Entscheidung), B3 (Wave senkt Last), B4 (Body-/Show-Pose nutzt CoG + Polygon)

---

## 6. Kritischer Self-Review (A1 Desktop, 2026-06-02)
| # | Punkt | Status |
|---|---|---|
| 1 | Physik validiert: Hand-Rechnung (τ=−L·F), Coxa=0 (vertikal), Eigengewicht, Hebelarm-Monotonie | OK (Tests) |
| 2 | CoG-Modell ⊇ Even-Split: symmetrischer Stand → alle F_i = M·g/6 exakt (lstsq-Beweis) | OK (Test) |
| 3 | Kräfte-/Momentenbilanz ΣF=M·g; Stabilitäts-Marge Vorzeichen (CoG innen>0) | OK (Bug gefunden+gefixt: Kreuzprodukt-Winding) |
| 4 | Masse als Param, KEINE physical_properties-Änderung; `--total-mass 3.0` skaliert korrekt | OK |
| 5 | Live-Text DIREKT am Gelenk (TEXT_VIEW_FACING an FK-Gelenkpos), farbcodiert; CoG+Polygon | OK (Sim-Sicht A1.6 offen) |
| 6 | **Quasi-statisch (Halten), KEINE Dynamik** — Lauf-/Beschleunigungs-Lastspitzen nicht erfasst | 🟡 dokumentiert; Servo-Hitze nur am laufenden Roboter beobachtbar |
| 7 | **Befund Femur>Tibia statisch** widerspricht „Tibia heiß" → Hinweis auf Dynamik/Servo-Kühlung, nicht statisches Halten | 🟡 am Roboter beobachten (kein Modell-Fehler: Hebelarme Knie→Fuß < Hüfte→Fuß bei diesen Posen) |
| 8 | n>3 least-norm: bei Asymmetrie/Instabilität (F<0) geclampt + geflaggt, Ergebnis dann approximativ | 🟡 ok für Symmetrie/Stand; für Show-Pose (B4) genauer prüfen |
| 9 | Segment-CoM = geometrische Mitte (nicht URDF-Inertial-Origin) | 🟢 ok (Massen eh Schätzung; verfeinerbar) |
| 10 | %-Auslastung gegen Nennmoment = konservativ (8,4 V real mehr Reserve) | 🟢 ok (konservativ) |

**Fazit:** Kein offenes 🔴 (Winding-Bug gefixt+getestet). 🟡 = die quasi-statische Grenze
(Dynamik nur am Roboter beobachtbar) + der Femur>Tibia-Befund, den der User mit der Praxis abgleicht.

## 7. Design-Log
- **CoG-basiert (Weg B) statt Even-Split:** wie vom User gewählt; reduziert sich im
  symmetrischen Fall auf Even-Split (Test belegt), ist aber Basis für Show-Pose/Balance.
- **least-norm (lstsq) für n>3:** eindeutige, glatte Verteilung ohne Annahmen; F<0→clamp+flag.
- **Eigengewicht der Segmente mitgerechnet** (Beine = 83 % Masse) — revidiert „Schwingbein gewichtslos".
- **Gravitation im Bein-Frame = −Z** (Mount nur Yaw) → Torque-Rechnung komplett im Bein-Frame,
  nur Stützkraft-Solve + Marker brauchen base_link.
- **In-Szene-Text am Gelenk** statt RViz-Panel-Plugin (einfacher, genau der User-Wunsch).
- **Massen als Tool-Param** statt physical_properties-Edit (User-Vorgabe „nichts an Config").
