# Block I Phase 11 — Längere Schritte — Progress

> **Done-Vertrag** (CLAUDE.md §4). Bullets 1:1 aus
> [`phase_11_stride_envelope_plan.md`](phase_11_stride_envelope_plan.md) §4.
> Alle `[x]` = Phase 11 fertig; pro erledigtem Bullet sofort abhaken (nicht batchen).
> Post-Review-Tabelle nach der Implementierung (`OK` / 🔴 fixen / 🟡 vormerken / 🟢 später).
>
> **Kern-Ergebnis der Offline-Messung (P11.1):** die Stance-Deckel standen bereits am
> **geometrischen Optimum** — mehr als **+5 mm Schrittweite** je Modus gibt die Bein-Geometrie
> nicht her, der **Fuß-Hub gar nichts**. Der eigentliche Hebel ist die **Tempo-Auslegung**: der
> Roboter schöpfte seinen erlaubten Deckel nicht aus. Boot-Kombination (mittel + schnell):
> **50 mm → 85 mm** bei unveränderter Fahrgeschwindigkeit.

```
Phase 11 (Laengere Schritte):
- [x] P11.1 Offline-Gates: Deckel-Kandidaten + Fallback-Treppen exit-code-basiert gemessen (check UND engine-check), finale Werte + verworfene Alternativen mit Messreihe dokumentiert  [zusaetzlich: alle 4 Gangarten geprueft; Clamp-Warn-Nebenwirkung gefunden -> B2b in den Scope]
- [x] P11.2 Code B1: _STANCE_MODES sl (0.065/0.085/0.055) + step_length_max-Default + step_length_intent_max + gait.launch.py-Default inkl. description-Texte  [Fuss-Hub unveraendert; Kommentarblock traegt die Messreihe + die verworfenen Alternativen]
- [x] P11.3 Code B2: _TEMPO_MODES (4.0/3.6/3.4/1.7 + aggressiv-Bremse 0.100/0.090/0.95) + cycle_time-Default (Node + Launch) + ps4_usb/bt.yaml-Kommentare + Clamp-Log entschaerft (B2b)  [Skalen bewusst unveraendert -> Sprungfrei-Invariante bleibt ohne YAML-Aenderung erfuellt; B2b: neue Engine-Property last_clamp_factor + _log_cmd_clamp im Node, Schwelle GERECHNET statt geschaetzt (s. Self-Review)]
- [x] P11.4 Tests: Tabellen-/Apex-/Reject-/intent_max-Pins, test_stance_switch auf Modus-sl gehaertet, Tempo-Pins (Sprungfrei Code+YAML+cycle_time, Ausschoepfung, keine-Stufe-schneller, Monotonie), Clamp-Log-Test; colcon test hexapod_gait hexapod_kinematics hexapod_teleop hexapod_supervisor + Lint gruen  [569 gait / 69 teleop / 43 kin / 38 supervisor, 0 failures; 10 bestehende Tests angepasst (davon 4 driftfest gemacht statt neu betoniert), 12 neue]
- [x] P11.5 Doku: hmi_config_manifest-Defaults, interface_contract §6a + v0.14.1-Changelog, README gait+teleop, ai_navigation, Backlog, H1/H2-Progress-Verweise, PHASE.md  [+ 00_overview.md, + apex_meter-Hilfetext]
- [ ] P11.6 Sim UEBER DIE APP (ein Befehl: always_on.launch.py -> App verbinden -> Hexapod starten -> Aufstehen): 3 Stance-Modi x 4 Tempo-Stufen, Schrittweite gemessen, kein IKError/Freeze/Regress, Alert-Liste sauber
- [ ] P11.7 HW aufgebockt: Tempo-Stufen + Stance-Modi durchschalten, apex_meter (Hub unveraendert), Kontakt-/Slip-Logs beobachten
- [ ] P11.8 HW Boden -> Gelaende: Schrittweite subjektiv bewertet, Stopp-Nachlauf einmal bewusst geprueft, Strom/Stabilitaet ok, keine False-Positive-Freezes
- [x] P11.9 kritische Self-Review-Tabelle (unten; final nach P11.6-P11.8)
```

## Finale Werte

### Stance-Deckel (B1)

