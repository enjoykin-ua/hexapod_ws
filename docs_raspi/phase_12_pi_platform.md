# Phase 12 — Pi-Plattform & Portierung

**Dauer-Schätzung:** 1–2 Tage (OS + ROS2 + Workspace + DDS-Konnektivität)
**Maschine:** Raspberry Pi 5 (8 GB) **und** Desktop (für SSH/Deployment)
**Vorbedingung:** Phase 10 abgeschlossen — `hexapod_hardware` läuft am
Desktop mit echten Servos kalibriert. Bench-Strom-Setup steht.

---

## Ziel

Den kompletten ROS2-Stack vom Desktop auf den Pi portieren. Pi läuft
headless Ubuntu Server 24.04 LTS, ROS2 Jazzy, Workspace baut, DDS-Discovery
zum Desktop funktioniert, Deployment-Workflow Desktop → Pi steht.

**In dieser Phase wird noch nicht** der echte Roboter am Pi getestet —
Servo2040 hängt weiter am Desktop. Phase 12 ist reine Plattform-Vorbereitung.
Erst Phase 13 schließt den Roboter an den Pi an.

---

## Provisioning als Code (Reproduzierbarkeit nach SD-/SSD-Ausfall)

> **Tracker:** [phase_12_progress.md](phase_12_progress.md) ·
> **Skript:** [`tools/provision_pi.sh`](../tools/provision_pi.sh)

SD-Karten (und SSDs) sterben bei Pi + unsauberer Abschaltung. Damit ein
Ausfall **nicht** stundenlanges Neu-Einrichten bedeutet, werden alle
System-Ebenen-Einstellungen, die nicht im Workspace-Git liegen
(APT-Pakete, ROS-Repo, Locale, `~/.bashrc`-Env, udev-Rule) in einem
**idempotenten Bash-Skript** [`tools/provision_pi.sh`](../tools/provision_pi.sh)
gehalten. Workspace + Kalibrierung sind bereits über Git reproduzierbar.

**Recovery-Pfad nach SD-Tod:**

```bash
# 1. Pi Imager: Ubuntu Server 24.04 LTS arm64 + SSH-Key + WLAN (Stufe A)
# 2. Workspace klonen. ACHTUNG: GitHub-Zugang des Pi ist nach SD-Tod weg —
#    entweder HTTPS+PAT (kein Pi-Key noetig) ...
git clone https://github.com/enjoykin-ua/hexapod_ws.git ~/hexapod_ws
#    ... ODER neuen SSH-Deploy-Key am Pi erzeugen + bei GitHub hinterlegen:
#    git clone git@github.com:enjoykin-ua/hexapod_ws.git ~/hexapod_ws
# 3. System provisionieren (installiert Pakete, setzt Configs idempotent)
~/hexapod_ws/tools/provision_pi.sh
# 4. Workspace bauen
cd ~/hexapod_ws && rosdep install --from-paths src --ignore-src -r -y \
  --skip-keys "ros_gz_sim ros_gz_bridge" \
  && colcon build --symlink-install
```

**Arbeitsweise:** Das Skript wird in den Stufen B/C/E **mitwachsend**
befüllt — wir führen die Einstell-Schritte über das Skript aus statt
manuell, sodass es am Phasenende genau einmal real erprobt ist. Stellen
mit Verifikationsbedarf am echten Pi sind im Skript mit `# VERIFY@PI`
markiert. Das Skript gibt am Ende eine **MANUELLE-SCHRITTE-Liste** aus
für alles, was es nicht automatisch wissen kann (ROS_DOMAIN_ID-Abgleich,
Servo2040-VID:PID, PS4-BT-Re-Pairing, WLAN/SSH-Key aus dem Imager).
Architektur-Guard (`aarch64`) verhindert versehentliche Ausführung am
x86-Desktop.

---

## Hardware-Setup für diese Phase

