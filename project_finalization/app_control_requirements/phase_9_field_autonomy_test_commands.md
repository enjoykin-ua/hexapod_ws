# Phase 9 — Test-Befehle: Feld-Autonomie (Boot-Autostart · Shutdown · Recovery)

> Du führst aus, knappe Status-Meldung zurück. **Kontext-Tags:** **▶ ROS** = Desktop-Terminal ·
> **▶ Pi** = auf dem Roboter (ssh) · **▶ App** = *echte App (Android-Session)*.
>
> **Ziel:** der Hexapod läuft **ohne Dev-Rechner** — Pi einschalten, App verbinden, fahren, per
> Schalter oder App sauber herunterfahren. Plan:
> [`phase_9_field_autonomy_plan.md`](phase_9_field_autonomy_plan.md) · Progress:
> [`phase_9_field_autonomy_progress.md`](phase_9_field_autonomy_progress.md).
>
> ⚠️ **Reihenfolge einhalten:** erst §2 (Shutdown reparieren), dann §3 (Autostart). So ist der
> Feld-Zyklus früh sicher statt zuerst bequem.

---

## 0. Zuerst: committen + pushen (▶ ROS)

Der Pi zieht von GitHub — ohne Push findet sein `git pull` in §2.1 nichts Neues.

```bash
cd ~/hexapod_ws
git add -A
git commit -m "phase9: Feld-Autonomie — Poweroff repariert, HW-Preset im App-Pfad, Freeze-Guard, provision_pi.sh"
git push
```

**Empfohlene Reihenfolge der Abschnitte:**

| Wann | Was | Wo |
|---|---|---|
| sofort, ohne Roboter | §1 Repo-Tests · §5a Freeze-Guard · §6 (Sim-Teil) | Desktop |
| am Roboter, **zuerst** | §2 Deploy + sudoers + **Schalter-Test** | Pi |
| danach | §3 Autostart + Reboot-Test ohne SSH | Pi |
| danach | §4 HW-Preset im App-Pfad prüfen | Pi + App |
| wenn die App-Session ihre Live-Tests fährt | §5 + §5b (Restart/Shutdown-Wege, hängender Stack) | App |
| — | ~~§7 Reconnect-Messung~~ **entfällt**, von der App-Session beantwortet | — |

---

## 1. Repo-Tests (▶ ROS) — ohne Pi

```bash
cd ~/hexapod_ws
source /opt/ros/jazzy/setup.bash && source ~/hexapod_ws/install/setup.bash
colcon build --symlink-install --packages-select hexapod_supervisor hexapod_gait hexapod_bringup
colcon test --packages-select hexapod_supervisor hexapod_gait hexapod_bringup
colcon test-result --all
```
**✅ Erwartung (T9.1/T9.3/T9.13):** `0 errors, 0 failures`. Neu dabei:
`test_shutdown_config_pinned.py` (4 Tests: `pi_hostname` in **beiden** Configs, `sudo -n`,
Master-Arm, Konsistenz) und drei neue im `test_hw_terrain_preset.py` (Comms-Loss-Wert,
Validator-Range, keine Struktur-Params im Preset).

**T9.14 — Sim darf sich nicht verändern:**
```bash
source /opt/ros/jazzy/setup.bash && source ~/hexapod_ws/install/setup.bash
ros2 launch hexapod_bringup ramp_walk.launch.py
# in einem zweiten Terminal, sobald der Roboter steht:
ros2 param get /gait_node comms_loss_sitdown_timeout      # -> 0.0 (aus)  ← der entscheidende Wert
ros2 param get /gait_node leveling_enable                 # -> True (Bestand, s.u.)
```
**✅ Erwartung:** `comms_loss_sitdown_timeout` ist **0.0** — der Roboter setzt sich im Leerlauf
**nicht** von selbst hin. Das ist der Punkt dieses Tests: Phase 9 schaltet den Fail-safe nur im
HW-/App-Pfad scharf (über `hw_terrain.yaml`), der Sim-Pfad bleibt unberührt.

