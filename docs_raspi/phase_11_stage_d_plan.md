# Phase 11 — Stufe D — Plan

> **Status:** Plan, in Vorbereitung der Implementation. **Pending User-Freigabe der 4 offenen Fragen D-Q1..D-Q4.**
>
> **Parent-Plan:** [`phase_11_param_gui.md`](phase_11_param_gui.md)
> Stufe D — rqt-Setup-Doku + Save/Load-Workflow.
>
> **Vorbedingung:** Stage A + B + C abgeschlossen, Live-Param-Setup
> (Gait + Cal + Diagnostics) verifiziert.

---

## Ziel

Aus den drei Live-Param-Surfaces (Stage A gait_node, Stage B Plugin-Cal,
Stage C Diagnostic-Topic) ein **persistierbares User-Workflow** machen:

1. **Presets ladbar beim Launch** — statt `ros2 param set` einzeln tippen
2. **Setup-Doku** — wie User rqt_reconfigure + rqt_plot + rqt_topic in
   einem Multi-Plugin-Layout aufsetzt (incl. Stage-C-rqt_plot-Limitation
   dokumentiert)
3. **Convention für Preset-Files** — wo sie liegen, wie sie heißen,
   wie sie versioniert werden

**Was Stage D NICHT macht:**
- Keine neuen Node-Params (alle 14 Gait + 72 Cal + 1 Diagnostic schon da)
- Keine neuen Tests im Plugin/gait_node (Stage A/B/C deckt das ab)
- Kein Custom-rqt-Plugin (siehe Mutter-Plan-Entscheidung A)

---

## 🔍 Pre-Implementation Code-Inspection

### gait.launch.py (Stand 2026-05-20)

[`src/hexapod_gait/launch/gait.launch.py`](../src/hexapod_gait/launch/gait.launch.py) — 212 Zeilen.

- Deklariert **15 LaunchArgs** (alle 14 Gait-Params + `use_sim_time`)
- Übergibt sie als Dict an `gait_node`-Node-Aktion via `parameters=[{...}]`
- Defaults im LaunchArg-Block selbst kodiert (z.B. `default_value='0.03'`
  für step_height)

→ Stage-D-Adds: ein `params_file:=...`-Arg der die Defaults überschreibt.

### real.launch.py (Stand 2026-05-20)

[`src/hexapod_bringup/launch/real.launch.py`](../src/hexapod_bringup/launch/real.launch.py) — 173 Zeilen.

- Hat nur 2 LaunchArgs: `loopback_mode`, `serial_port`
- **Keine Plugin-Cal-Params direkt** — die kommen vom Plugin selbst über
  Stage-B `register_live_cal_params` (declare_parameter mit YAML-Defaults
  aus `servo_mapping.yaml`)
- Plugin-Cal-Persistenz läuft über Stage-B `/save_calibration`-Service →
  schreibt direkt `servo_mapping.yaml` zurück

→ Stage-D-Frage: ist hier ein `params_file:=...`-Arg sinnvoll? Plugin-
Cal-Persistenz hat schon einen eigenen Save/Load-Mechanismus (Stage B).

### sim.launch.py (Stand 2026-05-20)

[`src/hexapod_bringup/launch/sim.launch.py`](../src/hexapod_bringup/launch/sim.launch.py) — 243 Zeilen.

- Startet Gazebo + RSP + Controllers — **kein gait_node, kein
  Plugin-Cal**
- Cal ist im Sim irrelevant (Gazebo-Joints, keine PWM-Pulses)
- Gait-Tuning passiert wenn User parallel `gait.launch.py` startet

→ Stage-D-Frage: braucht sim.launch.py einen params_file-Arg? Antwort:
nein, kein gait_node hier. params_file ist nur für gait.launch.py sinnvoll.

### Existing `ros2 param dump`-Output

`ros2 param dump /gait_node` produziert standardmäßig:
```yaml
/gait_node:
  ros__parameters:
    body_height: -0.052
    cycle_time: 2.0
    ...
```

Direkt ladbar via `params_file:=<dieses-file>.yaml`.

`ros2 param dump /hexapodsystem` analog für die 72 Cal-Params + 1
Diagnostic-Toggle — aber **redundant** zur servo_mapping.yaml (Stage-B-
Save), siehe D-Q2 unten.

---

## ⚠️ Kritische Punkte (Self-Review vor Code-Beginn)

### 1. Plugin-Cal-Persistenz doppelt?

