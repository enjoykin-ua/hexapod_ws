# Stufe 6 / IP3 — IMU-Balance-Tuning auf HW (§4-Plan)

> **Status: 🟡 Plan (grob) — Umsetzung im nächsten Chat, nach Phase 8 (Servo-Power).**
> Voraussetzungen: IP1 🟢 (`/imu/data` auf HW), IP2 🟢 (AXIS_MAP + yaw-unabh. Zero-Offset),
> **Servo-Power (2S-LiPo, aufgebockt)** und **DDS Dev↔Pi** (s. §0). Deckungsgleich mit Wiedereinstieg
> **P0** aus [`stage_3_terrain_following_plan.md` §7](stage_3_terrain_following_plan.md).
>
> ⚠️ **Die Gain-Zahlen hier sind Sim-Startwerte** — final formt sie der bestromte Roboter. Beim
> Implementieren evtl. Test-Details nachschärfen.

---

## 0. Kontext + Voraussetzungen

- **Warum überhaupt tunen — Sim ≠ HW:** In Gazebo ist alles rauschfrei und die Servos ideal. Auf HW:
  Sensor-Rauschen (BNO), **Servo-Lag ohne Positions-Feedback** (Echo-State), reale Reibung/Schlupf,
  Boden-Nachgeben. Die Sim-Defaults (`Kd 0.03`, Totband 1,5°, `max_level_angle` 10°/4°) sind nur
  **Startpunkte**.
- **Power-gated:** IP3 bewegt echte Beine → **2S-LiPo dran, aufgebockt zuerst** (CLAUDE.md §9,
  Kill-Switch, reduzierte Rate), dann Boden.
- **DDS Dev↔Pi Voraussetzung** (Logging/RViz/Live-`param set`): über den Handy-Hotspot ist DDS-Multicast
  blockiert (wie mDNS). **Vorher lösen** — entweder DDS-Unicast (`~/fastdds_hotspot.xml` + ufw-Regel am
  Dev) **oder** Dev+Pi ins Router-Netz. Sonst kein Live-Tuning.
- **Scope:** **nur die IMU-Balance-Features.** Die Fußkontakt-/Taster-Features (S4 adaptiver Touchdown,
  Slip-Detection) sind separat und bekommen einen **eigenen** HW-Test; ein kombinierter IMU+Taster-
  Integrationstest ist ein **späterer** Schritt (s. §5).

## 1. Ziel

Die sim-verifizierten Balance-Features — **Kipp-Erkennung** (St.1), **statisches Leveling** (St.2),
**Terrain-Following** (St.3/TF-2) — von „läuft mit Sim-Defaults" auf „läuft **sauber am echten
Roboter**" bringen: kein Fehlalarm, kein Zittern/Oszillieren, kein Aufschwingen. Ergebnis = ein Satz
**HW-Gains** (dokumentiert vs. Sim-Defaults), abgelegt in einer HW-Preset-YAML.

## 2. Logik-Skizze / Vorgehen (aufsteigend nach Risiko)

### IP3.1 — Kipp-Erkennung real kalibrieren  *(niedrigstes Risiko, rein defensiv)*
- **Was:** `tip_angle_warn`/`tip_angle_crit`/`tip_rate_crit_dps`/`tip_debounce_ticks` gegen echtes
  BNO-Rauschen + Gang-Ripple justieren. Löst nur **Freeze** aus (Safe-State) — bewegt selbst nichts
  gefährlich → **zuerst scharf**, als Netz für IP3.2/3.3.
- **Vorgehen:** aufgebockt, Roboter im Stand → Rausch-Niveau von `/imu/monitor` beobachten (Baseline).
  `warn`/`crit` so, dass Ruhe/Normal-Gang **fehlalarmfrei** bleibt, echtes Kippen aber rechtzeitig CRIT.
  `debounce` gegen Ripple-Spikes.
- **Live:** `ros2 param set /gait_node tip_* …` (alle live, `_rebuild_tip_monitor`).

### IP3.2 — Statisches Leveling (St.2) im STANDING
- **Was:** `leveling_enable:=true`, `leveling_mode:=horizontal` (roll+pitch→0). Gains + Totband nachziehen.
- **HW-Erwartung:** Sim-`Kd 0.03` auf HW ggf. **runter** (Rauschen + Servo-Lag → sonst Zittern),
  `deadband_deg` (1,5°) vorsichtig, `slew_max_dps` begrenzt die Korrektur-Rate.
- **Vorgehen:** im Stand von Hand leicht kippen / auf schiefe Unterlage stellen → Körper **levelt
  zurück, ohne zu oszillieren**. `max_level_angle_deg` (10° offline-bewiesen) als Clamp beachten.
- **Fallen:** Vorzeichen ist per IP2 = REP-103 = Sim (kein Aufschwingen erwartet); D rausch-verstärkend
  → Kd konservativ. `_LEVELING_NODE_STATES` (STANDING) — nur im Stand aktiv.

### IP3.3 — Terrain-Following (TF-2) im Laufen  *(höchstes Risiko)*
- **Was:** `leveling_mode:=terrain` (roll→0, pitch folgt Hang-Residual, Gyro-D-Dämpfung),
  `max_level_angle_walking_deg` (4°). Laufen auf flachem Grund → dann Hang/uneben.
- **Vorgehen:** erst geradeaus flach (Gyro-D gegen Gang-Wackeln prüfen), dann leichter Hang →
  Körper **folgt statt kämpft**, kein Aufschwingen. Grenz-Hang notieren.
- **Fallen:** Gyro-D auf HW konservativ (Sim rauschfrei); `slope_estimate_tau_s` (langsamer TP);
  roll→0 nur geradeaus (Quer-Hang = späterer Block `TF-Quer`).

