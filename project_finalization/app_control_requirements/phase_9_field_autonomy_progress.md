# Phase 9 — Feld-Autonomie — Progress

> **Done-Vertrag** aus [`phase_9_field_autonomy_plan.md`](phase_9_field_autonomy_plan.md) §3.
> Alle Bullets `[x]` = Phase fertig. Keine retroaktive Anpassung der Kriterien.
>
> **Stand: 🟢 ABGESCHLOSSEN** — alle Bullets `[x]`. Repo-Seite implementiert + unit-getestet
> (Contract v0.13.2), Pi-Schritte am Roboter verifiziert, App-Seite live bestätigt.
> Das Kern-Deliverable ist erreicht: **der Roboter ist ohne Dev-Rechner benutzbar.**
>
> **Mitgenommen in die Beobachtung** (kein offener Bullet, aber bewusst notiert): sporadische
> `controller_manager`-Overruns im App-Betrieb und ein dabei beobachteter Relay-Abfall nach dem
> Stack-Start. Analyse und Verdacht (Frame-Stille nahe der 200-ms-Watchdog-Schwelle unter CPU-Last)
> sind im Chat erarbeitet; der User beobachtet es im Betrieb und greift bei Wiederholung an.

---

## Checkliste

```
Phase 9 (Feld-Autonomie):
- [x] P9.1 [ROS] pi_hostname: 'hexapod-pi' in supervisor.yaml + launcher.real.yaml; shutdown_command auf 'sudo -n shutdown -h now' (T9.1/T9.2)
- [x] P9.2 [Pi] sudoers-Eintrag /etc/sudoers.d/hexapod-shutdown via visudo (NOPASSWD nur fuer shutdown)
- [x] P9.3 [Pi] systemd-User-Unit installiert + enable --now + enable-linger; Reboot-Test ohne SSH (T9.4)
- [x] P9.4 [Pi] Schalter-Shutdown faehrt den Pi wirklich herunter (T9.5)
- [x] P9.5 [ROS] provision_pi.sh: Platzhalter-Block 10 durch Autonomie-Block ersetzt (sudoers + Unit + linger, idempotent) (T9.11)
- [x] P9.6 [ROS] Deploy-Regeln dokumentiert (Doppelstart, wann systemctl restart noetig) in ai_navigation + dev_workflow (T9.8)
- [x] P9.7 [App] Button "Pi herunterfahren" in der Verbinden-Sicht (mit Bestaetigung) -> /hexapod_pi_shutdown (T9.6)
- [x] P9.8 [App] Button "Stack neu starten" in der Verbinden-Sicht -> stop + start (T9.7)
- [x] P9.9 [ROS] bringup_ondemand real-Zweig: params_file:=hw_terrain.yaml (Balance + S4 ab Stack-Start aktiv) (T9.12)
- [x] P9.9b [ROS] comms_loss_sitdown_timeout: 25.0 in hw_terrain.yaml + im Preset-Test gepinnt; Sim unveraendert (T9.9/T9.13/T9.14)
- [x] P9.10 [Pi/App] Reconnect nach WLAN-Abriss gemessen; Ergebnis dokumentiert, App-Arbeit nur falls noetig (T9.10)
      -> aus dem App-Code beantwortet statt gemessen: es gibt KEINEN Auto-Reconnect (RosbridgeClient,
         seit Phase 8) -> die Messung haette nur bestaetigt, was der Code deterministisch vorgibt.
         Ergebnis dokumentiert (s.u.), App-Arbeit fuer Phase 9 nicht noetig, Auto-Reconnect = Phase-10-Punkt.
- [x] P9.11 [ROS] Unit-Tests + Lint gruen (T9.3)
- [x] P9.12 [ROS] Contract-Praezisierung (v0.13.1) + Self-Review + Doku (README/architecture/progress/test_commands)
- [x] P9.13 [Integration] Feld-Probe: nur Roboter + Handy, kompletter Zyklus inkl. Herunterfahren
- [x] P9.14 [ROS] Freeze-Guard fuer die Sequenz-Services (sit_down/stand_up/shutdown/cycle_stance/show_toggle) — Reject statt wirkungslosem success (T9.15/T9.16)
- [x] P9.15 [ROS] Contract v0.13.2: performed-Marker als stabiler Vertragstext, gait_delay<->App-Timeout-Kopplung, Freeze-Reject
```

