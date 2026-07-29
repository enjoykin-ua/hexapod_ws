# Block I Phase 10 — Show „Free-Leg" (Wiederaufnahme der B4-Show-Pose) — Plan

> **Ziel:** Der Roboter stützt sich auf die vier hinteren Beine, die **zwei Vorderbeine sind frei**
> und werden mit den Sticks des Kishi bewegt. Gestartet wird **aus der App** über den bereits
> vorhandenen Menüeintrag `show_mode = free_leg`.
>
> **Status: 🟡 Plan — wartet auf Freigabe.** Self-contained für einen frischen Chat.
> **Vorgänger:** Phase 9 (Feld-Autonomie) 🟢 · fachlich:
> [`B4_show_pose_plan.md`](../B4_show_pose_plan.md) +
> [`B4_show_pose_progress.md`](../B4_show_pose_progress.md) — die ursprüngliche Show, mit den
> **alten** Beinen ausgelegt.
> **Contract:** [`interface_contract.md`](interface_contract.md) §6c (v0.13 → v0.14).
>
> ⚠️ **Nummerierung:** Diese Phase belegt die **10**. Die bisher unter „Phase 10" geführte
> **Politur** (Auto-Reconnect, Controller-Profile) rückt damit auf **Phase 11** — in `PHASE.md` und
> [`00_overview.md`](00_overview.md) beim Start dieser Phase nachziehen (Checkliste FL.16).
>
> **Lese-Reihenfolge neuer Chat:** `CLAUDE.md` §4/§5/§9 ·
> [`project_architecture/ai_navigation.md`](../../project_architecture/ai_navigation.md) →
> „Show-Pose (B4) ändern" · `B4_show_pose_progress.md` (IST-Architektur) · **diese Datei**.

---

## 0. Ausgangslage

### 0.1 Der Code ist vollständig vorhanden

Nichts wurde beim Bein-Umbau gelöscht — die Show ist **stillgelegt**, nicht entfernt:

| Schicht | Zustand |
|---|---|
| **Engine** (`gait_engine.py`) | `STATE_SHOW_ENTER` / `SHOW_ACTIVE` / `SHOW_EXIT`, σ-Skalar, CoG-Gate, `set_show_offsets`, `_show_foot`/`_front_foot` — **intakt** |
| **Node** (`gait_node.py`) | Service `/hexapod_show_toggle`, Sub `/cmd_show` (6 Werte), 11 `show_*`-Params — **intakt** |
| **Teleop** (`joy_to_twist.py`) | Cross-Longpress → Toggle, Sticks + L2/R2 → `/cmd_show`, R1-Dead-Man — **per `show_enabled: false` abgeschaltet** |
| **Tests** | `test_show_node.py` (11) + Teleop-Fälle **grün**; `test_show_pose.py` (**27 Engine-Tests**) mit `pytestmark = skip` deaktiviert |
| **Tool** | `tools/show_pose_cog_check.py` — **läuft**, liest Geometrie + URDF-Limits live |

**Zwei getrennte Gründe für die Abschaltung** (wichtig für das Verständnis):
1. **HW-Instabilität** mit den *alten*, langen Beinen — der Roboter kippte nach vorne
   ([`leg_change/stage_6_hw_plan.md`](../leg_change/stage_6_hw_plan.md) §5c → `show_enabled: false`).
2. **Bein-Umbau**: die Show wurde bewusst aus dem Scope genommen; die alte Show-Pose
   (radial 0.215 @ bh −0.120) ist mit den kurzen Beinen nicht mehr erreichbar → Tests geskippt mit
   dem Vermerk „separate Re-Param-Aufgabe". **Genau die ist diese Phase.**

### 0.2 Was die neuen Beine ändern

| | alt (B4-Auslegung) | neu |
|---|---|---|
| Femur / Tibia | 0.07994 / 0.200 | **0.060 / 0.134** |
| Reichweite ab Femur-Gelenk | 0.120 … 0.280 | **0.074 … 0.194** (−31 % außen) |
| Tibia-Limit | −1.00 … +2.50 | **−0.28** … +2.50 |
| Stand-Pose | radial 0.215 @ bh −0.120 | radial **0.160** @ bh −0.065/−0.080/−0.100 |
| Coxa- / Femur-Limit | ±0.415 / ±1.57 | **unverändert** ±0.415 / ±1.57 |

### 0.3 Messungen für diesen Plan (offline, mit der neuen Geometrie)

