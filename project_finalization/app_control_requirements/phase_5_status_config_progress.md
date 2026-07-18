# Phase 5 — Status-Overlay + Touch-Parameter-UI — Progress (ROS-Seite)

> **Done-Vertrag** (CLAUDE.md §4). Bullets 1:1 aus
> [`phase_5_status_config_plan.md`](phase_5_status_config_plan.md) §3.
> **ROS-Seite implementiert + unit-/lint-getestet + runtime-gesmoked**; Live-Sim (T5.1/T5.2/T5.10)
> + App-Shell (P5.10–P5.13) + E2E (P5.15) offen (User bzw. Android-Session).

```
Phase 5 (Status-Overlay + Touch-Parameter-UI):
- [x] P5.1 [ROS] gait_node publisht /hexapod/status (JSON: state/stance/gait/safety/tip + H1/H2-Caps), ~5 Hz (T5.1/T5.2 ✅ Live)
- [x] P5.2 [ROS] Tempo-Quelle: joy_to_twist publisht /hexapod/tempo (latched, aktives Preset + Scales) (T5.2b ✅ Live)
- [x] P5.3 [ROS] /hexapod/capabilities latched (gaits/stance_modes/tempo_presets) (T5.3 ✅)
- [x] P5.4 [ROS] config/hmi_config_manifest.yaml (39 Params, 4+1 Gruppen) + /hexapod/config_manifest latched (T5.4 ✅)
- [x] P5.5 [ROS] Whitelist-Params: Drift-Schutz-Test (alle 39 im Code deklariert); Live-Apply/Reject (T5.5-T5.7 ✅ Live)
- [x] P5.6 [ROS] /hexapod/alerts (WARN+ aus /rosout republished) (T5.8 ✅)
- [x] P5.7 [ROS] Set-Stance direkt = Weg (b): App cyclet ueber /hexapod_cycle_stance (kein neuer ROS-Code)
- [x] P5.8 [ROS] Contract §6a festgezurrt (Status/Capabilities/Manifest/Alerts/Tempo Feld-Typen), Version-Bump v0.9
- [x] P5.9 [ROS] Unit/Lint gruen (902 Tests) + Sim-Regression Walking (T5.10 ✅ Live)
- [ ] P5.10 [App] Overlay-Slots mit Live-Daten (status/tempo/foot_contacts/imu-monitor)  [Android-Session]
- [ ] P5.11 [App] Config-Panel generisch aus Manifest (Gruppen, Slider +/-, Eintipp, Hint, Reject-reason)  [Android-Session]
- [ ] P5.12 [App] Dropdowns gait/tempo/stance (Capabilities, standing-gated) + Alerts-View (+Kopieren)  [Android-Session]
- [ ] P5.13 [App] 3D-Roboter-Viz aus /joint_states + URDF (Center-View-Option)  [Android-Session]
- [x] P5.14 [ROS] Self-Review + Doku (Contract v0.9, architecture/ai_navigation-Nachzug, test_commands, App-Brief)
- [ ] P5.15 [Integration, User+App] End-to-End: Overlay live + Panel verstellt + Dropdowns + Alerts  [User + App]
```

## Stand — ROS-Seite implementiert + statisch/runtime verifiziert

**Fertig + verifiziert** (`colcon build` grün, `colcon test` **902 Tests / 0 errors / 0 failures**,
Lint clean; `hmi_status` Runtime-Smoke grün):

- **`hexapod_gait/gait_node.py`:** neuer `/hexapod/status`-Publisher (`std_msgs/String`, JSON),
  eigener 5-Hz-Timer in der Tick-CB-Gruppe (kein Race). Felder: `state`, `stance_idx`, `stance`,
  `gait`, `safety_frozen`, `tip`, `step_height_cap`, `step_length_cap` (dynamische H1/H2-Caps des
  aktuellen Stance-Modus). `_safety_frozen` in `_trigger_safety_freeze` gesetzt, `_tip_level` im
  Tick gecacht.
- **`hexapod_teleop/joy_to_twist.py`:** neuer `/hexapod/tempo`-Publisher (`String`, JSON, **latched**),
  publiziert beim Start + nach jedem Tempo-Wechsel (`_on_tempo_response`). Felder: `tempo`,
  `tempo_idx`, aktuelle `linear_x/y_scale`, `angular_z_scale`.
- **`hexapod_supervisor/hmi_status.py`** (neuer Node, Always-On): latcht `/hexapod/capabilities` +
  `/hexapod/config_manifest` (aus `config/hmi_config_manifest.yaml`) und republished `/rosout`
  WARN+ auf `/hexapod/alerts` (latched, Historie 50, VOLATILE-`/rosout`-Sub → kein Backlog-Flood).
- **`config/hmi_config_manifest.yaml`:** 39 Params — Lauf/Gang (3) · Teleop/Tempo (5) · Sensorik (5)
  · IMU/Balance (10) · IMU/Balance-Erweitert (16 Gains, `advanced:true`). Pro Param
  group/label/hint/widget/type/default/min/max/step/gating/dynamic_cap.
- **Wiring:** `hmi_status` in `always_on.launch.py` (mit `use_sim_time`); setup.py-Entry-Point;
  package.xml-Deps (`rcl_interfaces`, `ament_index_python`, `python3-yaml`).
