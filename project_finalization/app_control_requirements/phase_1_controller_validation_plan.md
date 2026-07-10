# Phase 1 — Controller-Validierung (Kishi Hello-World)

> **§4-Plan.** Ziel: **beweisen, dass Android den Razer Kishi V2 als Gamepad lesen kann** —
> die Grundlage für die native App ([D1](decisions.md)). Reine Input-Validierung, **kein
> ROS, kein Netz**. Erst der Zero-Code-Vorcheck, dann eine minimale native App.
>
> **Seite:** App (Android) — die ROS-Seite ist in dieser Phase **leer**.
> **Status: 🟡 Plan.** Master: [`00_overview.md`](00_overview.md).

---

## 0. Warum diese Phase zuerst

Die gesamte Architektur steht und fällt damit, dass das Handy den Kishi als **Standard-HID-
Gamepad** sieht (dann funktioniert `InputManager` nativ und später die `/joy`-Emulation).
Das ist die **billigste De-Risk-Maßnahme** — bevor irgendein rosbridge-/App-Gerüst gebaut
wird. Nebenprodukt: die **Kishi-Roh-Indizes** (welche Achse/welcher Button hat welche
Nummer), die Phase 2 für die `/joy`-Normalisierung ([interface_contract §1](interface_contract.md))
braucht.

## 1. Logik-Skizze / Vorgehen

**Stufe A — Zero-Code-Vorcheck (5 Minuten):**
- S22+ in den Kishi (USB-C), Chrome öffnen → Gamepad-Test-Seite (`html5gamepad.com` o. ä.).
- Prüfen: wird ein Gamepad **erkannt**? Reagieren **alle** Sticks/Buttons/D-Pad/Schulter-/
  Trigger-Tasten? Werte plausibel (Sticks −1..+1, Buttons 0/1)?
- Das beweist auf OS-Ebene, dass Android den Kishi als Gamepad enumeriert (die Web-Gamepad-
  API und die native `InputManager`-Seite sitzen auf derselben OS-Erkennung).

**Stufe B — Minimale native App (das eigentliche Hello-World):**
- Neues Android-Studio-Projekt (Kotlin), **eigenes Repo** (z. B. `hexapod_app`), leere
  Single-Activity.
- Gamepad lesen über die Standard-APIs:
  - `InputDevice`/`InputManager` → verbundene Gamepads auflisten.
  - `onGenericMotionEvent(MotionEvent)` → Achsen (`AXIS_X/Y/Z/RZ/HAT_X/HAT_Y/LTRIGGER/RTRIGGER…`).
  - `onKeyDown/onKeyUp(KeyEvent)` → Buttons (`KEYCODE_BUTTON_A/B/X/Y/L1/R1/…`).
- **UI:** simpel — je Achse ein Live-Wert (Text/Balken), je Button ein Indikator. Keine
  Schönheit, nur Sichtbarkeit.
- **Roh-Index-Erfassung:** die App zeigt zu jeder Eingabe die **Android-Achsen-Konstante /
  Keycode** an → daraus die Kishi→PS4-Abbildung für Phase 2 notieren.

**Bewusst NICHT in Phase 1:** kein rosbridge, kein `/joy`, kein Netz, keine Steuerung, keine
Video-/Touch-UI, kein Controller-Profil-System (nur Roh-Indizes notieren). Das kommt ab
Phase 2/8.

## 2. Tests-Liste (mit Begründung)

| Test | Prüft | Warum |
|---|---|---|
| **T1.A** Web-Vorcheck: Gamepad erkannt, alle Eingaben reagieren | OS-Enumeration des Kishi | billigster Machbarkeits-Beweis, vor jedem Code |
| **T1.B** native App listet den Kishi als `InputDevice` (Gamepad) | native Erkennung | `InputManager`-Weg trägt |
| **T1.C** beide Sticks liefern Live-Achswerte (−1..+1, zentriert ~0) | Analog-Achsen | Fahren/Drehen später |
| **T1.D** alle Buttons + D-Pad + Schulter/Trigger lösen aus | Vollständigkeit | Dead-Man/Sit-Stand/Stance/Gait brauchen sie |
| **T1.E** Roh-Index-Tabelle (Achse/Button → Android-Konstante) notiert | Phase-2-Input | die `/joy`-Normalisierung braucht sie |

**Bewusst offen / später:** Trigger analog vs. digital (nur **notieren**, unkritisch da wir
sie als Buttons nutzen); Latenz-Messung (Phase 2, im echten Steuer-Kontext); Passform mit
Hülle (mechanisch, User).

## 3. Progress-Checkliste (→ [`phase_1_..._progress.md`](phase_1_controller_validation_progress.md), Done-Vertrag)

```
Phase 1 (Controller-Validierung):
- [ ] P1.1 Web-Vorcheck (html5gamepad.com): Kishi erkannt, alle Sticks/Buttons/D-Pad/Trigger reagieren, Werte plausibel
- [ ] P1.2 Android-Studio-Projekt (Kotlin, eigenes Repo hexapod_app) angelegt, baut, startet auf dem S22+
- [ ] P1.3 native App listet den Kishi als Gamepad-InputDevice
- [ ] P1.4 beide Analog-Sticks liefern Live-Achswerte (zentriert ~0, Voll-Ausschlag ~±1)
- [ ] P1.5 alle Buttons + D-Pad + L1/R1 + L2/R2 lösen sichtbar aus
- [ ] P1.6 Roh-Index-Tabelle (Achse/Button -> Android-Konstante/Keycode) notiert -> interface_contract Phase-2-Input
- [ ] P1.7 Trigger analog-oder-digital notiert (unkritisch); Passform mit Huelle geprueft (mechanisch)
- [ ] P1.8 kurze Self-Review + Eignungs-Fazit (Kishi tauglich ja/nein)
```

## 4. Offene Punkte / Risiken

1. **Kishi wird nicht als Gamepad erkannt** (unwahrscheinlich, aber der ganze Sinn des
   Vorchecks): dann Fallback prüfen (anderer USB-Modus am Kishi? anderes Handy S26+?),
   ggf. Architektur-Re-Eval. **Deshalb Stufe A vor jeglichem Code.**
2. **Trigger digital:** falls L2/R2 nur 0/1 liefern — für uns ok (wir nutzen sie als
   Buttons), nur dokumentieren.
3. **Android-Achsen-Mapping variiert** je nach Controller-Firmware/Android-Version — genau
   deshalb erfassen wir die **Roh-Indizes** statt sie anzunehmen.
4. **Passform S22+ mit Hülle** — rein mechanisch, User verifiziert.

## 5. App-Seite vs. ROS-Seite

- **App-Seite (Android-Repo):** alles (Projekt-Setup, Gamepad-Read, Anzeige). Erste Zeilen
  des `hexapod_app`-Repos entstehen hier.
- **ROS-Seite (hexapod_ws):** **nichts** in dieser Phase.
- **Contract:** liefert Input (Roh-Indizes) für Phase 2, ändert den Contract selbst noch
  nicht (nur Vormerkung `[TBD-Phase 2]`).

## 6. Doku-Nachzug (nach Umsetzung)
- `phase_1_..._progress.md` abhaken + Eignungs-Fazit.
- Roh-Index-Tabelle → [`interface_contract.md`](interface_contract.md) §1 (als Phase-2-Vorbereitung).
- `hexapod_app`-Repo: dünnes README (Build/Run) + Zeiger auf diese Doku.
