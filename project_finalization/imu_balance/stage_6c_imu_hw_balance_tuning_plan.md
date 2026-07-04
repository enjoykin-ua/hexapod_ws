# Stufe 6 / IP3 — IMU-Balance-Tuning auf HW (Umriss)

> **Umriss-Doc** (weniger ausführlich). Wird nach IP1/IP2 zum vollen §4-Plan ausgebaut.
>
> **Status: ⚪ vorgeplant — power-gated.** Voraussetzungen: IP1 🟢 (`/imu/data` auf HW),
> IP2 🟢 (Achsen + Zero-Offset), **und Servo-Power (Phase 8 Elektronik)** — anders als IP1/IP2 braucht
> IP3 den **bestromten, aufgebockten → am Boden** stehenden Roboter (die Regelung bewegt Beine).
> Deckungsgleich mit dem **Wiedereinstieg P0** aus
> [`stage_3_terrain_following_plan.md` §7](stage_3_terrain_following_plan.md).

## Ziel

Die sim-getesteten Balance-Features (Kipp-Erkennung St.1, statisches Leveling St.2, Terrain-Following
St.3/TF-2) auf **echter HW** von „läuft mit Sim-Defaults" auf „läuft sauber am echten Roboter" bringen.
**Sim-verifiziert ≠ HW-verifiziert:** HW hat Rauschen, Servo-Dynamik (Echo-State, kein Positions-
Feedback), reale Reibung/Schlupf — die Sim-Defaults sind nur **Startpunkte**.

## Vorgehen (Skizze) — aufsteigend nach Risiko

### IP3.1 — Kipp-Erkennung (St.1) real kalibrieren  *(niedrigstes Risiko)*
- `angle_warn`/`angle_crit`/`rate_crit`/`debounce_ticks` gegen echtes Rauschen + Gang-Ripple justieren.
- Roboter aufgebockt / vorsichtig kippen → Fehlalarm-frei, aber CRIT feuert rechtzeitig.
- Rein defensiv (löst nur Freeze aus) → sicher zuerst.

### IP3.2 — Statisches Leveling (St.2) im STANDING
- `leveling_enable` an, im Stand: Gains + Totband nachziehen. Sim-Defaults `Kd 0.03`, Totband **1,5°**
  → auf HW ggf. **Kd runter** (Rauschen/Servo-Lag → sonst Zittern), **Totband vorsichtig**.
- Von Hand leicht kippen / auf schiefe Unterlage → Körper levelt zurück, ohne zu oszillieren.

### IP3.3 — Terrain-Following (TF-2) im Laufen  *(höchstes Risiko)*
- `gait_pattern`-Stabilität + Gyro-D-Term auf HW; roll→0 / pitch→Hang-Residual live.
- Am Hang / unebenem Grund: folgt statt zu kämpfen, wackelt nicht auf.

## Sicherheit (CLAUDE.md §9)
- **Aufgebockt zuerst** (Beine in der Luft), Kill-Switch griffbereit, reduzierte Rate; erst dann Boden.
- Kipp-Erkennung (IP3.1) **vor** Leveling (IP3.2) scharf — Safe-State-Netz zuerst.

## Tests (Skizze)
- St.1: Fehlalarm-frei im Normal-Gang, CRIT bei echtem Kippen (aufgebockt provoziert).
- St.2: kein Oszillieren, levelt zurück; Gains dokumentiert (HW-Werte vs Sim-Defaults).
- St.3: Hang folgen ohne Aufschwingen; Grenz-Hang notiert.
- Logging/Plots **am Dev** (DDS/Bag), nicht auf der Pi-SD.

## Offene Punkte (für den Voll-Plan nach IP1/IP2 + Phase 8)
- Reihenfolge St.1 → St.2 → St.3 vs. nach HW-Erkenntnissen (P0-Text lässt Reihenfolge offen).
- Gain-Ablage: Live-`param set` → in eine HW-Preset-YAML sichern (analog Gait-Presets).
- Wechselwirkung mit Fußkontakt-Closed-Loop (S4) — gemeinsamer bestromter Integrationstest?
- Auto-Tuning-Idee (stage_3 §7) — Sim-optimale Gains nur als Startpunkt, auf HW nachziehen.
