# Phase 7 Stage D — Test-Anleitung: Per-Servo-Enable

**Vorbedingung:** Stage-C-Tests grün, Firmware `vC.3` auf dem Servo2040 geflasht.

---

## Hardware-Setup

1. **Servo2040** per USB am Desktop (`/dev/ttyACM0`).
2. **Bench-PSU** an den Servo-Rail des Servo2040 (GND + V+):
   - **Spannung:** `6,0 V` (MG996R: Betriebsbereich 4,8–7,2 V)
   - **Current-Limit:** `3,0 A` (MG996R: ~500 mA Leerlauf je Servo,
     2,5 A Stall je Servo — 3 A schützt bei simultaner Blockade beider)
   - PSU erst einschalten, dann Test starten — Servos kommen von allein
     in Neutralposition sobald das Skript ENABLE_SERVO schickt.
3. **2× MG996R** an die Ausgänge **0** und **1** des Servo2040 stecken
   (die ersten zwei Schraubklemmen-Positionen, Signal + Power).

> **Sicherheit:** Roboter ist nicht angeschlossen, nur lose Test-Servos auf dem Tisch.
> Hardware-Kill-Switch (PSU-Off) griffbereit.

---

## Befehle

```bash
cd ~/hexapod_servo_driver

# Firmware ist schon geflasht — nur prüfen ob Board sichtbar ist
ls /dev/ttyACM*          # sollte ttyACM0 zeigen

# Alle Stage-C + Stage-D Tests mit 3 angeschlossenen Servos
python3 tools/test_servo2040.py --servos 3

# Alternativ, wenn du nur 2 Test-Servos hast:
python3 tools/test_servo2040.py --servos 2
```

---

## Erwarteter Output

```
=== Servo2040 stage-C + stage-D (3 servo(s)) tests on /dev/ttyACM0 ===

[..] C.1 hard-clamp: out-of-range pulses are clamped to min/max
[OK] all 18 servos clamped to 500 µs (min)
[OK] all 18 servos clamped to 2500 µs (max)
[..] C.2 watchdog: stall triggers trip + RESET recovers
     stalling 350ms to trigger watchdog…
[OK] unsolicited ERROR_REPORT received
[OK] status flags = 0x11 (WATCHDOG_TRIPPED + ANY_SERVO_DISABLED)
[OK] ENABLE_SERVO during trip is correctly NACKed
[OK] after RESET status = 0x10 (trip cleared)
[..] C.3 soft-ramp: target jump is rate-limited
[OK] after 100 ms: pulses ≈ 1700 µs (NOT immediately 2500)
[OK] after full ramp: pulses = 2500 µs

[..] D.1 per-servo-enable: staged boot for 3 servo(s) on outputs 0..2
     PHYSICAL OBSERVATION: servos should engage one by one, ~50 ms apart
[OK] servo 0: enabled (ACK received)
[OK] servo 1: enabled (ACK received)
[OK] servo 2: enabled (ACK received)
[OK] state flags = 0x10 (correct for 3/18 enabled)
[OK] enabled servos at target: [1800, 1800, 1800] µs
[OK] all 3 servo(s) returned to neutral and disabled

=== OK ALL STAGE-C + STAGE-D (3 SERVO(S)) TESTS PASSED in 8.3s ===
```

---

## Was physisch zu beobachten ist

| Was | Erwartetes Verhalten |
|---|---|
| Servo 0 | Springt auf Neutralposition (~1500 µs) **zuerst** |
| Servo 1 | Springt ~50 ms **nach** Servo 0 |
| Servo 2 | Springt ~50 ms **nach** Servo 1 |
| PSU Ammeter | 3 getrennte kleine Inrush-Spitzen, nicht ein gemeinsamer Peak |
| Bewegungstest | Alle 3 Servos fahren auf 1800 µs (Rampe ~150 ms) |
| Rückkehr | Alle 3 zurück auf 1500 µs, dann stromlos |

---

## Ergebnis eintragen

Nach erfolgreichem Test in `docs_raspi/phase_7_progress.md` die D.1-Bullet
auf `[x]` setzen und den Pfad-Entscheid (`ServoCluster per-servo enable, D.1`)
dokumentieren.
