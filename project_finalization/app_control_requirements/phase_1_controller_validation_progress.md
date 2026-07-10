# Phase 1 — Controller-Validierung — Progress

> **Done-Vertrag** (CLAUDE.md §4). Bullets 1:1 aus
> [`phase_1_controller_validation_plan.md`](phase_1_controller_validation_plan.md) §3.
> Alle `[x]` = Phase 1 fertig; pro erledigtem Bullet sofort abhaken (nicht batchen).
> Self-Review + Eignungs-Fazit nach Umsetzung.
>
> **Seite:** rein App (Android). ROS-Seite in dieser Phase leer.

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

## Roh-Index-Tabelle (P1.6-Ergebnis — nach Ausführung füllen)

| Physisch (Kishi) | Android-Achse/Keycode | Wertebereich | PS4-Ziel (Phase 2) |
|---|---|---|---|
| Linker Stick X | | | |
| Linker Stick Y | | | |
| Rechter Stick X | | | |
| Rechter Stick Y | | | |
| D-Pad X | | | |
| D-Pad Y | | | |
| A / B / X / Y | | | |
| L1 / R1 | | | |
| L2 / R2 | | | |
| Stick-Klicks L3/R3 | | | |
| Menü/Home/Share | | | |

## Eignungs-Fazit (P1.8 — nach Ausführung)

_(Kishi V2 @ S22+ tauglich ja/nein? Trigger analog/digital? Passform mit Hülle? Auffälligkeiten?)_