- **Tests:** `test_hmi_status.py` (6×): Manifest-Struktur, 16 advanced-Gains, Capabilities,
  **Manifest↔Code-Drift-Schutz** (alle 39 Params real im Ziel-Node deklariert), Alert-Filter+Format.

**Runtime-Smoke (ohne Gazebo, grün):** `hmi_status` gestartet → `/hexapod/capabilities` +
`/hexapod/config_manifest` (39 Params) gelatcht empfangen; eine `/rosout`-WARN erschien als JSON
auf `/hexapod/alerts`.

**Design-Entscheidungen (aus dem Plan, umgesetzt):** JSON-String-Format · keine Persistenz · 16
Gains als eingeklappter „Erweitert"-Bereich · Tempo eigenes Topic · Set-Stance = App-cycle · Host =
`hexapod_supervisor` (Always-On → Panel beim Connect befüllt).

### Live-Test-Befund (User) — alle grün

T5.1 `/hexapod/status` **~4.99 Hz**, Felder korrekt (`STANDING`/`mittel`/`tripod`/`safety_frozen:false`/
`tip:none`) · T5.2 Caps folgen dem Stance-Wechsel (mittel↔hoch, `step_height_cap`/`step_length_cap`) ·
T5.2b `/hexapod/tempo` latched (`schnell`, Scales) · T5.5 alle 3 Param-Sets akzeptiert · T5.6
`cycle_time`-Reject außerhalb STANDING mit `reason` · T5.7 `step_height`-Cap-Reject (H1) mit `reason` ·
T5.10 Roboter läuft normal (**kein Regress** durch den 5-Hz-Status-Timer). **ROS-Seite Phase 5
komplett verifiziert.**

**ROS-Seite abgeschlossen.** Contract **v0.9** (§6a) festgezurrt; architecture/ai_navigation nachgezogen.
**Offen (nicht ROS):** App-Shell **P5.10–P5.13** (Android-Session gegen §6a) · P5.15 End-to-End (User + App).

## Self-Review (P5.14)

| # | Punkt | Status |
|---|---|---|
| 1 | Status-Timer eigener 5-Hz-Timer in Tick-MutuallyExclusive-Gruppe → kein Read-Race | OK |
| 2 | Alle `_publish_status`-Member existieren bei erstem Timer-Fire (nach __init__) | OK |
| 3 | `/hexapod/tempo` latched → spät verbindende App bekommt Ist-Wert sofort | OK |
| 4 | Capabilities/Manifest aus EINER YAML (Single Source), keine Enums im Code dupliziert | OK |
| 5 | Manifest↔Code-Drift-Schutz (Test): kein Slider zeigt auf toten Param | OK (39/39) |
| 6 | Alerts: VOLATILE-`/rosout`-Sub (kein Backlog-Flood) + Eigen-Log-Loop-Schutz | OK |
| 7 | `hmi_status` in Always-On → Panel/Dropdowns beim Connect befüllt (vor On-Demand-Stack) | OK (Runtime-Smoke) |
| 8 | `colcon build` + 902 Tests + Lint grün | OK |
| 9 | Live-Apply aller Whitelist-Params (Slider ohne Wirkung wäre wertlos) | 🟢 T5.5 (Live, User) |
| 10 | Walking-Regression (Status-Timer stört den Gait-Tick nicht) | 🟢 T5.10 (Live, User) |
| 11 | `safety_frozen` bleibt True bis Node-Neustart (kein Reset) | 🟡 v1 bewusst (Recovery/Reset = Phase 6) |
| 12 | `/hexapod/tempo` re-publisht NICHT bei Config-Panel-Scale-Set (nur bei D-Pad-Tempo) | 🟡 App liest nach eigenem Set selbst nach (App macht die Änderung) |

Keine 🔴. Die 🟢 sind der Pflicht-Live-Smoke (T5.5/T5.10), die 🟡 bewusste v1-Grenzen.

## Design-Entscheidungen (mit Alternativen)

- **Status als eigener 5-Hz-Timer** (nicht in den Gait-Tick eingeflochten): entkoppelt von
  `tick_rate`, läuft auch in SAT/STANDING; gleiche CB-Gruppe → kein Race. Verworfen: Publish im
  `_tick` (an tick_rate gekoppelt, komplexeres On-Change-Handling).
- **Dynamische H1/H2-Caps im Status** (nicht im Manifest): die effektive Slider-Obergrenze ändert
  sich mit dem Stance-Modus → gehört in den Live-Status, nicht ins statische Manifest. Die App
  klemmt `min(manifest.max, status[cap])`.
- **Manifest-Ranges = app-sichere Grenzen** (nicht die Hard-Limits): die serverseitige Validierung
  (`_on_param_change`) bleibt die Wahrheit; das Manifest verhindert nur, dass die App sinnlose
  Werte anbietet. ⚠️ Die konkreten min/max/step sind ein **Vorschlag** (Plan §4.4) — User-Review.
- **Alerts latched Historie 50** (statt nur Live-Stream): eine spät verbindende App bekommt die
  letzten 50 Alerts. Verworfen: nicht-latched (App verpasst alles vor Connect).