## 3. Tests-Liste (mit Begründung)

| Test | Prüft | Setup |
|---|---|---|
| **IP3.1a Fehlalarm-frei** | Ruhe + Normal-Gang → **kein** WARN/CRIT | aufgebockt, Gang langsam |
| **IP3.1b CRIT feuert** | echtes Kippen (aufgebockt provoziert) → CRIT + Freeze rechtzeitig | aufgebockt, von Hand kippen |
| **IP3.2a kein Oszillieren** | Leveling im Stand → Körper ruhig, kein Zittern | Stand, Kd-Sweep |
| **IP3.2b levelt zurück** | leichtes Kippen / schiefe Unterlage → Körper level | Stand |
| **IP3.3a Lauf-Stabilität** | geradeaus flach → Gyro-D dämpft, kein Aufschwingen | Boden, langsam |
| **IP3.3b Hang folgen** | leichter Hang → folgt, wackelt nicht auf; Grenz-Hang notiert | Boden/Hang |
| **Gain-Doku** | HW-Werte vs. Sim-Defaults dokumentiert + in HW-Preset-YAML gesichert | — |

**Bewusst NICHT (→ scope-out / später):**
- **Taster/Fußkontakt-Closed-Loop (S4)** gleichzeitig — eigener HW-Test; Kombi-Integrationstest später.
- **Quer-/Diagonal-Hang** (`TF-Quer`), **Auto-Tuning** (stage_3 §7), **Kante/Stufe** (S4-Terrain).
- **Unit-Tests:** die Regler sind schon sim-unit-getestet (`test_balance_controller`/`test_tip_monitor`/
  `test_slope_estimator`); IP3 ist reines **HW-Tuning**, keine neue Logik.

## 4. Progress-Checkliste (→ Progress-File, Done-Vertrag; im nächsten Chat feinjustieren)

```
IP3 (IMU-Balance-Tuning auf HW):
- [ ] IP3.0 Voraussetzungen: 2S-LiPo/aufgebockt, DDS Dev↔Pi (Unicast oder Router), gait+IMU-Bringup läuft am Pi
- [ ] IP3.1 Kipp-Erkennung kalibriert: fehlalarmfrei (Ruhe+Gang) + CRIT/Freeze bei echtem Kippen; tip_*-Werte notiert
- [ ] IP3.2 Statisches Leveling: kein Oszillieren, levelt zurück; Kd/Totband/Slew (HW vs Sim) notiert
- [ ] IP3.3 Terrain-Following im Laufen: flach stabil + Hang folgt ohne Aufschwingen; Grenz-Hang + Gyro-D notiert
- [ ] IP3.4 HW-Gains in HW-Preset-YAML gesichert + Doku-Eintrag (HW-Werte vs Sim-Defaults)
- [ ] IP3.5 kritische Self-Review-Tabelle
```

## 5. Offene Punkte (im nächsten Chat entscheiden)

1. **Reihenfolge:** St.1 → St.2 → St.3 (Risiko-aufsteigend, empfohlen) vs. nach HW-Erkenntnissen umsortieren.
2. **Gain-Ablage:** Live-`param set` → in eine **HW-Preset-YAML** sichern (analog Gait-Presets
   `hexapod_gait/config/presets/`). Format + Lade-Weg festlegen.
3. **DDS-über-Hotspot:** Unicast-Config (`~/fastdds_hotspot.xml` + ufw) vs. Router-Netz — vor IP3 fixieren.
4. **gait.launch.py `use_sim_time`:** Default `true` blockt rclpy-Timer still auf HW ohne `/clock` →
   `use_sim_time:=false` setzen ([[project_phase13_gait_launch_sim_time_default]]).
5. **Kombi mit Taster (S4):** wann der gemeinsame bestromte Integrationstest — nach IP3.3 sauber?

## 6. Sicherheit (CLAUDE.md §9)
- **Aufgebockt zuerst** (Beine frei), Kill-Switch/Strom-Trennung griffbereit, reduzierte Rate; dann Boden.
- **Kipp-Erkennung (IP3.1) VOR Leveling (IP3.2)** scharf — Safe-State-Netz zuerst.
- Erste Leveling-/TF-Bewegung mit **niedriger** Korrektur-Rate (`slew_max_dps` klein), dann hochziehen.

## 7. Handoff / Anker (Code + Params)

- **Nodes:** `gait_node` (alle `tip_*`/`leveling_*`/`slope_*`-Params **live** per `ros2 param set`),
  `bno055_imu` + `imu_monitor` (IMU-Kette), `real.launch.py` (Servo-Stack, `loopback_mode:=false`),
  `gait.launch.py` (`use_sim_time:=false`).
- **Regler (ROS-frei, schon unit-getestet):** `tip_monitor.py`, `balance_controller.py`,
  `slope_estimator.py`; Stellpfad `gait_engine._compute_leveled_ik`.
- **Params (aus [`ai_navigation.md`](../../project_architecture/ai_navigation.md) A5-Abschnitt):**
  `leveling_enable/mode/kp/ki/kd/deadband_deg/slew_max_dps/max_level_angle_deg/max_level_angle_walking_deg/startup_grace`,
  `slope_aware_tip_enable/slope_estimate_tau_s/slope_clamp_deg`, `tip_angle_warn/crit_deg`,
  `tip_rate_crit_dps/tip_debounce_ticks`.
- **Offline-Envelope:** `python3 tools/leveling_envelope_check.py` (max_level_angle-Grenzen).
- **Test-Befehle:** [`stage_6c_imu_hw_balance_test_commands.md`](stage_6c_imu_hw_balance_test_commands.md).