**Sim-Abnahme (Desktop) erledigt:**
- **T9.14** ✅ `comms_loss_sitdown_timeout` bleibt in der Sim `0.0` — kein Auto-Hinsetzen im
  Leerlauf. *(Nebenbefund: `leveling_enable` ist in der Sim `True` — das ist der Launch-Default von
  `ramp_walk.launch.py` aus der A5-Arbeit, kein Phase-9-Effekt. Erwartung im Test-Doc korrigiert.)*
- **T9.17** ✅ Freeze-Guard live: `sit_down`/`stand_up` liefern `success=False` mit dem
  Klartext-Grund inkl. Ausweg; `recover` bleibt erreichbar; danach greift `sit_down` wieder
  (`sitting down (Rest, powered)`, Roboter endet auf dem Bauch). Die `service not available`-Logs
  für `safety_freeze`/`safety_reset` sind der erwartete Sim-Skip (Plugin-Services, nur HW).

**Pi-Abnahme (am Roboter) erledigt:**
- **P9.2** ✅ sudoers-Eintrag greift — nach `sudo -k` (Cache verworfen) liefert
  `sudo -n shutdown --help` `exit=0`, `sudo -n true` dagegen `sudo: a password is required` /
  `exit=1`. Damit ist belegt: passwortlos **nur** `/usr/sbin/shutdown`, kein breites NOPASSWD
  ([D-Feld-2] wie entworfen). `command -v shutdown` = `/usr/sbin/shutdown` (Pfad wie im Plan §4.3
  erwartet).

- **§2.3** ✅ Guard-Werte am Pi verifiziert: `pi_hostname: 'hexapod-pi'` +
  `shutdown_command: 'sudo -n shutdown -h now'` in **beiden** Configs (`supervisor.yaml` Z. 17/22,
  `launcher.real.yaml` Z. 19/22), Master-Arm `enable_os_shutdown: true` in beiden, und `hostname`
  liefert exakt `hexapod-pi`. Damit sind alle drei Guards des Schalter-Pfads scharf — offen ist nur
  noch der Live-Nachweis (T9.5).

- **P9.4 / T9.5** ✅ **Der Schalter fährt den Pi wirklich herunter** — Kette am Roboter komplett
  durchgelaufen (Hinsetzen → Relay → Poweroff), der Pi war anschließend aus. Damit ist der
  Block-A-Befund aus Plan §0 behoben: vorher endete die Kette nach dem Relay-Aus (`host-mismatch`),
  der Pi lief weiter und wurde am Hauptschalter hart getrennt (SD-Karten-Risiko).

- **§3.1** ✅ Always-On-Dienst eingerichtet: Unit nach `~/.config/systemd/user/` installiert,
  `enable` (Symlink in `default.target.wants`), **gestartet (active)**, `Linger` aktiv. Der neue
  Self-Check meldet alle vier Zeilen grün → `FELD-BEREIT`. **P9.3 bleibt offen bis T9.4** (der
  Reboot-Test ohne SSH ist der eigentliche Nachweis des Bullets).

- **P9.3 / T9.4** ✅ **Reboot-Test ohne SSH bestanden** — nach `sudo reboot` kam die Always-On-Schicht
  von selbst hoch (systemd-User-Dienst + Linger, **keine** SSH-Sitzung nötig); die App verband sich
  auf die Pi-IP, „Start" brachte den schweren Stack hoch, „Aufstehen" lief durch. Keine Fehler.
  **Damit ist das Kern-Deliverable der Phase erreicht: der Roboter ist ohne Dev-Rechner benutzbar.**

- **P9.7 / P9.8 / P9.13** ✅ **vom User bestätigt** — die beiden App-Buttons („Pi herunterfahren",
  „Stack neu starten") sind live gefahren, ebenso die Feld-Probe (nur Roboter + Handy, kompletter
  Zyklus inklusive Herunterfahren). Keine Fehler gemeldet. *(Abgehakt auf Bestätigung des Users; die
  Einzelausgaben der Testschritte §4/§5/§6 liegen nicht als Protokoll vor.)*

