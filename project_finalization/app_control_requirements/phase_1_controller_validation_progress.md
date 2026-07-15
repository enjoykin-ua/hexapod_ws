# Phase 1 — Controller-Validierung — Progress

> **Done-Vertrag** (CLAUDE.md §4). Bullets 1:1 aus
> [`phase_1_controller_validation_plan.md`](phase_1_controller_validation_plan.md) §3.
> Alle `[x]` = Phase 1 fertig; pro erledigtem Bullet sofort abhaken (nicht batchen).
> Self-Review + Eignungs-Fazit nach Umsetzung.
>
> **Seite:** rein App (Android). ROS-Seite in dieser Phase leer.

```
Phase 1 (Controller-Validierung):
- [x] P1.1 Web-Vorcheck (html5gamepad.com): Kishi erkannt, alle Sticks/Buttons/D-Pad/Trigger reagieren, Werte plausibel
- [x] P1.2 Android-Studio-Projekt (Kotlin, eigenes Repo hexapod_app) angelegt, baut, startet auf dem S22+
- [x] P1.3 native App listet den Kishi als Gamepad-InputDevice
- [x] P1.4 beide Analog-Sticks liefern Live-Achswerte (zentriert ~0, Voll-Ausschlag ~±1)
- [x] P1.5 alle Buttons + D-Pad + L1/R1 + L2/R2 lösen sichtbar aus
- [x] P1.6 Roh-Index-Tabelle (Achse/Button -> Android-Konstante/Keycode) notiert -> interface_contract §1 v0.2 (eingetragen)
- [x] P1.7 Trigger analog bestätigt (Stufe A + native); Passform ok (ohne Hülle getestet)
- [x] P1.8 kurze Self-Review + Eignungs-Fazit (Kishi tauglich ja/nein)
```

## Roh-Index-Tabelle (P1.6-Ergebnis — nach Ausführung füllen)

| Physisch (Kishi) | Android-Achse/Keycode | Wertebereich | PS4-Ziel (`axes[]`/`buttons[]`) |
|---|---|---|---|
| Linker Stick X | `AXIS_X` | −1..+1 | `axes[0]` `axis_lx` (Transform `−AXIS_X`) |
| Linker Stick Y | `AXIS_Y` | −1..+1 | `axes[1]` `axis_ly` (`−AXIS_Y`) |
| Rechter Stick X | `AXIS_Z` | −1..+1 | `axes[3]` `axis_rx` (`−AXIS_Z`) |
| Rechter Stick Y | `AXIS_RZ` | −1..+1 | `axes[4]` `axis_ry` (`−AXIS_RZ`) |
| D-Pad X | `AXIS_HAT_X` | −1/0/+1 | `axes[6]` `axis_dpad_x` |
| D-Pad Y | `AXIS_HAT_Y` | −1/0/+1 | `axes[7]` `axis_dpad_y` |
| A / B / X / Y | `KEYCODE_BUTTON_A/B/X/Y` | 0/1 | `buttons[0]`/`[1]`/`[3]`/`[2]` (positionsbasiert) |
| L1 / R1 | `KEYCODE_BUTTON_L1/R1` | 0/1 | `buttons[4]`/`[5]` (Slow / Dead-Man) |
| L2 / R2 | `AXIS_LTRIGGER/RTRIGGER` (analog; auch `KEYCODE_BUTTON_L2/R2`) | 0..1 | `axes[2]`/`[5]` (`1−2·t`); `buttons[6]`/`[7]` |
| Stick-Klicks L3/R3 | `KEYCODE_BUTTON_THUMBL` / `_THUMBR` | 0/1 | `buttons[11]`/`[12]` (gesendet, unbelegt) |
| Menü/Home/Share | `KEYCODE_BUTTON_START` / `_MODE` / `_SELECT` | 0/1 | `buttons[9]`/`[10]`/`[8]` |
| (Bonus) L4 / R4 | `KEYCODE_BUTTON_C` / `_Z` | 0/1 | reserviert, kein PS4-Index (spätere Erweiterung) |

> Doppelt gemeldete Trigger `AXIS_BRAKE`/`AXIS_GAS` ignoriert; nur `LTRIGGER`/`RTRIGGER`.
> Vollständige Abbildung inkl. Regeln + Phase-2-Verifikation: `interface_contract.md §1` (v0.2).

## Stufe-A-Web-Vorcheck (P1.1-Befund, html5gamepad.com @ Chrome/S22+)

- **Erkennung:** Gamepad gelistet, Vendor `0x1532` (Razer), Product `0x071b` (Kishi V2), `index 0`, `connected`. `mapping: n/a` → Web-API garantiert **keine** W3C-Standard-Reihenfolge; exakte Index-Zuordnung wird in Stufe B über Android `InputManager` gemessen, nicht angenommen.
- **Achsen:** 4 Achsen (axis 0–3). Beide Sticks erreichen in alle Richtungen **~±1 (analog)**. Ruhe-Drift ~±0.005 → unkritisch, wird von der bestehenden `joy_to_twist`-Deadzone (`ps4_usb.yaml`, D3-Reuse) geschluckt; **keine App-seitige Deadzone nötig** (App publisht roh, Roboter filtert).
- **Buttons:** B0–B16 reagieren. **L2/R2 analog 0…1** (gleitender Wert).
- **Nicht erkannt (erwartet, out-of-scope):** Kishi-Zusatztasten **L4/R4** (Razer-Nexus-Makro, keine Standard-HID-Buttons) und die **Screenshot-Taste** (Android-System-Taste). Unser Steuer-Layout (requirements §1) braucht sie nicht.
- **Fazit Stufe A:** Kishi V2 @ S22+ auf OS-Ebene als vollwertiges Gamepad lesbar → Architektur-Kern-Risiko (OS-Enumeration) entschärft. Stufe B (native App) kann die echten Android-Konstanten für die Contract-Tabelle erfassen.

## Eignungs-Fazit (P1.8)

**Kishi V2 @ S22+ = tauglich (ja).** Native App (`InputManager`) liest den Kishi vollständig:
beide Sticks analog ±1, alle Face-/Schulter-Buttons, D-Pad, L2/R2 **analog 0..1**, sogar die
Bonus-Tasten L4/R4 (`KEYCODE_BUTTON_C/Z`). Alle Achsen/Buttons, die `joy_to_twist` konsumiert,
sind belegbar → die `/joy`-Emulation ([D3]) ist tragfähig. Roh→PS4-Abbildung vollständig
abgeleitet und in `interface_contract.md §1` (v0.2) festgezurrt.

**Auffälligkeiten / vorgemerkt:**
- Sticks liefern hoch/links = −1 → in der App negieren (PS4-`/joy` erwartet +1). Vorzeichen in
  Phase 2 gegen `ros2 topic echo /joy` final bestätigen (Fallback: `sign_*`-Params).
- Trigger idle = 0 → Formel `1−2·t` **jeden Frame** anwenden (idle → +1), sonst Fehl-Stance beim Start.
- Kishi V2 **hat** Stick-Klicks L3/R3 (`KEYCODE_BUTTON_THUMBL`/`_THUMBR`, per App verifiziert) →
  `buttons[11]/[12]` (gesendet, aktuell unbelegt). Korrigiert die Erst-Annahme des Deliverables.