Erhoben mit `tools/show_pose_cog_check.py`, `tools/walking_envelope_check.py` und direkter
`leg_ik`-Auswertung.

**(a) Die Stütz-Pose trägt weiterhin** — CoG-Marge im 4-Bein-Polygon, `show_front_radial 0.19`:

| Stance | Körperhöhe | beste Marge | max. Rückversatz |
|---|---|---|---|
| **tief** (−0.065) | 65 mm | **49,0 mm** | 0.065 m |
| mittel (−0.080) | 80 mm | 49,3 mm | 0.065 m |
| hoch (−0.100) | 100 mm | 49,6 mm | 0.065 m |

> Die statische Marge ist über alle Höhen praktisch gleich (der Fußradius 0.160 ist einheitlich, das
> Stützpolygon also identisch). **Der Unterschied liegt im Kippwinkel** `atan(Marge / Schwerpunkthöhe)`:
> **tief ≈ 37°**, mittel ≈ 32°, hoch ≈ 26°. Näherung: Schwerpunkt auf Körperhöhe (Body dominiert).

**(b) Der Rückversatz ist enger als früher.** Ab `shift = 0.070` verletzen leg_3/leg_4 ihre
Joint-Limits (früher lag die Grenze bei 0.092). Der bisherige Default 0.065 sitzt damit **exakt auf
der Kante**; die in `B4_show_pose_progress.md` dokumentierte Safe-Range „0.05–0.09" ist für die neuen
Beine **falsch** und wird korrigiert.

**(c) Die alte Neutral-Pose ist unbrauchbar:**
- `show_front_radial 0.22` = **93 % der Reichweite** (fast gestrecktes Bein, kein Spielraum).
- `show_front_z −0.04` = nur **25 mm über dem Boden** — verschenkt den Aufwärts-Hub und begrenzt
  `show_vert_scale`, weil der Fuß sonst **in den Boden fährt** (Boden liegt bei `z = body_height`).
- Mit den alten Skalen (lat/vert 0.06, radial 0.05) sind nur **54–66 %** der Stick-Kombinationen
  erreichbar → beim Bedienen fühlt es sich an, als würde das Bein klemmen (die Engine hält dann
  die letzte gültige Pose).

**(d) Der Coxa-Bereich wurde nie genutzt.** Die Neutral-Pose ist als `(radial, 0, z)` definiert —
`y = 0` heißt **Coxa = 0**, das Bein zeigt exakt in seine Montagerichtung (45° schräg nach außen).
**Das ist die Ursache der „viel zu weit auseinander"-Optik**, nicht die Beinlänge:

| Coxa in der Neutral-Pose | Fuß-Abstand der beiden Vorderfüße |
|---|---|
| 0 (bisher) | **0,40 m** |
| 0.21 (= `lat 0.04` @ radial 0.19) | **0,34 m** |
| 0.40 (nahe Limit ±0.415) | **0,29 m** |

**(e) Das Laufen ist weit vom Coxa-Limit entfernt** (Envelope-Check, tiefe Stance, alle vier
cmd_vel-Szenarien): max genutzter Coxa-Betrag **0.188 rad** bei Limit ±0.415. Engpass ist überall
der **Femur** (Marge 0.117–0.196 rad). → Die Show darf den Coxa-Bereich ausschöpfen, ohne dem
Laufen etwas wegzunehmen.

**(f) Befund am Massen-Modell:** `joint_load.py` rechnet mit `_SEGMENT_MASS = 0.1167` für **alle 18**
Segmente — Stand vor dem Bein-Umbau. Real: Coxa 0.1167 / Femur **0.102** / Tibia **0.118**
(2.550 kg statt 2.631 kg, +3,2 %). Wirkung: das Modell **überschätzt** die Beinmassen und damit den
Vorwärts-Zug der angehobenen Vorderbeine → die echten Margen sind eher **besser** als gerechnet
(konservativ, kein Sicherheitsrisiko). Behandlung siehe [E9].

---

## 1. Die Auslegung

### 1.1 Parameter (Startwerte — in Stufe 1 final bestätigt)

