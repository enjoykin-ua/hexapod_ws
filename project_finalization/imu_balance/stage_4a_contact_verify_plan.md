# Stufe 4 / S4-1 — Fußkontakt-Consumer + Verifikation

> Erste Teil-Stufe von [Stufe 4 Terrain-adaptiv](stage_4_terrain_adaptive_plan.md) (Block A5).
> **Ziel:** den vorhandenen Fußkontakt-`Bool` im gait_node **konsumieren** (abonnieren + cachen +
> Debug-Sicht) und **rigoros verifizieren**, dass das Signal für den adaptiven Touchdown (S4-2)
> taugt — **kein Verhaltens-Change**. De-risked das Signal, bevor Verhalten darauf gebaut wird.
>
> **Status: ⚪ offen — Plan zum Review.** §4-Workflow: Plan → **User-Freigabe** → Code → Test →
> Self-Review. Methode der Stufe = **fixed-timing** (Umbrella §0.5). Nachfolge: **S4-2** (adaptiver
> Touchdown).

---

## 0. Kontext & Abgrenzung

- Die Pipeline existiert vollständig (Umbrella §0): `/leg_<n>/foot_contact` (`std_msgs/Bool`, 50 Hz)
  läuft per Default. **S4-1 baut nur den Consumer + die Verifikation** — keine Gait-Änderung.
- **Warum Verifikation kein Selbstläufer ist** (dokumentiert, [phase_5_gait_explained.md](../../docs/phase_5_gait_explained.md)):
  JTC hängt ~0.5–1 mm hinterm Ziel → Fuß schwebt knapp über Boden → Sensor feuert unzuverlässig;
  „bei zu schnellem Cycle weniger zuverlässig". **Hebel 1 (langsamer laufen) ist ausgeschlossen**
  (HW soll schneller, bis 2×) → wir müssen wissen, ob das Signal bei normalem/schnellem Cycle trägt,
  **bevor** S4-2 darauf baut.

## 1. Logik-Skizze

### 1.1 Kontakt-Consumer (gait_node)
- 6 Subscriber auf `/leg_${id}/foot_contact` (`Bool`, QoS 10) → State in `self._foot_contact[id]`
  (Default `False`). Ohne Pipeline (kein Topic) bleiben alle `False` → graceful (wie ohne IMU).

### 1.2 Per-Bein-Swing-Phase read-only aus der Engine
- Kleine **read-only** Engine-Methode `leg_gait_states() -> {leg_id: (is_swing, local_phase)}`,
  die die ohnehin in `compute_joint_angles` (WALKING-Pfad, ~Z.646–674) berechnete per-Bein-Phase
  zurückgibt (`cycle_phase < swing_duty` → swing). **Reuse:** S4-2 (late-swing erkennen) + S4-5
  (Plausibilität) brauchen das auch. Nur Lesezugriff, kein Verhaltens-Change.

### 1.3 Diagnose (das Herz der Verifikation, ROS-frei testbar)
- Eine kleine **ROS-freie** Helfer-Logik `ContactDiagnostic` (wie `tip_monitor`): bekommt pro Tick
  pro Bein `(contact, is_swing, local_phase)` und zählt:
  - **steigende Flanke** (Touchdown): bei welcher `local_phase` wird `contact` erstmals true?
    → **Latenz** gegen den erwarteten Touchdown (Swing-Ende, local_phase→1) bzw. Stance-Start.
  - **implausibel-Swing-Apex:** `contact==true` um den Apex (local_phase≈0.5 im Swing) → Fehlkontakt.
  - **implausibel-Stance-fehlt:** `contact==false` in der Stance-Mitte (belastetes Bein) → Aussetzer.
  - true/false-Quote pro Bein über ein Fenster.
- **S4-1 reagiert NICHT** darauf — es **misst/loggt** nur (die Reaktion = S4-5). Das macht die
  Verifikation **quantitativ** statt „sieht ok aus".

### 1.4 Debug-Ausgabe
- Throttled Log (z.B. 1 Hz): 6-Bool-Muster + die Diagnose-Zähler pro Bein.
- Optional ein kompaktes Topic `/foot_contacts` (`Bool[6]` als `Float64MultiArray` 0/1 oder
  `std_msgs/ByteMultiArray`) für `ros2 topic echo` / spätere Viz (offener Punkt 4.1).
- Param `foot_contact_debug_enable` (Default **true** für diese Stufe; in S4-2+ ggf. aus).

### 1.5 Was S4-1 NICHT tut
- **Keine** Touchdown-Modulation, **keine** Gait-Beeinflussung, **keine** Reaktion auf
  Implausibilität. Reiner Consumer + Messung.

## 2. Tests-Liste (mit Begründung)