Plugin-Cal-Params können via Stage-B `/save_calibration` → `servo_mapping.yaml`
geschrieben werden ODER via Stage-D `ros2 param dump /hexapodsystem` →
generic-yaml. Beide Pfade existieren parallel.

**Risiko:** User dumped via param dump → erzeugt yaml, lädt es später
zurück über `params_file:=...`, ABER URDF-`calibration_file` zeigt noch
auf alte `servo_mapping.yaml`. Cal in Plugin-State (via dump-yaml) vs.
Cal in File-State (servo_mapping.yaml) divergieren → Plugin-Restart
würde alte Werte aus servo_mapping.yaml laden.

**Empfehlung:** Stage D fokussiert auf **gait-Params-Presets** (kein
File-Konflikt mit Stage B). Für Plugin-Cal weiter Stage-B-Save-Service
als kanonischen Weg.

### 2. params_file mit fehlenden Keys

YAML mit z.B. nur `body_height: -0.060` (rest ungenannt) — was passiert?
Bei ROS2 declare_parameter mit Default: die fehlenden Keys behalten den
Default-Wert.

**OK** — aber Doku-Hinweis: "Preset-Files dürfen Subset enthalten".

### 3. Range-Validation bei params_file-Load

Stage-A-ParameterDescriptor hat Range-Limits (z.B. body_height
[-0.100, -0.020]). Wenn params_file out-of-range hat, schmeißt rclcpp
einen Error beim declare_parameter. Plugin/Node startet nicht.

**OK** — das ist gewünschtes Verhalten (klare Fail-Fast statt silent
Cap). Doku-Hinweis: "Preset-Files müssen Range-konform sein".

### 4. rqt_plot-Limitation aus Stage C dokumentieren

User-Smoke C-T5 hat gezeigt dass rqt_plot `MultiArray.data[N]`-Indexing in
ROS-Jazzy unzuverlässig ist (Plus-Button ausgegraut). Stage-D Setup-Doku
muss das explizit erwähnen + Workaround empfehlen (CLI-echo).

---

## Offene Fragen für User-Review (D-Q1..D-Q4)

### D-Q1 — Wie wird `params_file` an die Nodes weitergereicht?

| Option | Mechanismus | Tradeoff |
|---|---|---|
| **A** Pro Launch-File ein dedizierter Arg | `gait.launch.py params_file:=preset.yaml` lädt nur Gait-Params. Plugin-Cal bleibt YAML-only (Stage-B-Service-Pfad) | Klar getrennt, explicit. User muss verstehen dass Cal anders persistiert wird (über `/save_calibration`) |
| **B** Ein gemeinsames `params_file`-Arg, Multi-Node-YAML | YAML enthält sowohl `/gait_node:` als auch `/hexapodsystem:`-Sektionen. Beide Launch-Files können es laden | Ein File für alles, leichter zu versionieren. Aber doppelte Source-of-Truth für Cal (yaml + servo_mapping.yaml) — verwirrend |
| **C** Kein Launch-Arg, nur `ros2 param load` nach Launch | Launch-Files unverändert. User: `ros2 param load /gait_node my_preset.yaml` nach jedem Launch | Einfachste Implementation, aber jeder Launch braucht manuellen extra-Schritt |

**Empfehlung: A** — Stage-B-Cal-Persistenz hat schon einen
spezialisierten Save-Service (`servo_mapping.yaml` mit Timestamp-Bak).
Stage-D-params_file fokussiert auf Gait-Params. Saubere Trennung der
zwei Persistenz-Pfade.

### D-Q2 — Welche Preset-Beispiele sollen committed werden?

| Option | Welche Files | Tradeoff |
|---|---|---|
| **A** 2 Presets: `defensive_walk.yaml` (langsam/sicher) + `current_state.yaml` (Snapshot der aktuellen Tuning-Session 2026-05-20) | Sofort funktional, zeigt Format, ist Referenz für künftige Cal-Sessions | 2 Files zu pflegen, müssen bei Range-Änderungen aktualisiert werden |
| **B** Nur 1 Preset: `default_walk.yaml` (= aktuelle Werte aus gait.launch.py-Defaults) | Minimaler Maintenance-Overhead, klar als "starting point" markiert | Kein Vergleichs-Preset für unterschiedliche Walking-Stile |
| **C** 3+ Presets: `defensive_walk`, `demo_walk`, `aggressive_walk`, `single_leg_test` | Reicher Katalog für unterschiedliche Use-Cases. Demo-Material für Phase 13 | Mehr Files, mehr Drift-Risiko, einige sind erfunden (kein Real-Tuning-Hintergrund bis Phase 13) |

