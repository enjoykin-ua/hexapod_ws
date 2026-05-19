# Phase 12 — Pi-Plattform & Portierung

**Dauer-Schätzung:** 1–2 Tage (OS + ROS2 + Workspace + DDS-Konnektivität)
**Maschine:** Raspberry Pi 4 (8 GB) **und** Desktop (für SSH/Deployment)
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

## Hardware-Setup für diese Phase

- Raspberry Pi 4 (8 GB) — bisher unbenutzt
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
7. Loopback-Test: `real.launch.py loopback:=true` auf Pi startet alle
   Controller active
8. Shutdown-Disziplin dokumentiert

---

## Stufen

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
  - User: `enjoykin` (oder eigener Name), Passwort setzen (Fallback wenn
    SSH-Key nicht zieht)
  - WLAN-Credentials eintragen (für Headless-Boot)
  - Locale, Tastatur

#### A.3 Erstbootup

- SSD/SD an Pi, Pi an Strom (zunächst Standard-5V-USB-C-Netzteil)
- 2 Minuten warten
- Vom Desktop:

```bash
ping hexapod-pi.local       # mDNS, sollte funktionieren
ssh enjoykin@hexapod-pi.local
```

Wenn mDNS nicht klappt: IP-Adresse vom Router rausfinden, mit IP einloggen.

**Done-Kriterium A:**
1. Pi bootet, SSH-Login mit Key erfolgreich
2. `uname -a` zeigt arm64 / 24.04 LTS

---

### Stufe B — SSH-Workflow & Basis-Tools

#### B.1 SSH-Config am Desktop

`~/.ssh/config` ergänzen:

```
Host hexapod-pi
    HostName hexapod-pi.local
    User enjoykin
    IdentityFile ~/.ssh/id_ed25519
    ServerAliveInterval 60
```

Dann reicht `ssh hexapod-pi` als Kommando.

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
1. SSH-Config-Alias `hexapod-pi` funktioniert
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
mkdir -p ~/hexapod_ws
cd ~
git clone <repo-url> hexapod_ws    # User trägt URL ein
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
rosdep install --from-paths src --ignore-src -r -y
colcon build --symlink-install
source install/setup.bash
```

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

```bash
ros2 launch hexapod_bringup real.launch.py loopback:=true
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

**Done-Kriterium F:**
1. `real.launch.py loopback:=true` startet
2. Alle Controller active
3. Joint-States werden publisht (loopback echo)

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
- Begründung: Pi 4 + Linux + USB-SSD verzeiht keine schmutzige Abschaltung
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
| `hexapod-pi.local` nicht auflösbar | mDNS nicht aktiv | IP direkt verwenden, `avahi-daemon` prüfen |
| `apt install ros-jazzy-*` schlägt fehl | ROS-Repo nicht eingebunden / falsche Codename | `/etc/apt/sources.list.d/ros2.list` prüfen, `apt update` |
| `colcon build` extrem langsam | Pi mit SD-Karte + zu wenig Swap | SSD verwenden, `--parallel-workers 2` |
| DDS sieht nichts | `ROS_DOMAIN_ID` mismatch | beidseitig `echo $ROS_DOMAIN_ID` |
| Builds OK, aber Runtime-Fehler „ros2_control plugin not found" | hexapod_hardware nicht für ARM gebaut | `colcon build --packages-select hexapod_hardware` am Pi nochmal |
| rsync transferiert auch `build/` | Exclude vergessen | `--exclude=build --exclude=install --exclude=log` |

---

## Was in dieser Phase **NICHT** gemacht wird

- Kein Anschluss von Servo2040 an Pi (Phase 13)
- Keine Bewegungs-Tests am Pi (Phase 13)
- Kein PREEMPT-RT-Kernel — Standard-Kernel reicht für 50 Hz Gait
- Keine zusätzlichen Sensoren
- Kein Bluetooth-PS4 (separates Defer)

---

## Phasenabschluss-Checkliste

- [ ] Alle Stufen A–H Done-Kriterien erfüllt
- [ ] Pi headless via SSH erreichbar mit Schlüssel
- [ ] Workspace baut grün (außer hexapod_gazebo)
- [ ] DDS Desktop ↔ Pi bidirektional
- [ ] `real.launch.py loopback:=true` auf Pi grün
- [ ] `dev_workflow_desktop_to_pi.md` final
- [ ] Shutdown-Disziplin dokumentiert
- [ ] Git-Commit + Tag `phase-12-done`
- [ ] `PHASE.md` auf Phase 13 aktualisiert
- [ ] Retrospektive in `phase_12_progress.md`