- Raspberry Pi 5 (8 GB) — bisher unbenutzt
- USB-3-SSD (empfohlen) ODER SD-Karte (≥ 64 GB)
- Netzwerk: Pi und Desktop im gleichen LAN/WLAN-Segment
- Tastatur + HDMI-Monitor für Erst-Bootup (alternativ: Headless-Setup
  via Imager + WLAN-Config)
- DCDC-Wandler + Bench-PSU aus Phase 8 als Stromversorgung des Pi (optional,
  zunächst kann auch ein normales 5V-USB-C-Netzteil benutzt werden, der
  DCDC-Pfad wird erst in Phase 13 verifiziert)

---

## Done-Kriterien

1. Pi läuft headless mit Ubuntu Server 24.04 LTS arm64
2. SSH-Zugang vom Desktop mit Schlüssel-Auth (kein Passwort)
3. ROS2 Jazzy installiert (ros-base, kein Desktop), keine Sim-Pakete
4. Workspace gebaut grün (außer `hexapod_gazebo` via COLCON_IGNORE)
5. DDS-Discovery Desktop ↔ Pi bidirektional funktioniert
6. Deployment-Workflow Desktop → Pi dokumentiert in
   `dev_workflow_desktop_to_pi.md` und einmal vollständig durchgespielt
7. Loopback-Test: `real.launch.py loopback_mode:=true` auf Pi startet alle
   Controller active
8. Shutdown-Disziplin dokumentiert

---

## Stufen

> **Manuell vs. Skript:** Die Einstell-Befehle in den Stufen **B, C, E**
> (apt-Pakete, Locale, ROS-Repo, `~/.bashrc`-Env, `COLCON_IGNORE`, udev,
> rosdep) werden vom [`tools/provision_pi.sh`](../tools/provision_pi.sh)
> **automatisch** ausgeführt — du musst sie nicht einzeln abtippen. Die
> hier gezeigten Befehle dienen als **Referenz**, was das Skript tut (und
> zum manuellen Nachvollziehen/Debuggen).
>
> **Reihenfolge** (das Skript liegt IM Workspace, muss also erst geklont sein):
> 1. Stufe A (OS) + B.1 (SSH-Config am Desktop) — von Hand
> 2. Am Pi: `git` sicherstellen + Workspace klonen (E.1) —
>    `sudo apt install -y git` falls nötig, dann `git clone …`
> 3. Am Pi: **APT-Pocket `noble-updates` aktivieren** (Kasten unten) —
>    Pflicht-Vorschritt, **vor** `apt update` und vor dem Skript.
> 4. Am Pi: `~/hexapod_ws/tools/provision_pi.sh` — erledigt den Rest von
>    B/C/E (Pakete, Locale, ROS-Repo, Env, COLCON_IGNORE, udev, rosdep).
>    Das Skript **prüft** noble-updates und bricht mit Anleitung ab, falls
>    Schritt 3 vergessen wurde.
> 5. Am Pi: `colcon build --symlink-install` (E.3)

> **⚠️ Pflicht-Vorschritt — APT-Pocket `noble-updates` aktivieren:**
> Dieses Pi-Image kam nur mit `noble` + `noble-security` in den
> APT-Quellen. Ohne `noble-updates` fehlen die aktualisierten `-dev`-Pakete
> und die ROS-Installation scheitert an Versions-Mismatches (`libdrm-dev`,
> `zlib1g-dev`, `bzip2 not installable`, …). Einmalig am Pi:
>
> ```bash
> # Backup (es ist eine /etc/apt-Datei — CLAUDE.md §5)
> sudo cp /etc/apt/sources.list.d/ubuntu.sources \
>         /etc/apt/sources.list.d/ubuntu.sources.bak
> # in der ersten Sektion 'Suites: noble' -> 'Suites: noble noble-updates'
> # (NICHT die 'noble-security'-Zeile anfassen):
> sudo sed -i '/^Suites: noble$/s/.*/Suites: noble noble-updates/' \
>         /etc/apt/sources.list.d/ubuntu.sources
> sudo apt update    # 'noble-updates' muss jetzt in den Hits auftauchen
> ```
>
> Alternativ statt `sed` mit `sudo nano /etc/apt/sources.list.d/ubuntu.sources`
> die Zeile von Hand ergänzen. Danach erst Schritt 4 (Provisioning).