**Empfehlung: A** — 2 Files sind Goldilocks: genug für „so sieht's aus,
so wird's geladen", ohne Maintenance-Overhead. Stage-E kommt sowieso mit
„Best-Param-Preset-YAMLs" für Sim-Tuning-Workshop.

### D-Q3 — Bash-Aliases — committed oder Doku-only?

| Option | Was wird angelegt | Tradeoff |
|---|---|---|
| **A** Optional als `tools/hexapod-shell-aliases.sh` mit Hinweis im README wie zu source-n | User entscheidet ob er es in `~/.bashrc` source-t. Repo-Pflicht ist niedrig | Manche User finden Aliases hilfreich, manche stört es. Beide Camps zufriedenzustellen |
| **B** Pflicht, in Setup-Doku als Standard-Workflow | Stage-D-Doku sagt „source diese Datei". Aliases werden Teil des dokumentierten Workflows | Forcing convenience — manche User wollen das nicht in ihrer bashrc |
| **C** Gar nicht — nur die Raw-Befehle in der Setup-Doku | Keine Aliases im Repo. User kopiert die Befehle bei Bedarf | Minimaler Repo-Aufwand, aber „Save-Walking-Preset" tippt sich mehrmals |

**Empfehlung: A** — Bonus für convenience-orientierte User, optional
gehalten. Bei Phase-13-Vollbringup besonders nützlich (viele
Cal-Sessions hintereinander).

### D-Q4 — rqt-Perspective-File im Repo?

| Option | Was wird committed | Tradeoff |
|---|---|---|
| **A** Ja, als `tools/hexapod-rqt.perspective` (rqt-export) | Ein-Klick-Wiederherstellung des Multi-Plugin-Layouts. Sofort funktional für neue User | Perspective-Files sind manchmal nicht portabel (Path-abhängig) — kann auf User-System breaken |
| **B** Nein, nur Setup-Doku beschreibt manuell wie aufzubauen | Setup-Doku wird länger, aber kein Portability-Risk | User muss bei jedem System-Wechsel neu konfigurieren |
| **C** Beide: committet perspective-File + Doku als Fallback | Robustest: wenn perspective bricht, kann User aus Doku rekonstruieren | Doppelte Pflege bei Änderungen |

**Empfehlung: A** — testen ob die Perspective portabel committable ist
(Versuch macht klug). Falls bei User-Verify Probleme: Plan-Korrektur auf
B oder C.

---

## Logik-Skizze

### D.0 — Vorbereitung

Plan-Doku (diese Datei) finalisiert + User-Freigabe der D-Q1..D-Q4.
test_commands.md Skelett. Build-Status grün
(hexapod_hardware 220/0/20, hexapod_gait 20/0/1, hexapod_bringup 18/0/0).

### D.1 — `params_file`-Arg in gait.launch.py (~30 min)

Erweitere [`src/hexapod_gait/launch/gait.launch.py`](../src/hexapod_gait/launch/gait.launch.py):

```python
# Zusätzlicher LaunchArg
params_file_arg = DeclareLaunchArgument(
    'params_file',
    default_value='',
    description=(
        'Optionales YAML-Preset-File mit gait_node-Params (siehe '
        'src/hexapod_gait/config/presets/). Bei nicht-leer: '
        'überschreibt die individuellen Launch-Args.'
    ),
)

# parameters=[]-Liste erweitern: erst die Inline-Defaults, dann
# (falls gegeben) das params_file (überschreibt by ROS2-Konvention).
gait_node = Node(
    ...,
    parameters=[
        {'gait_pattern': LaunchConfiguration('gait_pattern'), ...},  # bisherig
        ParameterFile(  # Stage D NEU
            param_file=LaunchConfiguration('params_file'),
            allow_substs=True,
        ),
    ],
)
```

Test: `ros2 launch hexapod_gait gait.launch.py params_file:=path/to/preset.yaml`
→ Node nutzt Preset-Werte statt LaunchArg-Defaults.

Bei leerem params_file: ROS2-rclpy behandelt das als „no file" → Inline-
Defaults gelten.

### D.2 — Preset-Verzeichnis anlegen (~20 min)

