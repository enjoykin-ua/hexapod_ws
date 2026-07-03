# Stufe 4 — Terrain-adaptive Lokomotion (Fußkontakte) — Umbrella

> Stufe 4 von Block A5 ([Master](00_imu_balance_plan.md)). **Ziel:** **irreguläres** Terrain
> (Buckel, Stufen, Knick-Übergänge, lose Erde) — per-Fuß **kontakt-getriggertes Aufsetzen**,
> sodass jeder Fuß auf seiner **echten** Bodenhöhe landet statt auf einer festen Höhe.
>
> **Branch:** `imu_balance`. **Arbeitsweise:** CLAUDE.md §4 — pro Teil-Stufe Plan → Freigabe →
> Code → Test → kritischer Self-Review. Done-Vertrag: [`imu_balance_progress.md`](imu_balance_progress.md).
>
> **Status: 🟢 Kern komplett (S4-1/2/4/5/6 sim-verifiziert); offen nur optionales S4-3 free-gait.** Methode **fixed-timing gewählt** (s.u.). **S4-1 🟢 fertig** (Kontakt-Signal
> verifiziert: Sensor korrekt, der ~13-Tick-Offset = reiner Ausführungs-Lag des schnellen
> Aufsetzers). **S4-2 🟢 Sim-verifiziert (Option A)** — Erst-Entwurf war closed-loop-instabil
> (Körper-Anker verloren + ~13-Tick-Lag → Drift); **Option A** (downward-only, an `body_height`
> verankert, lag-Gate) ist Sim-bestätigt stabil + reicht selektiv am konvexen Knick nach (~6 mm auf
> 8°-Hang); sichtbarer Payoff → **S4-6** (Stufe/Graben). **S4-6 🟢 Sim-verifiziert** (Graben:
> `cmd_z` −0.105 vs −0.080, Roll ±1.3° vs ±2.7°). **S4-4 🟢 Sim-verifiziert** (Slip/Kontaktverlust →
> Freeze; `SupportMonitor` mit Leaky-Zähler — auch der kippende Fall freezt). **S4-5 🟢 Sim-verifiziert**
> (`SensorHealthMonitor`: stuck-on = lückenlose Apex-Pässe / dead → maskieren + warnen, kein Freeze;
> Inject-Hook. T1 ✅ Maske [1] / T2 ✅ kein Fehl-Freeze, Maske [2]; FP-Kaskade + Slip-Race + Geister-
> Flags gefunden + behoben). **✅ STUFE-4-KERN KOMPLETT** (S4-1/2/4/5/6 sim-verifiziert; offen nur das
> optionale S4-3 free-gait). —
> Detailplan: [`stage_4b_adaptive_touchdown_plan.md`](stage_4b_adaptive_touchdown_plan.md),
> Test-Doku: [`stage_4b_adaptive_touchdown_test_commands.md`](stage_4b_adaptive_touchdown_test_commands.md).
> S4-1-Detail: [`stage_4a_contact_verify_plan.md`](stage_4a_contact_verify_plan.md).
> **Abhängigkeit:** Fußkontakt-Pipeline (gz-contact in Sim **existiert vollständig**; HW-Taster =
> Block E2, später). TF-1/TF-2 (IMU) 🟢 — in Stage 4 zunächst **isoliert** (Leveling aus).

---

## 0. Kontext & Abgrenzung

- **IMU misst die Körperlage, Taster messen, wo der Boden wirklich ist** — zwei verschiedene
  Probleme (Master §1). Für *glatte* Hänge trägt die IMU (TF-1/TF-2); für *unvorhersehbares*
  Terrain + den **Knick-Übergang** braucht es per-Fuß-Kontakt (diese Stufe).
- Die Fußkontakt-Pipeline existiert in Sim **vollständig**: [`hexapod.foot_contact.xacro`](../../src/hexapod_description/urdf/hexapod.foot_contact.xacro)
  (gz-contact-Sensor pro foot_link, `preserveFixedJoint`) → [`bridge_foot_contact.yaml`](../../src/hexapod_bringup/config/bridge_foot_contact.yaml)
  → [`foot_contact_publisher.py`](../../src/hexapod_sensors/hexapod_sensors/foot_contact_publisher.py)
  (Event→Dauer-`Bool`, 50 Hz, `contact_timeout`) → `Bool` auf `/leg_<n>/foot_contact`. Läuft per
  Default (`enable_foot_contact:=true`, auch in `ramp_walk.launch.py`). **Wir bauen den Consumer,
  nicht die Sensorik.**