| Parameter | bisher | **neu** | Begründung |
|---|---|---|---|
| `show_front_radial` | 0.22 | **0.19** | 0.22 = 93 % Streckung; 0.19 = 83 %, lässt Spielraum |
| **`show_front_lat`** | — (neu) | **0.04** | ⭐ Neutral-Pose mit Coxa-Anteil (≈0.21 rad) → **Beine zeigen nach vorne** statt schräg nach außen |
| `show_front_z` | −0.04 | **0.00** | 65 mm über Boden (statt 25) → großer Auf/Ab-Hub möglich |
| `show_lat_scale` | 0.06 | **0.04** | Coxa nutzt damit [0.00 … 0.40] — praktisch der volle freigegebene Bereich |
| `show_vert_scale` | 0.06 | **0.05** | Fuß schwingt 15–115 mm über Boden, bleibt **immer** darüber |
| `show_radial_scale` | 0.05 | **0.03** | Trigger **nach außen** ([E6]); 98 % der Hülle erreichbar |
| `show_body_shift_back` | 0.065 | **0.055–0.060** | 0.065 ist die harte Kante (0.3b); der Pitch übernimmt einen Teil |
| **`show_body_pitch_deg`** | — (neu) | **5.0** | Hinterteil runter, Nase hoch — zusätzliche CoG-Verlagerung + Optik |
| `show_safety_margin` | 0.030 | 0.030 | unverändert (ENTER-Gate) |
| `show_return_rate` | 0.5 | 0.5 | unverändert |

**Erwartetes Ergebnis:** Stick-Hülle **100 %** erreichbar (lat/vert), Trigger 98 %; Fuß-Abstand in
Ruhe **0,34 m**, per Stick zusammenführbar auf **0,29 m**, spreizbar auf 0,40 m. **Alles im
bestehenden Limit ±0.415 — keine Kalibrierung, kein URDF-Eingriff.**

### 1.2 Das Coxa-Budget (so bewegen sich die Beine seitlich)

```
Neutral-Pose:   0.21 rad   (Beine zeigen nach vorne)
Stick zur einen Seite:  → 0.00 rad   (zurück in die Montagerichtung, „gespreizt")
Stick zur anderen Seite:→ 0.40 rad   (zusammengeführt, knapp unter dem Limit 0.415)
```
Also praktisch der **volle freigegebene Bereich**, nur von einem sinnvolleren Nullpunkt aus.
⚠️ Der Begrenzer ist **nicht allein die Coxa**: beim seitlichen Ausschwenken wächst auch der Abstand
zum Fuß (`√(x²+y²)`), und die Reichweite endet bei 0.194 m. Bei `radial 0.19` passt beides
zusammen auf; bei größerem `radial` käme die Reichweite **vor** dem Coxa-Limit an die Grenze.

### 1.3 Harte Randbedingungen (gelten für jede spätere Wert-Änderung)

1. **Coxa-Budget:** `atan((show_front_lat + show_lat_scale) / show_front_radial) ≤ 0.415`.
2. **Bodenfreiheit:** `show_front_z − show_vert_scale ≥ body_height + 0.010` — der Fuß darf nie in
   den Boden fahren (er würde aufsetzen und das Stützpolygon verfälschen).
3. **Femur-Kopplung:** `show_front_z` und `show_radial_scale` konkurrieren um den Femur-Winkel.
   Je höher der Fuß steht, desto weniger radialen Weg gibt es (bei `z = 0` steht der Femur bereits
   auf −1.09 von −1.57). **Wer eine der beiden Größen erhöht, muss die andere neu prüfen.**
4. **Reichweite:** `√(radial² + lat²)` inkl. aller Offsets muss in `[0.074 … 0.194]` ab dem
   Femur-Gelenk bleiben.
5. **Rückversatz:** `show_body_shift_back ≤ 0.065` (darüber verletzen leg_3/leg_4 die Limits).

---

## 2. Logik-Skizze

### 2.1 Datenfluss (unverändert zur B4-Architektur, nur ein neuer Einstieg)

```
App  ── set_parameters(show_mode='free_leg') ──►  gait_node._set_show_mode
                                                     │  (NEU: mappt auf die B4-Kette)
                                    ggf. Stance-Wechsel auf TIEF  ──►  _pending_show_enter
                                                     ▼
                                         engine.start_show_enter(...)
Kishi ── /joy ──► joy_to_twist._show_from_joy ──► /cmd_show [6 Werte, R1-gegated]
                                                     │
                                   gait_node._update_show_offsets (nur SHOW_ACTIVE)
                                                     ▼
                                    engine.set_show_offsets({leg: (lat, vert, radial)})
                                                     ▼
                              State-Machine + Tick → IK → joint_trajectory
```