```
src/hexapod_gait/config/presets/
├── README.md
├── defensive_walk.yaml
└── current_state.yaml
```

**`README.md`** beschreibt:
- Format-Schema (yaml mit `/gait_node:` Top-Level + `ros__parameters`-Block)
- Convention für Filenamen (`<walking_style>.yaml`)
- Wie ein Preset gespeichert wird (`ros2 param dump /gait_node ...`)
- Wie ein Preset geladen wird (`params_file:=...`)

**`defensive_walk.yaml`** (Beispiel, langsam-sicher):
```yaml
/gait_node:
  ros__parameters:
    cycle_time: 4.0
    step_length_max: 0.03
    step_height: 0.025
    body_height: -0.050
```

**`current_state.yaml`** wird in D.5 dynamisch generiert (per
`ros2 param dump`) — zeigt User wie's geht.

### D.3 — rqt-Setup-Doku (~1 h)

Neue Datei `docs_raspi/phase_11_rqt_setup.md` mit:

**Sektion 1 — Multi-Plugin-Layout:**
- rqt-Standalone starten: `ros2 run rqt rqt`
- Plugins → Configuration → Dynamic Reconfigure (für Param-Slider)
- Plugins → Visualization → Plot (für /servo_pulses)
- Plugins → Topics → Topic Monitor (für /joint_states etc.)
- Perspective → Save Perspective As → `tools/hexapod-rqt.perspective`

**Sektion 2 — Save-Workflow:**
- Gait-Params snapshot: `ros2 param dump /gait_node --output-dir
  src/hexapod_gait/config/presets/ --filename my_preset`
- Plugin-Cal snapshot: via Stage-B Service `/save_calibration`
- WICHTIG: zwei verschiedene Persistenz-Mechanismen, nicht verwechseln

**Sektion 3 — Load-Workflow:**
- Gait-Preset: `ros2 launch hexapod_gait gait.launch.py
  params_file:=src/hexapod_gait/config/presets/defensive_walk.yaml`
- Plugin-Cal: via URDF `calibration_file`-param (kommt vom
  `/save_calibration` zurückgeschriebenes servo_mapping.yaml)

**Sektion 4 — rqt_plot-Limitation:**
- `MultiArray.data[N]`-Indexing in ROS-Jazzy hat Plus-Button-Ausgegraut-Bug
- Workaround: CLI `ros2 topic echo /hexapodsystem/servo_pulses`
- Phase-13-Polish: Custom-Message `HexapodPulses` mit per-Pin-Feldern

**Sektion 5 — Bash-Aliases (optional):**
- Hinweis auf `tools/hexapod-shell-aliases.sh`
- Was die Aliases tun
- Wie zu source-n

### D.4 — Bash-Aliases (~20 min)

Neue Datei `tools/hexapod-shell-aliases.sh`:

```bash
# Quick-source: source <(curl -s https://raw.git.../hexapod-shell-aliases.sh)
# Or: source ~/hexapod_ws/tools/hexapod-shell-aliases.sh

# Speichere aktuelle gait-Tuning-Session als Preset
hexapod-save-walking-params() {
  local name=${1:-current_state}
  ros2 param dump /gait_node \
    --output-dir ~/hexapod_ws/src/hexapod_gait/config/presets/ \
    --filename "${name}"
  echo "Saved /gait_node params to .../presets/${name}.yaml"
}

# Lade ein Preset beim Start
hexapod-load-walking-preset() {
  local name=${1:?usage: hexapod-load-walking-preset <preset-name>}
  ros2 launch hexapod_gait gait.launch.py \
    params_file:=~/hexapod_ws/src/hexapod_gait/config/presets/${name}.yaml
}

# Speichere Plugin-Cal (ruft Stage-B-Service)
hexapod-save-cal() {
  ros2 service call /save_calibration std_srvs/srv/Trigger
}
```

### D.5 — `current_state.yaml` auto-generieren (~10 min)

```bash
ros2 param dump /gait_node \
  --output-dir src/hexapod_gait/config/presets/ \
  --filename current_state
```

→ Ergibt `current_state.yaml` mit den 14 Live-Params. Wird mit-committed
als Beispiel.

### D.6 — rqt-Perspective committen (~10 min, optional/D-Q4-abhängig)

Nach Aufbau Multi-Plugin-Layout: rqt → Perspective → Export →
`tools/hexapod-rqt.perspective`.

### D.7 — Tests + Regression (~30 min)