> ℹ️ **`leveling_enable` ist in der Sim `True` — das ist korrekt und Bestand:**
> `ramp_walk.launch.py` deklariert das Argument mit `default_value='true'` (aus der A5-Arbeit),
> unabhängig vom Code-Default `false` im gait_node. Es hat mit Phase 9 nichts zu tun — geändert
> wurde nur der `real`-Zweig von `bringup_ondemand.launch.py`. Wer Leveling in der Sim isoliert
> ausschalten will: `ros2 launch hexapod_bringup ramp_walk.launch.py leveling_enable:=false`.

---

## 2. Pi: den sanften Shutdown reparieren (P9.2 + P9.4)

> **Befund vor Phase 9:** Schalter → Hinsetzen ✅ → Relay ✅ → **und dann nichts**. Der Pi lief
> weiter (`pi_hostname` war leer → `host-mismatch`), das anschließende Ziehen des Hauptschalters
> trennte ihn **hart** vom Strom.

### 2.1 Neuen Code auf den Pi (▶ Pi)
```bash
ssh hexapod-pi
cd ~/hexapod_ws
git pull
source /opt/ros/jazzy/setup.bash
colcon build --symlink-install --packages-select hexapod_supervisor hexapod_gait hexapod_bringup
source ~/hexapod_ws/install/setup.bash
```

### 2.2 sudo-Recht für den Poweroff (P9.2, ▶ Pi)
```bash
command -v shutdown          # erwartet /usr/sbin/shutdown — merken, falls abweichend
sudo visudo -f /etc/sudoers.d/hexapod-shutdown
```
Im Editor **genau eine Zeile** eintragen (Pfad ggf. an die Ausgabe oben anpassen), speichern:
```
pi ALL=(root) NOPASSWD: /usr/sbin/shutdown
```
> `visudo` prüft die Syntax vor dem Speichern — deshalb **nicht** mit `echo >` oder einem Editor
> direkt schreiben: ein kaputtes sudoers-File sperrt dich aus.

Prüfen — **`sudo -k` ist Pflicht, sonst ist der Test falsch-positiv:**
```bash
sudo -k                                              # sudo-Timestamp verwerfen
sudo -n shutdown --help >/dev/null; echo "exit=$?"   # MUSS exit=0 sein  <- der belastbare Nachweis
sudo -n true; echo "exit=$?"                         # 0 ODER 1 — beides ok, siehe unten
```
**✅ Erwartung:** die **erste** Zeile `exit=0`. (Der Befehl fährt **nichts** herunter, er ruft nur die
Hilfe.)

> ⚠️ **Warum `sudo -k`:** direkt nach `sudo visudo` ist der sudo-Timestamp-Cache frisch (~15 min) —
> dann liefert **jeder** `sudo -n`-Aufruf `exit=0`, auch wenn der sudoers-Eintrag gar nicht greift.
> Der Dienst später hat diesen Cache **nicht**. `sudo -k` verwirft ihn und stellt genau die
> Situation her, in der `shutdown_supervisor` den Poweroff aufruft.
>
> ℹ️ **`sudo -n true` darf hier `exit=1` liefern** — das ist sogar das *erwartete* Ergebnis eines eng
> gefassten Eintrags (`NOPASSWD` nur für `/usr/sbin/shutdown`, [D-Feld-2]). Liefert es `exit=0`,
> hat der User zusätzlich ein breites NOPASSWD-Recht (Pi-Image-Default) — unschädlich, aber dann sagt
> diese Zeile nichts über unseren Eintrag aus. Entscheidend ist **nur** die `shutdown --help`-Zeile.

### 2.3 Guard-Werte im laufenden System prüfen (▶ Pi)
```bash
grep -n "pi_hostname\|shutdown_command" \
  ~/hexapod_ws/src/hexapod_supervisor/config/supervisor.yaml \
  ~/hexapod_ws/src/hexapod_supervisor/config/launcher.real.yaml
hostname
```
**✅ Erwartung:** beide Configs zeigen `pi_hostname: 'hexapod-pi'` und
`shutdown_command: 'sudo -n shutdown -h now'`; `hostname` liefert **exakt** `hexapod-pi`.

