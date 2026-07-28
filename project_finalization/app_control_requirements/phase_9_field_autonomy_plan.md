# Phase 9 — Feld-Autonomie (Boot-Autostart · sauberer Shutdown · Recovery-Wege) — Plan

> **Ziel:** der Hexapod ist **ohne Dev-Rechner** benutzbar. Raus ins Freie, dabei nur **Roboter +
> Handy im Controller**: Hotspot auf → Pi einschalten → App verbinden → aufstehen, fahren, Show →
> per Schalter **oder App** sauber herunterfahren. Und wenn unterwegs etwas hängt: **aus der App
> herauskommen**, ohne den Akku abzureißen.
>
> **Seite:** Pi-System + ROS-Config + App. **Status: 🟡 Plan — §4 entschieden, wartet auf die
> Umsetzungs-Freigabe.** Self-contained für einen frischen Chat.
> Vorgänger: Phase 8 (Show „Look-Around") 🟢. Contract:
> [`interface_contract.md`](interface_contract.md) — Services existieren bereits (§2a), nur eine
> Präzisierung nötig.

---

## 0. Ausgangslage (am Pi verifiziert)

Die Prüfung auf dem Pi (`hexapod-pi`, User `pi`, Workspace `/home/pi/hexapod_ws`) ergab:

| Befund | Bedeutung |
|---|---|
| `hexapod_always_on.service` **existiert nicht** | Ohne SSH läuft kein rosbridge → die App findet nichts. **Das ist der einzige Grund, warum der Feld-Start heute nicht geht.** |
| `Linger=no` | Eine User-Unit würde ohne Login gar nicht starten |
| `pi_hostname: ''` in **beiden** Configs, `git status` sauber | Der dritte Shutdown-Guard schlägt fehl (`host-mismatch`) → **das Poweroff-Kommando wird nie aufgerufen** |
| `sudo` verlangt Passwort (`exit=1`) | Selbst mit passendem Guard liefe `sudo shutdown -h now` aus einem Dienst ohne Terminal ins Leere |
| Pfad + installierte Unit-Datei ok | `%h/hexapod_ws` im Template stimmt; `share/hexapod_bringup/systemd/` wird mitinstalliert |
| nur `?? src/hexapod_gazebo/COLCON_IGNORE` untracked | harmlos (verhindert den Gazebo-Bau am Pi), `git pull` läuft konfliktfrei |

**Die wichtigste Konsequenz:** Der „sanfte Shutdown" per Schalter **endet heute nach dem
Relay-Aus**. Hinsetzen und Relay sind echt (gait_node + Plugin), der Pi läuft danach weiter — und
das anschließende Ziehen des Hauptschalters trennt ihn **hart** vom Strom, inklusive laufender
Schreibzugriffe. Das ist ein bestehendes Risiko für die SD-Karte und wird in Block A behoben.

**Die Kette, wie sie sein soll** (alle Teile existieren, nur ungeschärft):
```
Schalter am Roboter
  → Servo2040 (GET_INPUTS)
  → hexapod_hardware-Plugin  ← läuft NUR im schweren Stack
  → /hexapod/shutdown_request (latched)
  → shutdown_supervisor  ← Always-On-Schicht
  → /hexapod_shutdown (gait) → Hinsetzen → SAT → Relay aus
  → guarded_shutdown() → sudo shutdown -h now        ← Guard 3 + sudo fehlen heute
  (Backstop: kommt /hexapod/shutdown_complete nicht in 12 s → Relay-Aus erzwingen + trotzdem herunterfahren)
```

---

## 1. Logik-Skizze / Vorgehen

### Block A — Boot-Autonomie + sauberer Shutdown (Pi + Repo)

**A1 — `pi_hostname` setzen.** In `hexapod_supervisor/config/supervisor.yaml` **und**
`launcher.real.yaml`: `pi_hostname: 'hexapod-pi'`.

*Warum das im Repo stehen darf (und nicht lokal am Pi bleiben muss):* `guarded_shutdown` hat einen
**vom Parameter unabhängigen** Hard-Block auf die Dev-Hostnamen
([`os_shutdown.py`](../../src/hexapod_supervisor/hexapod_supervisor/os_shutdown.py), `DEV_HOSTS =
{'enjoykin-ubutu', 'enjoykin-ubuntu'}`). Auf dem Desktop greift der also weiterhin, egal was in der
YAML steht. Ein Wert, beide Hosts korrekt — **kein** lokal modifiziertes File am Pi, das bei jedem
`git pull` im Weg steht. *(Verworfen: Override-Datei am Pi — mehr bewegliche Teile, und genau die
lokale Modifikation, die wir vermeiden wollen.)*

**A2 — sudo-Recht + Kommando härten.**
1. Auf dem Pi ein eng gefasster sudoers-Eintrag (`/etc/sudoers.d/hexapod-shutdown`, angelegt mit
   `visudo -f`, weil das die Syntax vor dem Speichern prüft — ein kaputtes sudoers sperrt sonst aus):
   `pi ALL=(root) NOPASSWD: /usr/sbin/shutdown`
2. `shutdown_command` in beiden YAMLs auf **`sudo -n shutdown -h now`**.
   *Warum `-n`:* ohne Terminal würde `sudo` sonst auf eine Passworteingabe warten, die nie kommt —
   mit `-n` bricht es **sofort** ab und die Ursache steht im Log, statt dass der Shutdown hängt.

**A3 — Always-On als Dienst.** Unit aus dem Paket-Share nach `~/.config/systemd/user/` kopieren,
`systemctl --user enable --now`, `loginctl enable-linger pi`. Die Unit ist unverändert nutzbar
(`ExecStart` mit `%h/hexapod_ws` passt zum echten Pfad).

*Was sich dadurch NICHT ändert:* der schwere Stack startet weiterhin **nicht** automatisch — nur
rosbridge, `shutdown_supervisor` und `bringup_launcher`. Beim Einschalten bewegt sich nichts; die
App entscheidet ([D7]). Das bleibt bewusst so.

**A4 — Wissen sichern (der Neuaufsetz-Fall).** Alle drei Pi-Einstellungen kommen als **idempotenter
Block** in [`tools/provision_pi.sh`](../../tools/provision_pi.sh). Dort ist bereits ein Platzhalter
vorgesehen (Schritt 10, `provision_oled_button()`, „kommt mit Autonom-Doc") — dessen Text beschreibt
noch eine ältere Idee (zwei Services) und wird durch den heutigen Stand ersetzt: **eine** Unit +
On-Demand-Stack. Danach ist eine SD-Neuinstallation wieder ein einziger Skript-Aufruf.

Zusätzlich in die Doku (`ai_navigation.md` + `dev_workflow_desktop_to_pi.md`) die **zwei neuen
Betriebsregeln**:
- **Doppelstart:** läuft der Dienst, **nicht** zusätzlich manuell per SSH starten (zwei rosbridge auf
  Port 9090, zwei `bringup_launcher` auf denselben Service-Namen). Vorher `systemctl --user stop`.
- **Nach einem Update:** ändert sich nur der **schwere Stack** (gait_node/Engine/Teleop — der
  Normalfall, z.B. beim kommenden Free-Leg-Bau), genügt in der App **stoppen → starten**; der Stack
  wird bei jedem Start frisch als Subprozess geladen. Ändert sich die **Always-On-Schicht**
  (rosbridge-Launch, `bringup_launcher`, `hmi_status` **inkl. `hmi_config_manifest.yaml`**),
  zusätzlich `systemctl --user restart hexapod_always_on`.

### Block B — App-Lifecycle-Buttons (nur App-Seite)

Zwei Buttons, **beide in der Verbinden-/Start-Sicht** (User-Vorgabe) — nicht in der Fahr-Sicht, wo
ein Fehlgriff teuer wäre:

1. **„Pi herunterfahren"** → `/hexapod_pi_shutdown` (`std_srvs/Trigger`). **ROS-seitig fertig**
   ([`bringup_launcher.py`](../../src/hexapod_supervisor/hexapod_supervisor/bringup_launcher.py)):
   läuft der Stack → Block-F-Kette (Hinsetzen + Relay + Poweroff); läuft er nicht → direkter
   guarded Poweroff. Mit Bestätigungs-Dialog (Contract §2a).
   **Das ist der Rettungsanker:** funktioniert auch, wenn der Stack hängt (12-s-Backstop erzwingt
   Relay-Aus und fährt trotzdem herunter) — statt den Akku abzureißen.
2. **„Stack neu starten"** → `/hexapod_bringup_stop`, auf die Antwort warten, kurz Pause, dann
   `/hexapod_bringup_start`. Beide Services existieren; das ist reine Bündelung zweier Taps.
   Der Stop killt hart durch (SIGINT→TERM→KILL auf die Prozessgruppe) und wirkt daher auch auf einen
   hängenden Stack.

### Block C — Feld-Fail-safes + der App-Pfad bekommt sein Preset

**C1 — HW-Preset im App-Pfad** (User-Entscheidung, §4.1). Der real-Zweig von
`bringup_ondemand.launch.py` reicht künftig **`params_file:=hw_terrain.yaml`** an `gait.launch.py`
durch. Damit laufen im App-Betrieb dieselben HW-verifizierten Werte wie im 3-Terminal-Bringup:
Leveling `auto` (IMU-Balance + Terrain-Following), Tip-Schwellen, Slope-Schätzer und die
S4-Fußkontakt-Features (`adaptive_touchdown`, `adaptive_stand`, `slip_detection` mit den
H2.6-getunten Werten).

*Warum das mehr ist als Bequemlichkeit:* bisher startete der App-Betrieb mit **Code-Defaults**
(Leveling und alle Terrain-Features **aus**) — die Features mussten nach jedem Stack-Start im
Config-Panel neu aktiviert werden. Genau im Feld, wo sie am meisten bringen, waren sie am
wahrscheinlichsten aus.

**C2 — Comms-Loss-Absicherung.** Bricht das WLAN ab, bleibt der Roboter heute **bestromt stehen**
(`cmd_vel` bleibt aus → `cmd_vel_timeout` → STANDING). Der Param `comms_loss_sitdown_timeout`
(Code-Default **0 = aus**) kommt mit **25.0** ins `hw_terrain.yaml` — nach 25 s Funkstille setzt er
sich hin (Rest, **bestromt**; kein Shutdown, damit ein Reconnect wieder aufstehen lassen kann).
Ein kurzer Aussetzer lässt ihn also stehen, ein echter Abriss entlastet die Servos.

Der Wert wird im vorhandenen [`test_hw_terrain_preset.py`](../../src/hexapod_gait/test/test_hw_terrain_preset.py)
mitgepinnt (dort werden bereits die Slip-Werte gegen die Validator-Ranges geprüft) — sonst fällt eine
spätere Änderung niemandem auf.

⚠️ **Sim bleibt unverändert** (`0` = aus): sonst setzt sich der Roboter beim Entwickeln hin, sobald
der Stack ohne Teleop läuft. Die Sim-Presets bekommen den Wert **nicht**.

**C3 — Reconnect messen, dann entscheiden.** Ob die App nach einem WLAN-Abriss von selbst
zurückkommt, ist ungetestet. Erst messen (Stack läuft, Roboter steht, Hotspot ~15 s aus/an), dann
entscheiden, ob App-Arbeit nötig ist. Kein Blind-Bauen.

---

## 2. Tests-Liste (+ was bewusst NICHT)

| Test | Prüft | Wo |
|---|---|---|
| **T9.1** `pi_hostname`-Werte in beiden YAMLs gesetzt + gleich; `shutdown_command` nutzt `sudo -n` | Config-Drift | Unit-Test (Repo) |
| **T9.2** Guard-Logik unverändert korrekt: Dev-Host hart geblockt, Pi-Hostname passt, `enable=false` blockt | Sicherheit | vorhandener `test_os_shutdown_guard.py` (+ Ergänzung) |
| **T9.3** `colcon test` gesamt grün, Lint grün | keine Regression | Repo |
| **T9.4 (Pi)** Reboot → **ohne SSH**: App verbindet, „Start" bringt den Stack hoch | Kern-Deliverable A | Pi |
| **T9.5 (Pi)** Schalter umlegen → Hinsetzen, Relay, **Pi wirklich aus** (SSH tot, LED aus) | der reparierte Shutdown | Pi |
| **T9.6 (Pi/App)** „Pi herunterfahren" aus der App — **mit** laufendem Stack (Hinsetzen zuerst) **und ohne** (direkter Poweroff) | Rettungsanker | Pi + App |
| **T9.7 (Pi/App)** „Stack neu starten" während der Stack läuft → danach wieder verbind-/fahrbar | Recovery-Weg | Pi + App |
| **T9.8 (Pi)** Deploy-Zyklus: `git pull` + `colcon build` + `systemctl --user restart` → neuer Code aktiv (`ros2 param get` auf einen neuen Param) | die Update-Falle | Pi |
| **T9.9 (Sim)** `comms_loss_sitdown_timeout > 0`: cmd_vel verstummt → nach N s Hinsetzen; mit `0` unverändert | C1 ohne HW-Risiko | Sim |
| **T9.10 (Pi)** WLAN ~15 s weg: Roboter stoppt, kommt die App von selbst zurück? | C2-Messung | Pi + App |
| **T9.11 (Pi)** Provisioning-Block idempotent: zweiter Aufruf ändert nichts, meldet „bereits gesetzt" | Neuaufsetz-Fall | Pi |
| **T9.12 (Pi/App)** App-Bringup lädt das Preset: nach „Start" ist `leveling_enable=true`, `leveling_mode=auto`, die S4-Enables true und `comms_loss_sitdown_timeout=25` (`ros2 param get`) | C1 — der App-Pfad verhält sich wie der 3-Terminal-Bringup | Pi |
| **T9.13** `test_hw_terrain_preset.py` pinnt den neuen `comms_loss`-Wert + Validator-Range | Preset-Drift | Unit-Test |
| **T9.14 (Sim)** Sim-Bringup unverändert: `comms_loss_sitdown_timeout` bleibt 0, kein Auto-Hinsetzen im Leerlauf | keine Sim-Regression | Sim |

**Bewusst NICHT getestet / nicht gebaut:**
- **Watchdog** für eine *hängende* (nicht abgestürzte) Always-On-Schicht — vertagt, siehe §9
  [D-Feld-4]. `Restart=on-failure` deckt den Absturz ab.
- **Akku-/Undervoltage-Warnung** — der User hat eine Hardware-Spannungsanzeige; Software-Telemetrie
  bleibt im Backlog (D3).
- **Netzwerk-Layer** (WLAN-Reconnect des Pi zum Hotspot) — funktioniert bereits, ist
  NetworkManager-Sache, nicht ROS.
- **Automatischer Start des schweren Stacks beim Boot** — bewusst nicht ([D7]): der Roboter soll
  sich beim Einschalten nicht bewegen.

---

## 3. Progress-Checkliste (→ `phase_9_field_autonomy_progress.md`, Done-Vertrag)
```
Phase 9 (Feld-Autonomie):
- [ ] P9.1 [ROS] pi_hostname: 'hexapod-pi' in supervisor.yaml + launcher.real.yaml; shutdown_command auf 'sudo -n shutdown -h now' (T9.1/T9.2)
- [ ] P9.2 [Pi] sudoers-Eintrag /etc/sudoers.d/hexapod-shutdown via visudo (NOPASSWD nur fuer shutdown)
- [ ] P9.3 [Pi] systemd-User-Unit installiert + enable --now + enable-linger; Reboot-Test ohne SSH (T9.4)
- [ ] P9.4 [Pi] Schalter-Shutdown faehrt den Pi wirklich herunter (T9.5)
- [ ] P9.5 [ROS] provision_pi.sh: Platzhalter-Block 10 durch Autonomie-Block ersetzt (sudoers + Unit + linger, idempotent) (T9.11)
- [ ] P9.6 [ROS] Deploy-Regeln dokumentiert (Doppelstart, wann systemctl restart noetig) in ai_navigation + dev_workflow (T9.8)
- [ ] P9.7 [App] Button "Pi herunterfahren" in der Verbinden-Sicht (mit Bestaetigung) -> /hexapod_pi_shutdown (T9.6)
- [ ] P9.8 [App] Button "Stack neu starten" in der Verbinden-Sicht -> stop + start (T9.7)
- [ ] P9.9 [ROS] bringup_ondemand real-Zweig: params_file:=hw_terrain.yaml (Balance + S4 ab Stack-Start aktiv) (T9.12)
- [ ] P9.9b [ROS] comms_loss_sitdown_timeout: 25.0 in hw_terrain.yaml + im Preset-Test gepinnt; Sim unveraendert (T9.9/T9.13/T9.14)
- [ ] P9.10 [Pi/App] Reconnect nach WLAN-Abriss gemessen; Ergebnis dokumentiert, App-Arbeit nur falls noetig (T9.10)
- [ ] P9.11 [ROS] Unit-Tests + Lint gruen (T9.3)
- [ ] P9.12 [ROS] Contract-Praezisierung (v0.13.1) + Self-Review + Doku (README/architecture/progress/test_commands)
- [ ] P9.13 [Integration] Feld-Probe: nur Roboter + Handy, kompletter Zyklus inkl. Herunterfahren
```

---

## 4. Entscheidungen (vor Code geklärt)

**4.1 — HW-Preset im App-Pfad: JA** *(User-Entscheidung)*. Befund beim Planen: der real-Zweig von
[`bringup_ondemand.launch.py`](../../src/hexapod_bringup/launch/bringup_ondemand.launch.py) startet
`gait.launch.py` **ohne `params_file`** → im App-Betrieb liefen bisher die **Code-Defaults**
(`leveling_enable: false`, alle S4-Features aus). Künftig wird `hw_terrain.yaml` durchgereicht
(Block C1). *Verworfen:* so lassen und die Features nach jedem Start im Config-Panel setzen (genau
im Feld am fehleranfälligsten); eigenes „field.yaml" (zweites HW-Preset = zweite Wahrheit).
⚠️ **Eigener Testpunkt nötig** (T9.12), weil sich der App-Bringup dadurch spürbar ändert.

**4.2 — Comms-Loss: 25 s → Hinsetzen** *(User-Entscheidung)*. Wert kommt ins `hw_terrain.yaml`
(damit HW-Pfad scharf, Sim unverändert). **Kein** automatisches Aufstehen nach Reconnect — der User
drückt „Aufstehen" (sicherer; er entscheidet, ob der Roboter frei steht).

**4.3 — sudoers-Umfang: das Binary erlauben.** `NOPASSWD: /usr/sbin/shutdown` deckt auch
`shutdown -r`/`-c` ab; eine exakte Argument-Liste wäre in sudoers fehleranfälliger als sie nützt.
Vorher am Pi `command -v shutdown` prüfen (erwartet `/usr/sbin/shutdown`).

**4.4 — Reihenfolge: A1+A2 zuerst** (Shutdown reparieren), dann A3 (Autostart), dann B/C. So ist der
Feld-Zyklus früh sicher, statt zuerst bequem.

**4.5 — Wer führt die Pi-Schritte aus?** Wie bisher: der User. Alle Befehle kommen vollständig ins
`phase_9_field_autonomy_test_commands.md`, nicht in den Chat.

---

## 5. App-Seiten-Brief (Kern, Details im eigenen Brief nach der Freigabe)

- **Zwei Buttons, beide in der Verbinden-/Start-Sicht** (nicht in der Fahr-Sicht):
  **„Pi herunterfahren"** (mit Bestätigungs-Dialog) und **„Stack neu starten"**.
- Beide nutzen **vorhandene** Services — kein neues Interface, kein Contract-Bruch:
  `/hexapod_pi_shutdown` bzw. `/hexapod_bringup_stop` + `/hexapod_bringup_start` (alle
  `std_srvs/Trigger`).
- **„Pi herunterfahren" muss auch erreichbar sein, wenn der Stack NICHT läuft** — dann fährt der Pi
  direkt herunter. Das ist der Weg aus jeder Klemme (und ersetzt „Akku abreißen").
- **„Stack neu starten":** stop → auf `success` warten → ~2 s → start; danach über
  `/hexapod/bringup_running` prüfen, dass er wieder oben ist.
- Nach dem Herunterfahren bricht die Verbindung ab — das ist erwartet, die App sollte es als
  „Pi fährt herunter" anzeigen statt als Fehler.

## 6. Contract-Touchpoints (v0.13.1 — reine Präzisierung, kein Interface-Change)

- **§2a:** explizit festhalten, dass `/hexapod_pi_shutdown` **in beiden Zuständen** funktioniert
  (Stack läuft → Hinsetz-Kette; idle → direkter Poweroff) und dass er der vorgesehene Weg aus einem
  hängenden Stack ist (12-s-Backstop).
- **§2a:** „Stack neu starten" als App-Muster dokumentieren (stop → warten → start).
- Kein neues Topic, kein neuer Service, kein neuer Message-Typ.

## 7. Doku-Nachzug (nach Umsetzung)

- `phase_9_field_autonomy_{progress,test_commands}.md` + App-Brief.
- `ai_navigation.md`: neuer Abschnitt „Pi-Boot / Always-On / Deploy ändern" (Doppelstart-Falle,
  `systemctl restart`-Regel, wo `pi_hostname` lebt).
- `dev_workflow_desktop_to_pi.md`: Deploy-Sequenz um den `restart`-Schritt ergänzen.
- `README.md`: Quickstart-HW um „läuft ab Boot, kein SSH nötig" korrigieren.
- `tools/provision_pi.sh` (P9.5) + `tools_catalog.md`-Zeile.

## 8. Implementierungs-Leitfaden

1. **A1/A2 (Repo):** zwei YAMLs, dann Unit-Test T9.1 (Muster: `test_hw_terrain_preset.py` pinnt
   Preset-Werte — hier analog die Guard-Werte).
2. **Pi-Schritte** ins Test-Doc schreiben, User führt aus, Rückmeldung ins Progress-File.
3. **A4/P9.5:** `provision_pi.sh` — Block 10 ersetzen; jeder Schritt prüft vorher (`grep -q` auf die
   sudoers-Datei, `systemctl --user is-enabled`, `loginctl show-user … Linger`).
4. **C1:** je nach §4.1-Entscheidung entweder ins Preset oder als Launch-Argument im real-Zweig.
5. **App-Brief** schreiben, sobald §4 entschieden ist.

## 9. Design-Entscheidungen (mit Alternativen)

- **[D-Feld-1] `pi_hostname` ins Repo statt lokal am Pi.** Der `DEV_HOSTS`-Hard-Block macht das
  sicher; ein lokal modifiziertes YAML am Pi wäre bei jedem `git pull` im Weg (und wäre nach einem
  SD-Tod weg). **Verworfen:** Override-Datei am Pi, Environment-Variable.
- **[D-Feld-2] Eng gefasster sudoers-Eintrag** statt `NOPASSWD: ALL` oder polkit-Regel für
  `systemctl poweroff`. Ein Binary, kein Passwort im Klartext, per `visudo` syntaxgeprüft.
- **[D-Feld-3] `sudo -n`** statt `sudo`: ohne Terminal soll der Aufruf **scheitern und loggen**,
  nicht auf eine Passworteingabe warten, die nie kommt.
- **[D-Feld-4] Kein Watchdog (vertagt).** `Restart=on-failure` fängt Abstürze; ein *hängender*
  Dienst bräuchte einen Health-Check-Timer. Der hat aber einen Haken: der schwere Stack läuft als
  Subprozess **in derselben systemd-Control-Group**, ein Unit-Restart würde ihn mitreißen (Relay
  öffnet → der stehende Roboter sackt zusammen). Sauber wäre erst eine Trennung von rosbridge in
  eine eigene Unit. Aufwand + Testaufwand für ein Szenario, das noch nie aufgetreten ist →
  **erst bauen, wenn es real passiert** (dann sagen die Logs auch, wo es hing).
- **[D-Feld-5] Schwerer Stack startet weiterhin NICHT automatisch** ([D7] unverändert): beim
  Einschalten soll sich nichts bewegen. **Verworfen:** Auto-Standup beim Boot.
- **[D-Feld-6] Buttons in der Verbinden-Sicht, nicht in der Fahr-Sicht** *(User-Vorgabe)*: beides
  sind Lifecycle-Aktionen; in der Fahr-Sicht wäre ein Fehlgriff auf „herunterfahren" teuer.
- **[D-Feld-8] Der App-HW-Pfad lädt `hw_terrain.yaml`** *(User-Entscheidung)* statt mit
  Code-Defaults zu starten. Ein Preset als **eine** Wahrheit für den HW-Betrieb — egal ob per App
  oder 3-Terminal gestartet. **Verworfen:** Code-Defaults beibehalten (Features im Feld faktisch
  aus); ein zweites „field.yaml" (zwei HW-Wahrheiten, die auseinanderlaufen).
- **[D-Feld-7] Comms-Loss setzt hin, statt abzuschalten:** der Roboter bleibt bestromt und kann nach
  einem Reconnect wieder aufstehen. **Verworfen:** Auto-Shutdown bei Funkstille (zu drastisch, ein
  kurzer Aussetzer würde die Fahrt beenden).
