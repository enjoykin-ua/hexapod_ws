# Stufe 4 — Terrain-adaptive Lokomotion (Weg B + Fußkontakte)

> Stufe 4 von Block A5 ([Master](00_imu_balance_plan.md)). **Ziel:** **irreguläres**
> Terrain (Buckel, Stufen, lose Erde) — per-Fuß kontakt-getriggertes Aufsetzen,
> Online-Adaption. Das ist die **Forschungs-grade** Stufe; sie braucht die
> **Fußkontakte** (Block E2) und steht **weit hinten**.
>
> **Status: ⚪ offen — grobe Skizze.** Wird erst nach Stufe 3 + verfügbaren
> Fußkontakten konkret ausgeplant. Hier nur Richtung + offene Fragen, damit das
> Gesamtbild steht.
>
> **Abhängigkeiten:** Stufe 3 (🟢 nötig) · **E2 Fußkontakt-Sensorik** (gz-contact
> in Sim existiert schon; HW-Taster verbaut + verkabelt) · A/B-Entscheidung aus
> Stufe 3.

---

## 0. Kontext & Abgrenzung

- **IMU misst die Körperlage, Taster messen, wo der Boden wirklich ist** — zwei
  verschiedene Probleme (Master §1). Für *glatte* Hänge trägt die IMU (Stufe 2/3);
  für *unvorhersehbares* Terrain braucht es per-Fuß-Kontakt (diese Stufe).
- Die Fußkontakt-Pipeline existiert in Sim bereits vollständig
  (`hexapod.foot_contact.xacro` → Bridge → `foot_contact_publisher` → `Bool` auf
  `/leg_<n>/foot_contact`). Ab jetzt kann sie **passiv mitlaufen** (loggen/viz);
  hier wird sie zum **aktiven Consumer**.

## 1. Logik-Skizze (grob)

### A. Fußkontakt-Consumer
- vorhandenes `/leg_<n>/foot_contact` (Bool; Sim gz-contact, HW Taster) →
  **adaptiver Touchdown:** Schwung-Fuß senken **bis Kontakt** (innerhalb der
  Envelope-Grenze), statt auf feste Höhe. Boden höher → früher Stance; tiefer →
  weiter senken bis Kontakt.

### B. Per-Fuß-Terrain-Adaption
- jeder Fuß landet auf seiner echten Bodenhöhe; die Körper-Pose passt sich an das
  per-Fuß-Höhenprofil an (nicht durch eine einzelne Kippung beschreibbar).

### C. Weg-B Online-Planung (falls in Stufe 3 gewählt)
- Parameter bei Terrain-Änderung neu planen + **Live-Feasibility** (IK/CoG) prüfen,
  **amortisiert** (nicht jeden Tick; Echtzeit-Budget Pi 5 @ 50 Hz).

### D. Slip / Kontaktverlust
- Stance-Fuß verliert Kontakt (gerutscht / über Kante) → reagieren (Schritt
  nachsetzen / stoppen). Kombiniert mit der Slip-Erkennung aus Stufe 3.

### E. Fuß-Schalter-Fail-Safe (Brainstorm-Inhalt)
- **NO vs. NC** ist die kleinere Frage; der eigentliche Schutz ist der
  **Plausibilitätscheck gegen die Gait-Phase**: Kontakt im Swing-Apex oder fehlend
  bei belastetem Stance-Bein = **implausibel** → Sensor als defekt flaggen, für das
  Bein auf den **Open-Loop-Zeitplan** zurückfallen + warnen.
- **Taster = Optimierung, nie load-bearing:** Basis-Lokomotion läuft immer auf dem
  Zeit-Gait; Kontakt verbessert nur das Aufsetzen.

### F. Welten
- **irreguläres / Heightmap-Terrain** in Sim (Buckel, Stufen). Aufbauend auf den
  Schräg-/Rampen-Welten aus Stufe 2/3.

## 2. Tests-Liste (Skizze)

| Test | Prüft |
|---|---|
| Unit | Kontakt-Consumer (Touchdown-Logik, Entprellung), Plausibilitäts-Logik (Phase-Cross-Check) |
| Sim | Buckel-/Heightmap-Terrain: adaptiver Touchdown, kein Stub/Sacken, Schlupf-Reaktion |
| HW | mit verbauten Tastern; NO/NC + Fail-Safe real |

## 3. Progress-Checkliste (grob — verfeinert bei der echten Planung)

```
- [ ] 4.1 Fußkontakt-Consumer: adaptiver Touchdown (senken bis Kontakt, Envelope-Grenze)
- [ ] 4.2 Plausibilitätscheck gegen Gait-Phase + Fallback auf Open-Loop (Sensor-Fault)
- [ ] 4.3 Per-Fuß-Terrain-Adaption der Körper-Pose
- [ ] 4.4 (falls Weg B) Online-Planung + Live-Feasibility, amortisiert
- [ ] 4.5 Slip/Kontaktverlust-Reaktion
- [ ] 4.6 Irreguläre/Heightmap-Welten
- [ ] 4.7 HW: Taster NO/NC + Fail-Safe verifiziert
- [ ] 4.8 README/Konzept + colcon test/Lint + Self-Review
```

## 4. Offene Punkte (viel — Forschung)

- **A/B/Hybrid** (in Stufe 3 entschieden) — bestimmt 4.4.
- **Fuß-Schalter HW:** NO vs. NC + Fail-Safe-Plausibilität (Brainstorm); Entprellung;
  Schutz gegen Dauer-„betätigt" durch Dreck.
- **Touchdown-Algorithmus:** Senk-Rate, Envelope-Grenze, Kontakt-Entprellung.
- **Echtzeit-Budget** für Online-Planung (Pi 5, 50 Hz) — amortisieren.
- **Heightmap/irreguläre Welt-Modellierung** in gz Harmonic.
- **A4 (Selbst-Kollision)** verschärft sich (große Bein-Exkursionen auf Terrain).
- **Abhängig von E2** (Taster verkabelt) + HW-Inbetriebnahme.

## 5. Design-Entscheidungen (vorläufig)

| Entscheidung | Gewählt (Vorschlag) | Warum |
|---|---|---|
| Kontakt-Rolle | Optimierung, **nicht** load-bearing | Basis-Gait bleibt immer gültiger Fallback (E2: „flach kein Gewinn") |
| Sensor-Fault-Schutz | **Plausibilitätscheck gegen Gait-Phase** (+ NO/NC) | fängt Kabelbruch UND Dreck-Dauerkontakt; NO/NC biast nur einen Fehlermodus |
| Sim-Pipeline | vorhandene gz-contact-Kette (ab Stufe 0 passiv mitlaufen lassen) | sim/HW-identischer `Bool`-Topic, Consumer-Logik gleich |
