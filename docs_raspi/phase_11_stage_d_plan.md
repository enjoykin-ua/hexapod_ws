# Phase 11 — Stufe D — Plan

> **Status:** Plan finalisiert mit User-Freigabe aller 4 Fragen
> (D-Q1=A, D-Q2=A, D-Q3=A, D-Q4=B; 2026-05-20). Ready für Implementation.
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

**Ausgangssituation:**
Gait-Params (Stage A, 14 Stück) haben heute keinen Save-Mechanismus —
nach gait_node-Restart sind alle Werte wieder auf den
gait.launch.py-Defaults. Plugin-Cal-Params (Stage B, 72 Stück) haben
BEREITS einen spezialisierten Save-Mechanismus: der
`/save_calibration`-Service schreibt aktuelle Werte zurück in
`servo_mapping.yaml` mit Timestamp-`.bak`-Versionsgeschichte. Plugin
lädt beim nächsten Start automatisch die aktualisierte YAML.

Stage D's Aufgabe ist primär: **Gait-Params persistierbar machen**.
Frage ist, ob der neue Mechanismus auch Plugin-Cal mit umfassen soll
oder beide getrennt bleiben.

#### Option A (✅ User-Entscheidung 2026-05-20) — getrennt

`gait.launch.py` bekommt einen neuen `params_file:=...`-LaunchArg, der
Gait-Presets aus YAML lädt. `real.launch.py` bleibt unverändert —
Plugin-Cal-Persistenz läuft weiter über den Stage-B-Save-Service.

**Workflow:**
- **Gait:** `ros2 param dump /gait_node > .../presets/my_walk.yaml` zum
  Speichern; `ros2 launch hexapod_gait gait.launch.py
  params_file:=.../my_walk.yaml` zum Laden
- **Cal:** `ros2 service call /save_calibration std_srvs/srv/Trigger`
  zum Speichern; beim nächsten Plugin-Launch automatisch geladen aus
  `servo_mapping.yaml`

**File-Layout:**
- `src/hexapod_gait/config/presets/` — Gait-Presets (NEU in Stage D)
- `src/hexapod_hardware/config/servo_mapping.yaml*` — Plugin-Cal (Stage B)

**Begründung der Wahl:**
- Klare Trennung — zwei verschiedene Use-Cases (Gait wechselt häufig,
  Cal ist semi-permanent)
- Plugin-Cal-Persistenz bleibt mit ihrer spezialisierten YAML-Struktur
  (Header-Banner, defaults-Block, calibrated_at-Metadaten) erhalten
- Kein Drift-Risiko zwischen zwei parallelen Persistenz-Pfaden für
  dieselben Werte
- Standard ROS2-Workflow (`ros2 param dump` + `params_file:=`) — kein
  Custom-Mechanismus zu erfinden

#### Option B (verworfen) — vereinheitlicht via Multi-Node-YAML

Beide Launch-Files akzeptieren denselben `params_file:=...`-Arg. Das
YAML kann mehrere Node-Sektionen enthalten:

```yaml
/gait_node:
  ros__parameters:
    body_height: -0.060
    cycle_time: 4.0
/hexapodsystem:
  ros__parameters:
    pin_15:
      pulse_zero: 1750
```

**Theoretischer Vorteil:** ein File für alles, leichter zu versionieren.

**Gründe für Ablehnung:**
- **Plugin-Cal hätte zwei Source-of-Truths** — das params-yaml und
  `servo_mapping.yaml`. Wenn User via params-yaml lädt aber später
  `/save_calibration` ruft, geht das in `servo_mapping.yaml` während
  das params-yaml outdated bleibt → Verwirrungs-Falle.
- Stage-B-`.bak`-Strategie würde genau diese Klasse von „welcher File
  ist der aktuelle?"-Bug vermeiden — durch Option B wäre der wieder
  drin.
- Stage-B's spezialisierte YAML-Struktur (Header, defaults-Block) wäre
  durch das generische params-yaml-Format nicht 1:1 reproduzierbar.

---

### D-Q2 — Welche Preset-Beispiele sollen committed werden?

**Ausgangssituation:**
Stage D legt ein neues Verzeichnis `src/hexapod_gait/config/presets/`
an. Dort kommen Beispiel-YAML-Files. Diese erfüllen mehrere Zwecke
gleichzeitig:

- **Format-Demo** — User sieht wie eine Preset-YAML strukturell aussieht
- **Funktionale Snapshots** — Walking-Stile auf Knopfdruck ladbar
- **Reference-Werte** — Baseline für künftige Tuning-Sessions
- **Roundtrip-Sanity** — File aus `ros2 param dump` beweist dass der
  Save-Workflow funktioniert
- **Demo-Material** — Phase 13 / Vorführungen brauchen reproduzierbare
  „press play"-Konfigurationen

**Wichtiger Cross-Phase-Kontext:** Stage E plant sowieso noch
„Best-Param-Preset-YAMLs für Sim-Tuning-Workshop" (Mutter-Plan). Was in
Stage D nicht gemacht wird, wird ggf. in Stage E nachgeholt — daher
ist „weniger Files in Stage D" nicht „endgültig weniger Files".

**Was Stage-D-Presets NICHT sind:** statische Posen für Initial /
Stand / Shutdown (= „Beine eingefahren", „aufgerichtet" etc.). Das
sind Pulse-Werte pro Pin und gehören ins Plugin-State-Management. Siehe
„Bewusst NICHT in Stage D" am Ende für die Phase-13-Pose-Management-
Pendenz.

#### Option A (✅ User-Entscheidung 2026-05-20) — 2 Files: `defensive_walk` + `current_state`

**`defensive_walk.yaml`** — manuell konfiguriert, konservative Werte
für sicheres Walking (langsamer Cycle, kleinere Stride, etc.):

```yaml
/gait_node:
  ros__parameters:
    cycle_time: 4.0
    step_length_max: 0.03
    step_height: 0.025
    body_height: -0.050
    # rest = launch defaults
```