| Modus | radial | body_height | step_height | step_length_max | Änderung |
|---|---|---|---|---|---|
| tief | 0.160 | −0.065 | 0.040 | **0.065** | +5 mm |
| **mittel** (Boot) | 0.160 | −0.080 | 0.050 | **0.085** | +5 mm |
| hoch | 0.160 | −0.100 | 0.080 | **0.055** | +5 mm |

### Tempo-Stufen (B2)

| Stufe | cycle_time | Skala x/y/z | v | Schritt @ mittel |
|---|---|---|---|---|
| langsam | 4.0 | 0.030 / 0.030 / 0.28 | 0.030 | 60 mm |
| mittel | 3.6 | 0.040 / 0.040 / 0.35 | 0.040 | 72 mm |
| **schnell (Boot)** | **3.4** | 0.050 / 0.050 / 0.46 | 0.050 | **85 mm** |
| aggressiv | 1.7 | 0.100 / 0.090 / 0.95 | 0.100 | 85 mm |

---

## Messreihe P11.1

Gate: `--min-margin 0.10 --leveling-deg 4.0 --s4-floor 0.03 --scenario all`, **exit-code-basiert**
ausgewertet (H1.2-Lehre — die Kopfzeile meldet nur das forward-Szenario und kann „GREEN" sagen,
während sidestep/diagonal rot sind).

### Referenzen (heutige Werte — mussten GREEN sein, sonst wäre das Gate falsch parametriert)

| Zelle | check | worst-Joint |
|---|---|---|
| mittel 0.050 / 0.080 | ✅ | femur 0.209 · coxa 0.170 |
| hoch 0.080 / 0.050 | ✅ | femur 0.125 |

### Fuß-Hub (mittel) — Erhöhung datenbasiert verworfen

| Zelle | check | Befund |
|---|---|---|
| sh **0.060** / sl 0.085 | ❌ | femur **0.0195** (sidestep + diagonal) |
| sh **0.060** / sl 0.080 | ❌ | femur **0.0328** — der Hub allein reicht schon |
| sh **0.055** / sl 0.085 | ❌ | femur **0.0822** |
| sh 0.050 / sl 0.085 | ✅ | femur 0.204 · coxa 0.155 |

**Deutung:** Hub und Weite sind weitgehend **unabhängig**. Hub 50 → 60 kostet 10,1° Femur-Reserve,
Weite 80 → 85 nur 0,3°. Der Apex (`bh + sh`) läuft gegen die Femur-Wand; ab 0.055 bricht die Marge
im Seitwärtsgang ein. Deckt sich mit H1.2 (mittel 0.06 war dort bei nur sl 0.05 schon RED, 0.098).

### Schrittweite hoch — Grenze ist die Reichweite

| sl | check | Befund |
|---|---|---|
| 0.100 | ❌ | out_of_reach d=0.1949 > 0.194 (Floor z = −0.13) · femur 0.080 |
| 0.090 | ❌ | out_of_reach d=0.1948 · femur 0.091 |
| 0.085 | ❌ | out_of_reach d=0.1945 |
| 0.080 | ❌ | out_of_reach d=0.1942 |
| 0.070 | ❌ | out_of_reach (sidestep t=2.90 s, diagonal) |
| 0.060 | ❌ | out_of_reach (sidestep t=2.98 s, diagonal) |
| **0.055** | ✅ | femur 0.121 · coxa 0.245 |

**Deutung:** bei `body_height` −0.100 liegt der S4-Probe-Floor auf z = −0.13. Die Basis-Distanz ab
Femur-Gelenk beträgt dort `hypot(0.160−0.0436, 0.130) = 0.1745` bei 0.194 Reichweite — für die
Schritt-Amplitude bleiben nur ~2 × 28 mm. Reine Geometrie, kein Tuning-Problem.

### Schrittweite tief — Grenze ist der Femur im Seitwärtsgang

| sl | check | engine-check | Befund |
|---|---|---|---|
| 0.100 | ❌ | — | femur 0.096 + joint_limit (sidestep) |
| 0.090 | ❌ | — | femur 0.0182 |
| 0.080 | ❌ | — | femur 0.0556 |
| 0.070 | ❌ | — | femur 0.0885 |
| **0.065** | ✅ | ✅ | check femur 0.152 · engine femur 0.104 |

### engine-check der finalen Zellen (Transitions: Start / Richtungswechsel / Stopp / Sitdown / Reposition)