### 2.2 Engine (`gait_engine.py`)

```
_front_foot(leg, sigma, offset):
    # BISHER: Basis = (show_front_radial, 0, show_front_z)
    # NEU:    Basis = (show_front_radial, ±show_front_lat, show_front_z)
    #         Vorzeichen je Bein: leg_1 und leg_6 SPIEGELBILDLICH, damit beide
    #         nach VORNE schwenken (nicht beide zur selben Seite).
    basis = (radial, sign(leg) * front_lat, z)
    ziel  = basis + offset * lambda(sigma)

_show_foot(leg, sigma) / _front_foot(...):
    # NEU: Pitch. Nach der Ziel-Berechnung, VOR der IK, alle sechs Fuß-Targets
    #      um show_body_pitch_deg * sigma rotieren — mit sigma eingefahren, also
    #      kein Sprung beim Eintritt und sauberes Zurück beim EXIT.
    #      Wiederverwendung der A5-Rotationslogik (rotate_xy / _leveled_ik_at),
    #      NICHT neu implementieren.
```
*Warum die Show-States heute keinen Pitch haben:* `compute_joint_angles` leitet die SHOW-States
**vor** dem Leveling-Zweig ab (eigene `_compute_show_*_angles`-Pfade); der Node nullt den
Orientierungs-Offset außerhalb von STANDING/WALKING/STOPPING. Der Pitch muss deshalb **in** den
Show-Pfaden entstehen, nicht über den Balance-Regler ([D-FL-5]).

### 2.3 Node (`gait_node.py`)

```
_set_show_mode('free_leg'):
    if state != STANDING:      -> reject (Gate 1h4, unverändert)
    if safety_frozen:          -> reject (unverändert)
    if stance_idx != TIEF:
        _do_stance_switch(TIEF)          # dauert! eigener Engine-State
        _pending_show_enter = True       # Muster von _pending_sitdown
        return                            # Show startet, sobald STANDING erreicht ist
    _start_free_leg()

_tick:  # wie _pending_sitdown: feuert bei STANDING nach dem Switch
    if _pending_show_enter and state == STANDING:
        _pending_show_enter = False
        _start_free_leg()

_start_free_leg():
    engine.start_show_enter(t, dauer, shift_back, shift_fraction,
                            front_radial, front_lat, front_z,
                            body_pitch_deg, safety_margin, return_rate,
                            mass_model=<reale Segment-Massen>)   # siehe E9

_set_show_mode('none') aus einem SHOW-State:
    engine.start_show_exit(t, dauer)     # Rückweg ist IMMER erlaubt
    # Stance bleibt TIEF ([E10]) — kein Rückwechsel

_publish_status:
    show_mode = 'free_leg', sobald der Wunsch angenommen ist — also AUCH während
    des Stance-Wechsels (state == STANCE_SWITCH). Sonst zeigt die App den
    Menüpunkt kurz als inaktiv, obwohl die Show anläuft.
```

> **Wichtig — der Start dauert:** Stance-Wechsel (~2–3 s) + `show_enter_duration` (4 s) ≈ **7 s**,
> bis die Beine oben sind. Das ist erwartetes Verhalten, kein Hänger.

### 2.4 Teleop (`joy_to_twist.py`)

```
# BISHER: show_enabled gated BEIDES — den Cross-Toggle UND /cmd_show.
# NEU:    zwei getrennte Gates.
#   - Cross-Longpress → /hexapod_show_toggle : bleibt AUS (App-only, [E1])
#   - Sticks/Trigger  → /cmd_show            : AN
# R1-Dead-Man bleibt: ohne R1 sechs Nullen → Beine federn in die Neutral-Pose.
```

---

## 3. Entscheidungen (mit dem User geklärt, vor Code)