### 2.4 Der Schalter-Test (T9.5, ▶ Pi + Roboter)
> **Roboter aufgebockt oder auf freier Fläche** — er setzt sich hin. Akku voll genug.

```bash
# Terminal 1 (▶ Pi): Stack starten (noch manuell, der Autostart kommt in §3)
source /opt/ros/jazzy/setup.bash && source ~/hexapod_ws/install/setup.bash
ros2 launch hexapod_bringup always_on.launch.py mode:=real
```
App verbinden → **Start** → **Aufstehen**. Dann **den Schalter am Roboter umlegen**.

**✅ Erwartung (die Kette in dieser Reihenfolge):**
1. Roboter setzt sich hin (Rest-Pose)
2. Relay klickt (Servos stromlos)
3. **Der Pi fährt herunter** — im Log von Terminal 1 steht `executing OS shutdown: sudo -n shutdown -h now`

Nach ~20 s prüfen (vom Dev-Rechner):
```bash
ssh hexapod-pi 'echo alive'      # ✅ MUSS jetzt fehlschlagen (Pi ist aus)
```
**Erst wenn SSH nicht mehr geht**, den Hauptschalter ziehen und den Akku abklemmen.

> **Wenn der Pi weiterläuft:** im Log nach `no OS shutdown` suchen. `hostname ... != pi_hostname`
> → §2.3 prüfen. `sudo: a password is required` → §2.2 prüfen.

---

## 3. Pi: Always-On ab Boot (P9.3)