| Zelle | engine-check | worst-Joint (Walk-Phasen) |
|---|---|---|
| tief 0.040 / **0.065** | ✅ | femur 0.104 (B:sidestep) · coxa 0.211 |
| mittel 0.050 / **0.085** | ✅ | femur 0.146 (B:sidestep) · coxa 0.148 · tibia 0.195 |
| hoch 0.080 / **0.055** | ✅ | femur 0.102 (B:sidestep) · coxa 0.242 |

### Alle Gangarten mit den finalen Deckeln (beide Gates)

| Gangart | swing_duty | tief 0.065 | mittel 0.085 | hoch 0.055 |
|---|---|---|---|---|
| tripod | 0.500 | ✅ / ✅ | ✅ / ✅ | ✅ / ✅ |
| wave | 0.167 | ✅ / ✅ | ✅ / ✅ | ✅ / ✅ |
| tetrapod | 0.333 | ✅ / ✅ | ✅ / ✅ | ✅ / ✅ |
| ripple | 0.333 | ✅ / ✅ | ✅ / ✅ | ✅ / ✅ |

Die Fuß-Hülle ist gangart-unabhängig; es unterscheidet sich nur die Bodenzeit und damit
`linear_max` (Plan §7.2).

### Verworfene Budget-Quellen (mit Daten)

| Option | Messung | Verdikt |
|---|---|---|
| `cliff_depth` 0.03 → 0.02 (hoch) | sl 0.070 RED (femur 0.0787) · 0.080 RED (out_of_reach) | ~5 mm — Kantenschutz nicht wert |
| Walk-Radius 0.145 / 0.150 / 0.155 (hoch) | **alle 12 Zellen RED**, femur 0.002–0.043 | 0.160 ist das Optimum |
| Zwischen-Stance bh −0.085 / −0.090 / −0.095 mit mehr Hub | **alle 5 Zellen RED** (check + engine) | keine Kombination mit mehr Hub *und* Weite |

### Datenbasis für die optionale Ausbaustufe B3 (Plan §9)

Deckel ohne Kontakt-Suchtiefe, beide Gates:

| Stance | Floor 0.03 (= B1) | Floor 0.02 (Kanten-Freeze aus) | Floor 0 (beide Toggles aus) |
|---|---|---|---|
| tief | 0.065 | 0.065 | 0.065 |
| **mittel** | **0.085** | **0.095** | **0.100** (0.110 RED, coxa 0.084) |
| hoch | 0.055 | 0.055 | 0.055 |

---

## Erwartete Wirkung (real gefahrene Schrittweite)

| Stance | Tempo | heute | nach Phase 11 |
|---|---|---|---|
| **mittel** | **schnell (Boot)** | **50 mm @ 0.050 m/s** | **85 mm @ 0.050 m/s** |
| mittel | aggressiv | 80 mm @ 0.107 | 85 mm @ 0.100 |
| tief | schnell | 50 mm @ 0.050 | 65 mm @ 0.038 |
| hoch | schnell | 50 mm @ 0.050 | 55 mm @ 0.032 |
| hoch | aggressiv | 50 mm @ 0.067 | 55 mm @ 0.065 |

> ⚠️ In den Modi mit kleinem Deckel (tief/hoch) sinkt durch die längere Zykluszeit die
> Höchstgeschwindigkeit der unteren Tempo-Stufen (`linear_max = Deckel ÷ Bodenzeit`). Eine Stufe
> höher schalten stellt sie wieder her. Die Monotonie der Stufen bleibt in jedem Stance-Modus
> erhalten.

## HW-Messung (P11.7/P11.8 — nach Ausführung füllen)

| Stance | Tempo | Schrittweite kommandiert | gemessen | Fuß-Hub (apex_meter) | Anmerkung |
|---|---|---|---|---|---|
| mittel | schnell | 85 mm | | | |
| hoch | aggressiv | 55 mm | | | |
| tief | schnell | 65 mm | | | |

---

## Kritischer Self-Review (P11.9, nach P11.1–P11.5; final nach Sim/HW)