- `colcon build --packages-select hexapod_gait hexapod_bringup`
- `colcon test ...` → keine Regression (Tests prüfen die LaunchArgs nicht,
  Adding eines neuen Args sollte transparent sein)

### D.8 — User-Smoke (~30 min)

- Save Workflow: `hexapod-save-walking-params my_test` → Preset in
  `presets/my_test.yaml`
- Load Workflow: `ros2 launch hexapod_gait gait.launch.py
  params_file:=src/hexapod_gait/config/presets/defensive_walk.yaml`
- rqt-Perspective öffnen via `ros2 run rqt rqt
  --perspective-file tools/hexapod-rqt.perspective`

### D.9 — README hexapod_gait + Self-Review

---

## Tests-Liste

| # | Test | Erwartung | Wer |
|---|---|---|---|
| D-T1 | `colcon build --packages-select hexapod_gait hexapod_bringup` | grün | Claude |
| D-T2 | `colcon test`: hexapod_gait 20/0/1, hexapod_bringup 18/0/0, hexapod_hardware 220/0/20 (alles unverändert) | Claude |
| D-T3 (User) | `ros2 launch hexapod_gait gait.launch.py` ohne params_file → Defaults wirken | User |
| D-T4 (User) | `ros2 launch hexapod_gait gait.launch.py params_file:=presets/defensive_walk.yaml` → cycle_time=4.0, step_length_max=0.03 sichtbar via `ros2 param get` | User |
| D-T5 (User) | `ros2 param dump /gait_node --output-dir ...` erzeugt valides YAML, das wiederum als params_file ladbar ist (Roundtrip) | User |
| D-T6 (User) | Bash-Aliases (falls D-Q3 = A): `hexapod-save-walking-params test_session` erzeugt yaml | User |
| D-T7 (User) | rqt-Perspective (falls D-Q4 = A): `ros2 run rqt rqt --perspective-file tools/hexapod-rqt.perspective` lädt Layout | User |

### Was bewusst NICHT in Stage D getestet wird

- **Sim-Tuning-Szenarien** (Stage E)
- **Plugin-Cal-Reload** über params_file (= D-Q1 Option B/C, durch Plan-
  Korrektur verworfen)
- **Tibia-Sim-Verifikation** (Stage E hat das als Cross-Phase-Pendenz)

---

## Progress-Checkliste

- [ ] D.1 phase_11_stage_d_plan.md (Plan-Doku) finalisiert + User-Freigabe der D-Q1..D-Q4
- [ ] D.2 phase_11_stage_d_test_commands.md Skelett
- [ ] D.3 `params_file`-Arg in gait.launch.py (D-Q1 Option A)
- [ ] D.4 Preset-Verzeichnis `src/hexapod_gait/config/presets/` mit README + 2 Files (D-Q2 Option A)
- [ ] D.5 `current_state.yaml` per ros2 param dump auto-generieren + committen
- [ ] D.6 rqt-Setup-Doku `docs_raspi/phase_11_rqt_setup.md`
- [ ] D.7 Bash-Aliases `tools/hexapod-shell-aliases.sh` (falls D-Q3 Option A)
- [ ] D.8 rqt-Perspective `tools/hexapod-rqt.perspective` (falls D-Q4 Option A)
- [ ] D.9 colcon build + Regression
- [ ] D.10 User-Smoke D-T3..D-T7
- [ ] D.11 README hexapod_gait Phase-11-Stage-D-Block
- [ ] D.12 Self-Review-Tabelle
- [ ] D.13 Stage-D-Notizen + Übergang Stage E

**Done-Kriterium D:** alle Bullets `[x]`, Self-Review ohne 🔴,
User-Smoke D-T3..D-T7 bestätigt.

---

## Erwartete Stage-D-Dauer

- D.0 Plan-Doku (diese Datei): ~45 min Claude (in Arbeit)
- D.1-D.2 Test-Doku + Build: ~30 min
- D.3 params_file-Arg: ~30 min
- D.4-D.5 Preset-Verzeichnis + current_state: ~30 min
- D.6 rqt-Setup-Doku: ~1 h
- D.7 Bash-Aliases: ~20 min
- D.8 rqt-Perspective: ~10 min
- D.9 Build + Test: ~15 min
- D.10 User-Smoke: ~30 min User
- D.11-D.13 README + Review + Notes: ~30 min

**Schätzung:** ~5 h Claude + 30 min User = **~1 d Gesamt** (matched
Mutter-Plan).
