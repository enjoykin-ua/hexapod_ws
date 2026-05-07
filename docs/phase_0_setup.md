# Phase 0 — Desktop-Setup

**Dauer-Schätzung:** 0.5–1 Tag
**Maschine:** Ubuntu 24.04 Desktop (RTX 3080)
**Vorbedingung:** Frisch installiertes Ubuntu 24.04, Internet, sudo-Rechte

---

## Ziel

Ein lauffähiger ROS2-Jazzy-Stack mit Gazebo Harmonic, `ros2_control`,
`rviz2` und einem leeren, baubaren Workspace. Kein URDF, kein Roboter,
keine Hardware — nur die Toolchain.

---

## Done-Kriterien

Alle vier Smoke-Tests müssen ohne Fehler durchlaufen:

1. `ros2 run demo_nodes_cpp talker` (Terminal A)
   und `ros2 run demo_nodes_py listener` (Terminal B)
   tauschen Nachrichten aus.
2. `gz sim` öffnet ein leeres 3D-Fenster ohne Fehler.
3. `rviz2` öffnet sich ohne Fehler.
4. `colcon build` im leeren `~/hexapod_ws` läuft fehlerfrei durch.

---

## Vorbereitung (zwingend, vor jeder System-Änderung)

### Snapshot-Backup einrichten

```bash
sudo apt update
sudo apt install timeshift -y
```

Timeshift starten (GUI), als Backend **rsync** wählen, Ziel-Disk
festlegen, einen ersten Snapshot mit Namen `pre-ros` anlegen.

> **Warum:** Wenn irgendein Schritt das System bricht, bist du in
> Minuten zurück. Das hat beim letzten Anlauf gefehlt.

### Git-Identität setzen (falls noch nicht)

```bash
git config --global user.name "Dein Name"
git config --global user.email "deine@mail.tld"
```

---

## Schritte

### 1. Locale prüfen / setzen

```bash
locale
```

Wenn nicht UTF-8:

```bash
sudo apt update && sudo apt install locales -y
sudo locale-gen en_US en_US.UTF-8
sudo update-locale LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8
export LANG=en_US.UTF-8
locale
```

### 2. Universe-Repo aktivieren

```bash
sudo apt install software-properties-common -y
sudo add-apt-repository universe
```

> Das ist die **einzige** `add-apt-repository`-Aktion, die in Phase 0
> erlaubt ist. Universe ist ein offizielles Ubuntu-Repo, kein PPA.

### 3. ROS2-apt-Repo einrichten

Offizieller Weg (seit 2024 über das `ros2-apt-source`-Paket):

```bash
sudo apt update && sudo apt install curl -y

export ROS_APT_SOURCE_VERSION=$(curl -s https://api.github.com/repos/ros-infrastructure/ros-apt-source/releases/latest | grep -F "tag_name" | awk -F'"' '{print $4}')

curl -L -o /tmp/ros2-apt-source.deb \
  "https://github.com/ros-infrastructure/ros-apt-source/releases/download/${ROS_APT_SOURCE_VERSION}/ros2-apt-source_${ROS_APT_SOURCE_VERSION}.$(. /etc/os-release && echo ${UBUNTU_CODENAME:-${VERSION_CODENAME}})_all.deb"

sudo dpkg -i /tmp/ros2-apt-source.deb
sudo apt update
```

> **Verifikation:** `apt-cache policy ros-jazzy-desktop` muss eine
> Version aus `packages.ros.org` zeigen. Wenn nicht: STOP.

### 4. ROS2 + Gazebo + ros2_control installieren

```bash
sudo apt install -y \
  ros-jazzy-desktop \
  ros-jazzy-ros-gz \
  ros-jazzy-ros2-control \
  ros-jazzy-ros2-controllers \
  ros-jazzy-gz-ros2-control \
  ros-jazzy-joint-state-publisher-gui \
  ros-jazzy-xacro \
  ros-dev-tools
```

> **Was hier NICHT installiert wird:**
> - `gazebo` (das wäre Gazebo Classic, EOL)
> - irgendetwas aus `packages.osrfoundation.org`
> - PPA-Treiber

### 5. Environment einrichten