**`current_state.yaml`** — per `ros2 param dump /gait_node` aus
aktueller Session erzeugt, enthält alle 14 Live-Params mit den aktuellen
Werten. Doppelter Zweck:
- **Roundtrip-Sanity** (zeigt User dass dump-load-Workflow funktioniert)
- **Versionierte Tuning-Baseline** („so war es am 2026-05-20")

**Begründung der Wahl:**
- Goldilocks-Maß: ein manuell kuratiertes Preset zeigt
  Konfigurations-Variation, ein Live-Snapshot zeigt Save-Workflow
- Echte Diversität — `defensive_walk` ist anders als die Defaults
- Wenig Drift-Risiko bei nur 2 Files
- Stage E ergänzt später weitere Walking-Stile (`demo_walk`,
  `aggressive_walk` etc.)

#### Option B (verworfen) — Nur 1 File `default_walk.yaml`

Ein einziges Preset = die aktuellen `gait.launch.py`-Defaults als YAML
exportiert.

**Theoretischer Vorteil:** minimaler Maintenance-Overhead, klar als
„Starting Point" markiert.

**Gründe für Ablehnung:**
- Kein Vergleichs-Preset für unterschiedliche Walking-Stile
- Redundant — dieselben Werte stehen auch in `gait.launch.py` als
  Launch-Args, das File doppelt sie nur in anderem Format
- Roundtrip-Sanity fehlt — User muss selbst dumpen um zu sehen ob das
  funktioniert

#### Option C (verworfen) — 3 Files `defensive_walk` + `demo_walk` + `aggressive_walk`

Drei klar verschiedene Walking-Stile, manuell kuratiert.

**Theoretischer Vorteil:** reicher Katalog, hoher Demo-Wert für
Phase 13, Spannweite zeigt was möglich ist.

**Gründe für Ablehnung:**
- 3 Files = 3× Drift-Risiko bei Stage-A-Param-Erweiterungen
- `aggressive_walk.yaml` wäre erfunden — keine Real-Tuning-Daten dass
  die Werte funktionieren (Hexapod könnte mit max Stride + kurzer
  cycle_time kippen)
- **Stage-E-Überschneidung:** genau diese drei sind in Stage E geplant.
  Stage D wäre nur Vorgriff mit Doppel-Arbeit-Risiko
- Wahl-Lähmung für User: 3 Optionen, welches nehmen?

#### Option D (verworfen) — 4 Files inkl. `single_leg_test`

Wie Option C, aber statt `aggressive_walk` ein `single_leg_test.yaml`
(`gait_pattern: single_leg_3`) für isolierte Bein-Diagnose.

**Theoretischer Vorteil:** Single-Leg-Preset zeigt die `gait_pattern`-
Variation aus Stage A.

**Gründe für Ablehnung:**
- Maintenance noch höher (4 Files)
- Single-Leg-Test ist Debug-Tool, würde besser in `presets/debug/`-
  Unter-Sektion gehören — extra Komplexität
- Stage E hat eigene Sim-Tuning-Sub-Stage die das nachholen kann

---

### D-Q3 — Bash-Aliases — committed oder Doku-only?

**Ausgangssituation:**
Nach Stage D hat der User mehrere wiederkehrende lange ros2-Befehle
(Gait-Preset save/load, Plugin-Cal-Save, Backup-Listing). Jeder
Befehl ist 80-100 Zeichen lang mit Pfaden, die bei Tippfehler
unbemerkt brechen können. Bei intensiven Cal-Sessions (Phase 13
Vollbringup) tippt User das 100+ mal pro Tag.

Bash-Funktionen als Convenience-Layer könnten das vereinfachen:
```bash
hexapod-save-walking-params my_session       # statt 80-char-ros2-dump
hexapod-load-walking-preset my_session       # statt 100-char-launch-cmd
hexapod-save-cal                             # statt ros2 service call ...
```

**Use-Cases-Tabelle (wann lohnt sich das?):**
| Use-Case | Aliases-Nutzen |
|---|---|
| Phase-13-Voll-Bringup, intensive Cal-Sessions | sehr — User tippt 100+ mal Save/Load |
| Demo / Workshop mit Live-Hexapod | sehr — Tippfehler-Vermeidung unter Druck |
| Normales Sim-Tuning ohne Cal | mittelmäßig |
| Einmaliger CI-Test | nicht nötig |

#### Option A (✅ User-Entscheidung 2026-05-20) — Optional als `tools/hexapod-shell-aliases.sh`

Datei `tools/hexapod-shell-aliases.sh` mit Bash-Funktionen (nicht
Aliases, weil Parameter wie `<name>` Funktionen erfordern). User
entscheidet selbst ob er das File in seine `~/.bashrc` source-t.

**Geplante Funktionen:**
- `hexapod-save-walking-params <name>` — `ros2 param dump /gait_node ...`
- `hexapod-load-walking-preset <name>` — `ros2 launch hexapod_gait
  gait.launch.py params_file:=...`
- `hexapod-save-cal` — `ros2 service call /save_calibration ...`
- `hexapod-list-presets` — `ls .../config/presets/`
- `hexapod-list-cal-backups` — `ls .../servo_mapping.yaml.bak-*`

**Discoverability-Strategie (Wichtig — sonst geht der Tool-Vorteil
verloren weil keiner weiß dass es existiert):**

1. **Top-Kommentar im Script selbst** (`tools/hexapod-shell-aliases.sh`):
   - Use-Case-Erklärung (wann nutzt man das?)
   - Source-Befehl als Copy-Paste
   - Liste aller Funktionen mit Kurzbeschreibung
   - Beispiel-Workflow für eine typische Cal-Session
   → Wer die Datei aufmacht (egal warum), sieht sofort alles Nötige
2. **Neuer `tools/README.md`** als Index:
   - Auflistung aller Tools im `tools/`-Verzeichnis mit One-Liner-Beschreibung
   - Zukunftssicher: weitere Tools landen dort und werden hier
     aufgelistet
   → Wer ins `tools/`-Verzeichnis schaut, findet eine Übersicht
3. **`docs_raspi/phase_11_rqt_setup.md`** (Stage-D-Setup-Doku, neu):
   - Eigene Sektion „Convenience Aliases (optional)" mit:
     - Source-Befehl
     - Tabelle der Funktionen
     - Beispiel-Cal-Session unter Verwendung der Aliases
   → Wer die Phase-11-Setup-Doku liest, kann sich entscheiden ob er
     die Aliases will
4. **README hexapod_gait + README hexapod_hardware**:
   - In den jeweiligen Phase-11-Sektionen ein 2-Zeiler:
     „Convenience: siehe `tools/hexapod-shell-aliases.sh` für
     `hexapod-save-walking-params` / `hexapod-save-cal` etc."
   → Wer in den Paket-READMEs nach Phase-11-Befehlen sucht, sieht den
     Pointer
5. **Memory-Eintrag (Claude-side)**:
   - Neuer Memory-Eintrag `project_phase11_convenience_aliases.md`
     dass diese Aliases existieren und wo sie liegen
   → Künftige Claude-Sessions sehen das Tool sofort

**Begründung der Wahl A:**
- Convenience für intensive User (Cal-Sessions, Demo-Setups)
- Kein Zwang — wer Aliases nicht mag, ignoriert die Datei
- Repo-Pflicht niedrig — eine Datei, wenig Maintenance
- Bei zsh/fish-Users funktioniert die Bash-Syntax meist auch (Funktionen
  sind weitgehend portabel) — bei fish nicht, akzeptiert

#### Option B (verworfen) — Pflicht in Setup-Doku als Standard-Workflow

Dasselbe File wie Option A, aber Setup-Doku verlangt das Source-en und
verwendet die Aliases überall statt Raw-Befehle.

**Theoretischer Vorteil:** einheitlicher User-Erfahrung, Setup-Doku
ist kürzer.

**Gründe für Ablehnung:**
- **Forcing Convenience** — User die keine Aliases mögen (oder zsh/fish
  haben) müssen erst Workaround finden
- **Risikofaktor** — wenn User die Datei nicht source-t, schlagen alle
  Doku-Befehle fehl mit „command not found"
- **Bash-Lock-in** — ignoriert dass andere Shells existieren

#### Option C (verworfen) — Gar nicht, nur Raw-Befehle in der Doku

Keine Aliases im Repo, Setup-Doku zeigt die langen ros2-Commands direkt.

**Theoretischer Vorteil:** minimaler Repo-Aufwand, shell-agnostisch.

**Gründe für Ablehnung:**
- Lange Befehle → Tippfehler-Risiko bei wiederholtem Tippen
- User wird inoffizielle Aliases selbst bauen → Fragmentierung
  (verschiedene User haben verschiedene Aliases mit verschiedenen Namen)
- Demo / Live-Cal-Stress wird unhandlich

---

### D-Q4 — rqt-Perspective-File im Repo?

**Ausgangssituation:**
`rqt` ist ein Qt-basiertes Container-Programm für ROS-GUIs. Jedes der
rqt_…-Tools (rqt_reconfigure, rqt_plot, rqt_topic, rqt_console) kann
standalone oder gemeinsam in einem rqt-Container laufen. Bisher haben
wir nur Standalone-Modus genutzt (3 verschiedene Terminals).

**rqt-Container-Modus** erlaubt ein einziges Fenster mit mehreren
Plugins parallel:

```
┌─────────────────────────────────────────────┐
│ rqt — Hexapod-Workspace                     │
├─────────────────┬───────────────────────────┤
│ rqt_reconfigure │  rqt_plot                 │
│ (72 Pin-Slider) │  (/servo_pulses live)     │
│ + 14 Gait-Params│                           │
├─────────────────┼───────────────────────────┤
│ rqt_topic       │  rqt_console              │
│ (Topic-Monitor) │  (Plugin-Logger live)     │
└─────────────────┴───────────────────────────┘
```

Aufbau dauert manuell ~2-3 min pro Session (8 Schritte: rqt starten,
4 Plugins via Menü laden, Fenster-Layout per Drag&Drop, Topic in
rqt_plot adden, Nodes in rqt_reconfigure auswählen).

Eine **rqt-Perspective** ist ein gespeicherter Snapshot dieses Layouts
(Plugin-Liste + Fenster-Positionen + Plugin-Settings als XML). Laden
via `rqt --perspective-file foo.perspective` → Layout
sofort wieder da. Speichern via rqt-Menü „Perspectives → Save
Perspective As".

**Tricky-Faktoren bei Perspective-Files:**
- Bildschirm-Auflösung-Abhängigkeit (Fenster-Positionen in Pixeln)
- Absolute Pfade in manchen Plugin-Settings
- Topic-Name-Abhängigkeit (wenn `/hexapodsystem` umbenannt wird, bricht
  die rqt_plot-Reference)
- ROS-Version-Drift (Format kann sich zwischen Distros ändern)

Die Frage ist: **wie helfen wir dem User das Multi-Plugin-Layout zu
rekonstruieren?**

#### Option A (verworfen) — Perspective committen + Doku als Fallback

Datei `tools/hexapod-rqt.perspective` (rqt-export) + Schritt-für-Schritt-
Anleitung in Setup-Doku als Fallback.

**Theoretischer Vorteil:** Ein-Klick-Setup für Standard-User,
reproduzierbar via Git, Doku als Sicherheits-Net.

**Gründe für Ablehnung:**
- Portability-Risk — Perspective-Files brechen leichter als Doku
  (Bildschirm-Auflösung, absolute Pfade, ROS-Version-Drift)
- Doppelte Pflege bei Layout-Änderungen
- Verifikations-Schwierigkeit — wir können bei Commit nicht sicher
  wissen ob die Perspective auf anderem System funktioniert

#### Option B (✅ User-Entscheidung 2026-05-20) — Nur Setup-Doku, keine Perspective-File

Keine Datei im Repo. In `docs_raspi/phase_11_rqt_setup.md` eine
ausführliche Schritt-für-Schritt-Anleitung wie das Layout manuell
aufzubauen ist.

**User-Workflow:**
```bash
rqt
# Doku öffnen + den 8 Schritten folgen
# (Optional: User speichert sich selbst eine Perspective lokal,
#  z.B. ~/.config/ros.org/rqt_gui.ini)
```

**Setup-Doku-Inhalt (Sektion in phase_11_rqt_setup.md):**
1. `rqt` starten (leeres Fenster)
2. Plugins → Configuration → Dynamic Reconfigure
3. Plugins → Visualization → Plot
4. Plugins → Topics → Topic Monitor
5. Plugins → Logging → Console
6. Fenster-Layout per Drag&Drop optimieren (Empfehlung: 2×2-Grid)
7. Im rqt_reconfigure → Nodes `/hexapodsystem` und `/gait_node`
   auswählen
8. Im rqt_plot → Topic `/hexapodsystem/servo_pulses/data[15]` adden
   (siehe Stage-C-Limitation: `+`-Button bei Indexing manchmal
   ausgegraut → Workaround mit CLI-echo)
9. Optional: User-Setup via „Perspectives → Save Perspective As"
   lokal speichern (NICHT ins Repo committen)

**Begründung der Wahl:**
- Kein Portability-Risk — Doku ist System-agnostisch und alterungsstabil
- Keine Datei zu pflegen (kein Drift zwischen Repo-File und Realität)
- User lernt rqt-Container besser kennen (gut für späteres
  Hexapod-Tuning ohne unsere Doku)
- Bei Phase-13-Setup-Variationen (anderer Monitor, anderer Workspace-
  Pfad) muss nichts angepasst werden
- Per-User-Perspective wird lokal gespeichert wenn gewünscht — bleibt
  User-spezifisch ohne im Repo zu sein

#### Option C (verworfen) — Beide: Perspective + Doku als Redundanz

Wie Option A, aber Doku ist gleichwertig zur Perspective.

**Gründe für Ablehnung:** doppelte Pflege ohne klaren Mehrwert über
Option A oder B.

#### Option D (verworfen) — Gar nichts erwähnen

Stage-D-Doku ignoriert rqt-Container-Modus komplett.

**Gründe für Ablehnung:** User würde die Mehrfenster-Bequemlichkeit nie
entdecken. Stage D ist genau darum da, den Workflow zu verbessern.

---

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

**Sektion 1 — Multi-Plugin-Layout (manueller Aufbau, D-Q4 Option B):**
- rqt-Container starten: `rqt` (leeres Fenster)
- Plugins → Configuration → Dynamic Reconfigure (für Param-Slider)
- Plugins → Visualization → Plot (für /servo_pulses)
- Plugins → Topics → Topic Monitor (für /joint_states etc.)
- Plugins → Logging → Console (für Plugin-Logger live)
- Fenster-Layout per Drag&Drop (Empfehlung: 2×2-Grid)
- Im rqt_reconfigure: `/hexapodsystem` + `/gait_node` selektieren
- Im rqt_plot: Topic `/hexapodsystem/servo_pulses/data[15]` adden
  (Hinweis Stage-C-Limitation: `+`-Button manchmal ausgegraut →
  CLI-echo-Workaround)
- Optional für persönlichen Komfort: „Perspectives → Save Perspective
  As" lokal speichern (z.B. unter `~/.config/ros.org/`). **Nicht ins
  Repo committen** — siehe D-Q4 Option B: Portability-Risk zu hoch

**Sektion 2 — Save-Workflow:**
- Gait-Params snapshot: `ros2 param dump /gait_node > src/hexapod_gait/config/presets/my_preset.yaml`
  (Hinweis: Jazzy hat kein `--output-dir`/`--filename` mehr → stdout-Redirect)
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
# (Jazzy: ros2 param dump nur stdout → Redirect via `>`)
hexapod-save-walking-params() {
  local name=${1:-current_state}
  local out=~/hexapod_ws/src/hexapod_gait/config/presets/${name}.yaml
  ros2 param dump /gait_node > "${out}"
  echo "Saved /gait_node params to ${out}"
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
ros2 param dump /gait_node > src/hexapod_gait/config/presets/current_state.yaml
```

→ Ergibt `current_state.yaml` mit den 14 Live-Params. Wird mit-committed
als Beispiel.

### D.6 — ENTFÄLLT (D-Q4 Option B gewählt — keine Perspective-File im Repo)

Statt rqt-Perspective committen → ausführliche Setup-Doku in D.3
beschreibt manuellen Aufbau. User kann sich lokal eine eigene
Perspective speichern (außerhalb des Repos).

### D.7 — Tests + Regression (~30 min)

- `colcon build --packages-select hexapod_gait hexapod_bringup`
- `colcon test ...` → keine Regression (Tests prüfen die LaunchArgs nicht,
  Adding eines neuen Args sollte transparent sein)

### D.8 — User-Smoke (~30 min)

- Save Workflow: `hexapod-save-walking-params my_test` → Preset in
  `presets/my_test.yaml`
- Load Workflow: `ros2 launch hexapod_gait gait.launch.py
  params_file:=src/hexapod_gait/config/presets/defensive_walk.yaml`
- rqt-Multi-Plugin-Layout: `rqt` + manueller Aufbau
  nach Setup-Doku-Schritten (D-Q4 Option B — keine Perspective-File)

### D.9 — README hexapod_gait + Self-Review

---

## Tests-Liste

| # | Test | Erwartung | Wer |
|---|---|---|---|
| D-T1 | `colcon build --packages-select hexapod_gait hexapod_bringup` | grün | Claude |
| D-T2 | `colcon test`: hexapod_gait 20/0/1, hexapod_bringup 18/0/0, hexapod_hardware 220/0/20 (alles unverändert) | Claude |
| D-T3 (User) | `ros2 launch hexapod_gait gait.launch.py` ohne params_file → Defaults wirken | User |
| D-T4 (User) | `ros2 launch hexapod_gait gait.launch.py params_file:=presets/defensive_walk.yaml` → cycle_time=4.0, step_length_max=0.03 sichtbar via `ros2 param get` | User |
| D-T5 (User) | `ros2 param dump /gait_node > .../my_session.yaml` erzeugt valides YAML, das wiederum als params_file ladbar ist (Roundtrip) | User |
| D-T6 (User) | Bash-Aliases (falls D-Q3 = A): `hexapod-save-walking-params test_session` erzeugt yaml | User |
| D-T7 (User) | rqt-Multi-Plugin-Layout via `rqt` + Doku-Schritte → User baut Layout in <5 min auf, verifiziert dass Doku korrekt ist (D-Q4 Option B) | User |

### Was bewusst NICHT in Stage D getestet wird

- **Sim-Tuning-Szenarien** (Stage E)
- **Plugin-Cal-Reload** über params_file (= D-Q1 Option B/C, durch Plan-
  Korrektur verworfen)
- **Tibia-Sim-Verifikation** (Stage E hat das als Cross-Phase-Pendenz)

---

## Bewusst NICHT in Stage D (Scope-Abgrenzung)

### Pose-Management (Initial / Stand / Shutdown) — Phase 13

User-Konzept 2026-05-20: „3 statische Posen" — Initial-Pose (Beine
kompakt, vom User vor Power-On physisch platziert), Stand-Pose
(aufgerichtet, bereit zum Laufen), evtl. weitere wie „knee-down".

**Was heute (Stage A-D) existiert:**
- Plugin-Boot mit Stagger über 18× ENABLE_SERVO (~900 ms) zum Verteilen
  des Inrush-Currents — Memory `project_phase13_initial_pose_presets.md`
- Servos gehen beim on_activate auf `pulse_zero` (= mechanische Mitte
  pro Servo)
- JTC interpoliert smooth zwischen aktuellem Joint-State und nächster
  Trajectory → wenn gait_node nach Plugin-Enable startet, fährt
  Roboter sanft in Stand-Pose

**Was für User's Konzept FEHLT:**
- Definition von „Initial-Pose" als named Pulse-Werte pro Pin (nicht
  generisch `pulse_zero`)
- Plugin-Erweiterung: beim `on_activate` named-Pose senden statt
  `pulse_zero` — kein Servo-Sprung gegen Schwerkraft
- State-Machine `init → stand → walking → stand → init → power-off`
  mit sanften Transit-Trajectories
- Sicherheits-Validation dass Transitionen kollisionsfrei sind

**Warum nicht Stage D:**
- Pose-Management sind **Pulse-Werte pro Pin** (= Plugin-Sache, ähnlich
  Stage-B-Cal). Stage-D-Presets sind **gait_node-Walking-Params** —
  völlig anderer Layer
- Es bräuchte Plugin-Erweiterung oder neuen Pose-Manager-Node — eigene
  Sub-Stage in Phase 13
- Memory-Eintrag `project_phase13_initial_pose_presets.md` markiert das
  als Phase-13-Material

→ **Stage D macht Walking-Konfig-Snapshots** (= gait_node-Param-Sets),
nicht Pose-Definitionen. Beides sind nützliche Persistenz-Mechanismen,
aber auf verschiedenen Abstraktions-Ebenen.

### Andere Scope-Ausschlüsse

- **Custom rqt-Plugin** (Mutter-Plan Architektur-Entscheidung A —
  Standard rqt_reconfigure reicht)
- **Foxglove-Integration** (Phase 13+ falls Handy-Zugriff gewünscht)
- **Auto-Cal-Tool für 15 verbleibende Servos** (Phase 13 Stufe B)
- **PS4-Controller-Erweiterung um Live-Param-Switching** (Phase 13+)

---

## Progress-Checkliste

- [x] D.1 phase_11_stage_d_plan.md (Plan-Doku) finalisiert + User-Freigabe D-Q1=A, D-Q2=A, D-Q3=A, D-Q4=B (2026-05-20)
- [ ] D.2 phase_11_stage_d_test_commands.md Skelett
- [ ] D.3 `params_file`-Arg in gait.launch.py (D-Q1 Option A)
- [ ] D.4 Preset-Verzeichnis `src/hexapod_gait/config/presets/` mit README + 2 Files (D-Q2 Option A)
- [ ] D.5 `current_state.yaml` per ros2 param dump auto-generieren + committen
- [ ] D.6 rqt-Setup-Doku `docs_raspi/phase_11_rqt_setup.md`
- [ ] D.7 Bash-Aliases `tools/hexapod-shell-aliases.sh` (D-Q3 Option A — User-bestätigt)
  - [ ] D.7a Script mit Funktionen + selbst-dokumentierendem Top-Kommentar (Use-Case, Source-Befehl, Funktions-Tabelle, Beispiel-Cal-Session)
  - [ ] D.7b `tools/README.md` als Tools-Verzeichnis-Index
  - [ ] D.7c „Convenience Aliases (optional)"-Sektion in `docs_raspi/phase_11_rqt_setup.md`
  - [ ] D.7d 2-Zeiler-Pointer in `src/hexapod_gait/README.md` Phase-11-Block
  - [ ] D.7e 2-Zeiler-Pointer in `src/hexapod_hardware/README.md` Phase-11-Block
  - [ ] D.7f Memory-Eintrag `project_phase11_convenience_aliases.md` für künftige Claude-Sessions
- ~~D.8 rqt-Perspective committen~~ — **entfällt** (D-Q4 Option B: nur Setup-Doku, kein Perspective-File im Repo)
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
- D.6 rqt-Setup-Doku: ~1 h (inkl. ausführliche Multi-Plugin-Aufbau-
  Schritte als Ersatz für entfallene Perspective-File, D-Q4 Option B)
- D.7 Bash-Aliases: ~20 min
- ~~D.8 rqt-Perspective: ~10 min~~ — entfällt
- D.9 Build + Test: ~15 min
- D.10 User-Smoke: ~30 min User
- D.11-D.13 README + Review + Notes: ~30 min

**Schätzung:** ~5 h Claude + 30 min User = **~1 d Gesamt** (matched
Mutter-Plan).
