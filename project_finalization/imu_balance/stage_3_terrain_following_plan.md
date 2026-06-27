# A5 — Terrain-Following + Körper-Stabilisierung (Plan)

> **Neuer Ansatz fürs Hang-Laufen** (ersetzt das verworfene „Klettern via Voll-Leveling +
> θ-Geometrie-Tabelle", siehe [Retro](terrain_following_pivot_retro.md)). **Grundprinzip:**
> der Körper soll **parallel zum Untergrund** bleiben (flach → waagerecht, Hang →
> hangparallel) und mechanisches/Gang-bedingtes **Wackeln** ausgleichen — der IMU dient für
> **Sicherheit + Wackel-Dämpfung + Hang-Wissen**, NICHT zum Waagerecht-Zwingen.
>
> **Branch:** `imu_balance`. **Arbeitsweise:** CLAUDE.md §4 — pro Teil-Stufe Plan → Freigabe
> → Code → Test → kritischer Self-Review. Done-Vertrag: [`imu_balance_progress.md`](imu_balance_progress.md).

---

## 0. Grundprinzip & Kern-Erkenntnis

**Ein Ziel, kein Modus-Umschalten:** „Halte den Körper parallel zum Boden, auf dem du gerade
stehst, und halt ihn ruhig." Auf flachem Boden ist „parallel zum Boden" = waagerecht; am
Hang = hangparallel. Das frühere „Leveln vs. Terrain-Following" war ein Scheingegensatz.

**Achsen-Trennung (der saubere Trick, statt einer Größen-Heuristik):**

| Achse | Soll | Warum |
|---|---|---|
| **roll** (links-rechts) | **auf 0 ausrichten** | Beim Geradeaus-Klettern gibt es keine *gewollte* Seitneigung → jede Links-rechts-Neigung (Mechanik, Wackeln, Seithang) ist unerwünscht → ausgleichen. Schwerkraft-Referenz (Kalibrierung) liefert den Nullpunkt. **Keine** Slope-vs-Schieflage-Ambiguität. |
| **pitch** (vorn-hinten) | **dem Hang folgen** | Das *ist* die Kletter-Richtung → NICHT auf 0 zwingen (das wäre der verworfene Sprawl), sondern folgen; nur das schnelle Vor-zurück-Wackeln dämpfen. Auf dem Flachen ist pitch von allein ~0. |

**Bein-Geometrie:** bei terrain-following identisch zur Flach-Pose → **keine** Bein-Streckung
(nachgewiesen, [Retro](terrain_following_pivot_retro.md)). Stance bleibt **nominal** (radial
0.160 / body_height −0.080) — kein Spreizen, kein Tieflegen, kein step-Schrumpfen.

**Kletter-Grenze** = Schwerpunkt/Kippen + Traktion (nicht Bein-Reichweite) — vermutlich
steiler als die ~8° des Voll-Levelings. Wird in TF-1 gemessen.

## 1. Architektur / Technik-Kern (was wiederverwendet wird)

- **Regler:** der vorhandene [`BalanceController`](../../src/hexapod_gait/hexapod_gait/balance_controller.py)
  (Stufe 2) bleibt — aber **umgepolt**: Sollwert nicht mehr fix 0, sondern **per Achse**
  (roll → 0, pitch → langsam-gefilterte Ist-Neigung = „der Hang") + ein **Gyro-D-Term**
  (schnelle Drehrate dämpfen). Das ist die Dual-Timescale-Idee aus Master-D3: langsamer
  Anteil = Untergrund (folgen), schneller Anteil = Wackeln (dämpfen).
- **θ-Schätzung trivial:** der Körper folgt dem Hang → IMU-Neigung ≈ Hang **direkt** (kein
  `tilt+corr`-Trick wie im verworfenen 3c-1 nötig, weil keine große Aufricht-Korrektur läuft).
- **Stellpfad:** weiterhin der Engine-`set_body_orientation_offset` → `compute_joint_angles`
  (Round-Trip-Rotation), aber die Korrektur ist klein (nur roll-Ausgleich + Wackel-Dämpfung,
  kein Voll-Leveln) → bleibt mühelos im Envelope, **keine** θ-Geometrie-Tabelle nötig.
- **Sicherheit:** die Stufe-1-Kipp-Erkennung (`TipMonitor`) bleibt, wird aber **slope-bewusst**
  (Schwelle relativ zur erwarteten Hang-Neigung statt absolut — sonst Fehlalarm am Hang).
- **Welten:** die slope-/ramp-Welten aus Stufe 2/3a wiederverwenden (flach spawnen).

## 2. Teil-Stufen (klein anfangen)

| Stufe | Inhalt | Kern-Deliverable |
|---|---|---|
| **TF-1** ([Plan](stage_3a_passive_tf_plan.md)) | **Passiv terrain-following + slope-bewusster Tip** | Leveling-fürs-Klettern aus (Körper folgt passiv dem Hang); `TipMonitor` slope-relativ → kein Fehlalarm am Hang. **Test:** wie steil kommt er von allein hoch, ab wann kippt/rutscht er? |
| **TF-2** | **Aktive Körper-Stabilisierung** (roll → 0, pitch → folgen) + **Gyro-Wackel-Dämpfung** | `BalanceController` per-Achse umgepolt + D-Term → Körper bleibt sauber parallel (flach waagerecht, Hang hangparallel), Wackeln gedämpft. Der sichtbare IMU-Mehrwert (hilft auch Nicht-Tripod-Gangarten). |
| **TF-3** *(optional/später)* | **Schwerpunkt-Hilfe für steiler + Schlupf-Erkennung** | Gewicht in den Hang verlagern (kippt nicht nach hinten) ohne zu leveln; Schlupf-Indikator aus dem Regler-Zustand. Echtes unebenes Terrain + **Fußkontakte = Stufe 4** (eigene Planung). |

**Reihenfolge: TF-1 → TF-2 → (TF-3).** Jede mit eigenem §4-Review → Freigabe → Code → Test →
Self-Review.

## 3. Gelockte Entscheidungen

| Entscheidung | Gewählt | Verworfen / Alternative | Warum |
|---|---|---|---|
| Hang-Look | Körper **parallel zum Boden** (terrain-following) | Körper waagerecht (Voll-Leveln) | natürlich, kein Sprawl; Bein-Geometrie = Flach (nachgewiesen) |
| Achsen | **roll → 0 ausrichten, pitch → folgen** | beides leveln · α(θ)-Größen-Heuristik | klare Trennung, keine Slope-vs-Schieflage-Ambiguität; α(θ) unnötig |
| θ-Schätzung | **IMU-Neigung direkt** (Körper folgt Hang) | tilt+corr (3c-1) | keine große Korrektur läuft → IMU liest den Hang direkt |
| Geometrie | **Nominal-Stance fix** (radial 0.160 / bh −0.080) | θ-Geometrie-Tabelle | keine Streckung bei terrain-following → keine Adaption nötig |
| Wackeln | **Gyro-D im BalanceController** | separater Node | teilt Stellpfad, ein Modul (= das alte „3b") |
| Tip am Hang | **slope-relative Schwelle** | absolute Schwelle | Körper ist am Hang gewollt geneigt → sonst Fehlalarm |
| Fußkontakte | **deferiert (Stufe 4)** | jetzt einbauen | komplementäre Schicht (per-Bein/Terrain/Schlupf), invalidiert TF nicht |
| Waagerecht-Leveln | lebt als **Flach-Spezialfall** weiter (roll→0; pitch~0 flach) | als eigener Modus | „parallel zum Boden" deckt flach automatisch ab |

## 4. Offene Punkte (je Teil-Stufe vorm Code per §4 klären)

- **TF-1:** Form der slope-bewussten Tip-Schwelle (roll absolut vs. pitch relativ zur
  langsam-gefilterten Ist-Neigung?) · passiver Kletter-Limit messen (CoG/Traktion bei 8°+).
- **TF-2:** Gains roll-P/I vs. Gyro-D · Filter-Zeitkonstante „langsam = Hang" vs. „schnell =
  Wackeln" · wie viel pitch-Dämpfung (ohne den Hang-Follow zu bremsen).
- **Quer-/Diagonal-Hang:** „roll→0" stimmt exakt nur fürs Geradeaus-Klettern; Seithang hätte
  eine gewollte roll-Komponente → **später** (Randfall, Fokus = hochlaufen).
- **Persistente Flach-Schieflage** (statischer mechanischer Lean) vs. Hang: per IMU allein nur
  über die Achsen-Trennung gelöst (roll→0); ein statischer *pitch*-Lean würde gefolgt. Perfekt
  erst mit Fußkontakten (Stufe 4) — für Sim unkritisch (symmetrisch).

## 5. Test-Strategie

- **Sim (User):** ramp-Welt (flach spawnen), 8°+ hochlaufen, `/imu/monitor` beobachten.
  - TF-1: kommt er passiv hoch? bis wie steil (Kippen/Rutschen)? Tip feuert nicht fälschlich?
  - TF-2: Körper sichtbar **ruhig parallel** (flach waagerecht, Hang hangparallel), Wackeln
    sichtbar gedämpft, Plateau-Übergang sauber zurück (kein Hängenbleiben).
- **Offline/Unit:** Achsen-Sollwert-Logik, Gyro-D, slope-relative Tip-Schwelle.
- **Bewusst NICHT:** unebenes per-Fuß-Terrain + Fußkontakte (Stufe 4); Quer-Traversieren.

## 6. Abgrenzung zum verworfenen Ansatz

Dieser Plan ist **nicht** mit der θ-Geometrie-Tabelle / dem Voll-Leveling vermischt. Was von
A5 bleibt: Stufe 0/1/2 + die Regler-/Welt-Infrastruktur. Was ersetzt wird: das „Klettern via
Waagerecht-Leveln" (3a-Verhalten im Lauf + 3c). Details/Begründung: [Retro](terrain_following_pivot_retro.md).