**App-Seite gemeldet fertig** (P9.7/P9.8): beide Buttons in der Verbinden-Sicht verdrahtet,
`interpretShutdown` trennt SHUTTING_DOWN / NOT_PERFORMED / FAILED, Restart-Sequenz mit
`show_mode=none` → `sit_down`-Retry (1 s) → Stop → 2 s → Start → 40 s auf den ersten
`/hexapod/status`-Tick, Shutdown-Button nie durch fremdes `pendingAction` gesperrt.
Offen dort: die zwei Live-Tests (Sim-E2E + HW).

---

## Was gebaut wurde (Repo-Seite)

### Der reparierte Shutdown (P9.1)
`hexapod_supervisor/config/supervisor.yaml` **und** `launcher.real.yaml`:
- `pi_hostname: 'hexapod-pi'` (war `''` → `guarded_shutdown` meldete `host-mismatch`, der Poweroff
  feuerte **nie**). Sicher im Repo, weil `os_shutdown.DEV_HOSTS` den Dev-Rechner **parameter-
  unabhängig** hart blockt.
- `shutdown_command: 'sudo -n shutdown -h now'` — `-n` (non-interactive), damit der Aufruf aus einem
  Dienst ohne Terminal **sofort scheitert und loggt**, statt auf ein Passwort zu warten.

### Der App-Pfad bekommt sein Preset (P9.9/P9.9b)
`bringup_ondemand.launch.py` (real-Zweig) reicht `params_file:=hw_terrain.yaml` durch. **Vorher lief
der App-Bringup mit Code-Defaults** — Leveling und alle S4-Fußkontakt-Features **aus**. Ausgerechnet
im Feld, wo sie am meisten bringen, waren sie am wahrscheinlichsten nicht aktiv.
Im Preset neu: `comms_loss_sitdown_timeout: 25.0` (nach 25 s Funkstille setzt er sich hin — bestromt,
kein Shutdown).