| Punkt | Status |
|---|---|
| **Die eigene B2b-Schwelle war falsch gewählt.** 0.8 klang plausibel — nachgerechnet hätte sie in **34 von 48** ausgelegten Betriebspunkten gewarnt (wave/tetrapod/ripple und aggressiv in tief/hoch), also genau die Alert-Flut erzeugt, die sie verhindern sollte | 🔴→✅ Schwelle **gerechnet** statt geschätzt: kleinster regulärer Faktor 0.39 (wave+schnell+hoch) → `_CLAMP_WARN_FACTOR = 0.25`. Per Test über alle 48 Punkte gepinnt (`test_no_designed_operating_point_triggers_a_clamp_warning`), inkl. Gegenrichtung („Schwelle nicht so tief, dass sie nie greift") |
| **Die Plan-Zielwerte waren nicht erreichbar** (mittel Hub 0.060, hoch Weite 0.090/0.100) — die Deckel standen bereits am geometrischen Optimum | 🔴→✅ Fallback-Treppen bis zum Ende gegangen, jede Stufe einzeln gemessen; Ergebnis +5 mm je Modus, Hub unverändert. Statt „Done" zu rationalisieren wurde die Erwartung korrigiert und der eigentliche Hebel (Tempo-Auslegung) belegt |
| `test_stance_switch` — **der** real-engine-Test — fuhr `step_length_max=0.05` fix und prüfte die per-Modus-Schrittweite damit gar nicht | 🔴→✅ Modus-Quintupel + Schrittweite mitgeführt; zusätzlich `test_mode_constants_match_production` (Sync-Pin gegen `_STANCE_MODES`), damit der Drift von damals nicht zurückkommt |
| Vier bestehende Tests hingen an den alten Defaults (`linear_max`, `dead_ticks`) | ✅ **driftfest** gemacht statt neue Zahlen einzubetonieren — sie rechnen jetzt gegen die lebenden `cycle_time`/`step_length_max`. Beim nächsten Tuning bricht dadurch nichts mehr |
| Andere Gangarten (wave/tetrapod/ripple) waren in H1/H2 scope-out | ✅ Alle 9 Zellen mit beiden Gates geprüft, alle GREEN. Die Fuß-Hülle ist gangart-unabhängig; die Swing-Phase wird durch die längere Zykluszeit sogar entspannter (wave 0.57 s statt 0.33 s) |
| Zwei Default-Quellen (`_ParamSpec` + `gait.launch.py`) — der H2-Befund | ✅ beide nachgezogen und per `ros2 launch --show-args` verifiziert; der Sim-App-Pfad (`ramp_walk`) lädt kein params_file, dort sind die Launch-Defaults die gefahrenen Werte |
| `step_length_intent_max` (0.080) wäre unter den neuen Boot-Wert gerutscht → ein „größer"-Intent hätte gesenkt | ✅ auf 0.085 nachgezogen, Invarianten-Test greift |
| **In tief/hoch sinkt die Höchstgeschwindigkeit** der unteren Tempo-Stufen (`linear_max = Deckel ÷ Bodenzeit`) — hoch bei „schnell" 0.032 statt 0.050 m/s | 🟡 bewusst + dokumentiert (Plan §1.3, teleop-README, test_commands T3.4). Monotonie der Stufen ist in jedem Stance-Modus per Test gepinnt; „aggressiv" stellt das alte Tempo wieder her. **Im Sim-Test bewerten** — falls störend, ist es reines Umparametrieren |
| **Stopp-Nachlauf wächst** auf bis zu einen halben Zyklus (~8 cm bei „schnell") | 🟡 im HW-Test T5.1 bewusst einmal zu prüfen. Der E-Stop ist davon **nicht** betroffen (Tick-Gate, sofort) |
| Alte Sim-Presets (`sim_walk` 2.0/0.050, `demo_walk`, `aggressive_walk` 1.5/0.070) tragen weiter die alte Auslegung | 🟡 vormerken — sie liegen unter allen neuen Deckeln (kein Reject) und laufen nur im Direkt-Sim-Pfad, nicht im App-/HW-Pfad. Bei Bedarf beim nächsten Anfassen mitziehen |
| Neue Test-Kopplung `hexapod_teleop` → `hexapod_gait` (nur `test_depend`) | 🟡 bewusst: die Auslegungs-Invarianten brauchen **beide** Tabellen. Mit `try/except ImportError` + `skipif` abgesichert, zur Laufzeit keine Abhängigkeit; kein Zyklus (gait kennt teleop nicht) |
| README `hexapod_gait`: `body_height −0.052` / `radial 0.27` weiterhin veraltet | 🟡 vorbestehender Drift (schon H1-/H2-🟡), nicht Phase-11-Scope — nur die angefassten Zeilen aktualisiert |
| Reject-Text der App nennt weiterhin „H2 gate" | 🟢 historisch korrekt (der Mechanismus stammt aus H2); der Wortlaut ist für die App stabil, Änderung ohne Nutzen |
| `apex_meter --window` Default (10 s) deckt bei `cycle_time` 4.0 nur ~2.5 Zyklen | ✅ Hilfetext korrigiert, test_commands ruft mit `--window 12` |
| B3 (dynamischer Deckel je Terrain-Schalter) nicht umgesetzt | 🟢 bewusst zurückgestellt (User-Entscheid), aber **mit fertiger Datenbasis** dokumentiert (Plan §9 + Messreihe oben) — später ohne Neu-Recherche entscheidbar |
| Gate-Auswertung durchgehend exit-code-basiert | OK — die H1.2-Falle trat prompt wieder auf: bei mittel Hub 0.055 meldete die Kopfzeile „GREEN" (forward), während sidestep/diagonal rot waren |

---

## Sim-Befund aus P11.6 — der Trajektorien-Vorlauf ist der größere Hebel

Beim Sim-Test (Stance mittel, sl 0.085, Gangart tripod, Tempo aggressiv, `linear_x_scale` 0.25 →
die Engine clampt permanent auf `linear_max`, die Schrittweite hängt damit allein an Deckel und
Zykluszeit) wurde über eine **feste Strecke die Zahl der Gait-Zyklen gezählt** (mittleres Bein).
Weniger Zyklen = längere reale Schritte.

**Theoretische Erwartung:** der Vortrieb pro Zyklus ist von der Zykluszeit **unabhängig**
(`v × cycle_time = 2 × step_length_max = 0.17 m`) → für dieselbe Strecke müssten es immer gleich
viele Zyklen sein. Gemessen wurde etwas anderes:

| Schrittdauer | `time_from_start_factor` | Fuß-Hub | Zyklen | relative Schrittweite |
|---|---|---|---|---|
| 4 s | 2.0 (Default) | 50 mm | 7,5 | 87 % |
| 2 s | 2.0 | 50 mm | 9,2–9,5 | ~70 % |
| 1 s | 2.0 | 50 mm | ~14 | 46 % |
| 1 s | 2.0 | **10 mm** | 14 | 46 % (**Hub ohne Einfluss**) |
| 2 s | **1.0** | 50 mm | **7,0** | **93 %** |
| 2 s | 4.0 | 50 mm | 14,4 | 45 % |
| **4 s** | **1.0** | 50 mm | **6,5** | **100 % (Bestmarke)** |

**Deutung:** `time_from_start = factor / tick_rate` ist die Zeit, die der Bein-Controller bekommt,
um den nächsten Sollpunkt zu erreichen. Ist sie größer als das Tick-Intervall (20 ms bei 50 Hz),
startet die Interpolation alle 20 ms neu, bevor der Punkt erreicht ist — die Bewegung wird
gedämpft. Der Effekt ist **proportional** (deshalb war der Fuß-Hub ohne Einfluss) und wird bei
kürzerer Zykluszeit relativ stärker. Die Messreihe folgt sehr genau einem Verzögerungsglied
erster Ordnung mit τ ≈ 0.29 s.

**Konsequenz:** der Vorlauf ist für die real gefahrene Schrittweite ein **größerer Hebel als die
Deckel** — bei 2 s hebt `factor 1.0` sie von ~70 % auf 93 %. Verworfene Zwischen-Hypothesen (mit
Daten): URDF-`joint_velocity` (2.0 rad/s) — widerlegt, weil der Fuß-Hub keinen Unterschied macht;
weiche PID-Gains — es sind gar keine konfiguriert.

⚠️ **Noch offen (HW):** Auf der echten Hardware liefert das `hexapod_hardware`-Plugin kein echtes
Positions-Feedback (Echo-State, `controllers.real.yaml`). Die Dämpfung entsteht zwar rechnerisch
im Controller und sollte deshalb auch dort auftreten — was die **Servos** mechanisch davon
umsetzen, sieht aber kein Regelkreis. Größenordnung daher **nicht** aus der Sim übertragbar.

**Deshalb ist `time_from_start_factor` ins Config-Panel aufgenommen** („Bahn-Nachführung",
1.0…4.0, Default unverändert 2.0) — damit der Wert im Feld ohne Laptop gemessen werden kann.
Ein neuer Default wird **erst nach der HW-Messung** gesetzt.
