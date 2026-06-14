# Stage F1 — Test-Anleitung (servo2040 FW: Schalter → Bit 7)

> Plan: [`F1_fw_switch_bit_plan.md`](F1_fw_switch_bit_plan.md). **Kein ROS** — reiner
> FW-Bench-Test am Servo2040 über USB-CDC. Alle Befehle laufen im Repo
> `~/hexapod_servo_driver`. User führt aus, knappe Status-Rückmeldung genügt.

## Voraussetzungen

- Schalter verdrahtet: **Pin 1 → 3.3 V, Pin 2 → A1 (GP27)** (interner Pull-Down).
- Board am USB. Robot-Servos egal (Relay bleibt aus, nichts bewegt sich).
- FW mit der F1-Erweiterung gebaut + geflasht (s. u.).

## 0 — Bauen & Flashen

```bash
cd ~/hexapod_servo_driver
( cd build && make -j"$(nproc)" )
python3 tools/flash_and_verify.py
```

Erwartung: `=== OK FLASH+VERIFY successful ===`. Danach läuft die FW; die LED zeigt
den Schalter-Rohpegel (zu=grün / auf=rot).

## Hilfs-Kommando — `flags`-Spalte live mitschreiben

`log_state.py` pollt `GET_STATE` und schreibt eine CSV; Spalte 4 ist `flags`
(status_flags als Hex). **Bit 7 = `…80`** = SHUTDOWN_REQUEST.

Terminal A (Logger, 10 Hz, 25 s):
```bash
cd ~/hexapod_servo_driver
python3 tools/log_state.py /dev/ttyACM0 --rate 10 --duration 25 --out /tmp/f1.csv
```

Terminal B (nur t_s + flags ansehen, während/nach dem Lauf):
```bash
cut -d, -f1,4 /tmp/f1.csv
```

(`flags=0x10` o. ä. = nur ANY_SERVO_DISABLED etc. → Bit 7 NICHT gesetzt.
`flags=0x90` / jeder Wert mit gesetztem `0x80` → Bit 7 gesetzt.)

---

## F1-T1 — LED-Regression
Schalter mehrfach zu/auf legen.
**Erwartung:** zu → grün, auf → rot (unverändert zum Wiring-Test).

## F1-T2 — Arm-Guard: Boot mit offenem Schalter
1. Schalter **offen** lassen (rot).
2. Board neu booten (USB ab/an **oder** `sudo picotool reboot -f -a`).
3. Logger starten, **>3 s** nicht anfassen:
```bash
python3 tools/log_state.py /dev/ttyACM0 --rate 10 --duration 8 --out /tmp/f1_t2.csv
cut -d, -f1,4 /tmp/f1_t2.csv
```
**Erwartung:** `flags` zeigt **nie** ein gesetztes `0x80` — trotz >3 s offen. (Arm
fehlt, weil seit Boot nie „zu" gesehen.)

## F1-T3 — 3-s-Halten (Kern)
1. Logger 25 s starten (Terminal A, s. o. `/tmp/f1.csv`).
2. Schalter **zu** (grün) → kurz warten → Schalter **auf** (rot) und **offen lassen**.
3. Nach dem Lauf:
```bash
cut -d, -f1,4 /tmp/f1.csv
```
**Erwartung:** ab „auf" bleibt `flags` ohne `0x80` für **< 3 s**, dann kippt es bei
**~3 s** auf einen Wert **mit `0x80`** (z. B. `0x80`/`0x90`) und bleibt so.

## F1-T4 — Fehlauslöse-Schutz (auf < 3 s)
1. Logger 12 s starten.
2. Schalter **zu** → **auf** → nach **~1–2 s wieder zu** (vor Ablauf der 3 s).
```bash
python3 tools/log_state.py /dev/ttyACM0 --rate 10 --duration 12 --out /tmp/f1_t4.csv
cut -d, -f1,4 /tmp/f1_t4.csv
```
**Erwartung:** `0x80` wird **nie** gesetzt.

## F1-T5 — Storno (track-level)
1. Erst F1-T3 wiederholen, bis Bit 7 gesetzt ist (`0x80` sichtbar).
2. Dann Schalter **wieder zu** (grün), Logger weiterlaufen lassen.
```bash
python3 tools/log_state.py /dev/ttyACM0 --rate 10 --duration 12 --out /tmp/f1_t5.csv
cut -d, -f1,4 /tmp/f1_t5.csv
```
**Erwartung:** sobald „zu", verschwindet `0x80` wieder aus `flags`.

---

## Erfolgs-Kriterium F1
T1–T5 wie erwartet **und** Build grün → Progress-Checkliste F1.1–F1.7 abhaken,
dann Self-Review (Plan §3, F1.9). F1.8 (PROTOCOL.md) parallel.
