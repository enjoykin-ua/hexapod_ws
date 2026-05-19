# Phase 10 — Stufe I — Phase-10-Abschluss-Plan

> **Status:** Plan, in Implementierung.
>
> **Parent-Plan:** [`phase_10_single_leg.md`](phase_10_single_leg.md)
> Stufe I — Phase-10-Abschluss.
>
> **Vorbedingung:** Stages A–G komplett, alle 3 leg_6-Servos kalibriert,
> Tibia-Länge im URDF korrigiert, IK-Pipeline + gait_node-Walking
> verifiziert.

---

## Ziel

Phase 10 sauber abschließen:

1. **`servo_mapping.yaml`**: Pin 15/16/17 mit `status: calibrated` +
   `calibrated_at: <ISO>` (per-Eintrag, Top-Level bleibt `placeholder`)
2. **README** in `hexapod_hardware`: Phase-10-Quick-Start-Snippet
   ergänzen mit leg_6-Verifikations-Status
3. **PHASE.md**: Phase 10 → 🟢 abgeschlossen, Phase 11 (Param-GUI) → 🟡 aktiv,
   kurze Phase-10-Retro
4. **`phase_10_progress.md`**: Stage-I-Bullets, Phase-10-Retrospektive,
   Phasenabschluss-Checkliste komplett abgehakt
5. **User-Git-Aktion** (durch User selbst, nicht von mir):
   - Commit der Stage-I-Files
   - Tag `phase-10-done`
   - Optional: Phase-Wechsel-Hinweis im Commit

---

## Logik-Skizze

### I.1 — `servo_mapping.yaml` Pin 15/16/17 status-Felder (~5 min)

Pro Pin per-Eintrag-Field:
```yaml
15:
  joint: leg_6_coxa_joint
  status: calibrated
  calibrated_at: "2026-05-17"
  pulse_min:  1280
  pulse_zero: 1550
  pulse_max:  1860
  direction:  -1
```

Top-Level `status: placeholder` bleibt unverändert (15 andere Pins
sind weiter nicht kalibriert, kommen in Phase 13).

### I.2 — README hexapod_hardware Phase-10-Quick-Start (~10 min)

In `src/hexapod_hardware/README.md` (am Ende oder in eigener Sektion):

- Phase-10-Status: leg_6 (Pin 15/16/17) kalibriert
- Bench-Setup-Snippet (PSU 7.0 V / 8 A, alle 3 Servos)
- IK-Probe-Skript-Verweis (`tools/phase_10_f2_ik_probe.py`)
- gait_node HW-Args (`body_height:=-0.047 use_sim_time:=false`)
- cmd_vel-pub mit `--rate 10`
- Cross-Phase-Pendenz-Liste (Memory-Verweise)

### I.3 — PHASE.md updaten (~5 min)

- Phase 10 Status von 🟡 aktiv auf 🟢 abgeschlossen
- Phase 11 (Param-GUI) Status von ⚪ offen auf 🟡 aktiv
- Phase-10-Retro-Block am Anfang (analog Phase-9-Retro-Block):
  - Was gut lief
  - Was länger gedauert hat
  - Was offen ist (Memory-Cross-Phase-Pendenzen)
- „Aktuell"-Zeile auf Phase 11 (Param-GUI) + `docs_raspi/phase_11_param_gui.md` (Pi-Plattform ist jetzt Phase 12)

### I.4 — `phase_10_progress.md` finalisieren (~15 min)

- Stage-I-Bullets I.1-I.6 abhaken
- Phasenabschluss-Checkliste (im Mutter-Plan-Bottom) konsolidieren
- Phase-10-Retrospektive (was gut, was länger, was offen)
- Cross-Phase-Pendenz-Liste am Ende

### I.5 — Build + Test (~5 min)

Regression-frei nach YAML-Status-Updates:
```bash
colcon build --packages-select hexapod_hardware hexapod_control hexapod_bringup
colcon test --packages-select hexapod_hardware hexapod_control hexapod_bringup
```

Erwartung: 208/0/20 + 18/0/0 + 5/0/0 grün.

### I.6 — User-Commit + Git-Tag (~5 min User)

User macht selbst:
- `git add` der Stage-I-Files
- `git commit -m "phase10: stage I complete (phase 10 done)"`
- `git tag phase-10-done`
- `git push --tags` (optional)

---

## Tests-Liste

| # | Test | Erwartung | Wer |
|---|---|---|---|
| I-T1 | colcon build grün | 3 packages 0 errors | Claude |
| I-T2 | colcon test grün | 208/0/20 + 18/0/0 + 5/0/0 | Claude |
| I-T3 | servo_mapping.yaml Pin 15/16/17 `status: calibrated` sichtbar | YAML-Diff | Claude + User |
| I-T4 | PHASE.md Phase 10 🟢, Phase 11 (Param-GUI) 🟡 aktiv | User-Sichtkontrolle | User |

### Was bewusst NICHT in Stage I getestet wird

- **Real-Modus mit Bench-PSU + Servos** — Stage I ist Doku-only
- **Erneuter IK-Probe-Run** — alle HW-Verifikationen schon in Stages C/D/E/F gemacht
- **Phase 11 (Param-GUI)/12 Vorbereitung** — eigene Phasen

---

## Progress-Checkliste

- [ ] I.1 Stage-I-Plan-Doku (diese Datei) angelegt
- [ ] I.2 servo_mapping.yaml Pin 15/16/17 mit status + calibrated_at
- [ ] I.3 README hexapod_hardware Phase-10-Quick-Start
- [ ] I.4 PHASE.md Phase 10 → 🟢, Phase 11 (Param-GUI) → 🟡, Retro
- [ ] I.5 phase_10_progress.md Stage-I + Phase-10-Retrospektive + Phasenabschluss-Checkliste
- [ ] I.6 Build + Test grün
- [ ] I.7 User-Commit + Git-Tag `phase-10-done`

**Done-Kriterium I erreicht:** alle Bullets `[x]`, Phase 10 in PHASE.md
als 🟢 markiert, User-Tag gesetzt.

---

## Erwartete Stage-I-Dauer

~45 min Claude + 5 min User.