| # | Entscheidung | Verworfene Alternative |
|---|---|---|
| **E1** | **Start nur aus der App** (`show_mode=free_leg`), Bedienung App + Kishi | Cross-Longpress am Controller reaktivieren — ein Fehlgriff in der Fahr-Sicht wäre teuer |
| **E2** | **Keine Neu-Kalibrierung, kein URDF-Eingriff** — die Show bleibt im bestehenden ±0.415 | Coxa-Weitung für leg_1/leg_6: mechanisch nur für vordere **und** hintere Beine möglich, nicht für die mittleren → bricht die Konsistenz der Limit-Quellen ([D-FL-1], Ausbaustufe 3) |
| **E3** | **Tiefe Stance** für die Show (Kippwinkel 37° statt 26°) | mittel/hoch zulassen — schlechterer Kippwinkel bei identischer statischer Marge |
| **E4** | Bei falscher Höhe **wechselt ROS selbst auf tief** (aufgeforderte Bewegung, da der Nutzer die Show startet) | Reject mit `reason` — bedeutet App-Arbeit (Menüpunkt ausgrauen) und eine Fehlermeldung |
| **E5** | **Pitch 5° offen gesteuert** (Variante B) | C/D (IMU-Messung / IMU-Regelung) — als vorbereitete Ausbaustufen, §7 |
| **E6** | **Trigger = radial nach außen**, Skala 0.03 | Trigger weglassen; Trigger als Winke-Oszillator (Ausbaustufe 2) |
| **E7** | **Neutral-Pose mit Coxa-Anteil** (`show_front_lat`) | Neutral bei Coxa 0 lassen — genau das erzeugte die Spreiz-Optik |
| **E8** | **`show_front_z = 0.00`** statt −0.04 | tief lassen — kostet den Aufwärts-Hub und limitiert `show_vert_scale` |
| **E9** | **Massen-Modell nur im Show-Pfad korrigieren.** `MassModel` bekommt **optionale** Felder für Femur-/Tibia-Masse, **Default bleibt exakt das heutige Verhalten**; nur `start_show_enter` bekommt die realen Werte übergeben (der Parameter `mass_model` existiert bereits). **Bestand bit-identisch** — `torque_viz.py` und `leveling_envelope_check.py` bauen ihr Modell selbst | den Default in `joint_load.py` ändern — würde Torque-Analyse und Leveling-Envelope mitverschieben (User-Vorgabe: nichts am bestehenden System ändern) |
| **E10** | **Nach der Show bleibt der Roboter in der tiefen Stance** | zurück in die Ausgangshöhe — bräuchte gemerkten Vorzustand + zweite aufgeschobene Sequenz, also nochmal eine unaufgeforderte Bewegung. Die Höhe lässt sich danach jederzeit normal wechseln |

---

## 4. Tests-Liste

| Test | Prüft | Wo |
|---|---|---|
| **FL-T1** | Neutral-Pose + **gesamte** Stick-Hülle (lat × vert × Trigger) in-limit und in-reach | offline (Sweep) |
| **FL-T2** | CoG-Marge über die gesamte Hülle > `show_safety_margin`, **inkl. Pitch** — die 49 mm gelten nur für die Neutral-Pose; schwenken die Beine nach vorne, zieht ihre Masse Richtung Kippkante | offline (Tool, um Pitch erweitert) |
| **FL-T3** | Bodenfreiheit: tiefster Fußpunkt ≥ 10 mm über `body_height` in **jeder** Kombination | offline |
| **FL-T4** | Coxa-Budget: `front_lat + lat_scale` bleibt unter ±0.415 (Pin-Test gegen die Defaults) | Unit |
| **FL-T5** | Engine: ENTER → ACTIVE → EXIT → STANDING sauber, σ monoton, kein IKError | Unit (die 27 entsperrten Tests) |
| **FL-T6** | Pitch-Regression: bei `show_body_pitch_deg = 0` sind die Winkel **bit-identisch** zum Zustand ohne Pitch | Unit |
| **FL-T7** | Massen-Regression: `MassModel()` ohne Argumente liefert **exakt** die bisherigen Werte ([E9]) | Unit |
| **FL-T8** | `show_mode='free_leg'` startet die Show, `'none'` beendet sie; Rückweg **immer** erlaubt | Unit (Node) |
| **FL-T9** | Freeze/E-Stop: `free_leg` wird bei `safety_frozen` abgelehnt, `none` bleibt erreichbar | Unit (Node) |
| **FL-T10** | Stance-Wechsel: aus mittel/hoch wird erst gewechselt, dann die Show gestartet (`_pending_show_enter`); `status.show_mode` meldet schon während des Wechsels `free_leg` | Unit (Node) |
| **FL-T11** | Teleop: `/cmd_show` wird gesendet, `/hexapod_show_toggle` **nicht** ([E1]); R1 losgelassen → sechs Nullen | Unit (Teleop) |
| **FL-T12 (Sim)** | App → `free_leg` → Beine mit beiden Sticks bewegen → `none` → **danach normal weiterlaufen** | Live |
| **FL-T13 (Sim)** | **Selbstkollision visuell** — Beine bei maximaler Zusammenführung, Knie, Körper | Live |
| **FL-T14 (Sim)** | **Trigger-Richtung ausprobieren**: `sign_show_radial` in beide Richtungen (außen 0.03 / innen 0.02) → welche fühlt sich besser an | Live |
| **FL-T15 (HW)** | Aufgebockt → Boden: Show stabil, kein Kippen, Round-Trip sauber | Live |
| **FL-T16 (HW)** | **IMU-Messung**: 5° kommandiert vs. `/imu/monitor` gemessen → **Differenz = Servo-Durchsackung** | Live |

