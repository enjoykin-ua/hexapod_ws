# Phase 5 — Status-Overlay + Touch-Parameter-UI — §4-Plan

> **Ziel:** die in Phase 4 positionierten **leeren Overlay-Slots mit Live-Daten füllen** und ein
> **rqt-artiges Config-Panel** (kuratierte, verstellbare Parameter) bauen. Kern-ROS-Arbeit = ein
> **Status-Kanal** (State/Stance/Gangart/Tempo/Safety), ein **Capabilities-Kanal** (Enums), ein
> **Config-Manifest** (die verstellbaren Params + Ranges/Labels/Hints) und ein **Alerts-Kanal**.
>
> **Seite:** ROS + App. **Status: 🟡 Plan.** Master: [`00_overview.md`](00_overview.md) ·
> Contract: [`interface_contract.md`](interface_contract.md) (§6 `[TBD-Phase 5]`).

---

## 0. Ziel + Abgrenzung

**ROS-Seite (diese Session):**
1. **Status-Topic** `/hexapod/status` — kompakter Live-Zustand fürs Overlay (JSON-String, [D-neu]).
2. **Capabilities-Topic** `/hexapod/capabilities` — statische Enums (Gangarten, Stance-Modi,
   Tempo-Presets), gelatcht, einmal beim Start.
3. **Config-Manifest** `/hexapod/config_manifest` — die **kuratierte Whitelist** der verstellbaren
   Params (pro Param: Gruppe, Label, Hint, Default, min/max/step, Widget, Gating), gelatcht. Die App
   rendert das Panel **generisch** daraus; get/set der Werte läuft über die **nativen rosbridge-
   Parameter-Services** (`get_parameters`/`set_parameters`).
4. **Alerts-Topic** `/hexapod/alerts` — WARN/ERROR/FATAL aus `/rosout` republished.
5. **Set-Stance direkt** — Stance-Modus direkt wählen (Ergänzung zum L2/R2-Cycle).