### Provisioning (P9.5)
`tools/provision_pi.sh` Schritt 10 (bisher Platzhalter „kommt mit Autonom-Doc") ersetzt durch
`provision_shutdown_sudoers()` + `provision_always_on_service()` — beide idempotent
(`sudo test -f`, `cmp -s`, `systemctl --user is-enabled`, `Linger=yes`). sudoers wird über
`visudo -cf` **syntaxgeprüft**, bevor die Datei aktiv wird. Der OLED-Rest bleibt als
`provision_oled()` stehen; der GPIO-Button-Teil des alten Platzhalters ist obsolet (der Schalter
läuft über den Servo2040).

### Tests (P9.11)
- **neu** `hexapod_supervisor/test/test_shutdown_config_pinned.py` (4 Tests): `pi_hostname` in
  **beiden** Configs, `sudo -n`, Master-Arm an, **Konsistenz zwischen den Configs** (sonst hätte ein
  Weg — Schalter oder App-Button — eine andere Wahrheit als der andere).
- **erweitert** `test_hw_terrain_preset.py` (+3): Comms-Loss-Wert gepinnt, Validator-Range,
  **keine Struktur-Params im Preset** (`auto_standup_on_start` etc. würden die Launch-Args
  überschreiben → der Roboter stünde beim App-Start unaufgefordert auf).
- **Gesamt: 1021 Tests grün, 0 Fehler** (gait 530, teleop 63, supervisor 38, bringup inkl.
  launch_test), Lint grün.

---

## Self-Review (CLAUDE.md §4, Pflicht vor „fertig")

| # | Punkt | Bewertung | Status |
|---|---|---|---|
| 1 | **`params_file` überschreibt Launch-Args** — enthielte `hw_terrain.yaml` ein `auto_standup_on_start`, würde der Bauch-Start ausgehebelt und der Roboter stünde beim App-Start von selbst auf | echter Fund | **OK**: Preset geprüft (enthält nur Regelkreis-Params) + Test `test_preset_has_no_structural_params` verhindert die Regression |
| 2 | **Guard-Werte in zwei Configs** — wird nur eine gepflegt, ist genau einer der beiden Shutdown-Wege still kaputt | echter Fund | **OK**: `test_both_configs_agree` pinnt die Gleichheit |
| 3 | **Preset gilt jetzt für BEIDE HW-Startwege** (3-Terminal + App) — eine Änderung wirkt doppelt | bewusst | **OK (dokumentiert)**: Warnhinweis im Preset-Header ([D-Feld-8]: ein Preset = eine Wahrheit) |
| 4 | **Schalter braucht laufenden Stack** (Plugin liest ihn) — ohne Stack kein Schalter-Shutdown | bewusst | **OK (dokumentiert)**: Contract §2a + ai_navigation; der App-Button ist der Weg ohne Stack |
| 5 | **Dienst-Restart reißt den schweren Stack mit** (Subprozess in derselben Control-Group) — relevant, falls jemand später einen Watchdog baut | Risiko für später | 🟢 im Plan §9 [D-Feld-4] festgehalten, Watchdog bewusst vertagt |
| 6 | **`foot_contact_debug_enable: true`** im Preset erzeugt im Feld dauerhaft Diagnose-Logs (SD-Schreiblast) | 🟡 vormerken | 🟡 **später**: bewusst nicht geändert, weil dasselbe Preset noch für die HW-Diagnose genutzt wird. Wenn die Stufe-8-Messungen durch sind, auf `false` setzen |
| 7 | **Comms-Loss wirkt auch beim 3-Terminal-Bringup** (gleiches Preset) — dort ist es ohne Teleop leichter auszulösen | Nebenwirkung | **OK**: 25 s ist großzügig; ein Bench-Test ohne Teleop-Publisher setzt den Roboter nach 25 s hin — im Zweifel per `ros2 param set … 0.0` abschalten |
| 8 | **Sim-Regression?** Der Sim-Pfad (`ramp_walk`/`rubicon_walk`) lädt weiterhin seine eigenen Presets, `comms_loss` bleibt dort 0 | geprüft | **OK**: T9.14 im Test-Doc als Live-Gegenprobe |
| 9 | **sudoers-Fehler sperrt aus** | Risiko | **OK**: Skript nutzt `visudo -cf` vor `install`; im Test-Doc der manuelle Weg ebenfalls über `visudo -f` |
| 10 | **`provision_pi.sh` braucht einen gebauten Workspace** (Unit-Vorlage kommt aus dem `share/`) — beim allerersten Lauf auf frischem Pi fehlt sie | Reihenfolge | **OK**: Schritt meldet es und trägt sich als manueller Nachtrag ein („nach colcon build erneut ausführen") — das Skript ist idempotent |
| 11 | **Reboot-Verhalten des Dienstes ungetestet** (nur Repo-Seite fertig) | offen | 🟡 **P9.3/T9.4** durch den User |
| 12 | **`hostname` ist jetzt an einer Stelle im Repo gepinnt** — wird der Pi je umbenannt, schlägt der Test fehl | gewollt | **OK**: genau das soll auffallen (statt still keinen Poweroff mehr zu haben) |
| 13 | **Sequenz-Services meldeten im Freeze `success=true` und taten nichts** (der Tick ist gegated, der State aber unverändert) — die App wartete deshalb 15 s auf ein `SAT`, das nie kam, und stoppte hart | echter Fund (App-Integration) | 🔴→**OK**: Freeze-Guard in `sit_down`/`stand_up`/`shutdown`/`cycle_stance`/`show_toggle`, 17 Tests in `test_frozen_guards.py` |
| 14 | **Der Ausweg darf nie zu sein** — ein zu breiter Guard hätte `recover` mitblockiert | Risiko beim Fix | **OK**: `estop`/`recover`/`pi_shutdown` + reine Werte-Setzer bewusst ausgenommen, je ein Test |
| 15 | **Abgelehnter Shutdown darf nicht nachwirken** (`_relay_off_after_sat` würde sonst beim nächsten SAT feuern) | Detail beim Fix | **OK**: Reject **vor** dem Setzen des Flags, Test `test_sitdown_does_not_arm_relay_off_while_frozen` |
| 16 | **`performed=…` ist jetzt Vertragstext** (die App parst den Substring) — eine „harmlose" Log-Umformulierung würde die App brechen | neue Kopplung | **OK (dokumentiert)**: im Contract §2a als stabiler Marker festgeschrieben (v0.13.2) |
| 17 | **Die App verlässt sich jetzt auf `status.safety_frozen`** als primäres Freeze-Signal (besser als Text-Parsing) — es gab aber **keinen Test**, der garantiert, dass das Feld während des Freeze weiterhin gepublisht wird | echter Fund (App-Nachtrag) | 🔴→**OK**: 3 Tests in `test_frozen_guards.py` (Feld ist true im Freeze · Status-Timer läuft trotz gegatetem Tick weiter · nach `recover` wieder false) + Garantie im Contract §6a |
| 20 | **Grenzen des neuen Self-Checks** — er prüft `systemctl is-active`, **nicht** ob die vier Always-On-Nodes wirklich laufen (ein aktiver Dienst mit gecrashtem rosbridge wäre grün); und er liest nur `supervisor.yaml`, nicht `launcher.real.yaml` (der App-Pfad) | bewusst | **OK (dokumentiert)**: `ros2 node list` bleibt im Test-Doc-Prüfblock (bräuchte im Skript ein gesourctes ROS-Env + Wartezeit); die Config-Gleichheit pinnt `test_shutdown_config_pinned.py` im Repo, und lokale Pi-Edits sind per [D-Feld-1] ohnehin ausgeschlossen |
| 21 | **Skript-Änderung am Desktop nicht ausführbar getestet** (Architektur-Guard blockt x86, und `sudo`/`shutdown` auf dem Dev-Host sind tabu) | Verifikations-Lücke | **OK, bewusst**: verifiziert wurden `bash -n`, die `pi_hostname`-Extraktion gegen die echte YAML (Treffer/leer/fehlend), alle Fehlerzweige unter `set -euo pipefail` (kein Abbruch) und der Port-Check gegen einen echten Listener auf 9090 (erkannt / nach dem Schließen korrekt nicht erkannt). **Der Live-Beleg ist der §3.1-Lauf am Pi** |
| 19 | **§2.2-Prüfung war falsch-positiv möglich:** die beiden `sudo -n`-Checks liefen unmittelbar nach `sudo visudo` — der sudo-**Timestamp-Cache** (~15 min) lässt sie auch dann mit `exit=0` durchgehen, wenn der sudoers-Eintrag gar nicht greift. Der Dienst hat diesen Cache nicht → der Poweroff wäre erst in §2.4 aufgefallen, mit falscher Fährte | echter Fund (Pi-Live) | **OK**: Test-Doc §2.2 um `sudo -k` vor der Prüfung ergänzt + Klarstellung, dass `sudo -n true` bei eng gefasstem Eintrag korrekt `exit=1` liefert und nur die `shutdown --help`-Zeile zählt |
| 18 | **Sim-Sicherheit belegt statt angenommen:** Dev-Hostname ist `enjoykin-ubutu` und steht in `DEV_HOSTS` → Hard-Block greift; zusätzlich `pi_hostname='hexapod-pi'` ≠ Dev-Host → Guard 3 blockt ebenfalls | verifiziert | **OK**: der Desktop kann sich auch bei App-Tests nicht abschalten (doppelt abgesichert) |

---

## Beobachtung: `test_real_launch_loopback` ist zeitkritisch

Bei einem Testlauf unter Last (parallele colcon-Jobs) schlug
`hexapod_bringup / test_all_controllers_active` einmalig fehl: `leg_6_controller` war zum
Prüfzeitpunkt noch nicht gespawnt (5 von 6 aktiv). Zwei Wiederholungen — isoliert und in der vollen
Suite — waren grün. **Kein Zusammenhang mit Phase 9** (der Test fährt `real.launch.py` im
Loopback, nicht den geänderten App-Pfad); es ist Spawner-Timing. Nicht „wegdefiniert", sondern hier
notiert: **tritt es häufiger auf, gehört die Warte-/Retry-Logik des Tests angefasst**, nicht der
Test selbst entschärft.

## Offene Punkte / Nachträge

- **P9.2/P9.3/P9.4 (Pi):** sudoers, systemd-Dienst, Schalter-Test — Befehle stehen im
  [Test-Doc](phase_9_field_autonomy_test_commands.md) §2/§3.
- **P9.7/P9.8 (App):** zwei Buttons — [App-Brief](phase_9_app_brief.md).
- **P9.10 — beantwortet (App-Session):** die App hat **bewusst keinen Auto-Reconnect**
  (`RosbridgeClient`, seit Phase 8): nach WLAN-Abriss steht sie auf `ERROR`/`DISCONNECTED`, der
  Nutzer drückt „Verbinden". **Für den Shutdown ist das genau richtig** (der Abbruch dort ist
  erwartet und soll keinen Reconnect-Sturm auslösen). Für den WLAN-Abriss im Feld heißt es: manuell
  neu verbinden — und wegen des 25-s-Comms-Loss-Fail-safe danach ggf. erst „Aufstehen".
  → **Automatischer Reconnect ist ein eigener App-Punkt für Phase 10** (kein Interface-Change).
- **Befund für die App-Seite (aus der Rückfrage der App-Session):** `bringup_stop` nimmt dem
  Roboter **sofort das Drehmoment** — `on_deactivate` schickt bewusst Disable-Frames, und bei einem
  harten Kill greift der **FW-Watchdog nach 200 ms** (Relay fällt). Ein stehender Roboter **sackt
  zusammen**. Konsequenz: die App fährt vor einem geplanten Restart erst `/hexapod_sit_down` (wenn
  der Stack noch antwortet) und stoppt erst danach; bei hängendem Stack hart stoppen **mit Warnung**.
  Steht im App-Brief §3.
- 🟢 **Befund P9.3 (Pi-Live) — Ursache bestätigt und behoben:** `systemctl --user status
  hexapod_always_on` meldete `Unit … could not be found.` **zusammen mit** `Linger=no` — die
  Signatur des Früh-Ausstiegs in `provision_always_on_service()` (Unit-Vorlage über
  `ros2 pkg prefix hexapod_bringup` nicht gefunden → `return` **vor** `enable` und **vor**
  `enable-linger`). **Ursache:** §3 wurde vor §2 gefahren, der Workspace am Pi war nicht auf dem
  neuen Stand gebaut → die Vorlage lag nicht im installierten `share/`. Nach `git pull` +
  vollständigem `colcon build` lief das Skript durch (Unit installiert, enabled, gestartet, Linger).
  **Lehre:** die Reihenfolge §2 → §3 im Test-Doc ist keine Bequemlichkeit — §3 setzt den Build aus
  §2.1 voraus. Diagnose bleibt als [§3.1a](phase_9_field_autonomy_test_commands.md) stehen.
- 🟢 **Behoben (Option A, User-Freigabe): `ROS_DOMAIN_ID`-Mismatch zwischen Dienst und Shell.**
  `hexapod_always_on.service` setzt jetzt `Environment="ROS_DOMAIN_ID=42"
  "RMW_IMPLEMENTATION=rmw_fastrtps_cpp"` (mit Begründung im Datei-Kommentar), neuer Pin-Test
  `hexapod_bringup/test/test_always_on_unit_pinned.py` (4 Tests: Variablen vorhanden · Wert
  **identisch** mit `provision_bashrc` · Domain numerisch/in Range · ExecStart unverändert) —
  angebunden über `ament_add_pytest_test` + `ament_cmake_pytest`-test_depend. Zusätzlich:
  `provision_pi.sh` weist nach einer Unit-Änderung auf den nötigen `systemctl --user restart` hin
  (**kein** Auto-Restart — der reißt einen laufenden schweren Stack mit, Relay fällt), und der
  Self-Check hat eine fünfte Zeile „ROS-Domain: Dienst und Shell …", die genau den Fall
  „Unit geändert, alte Instanz läuft noch" fängt. **hexapod_bringup: 53 Tests grün** (inkl. Lint,
  copyright, launch_test). Pi-Nachzug + Verifikation: Test-Doc §3.1b (6).
  **✅ Am Pi verifiziert:** nach `git pull` + `colcon build` + `provision_pi.sh` +
  `systemctl --user restart` listet `ros2 node list` **ohne** `ROS_DOMAIN_ID=0`-Präfix alle fünf
  Nodes. Desktop und Pi sind damit wieder in derselben Domain.
  **Nachtrag aus dem Live-Lauf (Fehlalarm gefixt):** der Self-Check meldete beim Zwischenstand
  „Unit aktualisiert, Restart steht noch aus" ein **„NICHT feld-bereit"** — falsch, denn der
  Feld-Zyklus hängt nicht an der Domain (App ↔ rosbridge ↔ Stack liegen immer in *derselben*
  Domain, welche auch immer). Die Domain-Zeile setzt jetzt ein eigenes `domain_warn` statt `failed`
  → Ausgabe „FELD-BEREIT" **plus** Hinweis „Diagnose von außen eingeschränkt". Begründung: ein
  Fehlalarm entwertet die Ampel, und genau dafür wurde sie gebaut.
  <details><summary>Ursprünglicher Befund</summary>
  Nach §3.1 läuft der Dienst (`active`, Nodes im CGroup-Baum sichtbar), aber `ros2 node list` in der
  SSH-Shell ist **leer**. Ursache: `~/.bashrc` setzt `export ROS_DOMAIN_ID=42` (aus
  `provision_bashrc`), die Unit startet mit `/bin/bash -lc …` — **nicht interaktiv**, und Ubuntus
  `~/.bashrc` steigt dort in Zeile 1 aus (`case $- in *i*) ;; *) return;; esac`). Der Dienst läuft
  damit in **Domain 0**, die Shell in **42**. **Vorher unsichtbar**, weil die Always-On-Schicht
  manuell aus einer interaktiven Shell gestartet wurde — die Umstellung auf den Dienst (P9.3) hat
  das Verhalten geändert. **Tragweite:** die App ist **nicht** betroffen (rosbridge + der als
  Subprozess gestartete Stack liegen in derselben Domain), betroffen ist jede SSH-/Desktop-Diagnose
  — **inklusive §3.3 und §4** (`ros2 param get /gait_node …`). Nachweis + Workaround
  (`ROS_DOMAIN_ID=0` vor dem Befehl) in [§3.1b des Test-Docs](phase_9_field_autonomy_test_commands.md).
  **Fix-Vorschlag (wartet auf Freigabe):** explizites
  `Environment="ROS_DOMAIN_ID=42" "RMW_IMPLEMENTATION=rmw_fastrtps_cpp"` in
  `hexapod_always_on.service` + Pin-Test gegen den `provision_bashrc`-Wert (sonst driften die zwei
  Quellen auseinander — dasselbe Muster wie bei den zwei Shutdown-Configs, Self-Review #2).
  **Am Pi belegt (§3.1b):** Shell `ROS_DOMAIN_ID=42` · Dienst-Prozess (PID 2035) **ohne**
  `ROS_DOMAIN_ID` · `ROS_DOMAIN_ID=0 ros2 node list` listet **alle fünf** Always-On-Nodes
  (`rosbridge_websocket`, `rosapi`, `shutdown_supervisor`, `bringup_launcher`, `hmi_status`) ·
  Domain 42 leer. Der erste Domain-0-Aufruf war nur wegen des **kalten ros2-Daemons** leer.
  → Die Always-On-Schicht selbst ist **vollständig und gesund**; es ist rein ein Sichtbarkeits-/
  Dev-Workflow-Problem (Desktop-Tools in Domain 42 sehen den Roboter nicht mehr, seit die Schicht
  als Dienst statt aus einer interaktiven Shell läuft).
  </details>
- 🟢 **`provision_pi.sh`-Politur erledigt** (User-Freigabe, zwei Punkte aus dem Pi-Lauf):
  1. **Dienst wird jetzt auch gestartet** — `enable` + anschließend `start`, aber **nicht** blind
     `enable --now`: ist Port 9090 belegt (Always-On läuft manuell), warnt das Skript und startet
     **nicht** (zwei rosbridge würden kollidieren). Port-Check statt Prozessnamen-Match, weil der
     Port die eigentliche Kollisionsbedingung ist.
  2. **Self-Check am Skript-Ende** (`verify_field_autonomy`, bewusst als letzter Block nach der
     Manuell-Liste): Poweroff-Recht **mit `sudo -k`** (cache-frei), Dienst enabled+active, Linger,
     und `pi_hostname == hostname` — plus Schlusszeile `FELD-BEREIT` / `NICHT feld-bereit`.
     **Anlass:** die `[warn] Unit-Vorlage nicht gefunden`-Zeile ging beim ersten Pi-Lauf in der
     langen Ausgabe unter; der Fehler wurde erst beim manuellen Prüfen sichtbar.
- 🟡 **`foot_contact_debug_enable`** im HW-Preset auf `false`, sobald die S4-Diagnose nicht mehr
  gebraucht wird (Self-Review #6).
- 🟢 **Watchdog** für eine hängende Always-On-Schicht: bewusst vertagt (Plan §9 [D-Feld-4]) — sauber
  wäre erst rosbridge als eigene Unit, sonst reißt ein Restart den laufenden Stack mit.
- 🟢 **Akku-/Undervoltage-Warnung**: gestrichen (Hardware-Anzeige vorhanden), Backlog D3 bleibt.