```bash
echo "source /opt/ros/jazzy/setup.bash" >> ~/.bashrc
echo "export ROS_DOMAIN_ID=42" >> ~/.bashrc        # beliebige Zahl 0..101
echo "export RMW_IMPLEMENTATION=rmw_fastrtps_cpp" >> ~/.bashrc
source ~/.bashrc
```

> **`ROS_DOMAIN_ID`:** Trennt deine ROS-Knoten von anderen im Netz.
> Auf Pi und Desktop muss später dieselbe ID stehen.
> **`RMW_IMPLEMENTATION`:** FastDDS ist Default in Jazzy, expliziter
> Eintrag verhindert spätere Überraschungen.

### 6. RTX 3080 / Wayland — vorsorglicher Workaround

```bash
echo "export QT_QPA_PLATFORM=xcb" >> ~/.bashrc
source ~/.bashrc
```

Falls Gazebo dennoch zickt: am Login-Screen „Ubuntu on Xorg" wählen
statt Wayland. **NICHT** Treiber tauschen, NICHT Mesa anfassen.

### 7. Workspace anlegen

```bash
mkdir -p ~/hexapod_ws/src
cd ~/hexapod_ws
colcon build
```

Erwartete Ausgabe: `Summary: 0 packages finished` — keine Fehler.
Es entstehen `build/`, `install/`, `log/`.

### 8. Workspace-Source in .bashrc

```bash
echo "source ~/hexapod_ws/install/setup.bash" >> ~/.bashrc
source ~/.bashrc
```

> Das funktioniert auch bei leerem Workspace, weil `colcon build`
> ein generisches `setup.bash` erzeugt.

### 9. Git-Repo initialisieren

```bash
cd ~/hexapod_ws
git init
```

`.gitignore`:

```gitignore
build/
install/
log/
__pycache__/
*.pyc
.vscode/
```

```bash
git add .
git commit -m "phase0: initial workspace + docs"
```

### 10. Smoke-Tests

**Test 1 — talker/listener:**

Terminal A:
```bash
ros2 run demo_nodes_cpp talker
```

Terminal B:
```bash
ros2 run demo_nodes_py listener
```

Erwartung: Listener empfängt „Hello World: <Zähler>"-Meldungen.

**Test 2 — Gazebo:**

```bash
gz sim
```

Erwartung: GUI öffnet sich, „Empty"-Welt auswählbar, „Play"-Button
startet die Sim ohne Crash.

**Test 3 — RViz:**

```bash
rviz2
```

Erwartung: GUI öffnet sich, kein Crash.

**Test 4 — Build:**

```bash
cd ~/hexapod_ws
colcon build
```

Erwartung: 0 Pakete, 0 Fehler.

---

## Stolperfallen / typische Fehler

| Symptom | Ursache | Fix |
|---|---|---|
| `gz sim` crasht mit `libicu`-Fehler | inkonsistente Vendor-Pakete | `sudo apt install --reinstall ros-jazzy-ros-gz` |
| `gz sim` öffnet schwarzes Fenster | Wayland + NVIDIA | `QT_QPA_PLATFORM=xcb` setzen, Xorg-Session |
| `ros2: command not found` | `setup.bash` nicht gesourct | `.bashrc` prüfen, Terminal neu öffnen |
| `colcon: command not found` | `ros-dev-tools` fehlt | nachinstallieren |
| Listener empfängt nichts | `ROS_DOMAIN_ID` unterschiedlich pro Terminal | beide Terminals neu öffnen |
| `apt`-Konflikt mit `gz-*` | `packages.osrfoundation.org` versehentlich aktiv | `/etc/apt/sources.list.d/` prüfen, OSRF-Quelle entfernen |

---

## Was in dieser Phase **NICHT** gemacht wird

- Kein URDF schreiben
- Kein Roboter laden
- Kein `nvidia-*`, `mesa`, `libgl`, `kernel`-Paket anfassen
- Kein `apt full-upgrade` / `dist-upgrade`
- Kein `do-release-upgrade`
- Kein PPA hinzufügen (außer Universe)
- Kein VS-Code-Plugin-Setup-Detail (das machst du parallel selbst)

---

## Phasenabschluss

- [ ] Alle 4 Smoke-Tests grün
- [ ] Timeshift-Snapshot `phase_0_done` angelegt
- [ ] Git-Commit + Tag `phase-0-done`
- [ ] `PHASE.md` auf Phase 1 aktualisiert