## 0.5 Methoden-Wahl: fixed-timing (GEWÄHLT) vs. free-gait (Alternative)

> Festgehalten, damit die Entscheidung später nachvollziehbar ist. Beide modulieren das
> per-Fuß-Aufsetzen über den Kontakt — sie unterscheiden sich darin, ob die **Gait-Uhr** fest
> bleibt oder am Kontakt hängt.

**Grundlage:** Der Gait ist heute **open-loop, zeitgetaktet**: eine globale Gait-Uhr (0→1 pro
Cycle) + fester Phasen-Offset pro Bein bestimmt, wann es schwingt/stützt. Der Swing
([`swing_traj`](../../src/hexapod_gait/hexapod_gait/trajectory_gen.py)) landet bei **fester Höhe**
`z = body_height`. Alles zeitlich fest, ohne Boden-Rückmeldung.

### ✅ GEWÄHLT — fixed-timing (nur die Senk-Tiefe wird adaptiv)
- **Mechanik:** Gait-Uhr läuft **unverändert**. Nur die **z-Komponente** des Schwungbeins wird in
  der **späten Schwungphase** moduliert: kein Kontakt → weiter absenken (Senk-Rate) bis maximal
  zur **Envelope-Grenze**; Kontakt → z **einfrieren**, Fuß bleibt für den Rest der Stance auf
  *dieser* echten Bodenhöhe. Das Timing ändert sich nie; jedes Bein hat ein **festes Tast-Fenster**.
  Findet es in der Zeit keinen Boden → planmäßig in Stance (Envelope-Grenze) = Open-Loop-Fallback.