**App-Seite (zweite Session):** Overlay-Slots mit Live-Daten füllen (aus `/hexapod/status` +
`/foot_contacts` + `/imu/monitor`), Config-Panel (Slider ± + Eintipp-Feld) aus dem Manifest,
Dropdowns (gait/tempo/stance) aus Capabilities, Alerts-View (Liste + „Alles kopieren"), 3D-Viz aus
`/joint_states` + URDF. Siehe §5.

**Format-Entscheidung (getroffen):** **JSON-String** für Status/Capabilities/Manifest/Alerts
(`std_msgs/String`). Grund: einziger Consumer = Mobile-App über rosbridge (dort eh JSON), kein neues
Message-Paket, leicht erweiterbar. Upgrade auf Custom-`.msg` möglich, falls je ein ROS-nativer
Consumer dazukommt. Contract §7.3 → damit geschlossen.

**Bewusst NICHT in Phase 5:**
- **Config-Persistenz** (User: nicht nötig) — Änderungen gelten **nur zur Laufzeit**. Speichern
  bleibt der bestehende Preset-/Alias-Mechanismus (`hexapod-save-walking-params`), kein App-Button.
- **PWMs / Roh-Winkel / Cal-Werte** — nie verstellbar in der App.
- **E-Stop scharf / Recovery** — Phase 6.

**Enthalten, aber eingeklappt:** die **16 per-Achse-Balance-Gains** kommen als **„Erweitert"-
Unterbereich** der IMU-Gruppe mit rein (User-Wunsch) — im Manifest per `advanced:true` markiert, in
der App **standardmäßig zugeklappt** (damit die 16 Knöpfe die Standardansicht nicht erschlagen).
Nutzen: Live-Regler-Fein-Tuning fürs offene IP3.3-HW-Tuning. ⚠️ Warnhinweis in der App: falsche
Gains → Aufschwingen.

---

## 1. Logik-Skizze / Vorgehen (ROS-Seite)

### 1a. Status-Topic `/hexapod/status` (`std_msgs/String`, JSON)
- **Quelle State/Stance/Gangart/Safety/Caps = `gait_node`** (hat State-Machine, `_stance_idx`,
  `_pattern.name`, Freeze-Zustand, die H1/H2-Caps). Neuer Publisher, getriggert im Haupt-Tick
  (throttled auf ~5 Hz) **und** on-change (State-/Stance-/Gait-Wechsel sofort).
- **Felder (Vorschlag):**
  ```json
  {
    "state": "WALKING",              // GaitEngine-State (STANDING/WALKING/SAT/SITTING/...)
    "stance_idx": 1, "stance": "mittel",
    "gait": "tripod",
    "safety_frozen": false,
    "tip": "none",                   // none|warn|crit (aus TipMonitor)
    "step_height_cap": 0.05,         // H1-Cap des AKTUELLEN Stance-Modus (dynamisch)
    "step_length_cap": 0.08          // H2-Cap des AKTUELLEN Stance-Modus (dynamisch)
  }
  ```
  → die Caps liefern der App die **effektive** Slider-Obergrenze für `step_height`/`step_length_max`
  (die sich mit dem Stance ändern).
- **Tempo** liegt **nicht** im gait_node, sondern im `joy_to_twist` (`_tempo_idx`) → **eigenes
  `/hexapod/tempo`** (String/JSON) aus `joy_to_twist`, die App merged es (entschieden §4.1).

### 1b. Capabilities-Topic `/hexapod/capabilities` (`std_msgs/String`, JSON, latched/transient_local)
- Einmal beim Start publiziert (statische Enums):
  ```json
  { "gaits": ["tripod","wave","tetrapod","ripple"],
    "stance_modes": ["tief","mittel","hoch"],
    "tempo_presets": ["langsam","mittel","schnell","aggressiv"] }
  ```
  (Gangarten aus `GAIT_PRESETS`, Stance aus `_STANCE_MODES`, Tempos aus `_TEMPO_MODES`.)
- Latched → die App liest es einmal beim Connect für die Dropdown-Inhalte.

### 1c. Config-Manifest `/hexapod/config_manifest` (`std_msgs/String`, JSON, latched)
- **Die kuratierte Whitelist** — geladen aus einer statischen YAML (`config/hmi_config_manifest.yaml`),
  als JSON gelatcht publiziert. Pro Eintrag:
  ```json
  { "node": "/gait_node", "param": "step_height",
    "group": "Lauf / Gang", "label": "Fuß-Hub", "hint": "größer = höher",
    "widget": "slider", "default": 0.05, "min": 0.01, "max": 0.06, "step": 0.005,
    "unit": "m", "gating": null, "dynamic_cap": "step_height_cap" }
  ```
- `gating: "standing"` → App disabled den Slider außerhalb STANDING (State aus §1a).
- `dynamic_cap: "<status-feld>"` → App klemmt max auf `min(manifest.max, status[dynamic_cap])`.
- **Kein** Editieren der Param-Deklarationen nötig — die Ranges leben im Manifest (App-sichere
  Grenzen, dürfen enger als das Hard-Limit sein). get/set = native rosbridge-Param-Services; die
  Werte werden live über `_on_param_change` angewandt (atomarer validate-then-apply, liefert
  `reason` bei Reject → App zeigt ihn).

**Kuratierte Whitelist v1 (grounded aus dem Code):**

| Gruppe | node | param | Default | Gating | Hint |
|---|---|---|---|---|---|
| Lauf / Gang | gait_node | `cycle_time` | 2.0 | **standing** | kleiner = schneller |
| Lauf / Gang | gait_node | `step_length_max` | 0.080 | cap H2 | größer = weiter |
| Lauf / Gang | gait_node | `step_height` | 0.050 | cap H1 | größer = höher |
| Teleop / Tempo | joy_to_twist | `linear_x_scale` | 0.05 | — | Vorwärts-Tempo |
| Teleop / Tempo | joy_to_twist | `linear_y_scale` | 0.05 | — | Seitwärts-Tempo |
| Teleop / Tempo | joy_to_twist | `angular_z_scale` | 0.46 | — | Dreh-Tempo |
| Teleop / Tempo | joy_to_twist | `slow_factor` | 0.5 | — | L1-Präzision (kleiner = feiner) |
| Teleop / Tempo | joy_to_twist | `deadzone` | 0.10 | — | Stick-Totzone |
| Sensorik / Terrain | gait_node | `leveling_enable` | false | — | IMU-Balance an |
| Sensorik / Terrain | gait_node | `adaptive_touchdown_enable` | false | — | Fuß reicht nach Terrain |
| Sensorik / Terrain | gait_node | `slip_detection_enable` | false | — | Freeze an Kante |
| Sensorik / Terrain | gait_node | `sensor_plausibility_enable` | false | — | Sensor-Fail-Safe |
| Sensorik / Terrain | gait_node | `tip_detection_enable` | true | — | Kipp-Erkennung an |
| IMU / Balance | gait_node | `leveling_mode` | terrain | — | Dropdown: Boden folgen/waagerecht/auto |
| IMU / Balance | gait_node | `leveling_max_angle_deg` | 10.0 | — | max Ausgleich Stand |
| IMU / Balance | gait_node | `leveling_max_angle_walking_deg` | 4.0 | — | max Ausgleich Lauf |
| IMU / Balance | gait_node | `tip_angle_warn_deg_roll` | 15.0 | — | Kipp-Warnschwelle |
| IMU / Balance | gait_node | `tip_angle_warn_deg_pitch` | 15.0 | — | Kipp-Warnschwelle |
| IMU / Balance | gait_node | `tip_angle_crit_deg_roll` | 25.0 | — | Kipp-Krit → Freeze |
| IMU / Balance | gait_node | `tip_angle_crit_deg_pitch` | 25.0 | — | Kipp-Krit → Freeze |
| IMU / Balance | gait_node | `tip_rate_crit_dps` | 80.0 | — | Kipp-Rate krit |
| IMU / Balance | gait_node | `slope_estimate_tau_s` | 0.5 | — | Hang-Filter (größer = träger) |
| IMU / Balance | gait_node | `slope_clamp_deg` | 40.0 | — | Hang-Begrenzung |

**Gruppe „IMU / Balance — Erweitert" (`gait_node`, `advanced:true` → App eingeklappt):** die 16
per-Achse-Gains des Balance-Reglers (v2), je `_roll` **und** `_pitch`:

| param (×_roll/_pitch) | Default | Hint |
|---|---|---|
| `leveling_kp_{roll,pitch}` | 0.4 | P-Stärke (größer = härter; zu hoch = Pendeln) |
| `leveling_ki_{roll,pitch}` | 0.1 | I-Anteil (Rest-Neigung weg; zu hoch = Aufschwingen) |
| `leveling_kd_{roll,pitch}` | 0.03 | D-Dämpfung |
| `leveling_deadband_inner_deg_{roll,pitch}` | 1.5 | inneres Totband (Ruhe unter X°) |
| `leveling_deadband_outer_deg_{roll,pitch}` | 1.5 | äußeres Totband (Hysterese) |
| `leveling_slew_max_dps_{roll,pitch}` | 8.0 | max Stell-Tempo |
| `leveling_tau_fast_s_{roll,pitch}` | 0.0 | schneller Tiefpass (Glättung) |
| `leveling_tau_slow_s_{roll,pitch}` | 0.0 | langsamer Tiefpass (Drift) |

> min/max/step je Param zieh ich beim Impl aus sinnvollen sicheren Bereichen (nicht das Hard-Limit).
> Die 16 Gains laufen live durch `_on_param_change` (`_leveling_axis_param_map` → `_apply_leveling_
> axis_params`). App zeigt sie **zugeklappt** + Warnhinweis (falsche Werte → Aufschwingen).

### 1d. Alerts-Topic `/hexapod/alerts` (`std_msgs/String`, JSON)
- Kleiner Node subscribt `/rosout` (`rcl_interfaces/msg/Log`), filtert `level >= WARN`, republished:
  `{ "stamp": <sec>, "level": "WARN", "name": "gait_node", "msg": "..." }`.
- Die App führt eine Liste + „Alles kopieren" (Clipboard).

### 1e. Set-Stance direkt (entschieden §4.2)
- **Weg (b):** die App cyclet über das bestehende `/hexapod_cycle_stance` (`SetBool` up/down) zum
  Ziel — sie kennt den aktuellen `stance_idx` aus dem Status und ruft so oft, bis Ziel erreicht.
  **Kein neues ROS-Interface.** (Standing-only bleibt serverseitig geprüft.)

### 1f. Host-Node der neuen Topics (entschieden §4.3)
- **Neuer Node `hmi_status` im `hexapod_supervisor`-Paket** (Always-On-Schicht, `always_on.launch.py`,
  ab Boot) publiziert **Capabilities + Config-Manifest + Alerts** (gelatcht) → schon **beim App-
  Connect** verfügbar (vor dem On-Demand-Stack). Der Live-**Status** (`/hexapod/status` + Tempo)
  kommt aus dem `gait_node`/`joy_to_twist` (Daten nur im laufenden Stack).

**Verworfene Alternativen:** Custom-`.msg` für Status (Message-Paket-Overhead, single Consumer);
`DiagnosticArray` (Key-Value-Strings, klobig); `ParameterDescriptor`-Ranges statt Manifest (kein
Label/Gruppe/Hint, und erzwingt Editieren jeder Deklaration).

---

## 2. Tests-Liste (mit Begründung) + was NICHT

| Test | Prüft | Warum |
|---|---|---|
| **T5.1** `/hexapod/status` JSON valide + Felder ändern sich (State/Stance/Gait-Wechsel) | Status-Publisher | Overlay-Quelle |
| **T5.2** `/hexapod/status` liefert korrekte `step_height_cap`/`step_length_cap` je Stance | dynamische Caps | App-Slider-Klemmung |
| **T5.3** `/hexapod/capabilities` gelatcht, korrekte Enums, kommt bei spätem Subscribe an | Capabilities | Dropdown-Inhalte |
| **T5.4** `/hexapod/config_manifest` gelatcht, valide, deckt die Whitelist | Manifest | generisches Panel |
| **T5.5** `set_parameters` je Whitelist-Param wirkt **live** (Wert ändert Verhalten) | Live-Apply | Slider ohne Wirkung wäre wertlos |
| **T5.6** `standing_only`-Param außerhalb STANDING → Reject mit `reason` | Gating | App muss Reject sauber zeigen |
| **T5.7** `step_height`/`step_length_max` über Stance-Cap → Reject (H1/H2) | Cap-Gate | verhindert IKError/Freeze auf HW |
| **T5.8** `/hexapod/alerts`: ein WARN im `/rosout` erscheint dort | Alerts | Fehler-Liste |
| **T5.9** Set-Stance direkt erreicht den Ziel-Modus | Stance-Direkt | Touch-Dropdown |
| **T5.10** Unit/Lint grün, Sim-Regression (Walking unverändert) | keine Regression | §4-Pflicht |

**App-Tests (zweite Session):** Overlay zeigt Live-Werte · Config-Panel rendert Gruppen/Slider/Hints
aus dem Manifest · ±/Eintipp setzt Params · Dropdowns aus Capabilities · Alerts-Liste + Kopieren ·
3D-Viz aus `/joint_states`.

**Bewusst offen / später:** Config-Persistenz (nicht gewünscht); 16 Balance-Gains (IP3.3/Phase 8);
E-Stop/Recovery (Phase 6); Audio (Phase 7).

---

## 3. Progress-Checkliste (→ `phase_5_..._progress.md`, Done-Vertrag)

```
Phase 5 (Status-Overlay + Touch-Parameter-UI):
- [ ] P5.1 [ROS] gait_node publisht /hexapod/status (JSON: state/stance/gait/safety/tip + H1/H2-Caps), ~5 Hz + on-change (T5.1/T5.2)
- [ ] P5.2 [ROS] Tempo-Quelle geklaert + publiziert (joy_to_twist -> /hexapod/tempo o. Aggregator, §4.1)
- [ ] P5.3 [ROS] /hexapod/capabilities latched (gaits/stance_modes/tempo_presets) (T5.3)
- [ ] P5.4 [ROS] config/hmi_config_manifest.yaml (kuratierte Whitelist) + /hexapod/config_manifest latched (T5.4)
- [ ] P5.5 [ROS] Whitelist-Params live-apply verifiziert (_on_param_change deckt alle) (T5.5); Reject-Pfade Gating+Cap (T5.6/T5.7)
- [ ] P5.6 [ROS] /hexapod/alerts (WARN+ aus /rosout republished) (T5.8)
- [ ] P5.7 [ROS] Set-Stance direkt (Weg b: App-cycle-to-target, o. Entscheidung §4.2) (T5.9)
- [ ] P5.8 [ROS] Contract §6 festgezurrt (Status/Capabilities/Manifest/Alerts/Set-Stance Feld-Typen), Version-Bump
- [ ] P5.9 [ROS] Unit/Lint gruen + Sim-Regression Walking unveraendert (T5.10)
- [ ] P5.10 [App] Overlay-Slots mit Live-Daten (status/foot_contacts/imu-monitor)
- [ ] P5.11 [App] Config-Panel generisch aus Manifest (Gruppen, Slider +/-, Eintipp-Feld, Hint, Reject-reason)
- [ ] P5.12 [App] Dropdowns gait/tempo/stance (Capabilities, standing-gated) + Alerts-View (+Kopieren)
- [ ] P5.13 [App] 3D-Roboter-Viz aus /joint_states + URDF (Center-View-Option)
- [ ] P5.14 [ROS] Self-Review + Doku (READMEs, architecture-Nachzug, test_commands)
- [ ] P5.15 [Integration, User+App] End-to-End: Overlay live + Panel verstellt + Dropdowns + Alerts
```

---

## 4. Offene Punkte / Risiken

**Entschieden (User-Freigabe):**
1. ✅ **Tempo-Quelle:** eigener `/hexapod/tempo`-Publish aus `joy_to_twist` (App merged 2 kleine
   Topics — entkoppelt, jeder Node bleibt Herr seiner Daten). ⚠️ Nebenwirkung: Tempo-Preset-Wechsel
   (D-Pad) überschreibt die Scales → die App liest die Scale-Slider nach einem Tempo-Wechsel neu.
2. ✅ **Set-Stance direkt:** Weg (b) — App cyclet über das bestehende `/hexapod_cycle_stance` zum
   Ziel (App kennt aktuellen `stance_idx` aus dem Status). **Kein neues Interface.**
3. ✅ **Host-Node:** neuer kleiner Node **`hmi_status` im `hexapod_supervisor`-Paket** (Always-On-
   Schicht, ab Boot) publiziert Capabilities/Manifest/Alerts (gelatcht) → Config-Panel + Dropdowns
   schon **beim Connect** befüllt, vor dem On-Demand-Stack. Der Live-**Status** bleibt im `gait_node`
   (Daten nur im laufenden Stack).

**Noch offen (beim Impl, unkritisch):**
4. **Manifest-Ranges:** min/max/step je Param = **app-sichere** Bereiche (enger als Hard-Limit) —
   inkl. der 16 Balance-Gains. Werte-Vorschlag beim Impl; User-Review der konkreten Grenzen.
5. **Status-Rate:** ~5 Hz + on-change reicht fürs Overlay (kein Hot-Path-Bedarf).

---

## 5. App-Seiten-Brief (self-contained) — Overlay-Daten + Config-Panel

**Interface = `interface_contract.md §6`** (nach P5.8 festgezurrt). Alles über rosbridge (Kanal 1).

- **Overlay-Slots füllen** (die in Phase 4 positionierten leeren Slots):
  - `state`/`stance`/`gait`/`tempo`/`safety`/`tip` ← `/hexapod/status` (+ `/hexapod/tempo`).
  - `foot 1–6` ← `/foot_contacts` (`std_msgs/Float64MultiArray`, 6× 0/1, Zahl grün = Kontakt).
  - `tip` ← `/hexapod/status.tip` bzw. `/imu/monitor` (roll/pitch).
- **Config-Panel (generisch aus dem Manifest):** `/hexapod/config_manifest` lesen → **gruppierte
  Abschnitte mit Überschrift**; pro Param **Slider mit ± UND Eintipp-Feld**, Default + Hint + min/max
  anzeigen. Wert lesen = `get_parameters`, setzen = `set_parameters` (rosbridge). **Gating:**
  `gating:"standing"` → Slider disabled wenn `status.state != STANDING`. **Dynamischer Cap:**
  `dynamic_cap` → max = `min(manifest.max, status[cap])`. **Reject:** `set_parameters`-Antwort mit
  `successful=false` → `reason`-String als Fehler zeigen.
- **Dropdowns** (gait/tempo/stance) ← `/hexapod/capabilities`; gait/stance **standing-only**
  (disabled außerhalb STANDING). Auswahl: gait → Param `gait_pattern` (set), tempo → Tempo-Wechsel-
  Service/Param, stance → Set-Stance-direkt (§4.2).
- **Alerts-View** ← `/hexapod/alerts` (Liste, neueste oben) + **„Alles kopieren"** (Clipboard).
- **3D-Roboter-Viz** (Center-View-Option, aus Phase 4 reserviert): `/joint_states` (rosbridge) +
  URDF (statisch geladen o. aus `/robot_description`) → Modell animieren. **Kein** Status-Topic nötig.
- **Config-Persistenz:** keine (nur Laufzeit).

---

## 6. Contract-Touchpoints (→ nach Impl festzurren, §6)
- `/hexapod/status` (JSON-Felder), `/hexapod/capabilities` (JSON), `/hexapod/config_manifest`
  (JSON-Schema pro Eintrag), `/hexapod/alerts` (JSON), Set-Stance-direkt (Weg + Signatur).
- Whitelist-Params (node/param) als **stabile** Config-Naht dokumentieren. Version-Bump v0.9.

## 7. Doku-Nachzug (nach Umsetzung)
- `phase_5_..._progress.md` + `phase_5_..._test_commands.md`.
- READMEs (`hexapod_gait` Status-Publisher, Host-Paket HMI-Node) + `architecture.md`/`ai_navigation.md`
  (neue Topics + Config-Manifest-Naht). App-`CLAUDE.md`-Zeile „Aktuell: Phase 5".

> **§8 Implementierungs-Leitfaden (file-by-file)** folgt **nach** der Entscheidung der §4-Punkte
> (Host-Node, Tempo-Quelle, Set-Stance) — dann self-contained mit Snippets wie im Phase-4-Plan.

---

## 9. Nachtrag (App-Feedback) — `/hexapod_cycle_tempo` (Tempo-Dropdown-Setz-Weg)

**Lücke (App-Session gemeldet):** der Contract hatte **keinen** direkten Tempo-Setz-Weg — Tempo
lief nur über D-Pad (`_on_joy` → `_cycle_tempo`). Ein Tempo-**Dropdown** braucht aber einen
Setz-Pfad. (Gangart/Stance haben Cycle-Services im gait_node; Tempo wurde nie exponiert, weil es
Teleop-seitig in `joy_to_twist` liegt.)

**Fix (symmetrisch zu Set-Stance):** neuer **`/hexapod_cycle_tempo`-Service (`std_srvs/SetBool`,
`data=true` schneller / `false` langsamer)** in **`joy_to_twist`**, Callback ruft das bestehende
`_cycle_tempo`. Die App macht **cycle-to-target** (liest `tempo_idx` aus `/hexapod/tempo`, ruft
up/down bis Ziel) — exakt wie der Stance-Dropdown. **Kein neuer Message-Typ**, `/hexapod/tempo`
bleibt autoritativ (`_cycle_tempo` pflegt `_tempo_idx`), **standing-gated automatisch** (Tempo setzt
`cycle_time`=standing_only → gait_node rejected außerhalb STANDING → `_cycle_tempo` bricht sauber ab).

- **Logik:** `_cycle_tempo` bekommt einen **bool-Rückgabewert** (True = Request rausgegangen bzw.
  bereits am Limit / False = blockiert: pending oder gait-Param-Services nicht bereit); der D-Pad-
  Aufrufer ignoriert ihn, der Service mappt ihn auf `SetBool.Response.success`.
- **Tests:** `_cycle_tempo`-Return (ready+ok → True + idx+1; am Limit → True/no-op; `ready=False` →
  False; pending → False) via bestehende `_FakeParamClient`-Harness; Service-Wrapper gibt den
  Return als `success` zurück. **NICHT getestet:** echte App-cycle-to-target-Schleife (Live/App).
- **Progress:** `- [ ] P5.7b [ROS] /hexapod_cycle_tempo (SetBool) in joy_to_twist → Tempo-Dropdown-Setz-Weg (cycle-to-target); Test + Contract §2/§6a v0.9.1`
- **Contract:** §2 neuer Service (wie `cycle_gait`/`cycle_stance`) + §6a-Notiz; Version-Bump v0.9.1.