**Bewusst NICHT getestet / nicht gebaut:**
- **Selbstkollision automatisiert** — es gibt im Projekt keinen Kollisions-Checker (A4 pausiert).
  Bleibt visuell (FL-T13). Bei zusammengeführten Beinen erstmals überhaupt relevant.
- **Comms-Loss in der Show** — greift dort bis heute nicht (Altbestand aus B4). Bricht das WLAN in
  der Show ab, bleibt der Roboter auf vier Beinen stehen (statisch stabil). Als offener Punkt
  notiert, nicht in dieser Phase gelöst (Ausbaustufe 5).
- **Dynamische Stabilität / Stoß** — nur statische CoG-Betrachtung, wie in B4.
- **`dancing`** — bleibt Platzhalter.

---

## 5. Progress-Checkliste (Done-Vertrag → `phase_10_free_leg_progress.md`)

```
Phase 10 (Show „Free-Leg"):
- [ ] FL.1 [Offline] Auslegung final: alle Werte aus §1.1 gegen die Randbedingungen §1.3 geprueft (FL-T1/T2/T3)
- [ ] FL.2 [Tool] show_pose_cog_check.py um Pitch + Offset-Huelle erweitert; Plan §1.1 an die Tool-Ausgabe nachgezogen
- [ ] FL.3 [Engine] show_front_lat: Neutral-Pose mit Coxa-Anteil, spiegelbildlich fuer leg_1/leg_6
- [ ] FL.4 [Engine] show_body_pitch_deg: Fuss-Targets ueber sigma rotiert (A5-Rotationslogik wiederverwendet), Regression bei 0 Grad (FL-T6)
- [ ] FL.5 [Engine] neue Defaults eingetragen; Safe-Ranges in der Param-Doku korrigiert (0.065-Kante!)
- [ ] FL.6 [Engine] MassModel um optionale Femur-/Tibia-Masse erweitert, Default unveraendert; Show-Pfad uebergibt die realen Werte (FL-T7)
- [ ] FL.7 [Node] show_mode='free_leg' startet die B4-Kette, 'none' beendet sie (FL-T8/T9)
- [ ] FL.8 [Node] _pending_show_enter: Stance-Wechsel auf tief, dann Show; show_mode meldet schon waehrend des Wechsels (FL-T10)
- [ ] FL.9 [Teleop] show_enabled-Gate getrennt: /cmd_show an, Cross-Toggle aus (FL-T11)
- [ ] FL.10 [Tests] die 27 geskippten test_show_pose-Tests entsperrt + Fixtures auf die neue Geometrie (Tibia -0.28!)
- [ ] FL.11 [Tests] colcon test hexapod_gait + hexapod_teleop gruen, Lint gruen
- [ ] FL.12 [Contract] v0.14: free_leg ist implementiert (App-Seite unveraendert)
- [ ] FL.13 [Sim] FL-T12 Round-Trip + FL-T13 Kollision visuell + FL-T14 Trigger-Richtung entschieden
- [ ] FL.14 [HW] FL-T15 aufgebockt -> Boden
- [ ] FL.15 [HW] FL-T16 IMU-Durchsackungs-Messung dokumentiert
- [ ] FL.16 [Doku] Self-Review + progress-File + test_commands + ai_navigation; PHASE.md/00_overview auf Phase 10 = Free-Leg, Politur -> Phase 11
```

---

## 6. Was bewusst erst in der Umsetzung entschieden wird

Alle Vorab-Fragen sind mit dem User geklärt (§3). Offen bleiben nur Punkte, die **Messwerte oder das
Sim-Gefühl** brauchen:

1. **Rückversatz 0.055 oder 0.060** — fällt in Stufe 1 aus der CoG-Rechnung mit Pitch (FL.1/FL.2).
2. **Trigger-Richtung** — Variante A (nach außen) ist gesetzt; die Umkehr ist ein reiner Parameter
   (`sign_show_radial`), Skala dann 0.02 statt 0.03. **In der Sim beides ausprobieren** (FL-T14).
3. **Pitch-Startwert 5°** — bewusst konservativ; nach der IMU-Messung (FL-T16) ggf. überhöhen.
4. **Feinwerte der Skalen** — die Startwerte sind gerechnet, das Bediengefühl entscheidet die Sim.

---

## 7. Vorbereitete Ausbaustufen (bewusst NICHT in dieser Phase)

| # | Was | Wann ziehen |
|---|---|---|
| **1a** | **IMU misst den Pitch nach** (Variante C) | sobald FL-T16 eine Abweichung > 1–2° zeigt → Soll-Wert überhöhen |
| **1b** | **IMU regelt den Pitch** (Variante D, Balance-Regler mit Soll-Offset) | nur wenn die Abweichung mit der Beinbewegung **schwankt** statt konstant zu sein — dann hilft Überhöhen nicht mehr. ⚠️ Regler ist auf 6 Stützbeine ausgelegt, hier sind es 4 |
| **2** | **Trigger als Winke-Regler** (Oszillation um die Stick-Position, Amplitude/Tempo aus dem Trigger) | wenn die 3 cm radial optisch zu wenig hergeben — braucht keine Reichweite, dafür einen Oszillator in der Engine |
| **3** | **Coxa-Weitung für leg_1/leg_6** (Fuß-Abstand bis 0,13 m) | nur wenn 0,29 m optisch nicht reicht. **Preis:** Nachkalibrierung (Limit **und** `pulse_min` gemeinsam, damit die Slope konstant bleibt), `config.py` per-Bein-fähig machen, Envelope-Tool nachziehen, Kollisions-Check |
| **4** | **Stützbein-Reposition beim Show-Eintritt** (statt nur Körper-Rückversatz) | wenn mehr CoG-Marge nötig ist — hebt die 0.065-Kante auf, ist aber Engine-Arbeit |
| **5** | **Comms-Loss in der Show** absichern | eigenständiger Punkt, betrifft auch die alte B4-Lücke |

---

## 8. Contract-Touchpoints (v0.14)

- **§6c:** `free_leg` ist **nicht mehr Platzhalter**, sondern implementiert — Wirkung (4 Stützbeine,
  2 Vorderbeine frei) + Bedien-Tabelle (R1 halten, linker Stick = linkes Vorderbein, rechter Stick =
  rechtes, Trigger = strecken).
- **§6c-Regeln:** „Show-Modi nur aus STANDING" und „nicht bei `safety_frozen`" gelten unverändert.
  **Neu:** der Roboter wechselt beim Start selbstständig in die **tiefe Stance** ([E4]) und **bleibt
  danach dort** ([E10]); der Show-Start dauert dadurch bis zu ~7 s.
- **Kein neues Topic, kein neuer Service, kein neuer Message-Typ.** `/cmd_show` existiert seit B4.
- **App-Seite: keine Änderung nötig.** Menüeintrag aus `capabilities.show_modes`, aktiver Modus aus
  `status.show_mode`, Bedienung über `/joy`. Einzige Kosmetik-Option: ein modus-spezifischer
  Bedien-Hinweistext im Show-Menü (falls dort pro Modus hartkodiert — kann die ROS-Seite nicht
  prüfen, das App-Repo liegt außerhalb).

---

## 9. Design-Log (mit Alternativen)

- **[D-FL-1] Kein Hardware-Eingriff.** Die Show wird vollständig im bestehenden Coxa-Limit ±0.415
  ausgelegt. **Verworfen:** Nachkalibrierung der Vorderbein-Coxa. *Gründe:* (a) mechanisch ginge es
  nur für die vorderen und hinteren Beine, nicht für die mittleren — das bricht die Symmetrie der
  Limit-Quellen; (b) die rad→Puls-**Slope** hängt direkt an `joint_upper`
  (`slope = (pulse_zero − pulse_min) / joint_upper`), Limit und Puls-Anschlag müssten exakt
  gemeinsam gezogen werden, sonst verschiebt sich **jeder** Winkel — derselbe Mechanismus, der die
  Femur-Asymmetrie verursacht hat; (c) `config.py` kennt keine per-Bein-Limits. Der optische Gewinn
  kommt stattdessen aus [D-FL-2].