| Test | Prüft | Done-Idee |
|---|---|---|
| **Unit: ContactDiagnostic** | steigende/fallende Flanke, Apex-Fehlkontakt, Stance-Aussetzer, Quoten — bei konstruierten (contact, is_swing, phase)-Sequenzen | ROS-frei, deterministisch |
| **Unit: leg_gait_states** | gibt die per-Bein (is_swing, local_phase) konsistent zur swing/stance-Berechnung zurück | white-box gegen swing_duty-Grenze |
| **Node-Smoke** | 6 Subscriber verdrahtet, Cache updatet, Diagnose tickt, kein Crash, Param live | rclpy |
| colcon + Lint | alle bestehenden + neue grün | 0 Fehler |
| **Sim (User) — Verifikations-Matrix** | **flach + Hang (8°)** × **cycle_time {2.0, 1.0}** × **step_height {0.04, 0.06}**: feuert Kontakt in Stance, still im Swing-Apex? Latenz (steigende Flanke) ≤ ~2 Ticks? Quote/Aussetzer pro Bein? | `/leg_<n>/foot_contact`-Echo + Diagnose-Log |

**Bewusst NICHT getestet (→ spätere Teil-Stufen):**
- Adaptiver Touchdown (Senken bis Kontakt) → **S4-2**.
- Reaktion auf Implausibilität / Sensor-Fault → **S4-5** (S4-1 misst nur).
- Slip / Kontaktverlust (fallende Flanke, `contact_timeout`-Latenz) → **S4-4**.
- Stufen-/Buckel-Welten → **S4-6** (S4-1 nutzt flach + bestehende Hang/Knick-Welt).

## 3. Progress-Checkliste (→ Progress-File, Done-Vertrag)

```
S4-1:
- [ ] S4-1.1 gait_node: 6 Subscriber /leg_<n>/foot_contact (Bool) + State-Cache (graceful ohne Pipeline)
- [ ] S4-1.2 Engine read-only leg_gait_states() (per-Bein is_swing + local_phase), kein Verhaltens-Change
- [ ] S4-1.3 ContactDiagnostic (ROS-frei): Flanken/Latenz/Apex-Fehlkontakt/Stance-Aussetzer/Quote
- [ ] S4-1.4 Debug-Log (throttled) + optional /foot_contacts-Topic; Param foot_contact_debug_enable (live)
- [ ] S4-1.5 Unit-Tests (ContactDiagnostic, leg_gait_states) + Node-Smoke
- [ ] S4-1.6 colcon test + Lint grün
- [ ] S4-1.7 README/Konzept (hexapod_gait: Kontakt-Consumer + Diagnose; Pipeline-Verweis)
- [ ] S4-1.8 Test-Doku stage_4a_contact_verify_test_commands.md (Verifikations-Matrix flach+Hang × cycle × step) + Sim-Verify durch User
- [ ] S4-1.9 kritische Self-Review-Tabelle (OK/🔴/🟡/🟢)
```

## 4. Offene Punkte für User-Review (vor Code)

1. **Debug-Ausgabe-Form:** reicht ein **throttled Log** der Diagnose, oder zusätzlich ein
   **`/foot_contacts`-Topic** (für `ros2 topic echo` / spätere Viz)? Vorschlag: **beides** (Topic
   ist klein und in der HW-Phase eh nützlich fürs UI).
2. **Latenz-Akzeptanzschwelle:** ab wann gilt das Signal als „gut genug" für S4-2? Vorschlag:
   **steigende Flanke ≤ 2 Ticks** (40 ms) nach Boden-Berührung **und** keine systematischen
   Apex-Fehlkontakte. Bestätigen / anpassen.
3. **Verifikations-Matrix-Umfang:** flach + Hang × cycle {2.0, 1.0} × step {0.04, 0.06} (= 8 Läufe)
   — reicht das, oder gröber/feiner? Vorschlag: so (deckt die „schneller-Cycle"-Schwäche ab).
4. **Falls die Verifikation Probleme zeigt:** Hebel 2 (`contact_timeout`) / Hebel 3
   (Touchdown-Offset, erst in S4-2 relevant) gemäß Umbrella §3 — bestätigt. Hebel 4 (Geometrie)
   nur als separater Punkt. (Reine Bestätigung, schon entschieden.)

## 5. Design-Entscheidungen (mit Alternativen)

| Entscheidung | Gewählt | Verworfen / Alternative | Warum |
|---|---|---|---|
| S4-1-Umfang | **Subscriber + Diagnose im gait_node** | reine `topic echo`-Verifikation ohne Code | Subscriber wird in S4-2 eh gebraucht → kein Wegwerf-Code; Diagnose macht Verifikation quantitativ |
| Diagnose-Ort | **ROS-frei (`ContactDiagnostic`)** | inline im Node | unit-testbar wie `tip_monitor`; Plausibilitäts-Kern für S4-5 wiederverwendbar |
| Reaktion | **keine — nur messen** | gleich auf Implausibilität reagieren | S4-1 = de-risken/messen; Reaktion erst S4-5 (klare Stufung) |
| Engine-Phase | **read-only exponieren** | im Node nachrechnen | Single Source of Truth (Engine rechnet die Phase eh); reuse S4-2/S4-5 |
| Latenz-Befund-Erwartung | **steigende Flanke ~1–2 Ticks** | — | gz 50 Hz + Publisher 50 Hz; `contact_timeout` betrifft nur fallende Flanke (S4-4) |