- **Pro:** robust + minimaler Eingriff (nur z-Berechnung im Swing); **sicherer Fallback eingebaut**
  (kein Bein „hängt"); geringes Risiko (keine neuen Echtzeit-/Stabilitäts-Probleme); löst moderate
  Unebenheit + moderaten Knick (jeder Fuß landet auf echter Höhe → Körper „sitzt" aufs Profil).
- **Contra:** **begrenzte Tiefe** (nur die feste Schwung-Restzeit zum Tasten → großer
  Höhenunterschied/scharfer Bordstein wird nicht ganz erreicht → Fallback); kein „Warten" (nächstes
  Bein hebt planmäßig, auch wenn ein anderes noch keinen sicheren Stand hat — in *extremem* Terrain
  ein Stabilitätsrisiko, auf moderatem unkritisch).

### ⏸️ ALTERNATIVE (nicht jetzt) — free-gait (das Timing selbst hängt am Kontakt)
- **Mechanik:** Gait-Uhr **nicht mehr fest** — Phasen-Übergänge ereignis-gekoppelt: Schwungbein
  geht erst in Stance, **wenn Kontakt** (darf „warten"); Stützbein hebt erst, wenn genug andere
  Beine sicheren Stand haben (laufende Stützpolygon-Garantie). Die Uhr wird Koordinator mit
  Vetorecht; der Roboter findet seinen eigenen Rhythmus.
- **Pro:** **beliebige Höhenunterschiede** (kein Zeitlimit fürs Tasten → tiefe Löcher, hohe Stufen,
  scharfe Knicks); echte statische Sicherheit (nie zu früh heben).
- **Contra:** **großer Umbau** (Koordination von zeit- auf ereignis-getrieben); **Scheduling-Problem**
  (welches Bein hebt als Nächstes = Laufzeit-Entscheidung); **Vortrieb wackelt** (warten → cmd_vel-
  Tracking unsauber); mehr Logik im 50-Hz-Pfad (Koordinations-Fehler = Sturz); **Sensor wird
  kritisch** (Bein „wartet ewig" bei Defekt → Plausibilitäts-Fail-Safe zwingend). Voller Wert eher
  auf echter HW.

**Begründung der Wahl:** fixed-timing = ~80 % des Nutzens für ~20 % von Aufwand und Risiko, ohne
die bewährte Engine zu zerlegen. Erst fixed-timing, dann **messen**, wie weit es trägt; free-gait
nur, wenn fixed-timing nachweislich nicht reicht — dann als großer eigener Block (eher HW-nah).

## 1. Teil-Stufen (klein anfangen — wie bei TF)

| Stufe | Inhalt | Kern-Deliverable |
|---|---|---|
| **S4-1** 🟢 ([Plan](stage_4a_contact_verify_plan.md)) | **Kontakt-Consumer + Verifikation** | ✅ Signal verifiziert: Sensor zuverlässig+korrekt; ~13-Tick-Offset = reiner Ausführungs-Lag (schneller Aufsetzer). De-risk vor S4-2 erledigt. |
| **S4-2** 🟢 ([Plan](stage_4b_adaptive_touchdown_plan.md)) | **Adaptiver Touchdown (Option A)** | downward-only ab Stance-Gate, an `body_height` verankert (Erst-Entwurf war closed-loop-instabil). **Sim-verifiziert stabil + selektives Nachreichen** (~6 mm am 8°-Scheitel). Sichtbarer Payoff (großer Höhensprung) → **S4-6**. |
| **S4-3** *(später, evtl.)* | **Kontakt-getriggertes Timing (free-gait)** | nur falls fixed-timing nicht reicht — großer eigener Block. |
| **S4-4** 🟢 ([Plan](stage_4d_slip_detection_plan.md)) | **Slip / Kontaktverlust → Freeze** | `SupportMonitor` (ROS-frei, **Leaky-Zähler**): Stance-Bein ohne Kontakt nach Grace → Freeze (= Stufe 1). `cliff_depth` 0.03 = Grenze folgbar↔Abgrund. **Sim-verifiziert** (Kante `step_drop:=0.06`: freezt statt drüber, auch im kippenden Fall). ⚠️ `contact_timeout` → Debounce > 5. |
| **S4-5** 🟢 ([Plan](stage_4e_plausibility_plan.md)) | **Plausibilität + Sensor-Fault-Fail-Safe** | `SensorHealthMonitor` (ROS-frei): stuck-on = **N lückenlose Apex-Pässe in Folge** (gz-Apex-Artefakt liefert gesund lückenhaften Kontakt → Pass-Logik) / dead = überhaupt kein Kontakt über N Cycles → **maskieren** (S4-2 adaptiv-aus + aus S4-4-Zählung; nie-kontaktiertes Bein sofort aus Slip-Freeze gg. den Race) + throttled WARN, **kein** Freeze. Sim-Hook `sensor_fault_inject`. **Sim-verifiziert (T1 stuck_on, T2 stuck_off).** HW-gerichtet/defensiv. |
| **S4-6** 🟢 ([Plan](stage_4c_step_worlds_plan.md)) | **Stufen- + Graben-Welt (Demo)** | `step.*` (Stufe) **+ `trench.*` (Graben — die klare Demo)**. **Sim-verifiziert:** Stufe vom Pitch geschluckt (~3 mm), **Graben** zeigt den per-Fuß-Reach (`cmd_z` −0.105 vs −0.080 = ~2.5 cm; Roll ±1.3° vs ±2.7°). `miss 0` beide (Füße straddeln 10-cm-Graben). |
| **S4-7** 🟡 ([Plan](stage_4f_adaptive_stand_plan.md)) | **Terrain-anpassendes Stehen (Adaptive Stand)** | statischer Zwilling von S4-2: im **STANDING** senkt jedes Bein downward-only bis Kontakt (auf unebenem Grund aufsetzen statt hängen); Floor `body_height − max_depth`; AUS = starre Pose. **Code+Tests+Envelope+Doku fertig** (782 Tests grün; Envelope tief/mittel/hoch GREEN), **Sim-Verify (Rubicon) durch User offen.** |

**Reihenfolge: S4-1 🟢 → S4-2 🟢 → S4-6 🟢 (Graben-Demo) → S4-4 🟢 (Slip→Freeze) → S4-5 🟢
(sim-verifiziert) → (S4-3, nur falls nötig).** Jede mit eigenem §4-Review. **✅ Stufe-4-Kern komplett**
(S4-1/2/4/5/6); offen bleibt nur das optionale S4-3 (free-gait), nur falls fixed-timing nicht reicht.

## 2. Logik-Skizze der Gesamt-Stufe (grob — Detail je Teil-Stufe)

- **A. Kontakt-Consumer:** `/leg_<n>/foot_contact` (Bool) cachen; in S4-2 → adaptiver Touchdown.
- **B. Per-Fuß-Terrain-Adaption:** jeder Fuß landet auf echter Bodenhöhe; Körper-Pose folgt dem
  per-Fuß-Höhenprofil (nicht durch eine einzelne Kippung beschreibbar — komplementär zur IMU).
- **C. Slip/Kontaktverlust:** Stance-Fuß verliert Kontakt → Schritt nachsetzen / stoppen (S4-4).
- **D. Fail-Safe:** Plausibilitätscheck gegen die Gait-Phase; **Taster = Optimierung, nie
  load-bearing** — Basis-Lokomotion läuft immer auf dem Zeit-Gait, Kontakt verbessert nur das
  Aufsetzen (S4-5).

## 3. Hebel-Katalog — Kontakt-Zuverlässigkeit (Referenz, falls S4-1 Probleme zeigt)

> **Bekanntes Thema** ([phase_5_gait_explained.md](../../docs/phase_5_gait_explained.md)): JTC hängt
> ~0.5–1 mm hinterm Ziel → Fuß schwebt knapp über Boden → Sensor feuert unzuverlässig; „bei zu
> schnellem Cycle weniger zuverlässig". **Wichtig:** Hebel 1 (langsamer laufen) ist **ausgeschlossen**
> (User will auf HW eher schneller, bis 2×) → die Lösung muss bei normalem/schnellem Cycle tragen.

| # | Hebel | Wirkung | Status |
|---|---|---|---|
| 1 | langsamer Cycle (`cycle_time`↑) | mehr JTC-Konvergenzzeit → zuverlässiger | ❌ **ausgeschlossen** (User: HW schneller) |
| 2 | `contact_timeout`↑ (Publisher-Param) | überbrückt Flackern (hält `true` länger) | ✅ erlaubt — nur moderat (verzögert sonst die Verlust-Flanke, S4-4) |
| 3 | Touchdown-**Penetrations-Offset** (in S4-2) | Fuß 2–3 mm unter erkannte Höhe → stabiler Kontakt | ✅ erlaubt (Sim-Artefakt; auf HW = 0) |
| 4 | Fuß-Kollisions-**Geometrie** (Kugel-Radius) | größere Kontaktfläche | ⚠️ **nur falls 2+3 nicht reichen** — §7-Geometrie-TABU-nah (TCP/IK/Posen/Kal + Sim/HW-Divergenz), eigener freizugebender Punkt |

**Timing-Befund (gut):** Touchdown = **steigende** Flanke → Latenz nur ~1–2 Ticks (gz 50 Hz +
Publisher 50 Hz); der `contact_timeout` verzögert nur die **fallende** Flanke (→ S4-4).

## 4. Tests-Strategie (drei Schichten)

1. **Unit (ROS-frei):** Touchdown-Logik (senken bis Kontakt, Envelope-Grenze, Entprellung),
   Plausibilitäts-Logik (Phase-Cross-Check) — wie `tip_monitor`/`balance_controller`.
2. **Sim:** Knick (ramp-Welt) zuerst, dann Stufen/Buckel (S4-6); flach **und** Hang.
3. **HW (später):** verbaute Taster (E2), NO/NC + Fail-Safe real.

## 5. Gelockte Entscheidungen (mit Alternativen)

| Entscheidung | Gewählt | Verworfen / Alternative | Warum |
|---|---|---|---|
| Methode | **fixed-timing** (Senk-Tiefe adaptiv) | free-gait (Timing am Kontakt) | 80/20 Nutzen/Aufwand; bewährte Engine bleibt; free-gait = großer Umbau, später falls nötig |
| Kontakt-Rolle | **Optimierung, nie load-bearing** | load-bearing | defekter Sensor legt nie lahm; Zeit-Gait bleibt gültiger Fallback |
| Reihenfolge | **erst S4-1 verifizieren**, dann S4-2 | direkt S4-2 | Signal-Risiko (JTC-Lag/Penetration/Cycle) **billig** entschärfen, bevor Verhalten drauf baut |
| IMU-Kombination | **erst isoliert** (Leveling aus), dann kombiniert | gleich kombiniert | eine Variable; Stage-4 = per-Fuß, TF = global → trennbar testen |
| Welten | **selbst gebaute Stufen/Buckel** (Knick zuerst) | Heightmap/Fuel sofort | Maßstab-Kontrolle (Hexapod klein); Heightmap später |
| Geometrie | **Fuß-Kugel NICHT anfassen** (außer Notfall) | Radius vergrößern | §7-Geometrie-TABU-nah (Rattenschwanz + Sim/HW-Divergenz) |

## 6. Doku-/Querverweis-Plan (bei Bedarf nachziehen)
- `PHASE.md` + [`../00_backlog.md`](../00_backlog.md): Stufe 4 / E2 aktiv.
- `ai_navigation.md`: Eintrag „Fußkontakt / Terrain-Adaption ändern".
- READMEs: `hexapod_sensors` (Consumer), `hexapod_gait` (adaptiver Touchdown).