### 3.1 Dienst einrichten (▶ Pi)
```bash
ssh hexapod-pi
cd ~/hexapod_ws
git pull                                   # holt die provision_pi.sh-Politur (Start + Self-Check)
source /opt/ros/jazzy/setup.bash && source ~/hexapod_ws/install/setup.bash
./tools/provision_pi.sh
```
> ⚠️ **Das `source` ist nicht optional:** das Skript findet die Unit-Vorlage über
> `ros2 pkg prefix hexapod_bringup`. Ohne gesourcten Workspace steigt Schritt 10 aus (Diagnose:
> §3.1a). `tools/` wird nicht gebaut — nach dem `git pull` ist **kein** `colcon build` nötig.
> Das Skript ist **idempotent** — es macht nur, was fehlt (apt-Schritte melden „skip"). Am Ende
> richtet Schritt 10 den sudoers-Eintrag (falls §2.2 noch nicht erledigt), die systemd-Unit und
> `enable-linger` ein und listet die manuellen Nachträge auf.

Alternativ die drei Schritte einzeln (falls du das Skript nicht laufen lassen willst):
```bash
mkdir -p ~/.config/systemd/user
cp "$(ros2 pkg prefix hexapod_bringup)/share/hexapod_bringup/systemd/hexapod_always_on.service" \
   ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now hexapod_always_on.service
sudo loginctl enable-linger "$USER"
```

Prüfen:
```bash
systemctl --user status hexapod_always_on --no-pager | head -12
loginctl show-user "$USER" | grep -i linger        # -> Linger=yes
ros2 node list                                      # -> rosbridge_websocket, bringup_launcher, shutdown_supervisor, hmi_status
```
**✅ Erwartung:** `active (running)`, `Linger=yes`, die vier Always-On-Nodes sind da — **ohne** dass
du etwas manuell gestartet hast.

> ℹ️ **Das Skript startet den Dienst jetzt selbst** (`enable` + `start`, nicht blind `enable --now`):
> läuft die Always-On-Schicht schon — erkennbar an **belegtem Port 9090**, typisch nach einem
> manuellen `always_on.launch.py` — startet es den Dienst **nicht**, sondern warnt (zwei rosbridge
> auf 9090 würden kollidieren). Dann erst den manuellen Start beenden und
> `systemctl --user start hexapod_always_on` nachziehen.
>
> ℹ️ **Am Ende des Skript-Laufs steht ein Self-Check** („SELF-CHECK Feld-Autonomie") mit vier
> Ampel-Zeilen: Poweroff-Recht (mit `sudo -k`, also cache-frei), Dienst enabled+active, Linger,
> und `pi_hostname == hostname`. Schlusszeile `FELD-BEREIT` = alles grün. **Das ersetzt den
> Prüfblock oben nicht** (`ros2 node list` zeigt zusätzlich, dass die vier Nodes wirklich da sind),
> macht aber sofort sichtbar, wenn ein Schritt still ausgestiegen ist.

### 3.1a Diagnose: `Unit … could not be found` / `Linger=no` (▶ Pi)

> **Symptom:** `systemctl --user status hexapod_always_on` meldet
> `Unit hexapod_always_on.service could not be found.` **und** `Linger=no`.
>
> **Was das bedeutet:** genau dieser Doppel-Befund ist die Signatur des Früh-Ausstiegs in
> `provision_always_on_service()` — findet das Skript die **Unit-Vorlage** nicht
> (`$(ros2 pkg prefix hexapod_bringup)/share/hexapod_bringup/systemd/hexapod_always_on.service`),
> steigt es mit `[warn] Unit-Vorlage nicht gefunden` **vor** `enable` und **vor** `enable-linger`
> aus. Deshalb fehlt beides gleichzeitig. Der sudoers-Schritt davor ist davon unberührt.

> ⚠️ **Zweite mögliche Ursache — das Skript kam nie bis Schritt 10.** `provision_pi.sh` läuft mit
> `set -euo pipefail`: schlägt irgendein früherer Schritt fehl (apt, ROS-Repo, rosdep), bricht es
> **sofort** ab — dann fehlt zusätzlich der sudoers-Eintrag. Unterscheidungsmerkmal ist die
> Schlusszeile `[ok] Automatisierte Provisionierung abgeschlossen.` samt der Liste
> „MANUELLE SCHRITTE". Fehlt sie, ist das Skript unterwegs gestorben (Befehl (0) unten zeigt es).

```bash
ssh hexapod-pi
cd ~/hexapod_ws
source /opt/ros/jazzy/setup.bash && source ~/hexapod_ws/install/setup.bash

# (0) Kam das Skript ueberhaupt bis Schritt 10? sudoers ist der Schritt DAVOR:
sudo -n true; echo "sudo_nopasswd_exit=$?"     # 0 = Schritt 10a lief, 1 = Skript starb vorher
sudo test -f /etc/sudoers.d/hexapod-shutdown; echo "sudoers_file_exit=$?"

# (1) Kennt ROS das Paket, und liegt die Unit-Vorlage im installierten share/?
ros2 pkg prefix hexapod_bringup
ls -l "$(ros2 pkg prefix hexapod_bringup)/share/hexapod_bringup/systemd/"

# (2) Ist im User-Unit-Verzeichnis etwas angekommen?
ls -la ~/.config/systemd/user/

# (3) Wurde das Paket ueberhaupt gebaut?
ls -ld ~/hexapod_ws/install/hexapod_bringup
```

**Auswertung — Fall (0) zuerst:** beide `exit=1` **und** keine Abschluss-Zeile in der Skript-Ausgabe
→ das Skript ist vor Schritt 10 gestorben. Dann **nicht** raten, sondern es erneut laufen lassen und
die **vollständige** Ausgabe sichern:
```bash
./tools/provision_pi.sh 2>&1 | tee ~/provision_run.log
```
(Die Fehlerzeile steht am Ende von `~/provision_run.log`.)

**Auswertung (1)–(3) — drei Fälle:**

| Ausgabe | Ursache | Fix |
|---|---|---|
| (1) liefert Pfad **und** die `.service`-Datei ist da | Das Skript lief in einer Shell **ohne** `source install/setup.bash` → `ros2 pkg prefix` war leer | In **dieser** (gesourcten) Shell `./tools/provision_pi.sh` erneut aufrufen — es ist idempotent |
| (1) leer / (3) fehlt | `hexapod_bringup` ist am Pi **nicht gebaut** | `colcon build --symlink-install --packages-select hexapod_bringup`, dann `source ~/hexapod_ws/install/setup.bash`, dann Skript erneut |
| Paket da, aber `systemd/`-Verzeichnis fehlt im `share/` | Build ist **älter** als die Install-Regel (`install(DIRECTORY launch config systemd …)` in der `CMakeLists.txt`) | dasselbe: `hexapod_bringup` neu bauen, sourcen, Skript erneut |

Nach dem Fix nochmal prüfen (Block aus §3.1). Wenn der Skript-Weg lief, zusätzlich starten:
```bash
systemctl --user start hexapod_always_on
systemctl --user status hexapod_always_on --no-pager
loginctl show-user "$USER" | grep -i Linger
ros2 node list
```
**✅ Erwartung:** `active (running)`, `Linger=yes`, vier Nodes (`rosbridge_websocket`,
`bringup_launcher`, `shutdown_supervisor`, `hmi_status`).

> **Falls du stattdessen den manuellen Drei-Schritt-Weg genommen hast:** dort scheitert dasselbe
> Problem am `cp` (`ros2 pkg prefix` leer → Quellpfad beginnt mit `/share/…`). Die Fehlermeldung
> steht dann in der `cp`-Zeile; `enable --now` meldet danach ebenfalls „does not exist". Gleiche
> Fixe wie oben, dann den Drei-Schritt-Block wiederholen.

### 3.2 Der eigentliche Test: Reboot ohne SSH (T9.4, ▶ Pi)
```bash
sudo reboot
```
Danach **nicht** per SSH verbinden. Stattdessen: warten (~40–60 s), Hotspot am Handy an,
**App verbinden** auf die Pi-IP → **Start** → **Aufstehen**.

**✅ Erwartung:** funktioniert komplett ohne Dev-Rechner. Das ist das Kern-Deliverable.

> **Ab jetzt gilt:** die Always-On-Schicht läuft als Dienst — **nicht** zusätzlich manuell per SSH
> starten (zwei rosbridge auf Port 9090 kollidieren). Vorher immer:
> `systemctl --user stop hexapod_always_on`

### 3.3 Deploy-Zyklus mit Dienst (T9.8, ▶ Pi)
```bash
cd ~/hexapod_ws && git pull
source /opt/ros/jazzy/setup.bash
colcon build --symlink-install --packages-select hexapod_gait hexapod_teleop hexapod_supervisor
systemctl --user restart hexapod_always_on      # NUR noetig, wenn sich die Always-On-Schicht geaendert hat
```
**Merksatz:** ändert sich nur der **schwere Stack** (gait_node/Engine/Teleop — der Normalfall),
genügt in der App **stoppen → starten**. Ändert sich die **Always-On-Schicht** (rosbridge-Launch,
`bringup_launcher`, `hmi_status` inkl. `hmi_config_manifest.yaml`), zusätzlich der `restart` oben.

Verifizieren, dass wirklich neuer Code läuft:
```bash
ros2 param get /gait_node show_mode        # Phase-8-Param: 'none' = neuer Code aktiv
```

### 3.4 Idempotenz (T9.11, ▶ Pi)
```bash
./tools/provision_pi.sh
```
**✅ Erwartung:** Schritt 10 meldet `[skip] sudoers-Eintrag vorhanden`, `[skip] Unit aktuell`,
`[skip] Dienst bereits enabled`, `[skip] Linger bereits aktiv` — nichts wird doppelt angelegt.

---

## 4. Das HW-Preset im App-Pfad (T9.12, ▶ Pi + App)

> Neu in Phase 9: der App-Bringup lädt `hw_terrain.yaml`. Vorher lief er mit Code-Defaults —
> **Balance und alle Terrain-Features waren aus**, außer man schaltete sie nach jedem Start im
> Config-Panel ein.

App: **Start** → **Aufstehen**. Dann (▶ Pi):
```bash
source /opt/ros/jazzy/setup.bash && source ~/hexapod_ws/install/setup.bash
ros2 param get /gait_node leveling_enable              # -> true
ros2 param get /gait_node leveling_mode                # -> auto
ros2 param get /gait_node adaptive_stand_enable        # -> true
ros2 param get /gait_node adaptive_touchdown_enable    # -> true
ros2 param get /gait_node slip_detection_enable        # -> true
ros2 param get /gait_node comms_loss_sitdown_timeout   # -> 25.0
ros2 param get /gait_node auto_standup_on_start        # -> false (Bauch-Start UNVERAENDERT)
```
**✅ Erwartung:** alle Werte wie oben. Besonders die letzte Zeile: das Preset darf den Bauch-Start
**nicht** überschreiben (sonst stünde der Roboter beim App-Start unaufgefordert auf).

Danach **fahren wie gewohnt** — der Roboter sollte sich jetzt anfühlen wie beim 3-Terminal-Bringup
(Balance aktiv, Terrain-Anpassung an).

---

## 5. Recovery-Wege (T9.6/T9.7, ▶ App) — nach dem App-Bau

| Schritt | ✅ Erwartung |
|---|---|
| „Stack neu starten" während der Stack läuft | Roboter setzt sich zuerst hin, dann Stack aus/an; nach ~40 s wieder bedienbar („Aufstehen" wird freigegeben) |
| „Stack neu starten" während der Roboter **sitzt** | direkt Stop/Start, kein Dialog nötig |
| „Stack neu starten" aus dem **Look-Around** | App setzt erst `show_mode=none`, dann Hinsetzen — kein hartes Stoppen |
| „Pi herunterfahren" **mit** laufendem Stack | Roboter setzt sich hin, Relay, Pi fährt herunter (SSH tot) |
| „Pi herunterfahren" **ohne** laufenden Stack (nur verbunden) | Pi fährt direkt herunter — ohne Hinsetzen (er steht ja nicht) |
| Verbindung bricht nach dem Shutdown ab | Die App zeigt „Pi fährt herunter", **keine** Fehlermeldung |

### 5a. Freeze-Guard live prüfen (T9.17, ▶ ROS/Sim + App)

> Neu in v0.13.2: bei aktivem E-Stop lehnen die Sequenz-Services **sofort** ab, statt Erfolg zu
> melden und nichts zu tun.

```bash
source /opt/ros/jazzy/setup.bash && source ~/hexapod_ws/install/setup.bash
ros2 service call /hexapod_estop std_srvs/srv/Trigger {}
ros2 service call /hexapod_sit_down std_srvs/srv/Trigger {}     # -> success=False + Grund
ros2 service call /hexapod_stand_up std_srvs/srv/Trigger {}     # -> success=False + Grund
ros2 service call /hexapod_recover std_srvs/srv/Trigger {}      # -> success=True (der Ausweg)
ros2 service call /hexapod_sit_down std_srvs/srv/Trigger {}     # -> success=True (geht wieder)
```
**✅ Erwartung:** die beiden mittleren Aufrufe melden
`… rejected: robot is frozen (E-Stop/safety) — call /hexapod_recover first`.
**In der App:** „Stack neu starten" bei aktivem E-Stop läuft **nicht** 15 s ins Leere, sondern zeigt
den Grund sofort — der Nutzer drückt erst „Recover".

### 5a2. Testfall 4b — Restart bei aktivem E-Stop (▶ Sim + App)

> Die App wertet seit v0.13.2 **`status.safety_frozen`** aus (nicht den Reject-Text) und bricht
> ihren Hinsetz-Retry sofort ab.

1. Stack läuft, Roboter **steht**.
2. In der App **E-STOP** drücken (oder `ros2 service call /hexapod_estop std_srvs/srv/Trigger {}`).
3. In der Verbinden-Sicht **„Stack neu starten"** drücken.

**✅ Erwartung:**
- **keine 15 s Stille** — der Hinsetz-Versuch bricht **sofort** ab
- rote Warnung sinngemäß „E-Stop aktiv — der Roboter kann sich nicht hinsetzen. Erst ‚Recover',
  sonst sackt er beim Stoppen zusammen."
- `bringup_stop`/`start` laufen trotzdem durch (der Restart ist auch der Rettungsanker)
- danach: **„Recover"** → Roboter steht wieder → Restart läuft normal (mit Hinsetzen)

### 5b. Hängenden Stack simulieren (für den App-Testfall „Stack hängt")

> Ein `pkill` erzeugt einen **toten**, keinen **hängenden** Stack. Realistischer ist `SIGSTOP`:
> der Prozess lebt weiter (der Launcher sieht ihn als „running"), reagiert aber auf nichts mehr.

```bash
# ▶ ROS/Pi — Stack läuft, Roboter steht:
pkill -STOP -f gait_node          # gait_node einfrieren -> /hexapod/status verstummt
# ... jetzt in der App "Stack neu starten" drücken:
#     -> kein Status-Tick => kein sit_down-Versuch, harter Stop mit Warnung
#     -> danach Start, ~40 s bis der neue Stack meldet

# Falls du den Test abbrechen willst, ohne zu stoppen:
pkill -CONT -f gait_node          # wieder aufwecken
```
**✅ Erwartung:** die App erkennt den fehlenden Status-Tick, überspringt das Hinsetzen, warnt
(„Roboter sackt zusammen") und startet den Stack neu. Der `bringup_stop` killt den gestoppten
Prozess zuverlässig durch (SIGKILL wirkt auch auf SIGSTOP-Prozesse).

---

## 6. Comms-Loss-Fail-safe (T9.9, ▶ Sim zuerst)

**In der Sim gefahrlos prüfen** (der Wert ist dort 0, also von Hand setzen):
```bash
source /opt/ros/jazzy/setup.bash && source ~/hexapod_ws/install/setup.bash
ros2 launch hexapod_bringup ramp_walk.launch.py
# zweites Terminal, sobald der Roboter steht:
ros2 param set /gait_node comms_loss_sitdown_timeout 8.0    # kurzer Wert zum Testen
ros2 topic pub -r 10 /cmd_vel geometry_msgs/msg/Twist "{linear: {x: 0.02}}"
# ~3 s fahren lassen, dann Strg-C  -> ab jetzt kommt kein cmd_vel mehr
```
**✅ Erwartung:** Roboter stoppt (cmd_vel_timeout), und **~8 s später** setzt er sich selbst hin
(Log: `comms-loss: no /cmd_vel for … — auto sit-down (Rest)`). Danach `/hexapod_stand_up` → er steht
wieder.

**Auf HW (▶ App):** Stack läuft, Roboter steht. Hotspot am Handy **aus** lassen.
**✅ Erwartung:** nach 25 s setzt er sich hin (bleibt bestromt). Hotspot wieder an → App verbinden →
**Aufstehen** → fahren.

---

## 7. Reconnect-Messung (T9.10) — ✅ ERLEDIGT, nichts mehr zu tun

Von der App-Session beantwortet: die App hat **bewusst keinen Auto-Reconnect**
(`RosbridgeClient`, seit Phase 8). Nach einem WLAN-Abriss bleibt sie auf `ERROR`/`DISCONNECTED`,
der Nutzer drückt „Verbinden".

Für Phase 9 ist das genau richtig — beim Poweroff wäre ein Reconnect-Sturm kontraproduktiv.
**Automatischer Reconnect ist als Phase-10-Punkt notiert.** Praxis-Hinweis fürs Feld: nach einem
Reconnect ist der Roboter wegen des 25-s-Comms-Loss-Fail-safe womöglich schon hingesetzt → erst
„Aufstehen" drücken.