### Stufe A — OS-Image flashen

#### A.1 Storage-Wahl

- **USB-3-SSD bevorzugen** statt SD-Karte: SD korrumpiert bei jeder
  schmutzigen Abschaltung (= Servo-Brown-out + Pi runter), SSD verzeiht
  das eher
- Falls nur SD verfügbar: hochwertige Karte (≥ A2-Rating, SanDisk Extreme
  o. ä.)

#### A.2 Image schreiben

- **Raspberry Pi Imager** verwenden
- Image: **Ubuntu Server 24.04 LTS (64-bit)** für arm64. Kein Desktop.
- Imager-Settings (Zahnrad → „Edit settings"):
  - Hostname: `hexapod-pi`
  - SSH aktivieren mit Public-Key-Auth (Desktop-Pubkey eintragen)
  - User: `pi`, Passwort setzen
  - WLAN-Credentials eintragen (für Headless-Boot)
  - Locale, Tastatur

> **⭐ Login-Referenz (so kommst du auf den Pi):**
>
> | | |
> |---|---|
> | Hostname | `hexapod-pi` |
> | IP im LAN | `192.168.2.65` |
> | User | `pi` |
> | **Login** | **`ssh pi@hexapod-pi`** (Passwort) — Fallback `ssh pi@192.168.2.65` |
>
> `.local`/mDNS ist auf Ubuntu Server NICHT aktiv (`ping hexapod-pi.local`
> schlägt fehl) — der **reine Name `hexapod-pi` wird vom Router-DNS
> aufgelöst**. **Empfehlung:** im Router eine DHCP-Reservierung auf die
> Pi-MAC setzen, dann bleibt `.65` stabil. (Optional `.local`:
> `sudo apt install avahi-daemon` am Pi.)

#### A.3 Erstbootup

- SSD/SD an Pi, Pi an Strom (zunächst Standard-5V-USB-C-Netzteil)
- 2 Minuten warten
- Vom Desktop:

```bash
ping hexapod-pi              # Router-DNS (kein .local noetig)
ssh pi@hexapod-pi            # Passwort aus dem Imager
```

Details und Fallback (IP, mDNS) siehe Login-Referenz oben.

#### A.3b Optional — Konsole rotieren (gedrehter/hochkant Monitor)

Nur relevant, wenn du zum Headless-Debugging einen Monitor anschließt und
der hochkant steht (TTY-Konsole läuft quer). Sofort, ohne Reboot:

```bash
echo 3 | sudo tee /sys/class/graphics/fbcon/rotate_all
```

Werte: `0`=normal, `1`=90° im Uhrzeigersinn, `2`=180°, `3`=90° gegen
Uhrzeigersinn. Für den aktuellen Aufbau passt **3**.

Persistent über Reboots — Kernel-Cmdline (alles in **einer** Zeile lassen,
am Ende ` fbcon=rotate:3` anhängen):

```bash
sudo nano /boot/firmware/cmdline.txt
```

Falls die Cmdline-Variante nach Reboot nicht greift (KMS-Treiber
überschreibt sie), Plan B per systemd-Service:

```bash
sudo tee /etc/systemd/system/fbcon-rotate.service >/dev/null <<'EOF'
[Unit]
Description=Rotate framebuffer console
After=multi-user.target
[Service]
Type=oneshot
ExecStart=/bin/sh -c 'echo 3 > /sys/class/graphics/fbcon/rotate_all'
[Install]
WantedBy=multi-user.target
EOF
sudo systemctl enable fbcon-rotate.service
```

**Done-Kriterium A:**
1. Pi bootet, SSH-Login (`ssh pi@hexapod-pi`) mit Passwort erfolgreich
   (Schlüssel-Auth folgt in B.1)
2. `uname -a` zeigt arm64 / 24.04 LTS

---

### Stufe B — SSH-Workflow & Basis-Tools

#### B.1 SSH-Config & Schlüssel-Auth am Desktop

Alle Schritte am **Desktop** (nicht am Pi). Ziel: passwortloser Login via
Kurzname `ssh hexapod-pi`.

**1. SSH-Key prüfen — existiert schon einer?**

```bash
ls ~/.ssh/id_ed25519.pub
```

- Datei existiert → weiter zu Schritt 2.
- „No such file" → Key erzeugen (3× Enter: Default-Pfad, Passphrase optional):

```bash
ssh-keygen -t ed25519 -C "desktop-to-hexapod-pi"
```

**2. `~/.ssh/config` anlegen/ergänzen.** Die Datei wird angelegt, falls sie
nicht existiert; bei bestehenden `Host`-Einträgen den Block unten **anhängen**
(nicht überschreiben):

```bash
nano ~/.ssh/config
```

```
Host hexapod-pi
    HostName hexapod-pi
    User pi
    IdentityFile ~/.ssh/id_ed25519
    ServerAliveInterval 60
```

Speichern: `Strg+O`, `Enter` — beenden: `Strg+X`.

`HostName hexapod-pi` (ohne `.local`) wird vom Router-DNS aufgelöst. Bei
DNS-Problemen stattdessen die feste IP eintragen: `HostName 192.168.2.65`.

**3. Rechte der Config setzen** (sonst ignoriert SSH sie teilweise):

```bash
chmod 600 ~/.ssh/config
```

**4. Public-Key auf den Pi kopieren** (danach kein Passwort mehr nötig).
Fragt **einmal** nach dem Pi-Passwort (`pi`):

```bash
ssh-copy-id hexapod-pi
```

**5. Test:**

```bash
ssh hexapod-pi
```

→ sollte jetzt **direkt** reingehen — ohne Passwort, ohne `pi@…` tippen.
Ab hier nutzen auch `scp`, `rsync` und VSCode Remote-SSH denselben Alias
`hexapod-pi`.

#### B.2 Basis-Tools auf Pi

```bash
sudo apt update
# KEIN apt full-upgrade — gezielte Pakete reichen (CLAUDE.md §5)
sudo apt install -y vim git curl net-tools tmux htop
```

#### B.3 Locale, Universe-Repo, ROS-Repo

Identisch zu Phase 0 Schritte 1–3.

```bash
sudo apt install -y locales
sudo locale-gen en_US en_US.UTF-8
sudo update-locale LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8
export LANG=en_US.UTF-8

sudo apt install -y software-properties-common
sudo add-apt-repository universe   # einzige add-apt-repository-Ausnahme, dokumentiert
sudo apt update

# ROS-Repo
sudo apt install -y curl gnupg lsb-release
sudo curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key \
  -o /usr/share/keyrings/ros-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] http://packages.ros.org/ros2/ubuntu $(lsb_release -cs) main" \
  | sudo tee /etc/apt/sources.list.d/ros2.list > /dev/null
sudo apt update
```

**Done-Kriterium B:**
1. `ssh hexapod-pi` funktioniert **passwortlos** (Key-Auth + Config-Alias)
2. Basis-Tools installiert
3. ROS-Repo eingerichtet, `apt update` läuft sauber

---

### Stufe C — ROS2 Jazzy installieren (ohne Sim-Pakete)

```bash
sudo apt install -y \
  ros-jazzy-ros-base \
  ros-jazzy-ros2-control \
  ros-jazzy-ros2-controllers \
  ros-jazzy-xacro \
  ros-jazzy-joy \
  ros-jazzy-joint-state-publisher \
  ros-jazzy-robot-state-publisher \
  ros-jazzy-rclpy \
  ros-jazzy-pluginlib \
  ros-dev-tools
```

**Nicht installiert auf Pi:**
- `ros-jazzy-desktop` (kein RViz)
- `ros-jazzy-ros-gz` (kein Gazebo)
- `ros-jazzy-gz-ros2-control` (Sim-Plugin)

Environment in `~/.bashrc`:

```bash
echo "source /opt/ros/jazzy/setup.bash" >> ~/.bashrc
echo "export ROS_DOMAIN_ID=42" >> ~/.bashrc      # IDENTISCH zu Desktop!
echo "export RMW_IMPLEMENTATION=rmw_fastrtps_cpp" >> ~/.bashrc
source ~/.bashrc
```

`ROS_DOMAIN_ID` **muss** mit Desktop übereinstimmen. Auf Desktop nachsehen
und gleichen Wert setzen.

**Done-Kriterium C:**
1. `ros2 --help` zeigt Hilfe
2. `ros2 pkg list` zeigt installierte Pakete
3. `echo $ROS_DOMAIN_ID` gibt gleichen Wert wie Desktop

---

### Stufe D — DDS-Konnektivität Desktop ↔ Pi

**Ziel:** Bidirektionale ROS2-Topic-Kommunikation zwischen Desktop und Pi.

#### D.1 Talker/Listener-Test

Terminal A (Desktop):
```bash
ros2 run demo_nodes_cpp talker
```

Terminal B (auf Pi via SSH):
```bash
ros2 run demo_nodes_py listener
```

**Erwartung:** Pi empfängt vom Desktop. Umgekehrt:

Terminal C (Pi): `ros2 run demo_nodes_cpp talker`
Terminal D (Desktop): `ros2 run demo_nodes_py listener`

#### D.2 Wenn nichts ankommt

- `ROS_DOMAIN_ID` beidseitig prüfen: muss identisch sein
- Firewall: `sudo ufw status` — auf Pi typischerweise inactive, auf Desktop
  evtl. erlauben (`sudo ufw allow from 192.168.0.0/16`)
- WLAN-Isolation: manche Router blockieren Multicast zwischen Clients
- `ros2 multicast send` / `ros2 multicast receive` als Diagnose
- `ros2 daemon stop && ros2 daemon start` beidseitig

#### D.3 Topic-List-Sanity

Vom Pi aus:
```bash
ros2 topic list
ros2 node list
```

Sollte Knoten von beiden Seiten zeigen wenn jeweils Talker läuft.

**Done-Kriterium D:**
1. Talker/Listener Desktop → Pi grün
2. Talker/Listener Pi → Desktop grün
3. `ros2 topic list` zeigt Topics beider Seiten

---

### Stufe E — Workspace klonen + bauen

#### E.1 Workspace auf Pi anlegen

```bash
cd ~
# User pi hat keinen GitHub-SSH-Key -> HTTPS (ggf. mit Personal Access Token)
git clone https://github.com/enjoykin-ua/hexapod_ws.git
cd hexapod_ws
```

#### E.2 Sim-Paket überspringen

```bash
touch src/hexapod_gazebo/COLCON_IGNORE
```

Damit baut `hexapod_gazebo` auf dem Pi nicht (würde fehlschlagen weil
ros-gz nicht installiert ist).

#### E.3 rosdep + build

```bash
sudo rosdep init     # falls noch nie auf Pi gemacht
rosdep update
# --skip-keys: rosdep beachtet COLCON_IGNORE NICHT und wuerde sonst die
# Gazebo-Bridge (ros_gz_sim/ros_gz_bridge) aus hexapod_gazebo/package.xml
# mitziehen — die wollen wir am Pi nicht.
rosdep install --from-paths src --ignore-src -r -y \
  --skip-keys "ros_gz_sim ros_gz_bridge"
colcon build --symlink-install
source install/setup.bash
```

> **Hinweis:** Falls rosdep beim ersten Lauf (ohne `--skip-keys`) schon
> `ros-gz-bridge`/`ros-gz-interfaces` installiert hat: funktional
> unkritisch (läuft nichts davon, belegt nur Platz). Optional entfernen
> mit `sudo apt autoremove ros-jazzy-ros-gz-bridge ros-jazzy-ros-gz-interfaces`
> — nicht nötig.

#### E.4 Test: gait_node läuft

```bash
ros2 run hexapod_gait gait_node
# erwartet: startet, kein Crash, wartet auf /cmd_vel
```

`gait_node` wird auf Pi laufen können auch ohne HW (er publisht
Trajectories, niemand muss zuhören in dieser Phase).

**Done-Kriterium E:**
1. Workspace gebaut grün
2. `gait_node` startet sauber
3. Keine fehlenden Dependencies

---

### Stufe F — Loopback-Test `real.launch.py`

**Ziel:** Stack auf Pi ohne echte HW grün.

> **⚠️ Workspace sourcen nicht vergessen!** In *jeder* Shell, die ROS-Befehle
> oder Launches ausführt, muss der lokale Workspace geladen sein:
> ```bash
> source ~/hexapod_ws/install/setup.bash
> ```
> In **neuen** SSH-Sessions passiert das automatisch (`provision_pi.sh` hat
> es in `~/.bashrc` eingetragen). Nur in der Shell, in der du gerade
> `colcon build` ausgeführt hast, musst du es einmal von Hand sourcen —
> sonst meldet ROS `Package 'hexapod_bringup' not found` (es sucht dann nur
> in `/opt/ros/jazzy`, nicht in deinem Workspace).

```bash
source install/setup.bash    # falls in dieser Shell noch nicht geladen
ros2 launch hexapod_bringup real.launch.py loopback_mode:=true
```

`real.launch.py` aus Phase 9 wird hier zum ersten Mal auf Pi gefahren.
`hexapod_hardware` muss als Binary-Plugin (ARM-Build) vorhanden sein
— wurde in Stufe E mit gebaut.

Verifikation:
```bash
ros2 control list_controllers
# erwartet: 1× JSB + 6× JTC, alle "active"

ros2 topic list
# erwartet: /joint_states, /leg_*_controller/joint_trajectory, /cmd_vel, ...

ros2 topic echo /joint_states --once
# erwartet: 18 Joints mit position=0.0 (loopback echo)
```

#### F.4 Die 3 Starts via tmux (Test-Workflow)

Der Stack ist bewusst in **3 unabhängige Launches** geschnitten
(real.launch.py startet nur den ros2_control-Stack, *kein* gait/teleop).
Im Test fährst du sie in `tmux`-Panes über *eine* SSH-Session — robust
gegen Verbindungsabbruch (tmux läuft am Pi weiter).

```bash
ssh hexapod-pi
tmux new -s hexapod          # Session starten

# Pane 1 — Stack (real.launch). Loopback in Phase 12, HW spaeter.
ros2 launch hexapod_bringup real.launch.py loopback_mode:=true

# Ctrl-b "  (Pane horizontal splitten), dann Pane 2 — Gait:
ros2 launch hexapod_gait gait.launch.py use_sim_time:=false

# Ctrl-b %  (Pane vertikal splitten), dann Pane 3 — Teleop:
ros2 launch hexapod_teleop joy_teleop.launch.py controller:=ps4_bt
```

**Reihenfolge ist eine echte Abhängigkeit:** real muss laufen (JTCs
active), bevor gait sinnvoll publisht; gait muss laufen, bevor teleop
etwas bewirkt.

> **Falle (Memory `project_phase13_gait_launch_sim_time_default.md`):**
> `gait.launch.py` **immer mit `use_sim_time:=false`** auf HW/Pi — ohne
> `/clock` blockieren rclpy-Timer sonst still. Default ist bereits
> `false`, aber explizit setzen schadet nicht.

> **tmux-Bedienung:** `Strg+b` ist das **Prefix** — drücken, **loslassen**,
> *dann* die Befehlstaste (nicht gleichzeitig halten!). Auf der **deutschen
> Tastatur** brauchen die Split-Zeichen Shift: `"` = `Shift+2`, `%` =
> `Shift+5`. Zwischen Panes wechseln: `Strg+b` dann Pfeiltaste.
> **Einfacher zum Üben:** statt Splits einfach **3 separate SSH-Terminals**
> öffnen (je `ssh hexapod-pi` + `source install/setup.bash` + ein Launch).
> tmux ist nur nötig, damit es einen SSH-Abbruch übersteht.

> **Detach/Reattach:** `Strg+b` dann `d` löst von der Session, `tmux attach -t
> hexapod` hängt wieder an — der Stack läuft währenddessen weiter.

> **Ausblick (D4/D5):** Im Autonom-Betrieb ersetzt ein kombiniertes
> `autonomous.launch.py` + systemd-Service-Paar diesen manuellen
> tmux-Ablauf — siehe künftiges Autonom/untethered-Doc.

**Done-Kriterium F:**
1. `real.launch.py loopback_mode:=true` startet
2. Alle Controller active
3. Joint-States werden publisht (loopback echo)
4. 3-Starts-tmux-Ablauf einmal durchgespielt (Loopback)

---

### Stufe G — Deployment-Workflow

**Ziel:** Code-Änderung am Desktop landet schnell und reproduzierbar
auf dem Pi.

Wird in `docs_raspi/dev_workflow_desktop_to_pi.md` detailliert dokumentiert.
Kurzfassung:

- **Git als Source of Truth:** Commit am Desktop, `git pull` am Pi.
- **rsync für schnelle Iteration:** `rsync -avz --exclude=build --exclude=install --exclude=log ~/hexapod_ws/ hexapod-pi:~/hexapod_ws/`
- **VSCode Remote-SSH:** Workspace im Remote-Mode öffnen.
- **`colcon build` immer auf Pi** (ARM-Build, Desktop-`install/` ist nicht
  portabel).

#### G.1 Workflow-Probe

- Eine Trivial-Änderung am Desktop machen (Kommentar in `gait_node.py`
  einfügen)
- Per beiden Wegen (Git und rsync) zum Pi bringen, jeweils rebuild
- Beobachten: was ist schneller, was ist robuster?

#### G.2 Dokumentation finalisieren

In `dev_workflow_desktop_to_pi.md` festhalten:
- SSH-Setup
- Beide Workflows (Git, rsync)
- VSCode Remote-SSH-Hinweis
- Anti-Pattern: kein NFS-Mount mit gemeinsamem `build/`

**Done-Kriterium G:**
1. `dev_workflow_desktop_to_pi.md` final
2. Workflow-Probe mit Git **und** rsync je einmal durchgespielt

---

### Stufe H — Shutdown-Disziplin

**Ziel:** Pi-Image schützen vor Korruption durch unsaubere Abschaltung.

In `phase_12_progress.md` Stufe H schriftlich:

- **Immer** `sudo shutdown -h now` per SSH bevor Hauptschalter aus.
- Warten bis grüne LED am Pi erlischt.
- **Erst dann** Strom trennen.
- Begründung: Pi 5 + Linux + USB-SSD verzeiht keine schmutzige Abschaltung
  im laufenden Schreibvorgang. SD ist noch empfindlicher.
- Alias am Desktop sinnvoll: `alias hexapod-shutdown='ssh hexapod-pi sudo shutdown -h now'`

**Done-Kriterium H:**
1. Shutdown-Prozedur im Progress-File
2. Alias / Konvention im Workflow-Doc

---

### Stufe I — Phase-12-Abschluss

- `phase_12_progress.md` finalisieren
- `dev_workflow_desktop_to_pi.md` final (separates Doc, kein Phasen-Done-
  Kriterium dort, aber Voraussetzung für Phase 13)
- Git-Commit + Tag `phase-12-done`
- `PHASE.md` auf Phase 13 aktualisieren
- Retro

---

## Stolperfallen

| Symptom | Ursache | Fix |
|---|---|---|
| Pi bootet nicht / kein SSH | Image-Schreibfehler, WLAN-Credentials falsch | Imager mit Verify nochmal, Direkt-Bootup mit HDMI |
| `hexapod-pi.local` nicht auflösbar | mDNS/avahi nicht installiert (Ubuntu Server Default) | reinen Namen `hexapod-pi` (Router-DNS) oder IP `192.168.2.65` nutzen; optional `avahi-daemon` installieren |
| `apt install ros-jazzy-*` schlägt fehl | ROS-Repo nicht eingebunden / falsche Codename | `/etc/apt/sources.list.d/ros2.list` prüfen, `apt update` |
| `colcon build` extrem langsam | Pi mit SD-Karte + zu wenig Swap | SSD verwenden, `--parallel-workers 2` |
| DDS sieht nichts | `ROS_DOMAIN_ID` mismatch | beidseitig `echo $ROS_DOMAIN_ID` |
| Builds OK, aber Runtime-Fehler „ros2_control plugin not found" | hexapod_hardware nicht für ARM gebaut | `colcon build --packages-select hexapod_hardware` am Pi nochmal |
| `Package 'hexapod_bringup' not found` (sucht nur in `/opt/ros/jazzy`) | Workspace in dieser Shell nicht gesourct | `source ~/hexapod_ws/install/setup.bash` (in neuer SSH-Session automatisch via `~/.bashrc`) |
| rsync transferiert auch `build/` | Exclude vergessen | `--exclude=build --exclude=install --exclude=log` |

---

## Was in dieser Phase **NICHT** gemacht wird

- Kein Anschluss von Servo2040 an Pi (Phase 13)
- Keine Bewegungs-Tests am Pi (Phase 13)
- Kein PREEMPT-RT-Kernel — Standard-Kernel reicht für 50 Hz Gait
- Keine zusätzlichen Sensoren
- Kein Bluetooth-PS4 (separates Defer)
- **Kein OLED-Status, kein GPIO-Button, kein systemd-Autostart, keine
  Power-On-Relay-Sequenz** — der gesamte **Autonom/untethered-Betrieb**
  (immer-laufender Supervisor-Service + OLED über EKM002-QWIIC-I²C +
  Button-Trigger + kombiniertes `autonomous.launch.py`) kommt in ein
  **eigenes Doc unter Block D4/D5**. Phase 12 bleibt bewusst schlank
  („Plattform steht, Stack startbar via SSH/tmux"). Provisioning-Stubs
  dafür sind in [`tools/provision_pi.sh`](../tools/provision_pi.sh) als
  `provision_oled_button()` bereits als Platzhalter markiert.

---

## Phasenabschluss-Checkliste

- [ ] Alle Stufen A–H Done-Kriterien erfüllt
- [ ] Pi headless via SSH erreichbar mit Schlüssel
- [ ] Workspace baut grün (außer hexapod_gazebo)
- [ ] DDS Desktop ↔ Pi bidirektional
- [ ] `real.launch.py loopback_mode:=true` auf Pi grün
- [ ] `dev_workflow_desktop_to_pi.md` final
- [ ] Shutdown-Disziplin dokumentiert
- [ ] Git-Commit + Tag `phase-12-done`
- [ ] `PHASE.md` auf Phase 13 aktualisiert
- [ ] Retrospektive in `phase_12_progress.md`