- **[D-FL-2] Der Coxa-Bereich wird über die Neutral-Pose erschlossen** (`show_front_lat`) statt über
  größere Limits. Die alte Pose stand auf Coxa 0 und ließ ±0.415 komplett ungenutzt — daher die
  Spreiz-Optik. **Verworfen:** Neutral bei Coxa 0 lassen und nur die Stick-Skala erhöhen (der Stick
  müsste dann erst den halben Weg „aufholen", die Ruhe-Pose bliebe hässlich).
- **[D-FL-3] Tiefe Stance.** Die statische CoG-Marge ist über alle Höhen gleich; der Kippwinkel nicht
  (37° vs. 26°). **Verworfen:** freie Höhenwahl — verschenkt genau die Reserve, die beim ersten
  HW-Versuch gefehlt hat.
- **[D-FL-4] Pitch offen gesteuert, nicht geregelt.** Eine Show soll **ruhig stehen**; ein Regler an
  der Totband-Kante neigt zum Pendeln, und er ist auf sechs Stützbeine ausgelegt. **Verworfen
  (vorerst):** IMU-Regelung → Ausbaustufe 1b. Die IMU wird zunächst als **Messgerät** eingesetzt
  (FL-T16) — die Differenz Soll/Ist beziffert die Servo-Durchsackung, also genau die Größe, die den
  Kipp-Effekt der alten Show erklärt.
- **[D-FL-5] Pitch in den Show-Pfaden, nicht über den Balance-Regler.** Die SHOW-States haben eigene
  `compute_*`-Pfade und laufen bewusst am Leveling vorbei; der Node nullt den Orientierungs-Offset
  außerhalb von STANDING/WALKING/STOPPING. **Verworfen:** SHOW in `_LEVELING_NODE_STATES` aufnehmen —
  das würde den Balance-Regler in der Show scharf schalten (siehe [D-FL-4]).
- **[D-FL-6] Automatischer Stance-Wechsel statt Ablehnung** ([E4]). Der Nutzer startet die Show
  bewusst — die Höhenanpassung ist damit eine **aufgeforderte** Bewegung. Spart App-Arbeit (kein
  Ausgrauen) und erspart eine Fehlermeldung. **Verworfen:** Reject mit `reason`. Umgesetzt über das
  erprobte `_pending_sitdown`-Muster, kein neues Konzept.
- **[D-FL-7] Trigger nach außen** (Variante A). Mit den kurzen Beinen ist radial die **kleinste**
  Achse (2–3 cm), weil `z` und `radial` um den Femur-Winkel konkurrieren. Nach außen sind 98 % der
  Hülle erreichbar, nach innen nur 82 %. Die Richtung ist ein reiner Parameter und wird in der Sim
  gegengeprüft (FL-T14). **Verworfen (vorerst):** Trigger als Winke-Oszillator → Ausbaustufe 2.
- **[D-FL-8] `show_front_z` von −0.04 auf 0.00.** Der Fuß stand nur 25 mm über dem Boden und
  begrenzte damit den vertikalen Hub. Auf Gelenkhöhe sind es 65 mm, der Fuß kann 15–115 mm
  schwingen. **Preis:** der Femur steht dort steiler, was den radialen Weg kostet ([D-FL-7]) —
  bewusster Tausch: großer sichtbarer Hub gegen wenige Zentimeter radial.
- **[D-FL-9] Massen-Korrektur nur im Show-Pfad** ([E9]). Der Default in `joint_load.py` bleibt
  unangetastet, damit Torque-Analyse und Leveling-Envelope bit-identisch bleiben. Möglich, weil
  `start_show_enter` bereits einen `mass_model`-Parameter hat und die Engine das Modell **nur** im
  Show-CoG-Gate verwendet. **Verworfen:** globalen Default korrigieren (User-Vorgabe: nichts am
  bestehenden System ändern) — bleibt als eigener, separat zu bewertender Schritt offen.
- **[D-FL-10] Nach der Show bleibt die tiefe Stance** ([E10]). **Verworfen:** Rückkehr in die
  Ausgangshöhe — bräuchte einen gemerkten Vorzustand und eine zweite aufgeschobene Sequenz nach dem
  Exit, also nochmal eine unaufgeforderte Bewegung für einen Komfort, den ein einziger Höhen-Tap
  ohnehin liefert.
