#!/usr/bin/env bash
#
# provision_pi.sh — Idempotentes Provisioning des Raspberry Pi 5 fuer den
# Hexapod-Stack (Phase 12, Block D1).
#
# ZWECK
#   Bringt einen frisch geflashten Pi (Ubuntu Server 24.04 LTS arm64,
#   headless) von "nackt" auf "Workspace baut + Stack startbar". Alle
#   System-Ebenen-Einstellungen, die NICHT im Workspace-Git liegen
#   (APT-Pakete, ROS-Repo, Locale, ~/.bashrc-Env, udev-Rules), werden
#   hier als Code gehalten.
#
#   Recovery nach SD-/SSD-Ausfall:
#     1. Pi Imager: Ubuntu Server 24.04 LTS arm64 + SSH-Key + WLAN
#     2. Workspace klonen. ACHTUNG: der GitHub-Zugang des Pi ist selbst
#        System-State und nach SD-Tod weg. Daher entweder
#          a) HTTPS + Personal Access Token (kein Pi-seitiger Key noetig):
#             git clone https://github.com/enjoykin-ua/hexapod_ws.git ~/hexapod_ws
#          b) ODER neuen SSH-Deploy-Key am Pi erzeugen und bei GitHub
#             hinterlegen, dann:
#             git clone git@github.com:enjoykin-ua/hexapod_ws.git ~/hexapod_ws
#     3. ~/hexapod_ws/tools/provision_pi.sh
#     4. cd ~/hexapod_ws && colcon build --symlink-install
#
# IDEMPOTENZ
#   Jeder Schritt prueft vor der Aenderung, ob er noetig ist. Das Skript
#   ist beliebig oft ausfuehrbar, ohne Schaden anzurichten. Genau das
#   macht es als Recovery-Werkzeug brauchbar.
#
# MITWACHSEND (Phase 12 Stufen B/C/E)
#   Dieses Skript wird NICHT vorab "fertig" geschrieben und dann blind
#   ausgefuehrt. Beim ersten echten Aufsetzen am Pi wird jeder Block
#   einzeln verifiziert und ggf. korrigiert (z. B. Servo2040-VID:PID,
#   ROS_DOMAIN_ID). So ist das Skript am Ende von Phase 12 genau einmal
#   real erprobt. Stellen mit Verifikationsbedarf sind mit
#   "# VERIFY@PI" markiert.
#
# CLAUDE.md §5 — KEINE verbotenen Aktionen:
#   Keine full-upgrade/dist-upgrade, keine NVIDIA/Kernel/GRUB-Eingriffe,
#   nur ros-* + klar dokumentierte Build-Tools. add-apt-repository nur
#   fuer 'universe' (dokumentierte Ausnahme, Phase 12 Stufe B.3).

set -euo pipefail

# ---------------------------------------------------------------------------
# 0. Guards & Setup
# ---------------------------------------------------------------------------

# Architektur-Guard: NIEMALS am x86-Desktop laufen lassen — das wuerde dort
# apt/locale/~/.bashrc veraendern. Nur auf arm64 (Pi) zugelassen.
if [[ "$(uname -m)" != "aarch64" ]]; then
    echo "FEHLER: Dieses Skript ist fuer den Raspberry Pi (aarch64) gedacht." >&2
    echo "        Aktuelle Architektur: $(uname -m). Abbruch." >&2
    echo "        (Schutz gegen versehentliche Ausfuehrung am Desktop.)" >&2
    exit 1
fi

if [[ "${EUID}" -eq 0 ]]; then
    echo "FEHLER: Nicht als root ausfuehren. Skript ruft 'sudo' wo noetig." >&2
    exit 1
fi

readonly ROS_DISTRO="jazzy"
readonly WS_DIR="${HOME}/hexapod_ws"

# Sammelbecken fuer Schritte, die das Skript NICHT automatisieren kann und
# die der Mensch nach dem Lauf erledigen muss. Wird am Ende ausgegeben.
MANUAL_STEPS=()

# --- Logging-Helper ---------------------------------------------------------
c_info()   { printf '\033[1;34m[ .. ]\033[0m %s\n' "$*"; }
c_ok()     { printf '\033[1;32m[ OK ]\033[0m %s\n' "$*"; }
c_skip()   { printf '\033[1;90m[skip]\033[0m %s\n' "$*"; }
c_warn()   { printf '\033[1;33m[warn]\033[0m %s\n' "$*"; }
c_manual() { MANUAL_STEPS+=("$*"); printf '\033[1;35m[MANL]\033[0m %s\n' "$*"; }

# ---------------------------------------------------------------------------
# 1. Locale (Phase 12 Stufe B.3)
# ---------------------------------------------------------------------------
provision_locale() {
    c_info "Locale en_US.UTF-8 sicherstellen ..."
    if locale | grep -q 'LANG=en_US.UTF-8'; then
        c_skip "Locale bereits en_US.UTF-8"
        return
    fi
    sudo apt-get install -y locales
    sudo locale-gen en_US en_US.UTF-8
    sudo update-locale LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8
    c_ok "Locale gesetzt (greift in neuer Shell)"
}

# ---------------------------------------------------------------------------
# 2. universe-Repo (Phase 12 Stufe B.3)
#    Einzige dokumentierte add-apt-repository-Ausnahme (CLAUDE.md §5).
# ---------------------------------------------------------------------------
provision_universe() {
    c_info "universe-Repo sicherstellen ..."
    if apt-cache policy 2>/dev/null | grep -q 'universe'; then
        c_skip "universe bereits aktiv"
        return
    fi
    sudo apt-get install -y software-properties-common
    sudo add-apt-repository -y universe
    c_ok "universe aktiviert"
}

# ---------------------------------------------------------------------------
# 3. ROS-2-apt-Repo (Phase 12 Stufe B.3)
# ---------------------------------------------------------------------------
provision_ros_repo() {
    c_info "ROS-2-apt-Repo sicherstellen ..."
    local keyring="/usr/share/keyrings/ros-archive-keyring.gpg"
    local list="/etc/apt/sources.list.d/ros2.list"

    sudo apt-get install -y curl gnupg lsb-release

    if [[ ! -f "${keyring}" ]]; then
        sudo curl -sSL \
            https://raw.githubusercontent.com/ros/rosdistro/master/ros.key \
            -o "${keyring}"
        c_ok "ROS-Keyring installiert"
    else
        c_skip "ROS-Keyring vorhanden"
    fi

    if [[ ! -f "${list}" ]]; then
        echo "deb [arch=$(dpkg --print-architecture) signed-by=${keyring}] http://packages.ros.org/ros2/ubuntu $(lsb_release -cs) main" \
            | sudo tee "${list}" > /dev/null
        c_ok "ROS-sources.list angelegt"
    else
        c_skip "ROS-sources.list vorhanden"
    fi

    sudo apt-get update
}

# ---------------------------------------------------------------------------
# 4. Basis-Tools (Phase 12 Stufe B.2)
# ---------------------------------------------------------------------------
provision_base_tools() {
    c_info "Basis-Tools sicherstellen ..."
    # tmux ist Pflicht: die 3 Stack-Starts laufen in tmux-Panes (Stufe F).
    sudo apt-get install -y vim git curl net-tools tmux htop
    c_ok "Basis-Tools installiert"
}

# ---------------------------------------------------------------------------
# 5. ROS-2-Jazzy-Pakete (Phase 12 Stufe C) — ros-base, KEINE Sim-Pakete
# ---------------------------------------------------------------------------
provision_ros_packages() {
    c_info "ROS-2-${ROS_DISTRO}-Pakete sicherstellen (ros-base, kein Gazebo/RViz) ..."
    sudo apt-get install -y \
        ros-${ROS_DISTRO}-ros-base \
        ros-${ROS_DISTRO}-ros2-control \
        ros-${ROS_DISTRO}-ros2-controllers \
        ros-${ROS_DISTRO}-xacro \
        ros-${ROS_DISTRO}-joy \
        ros-${ROS_DISTRO}-joint-state-publisher \
        ros-${ROS_DISTRO}-robot-state-publisher \
        ros-${ROS_DISTRO}-rclpy \
        ros-${ROS_DISTRO}-pluginlib \
        ros-dev-tools
    c_ok "ROS-Pakete installiert"
    # Bewusst NICHT: ros-jazzy-desktop, ros-jazzy-ros-gz, gz-ros2-control.
}

# ---------------------------------------------------------------------------
# 6. ~/.bashrc-Environment (Phase 12 Stufe C)
# ---------------------------------------------------------------------------
provision_bashrc() {
    c_info "~/.bashrc-Environment sicherstellen ..."
    local rc="${HOME}/.bashrc"
    local marker="# >>> hexapod provision_pi.sh >>>"

    if grep -qF "${marker}" "${rc}"; then
        c_skip "bashrc-Block bereits vorhanden"
    else
        {
            echo ""
            echo "${marker}"
            echo "source /opt/ros/${ROS_DISTRO}/setup.bash"
            # ROS_DOMAIN_ID MUSS mit dem Desktop uebereinstimmen. 42 ist der
            # in der Phase-12-Doku gesetzte Wert. VERIFY@PI: am Desktop
            # 'echo $ROS_DOMAIN_ID' pruefen und hier ggf. anpassen.
            echo "export ROS_DOMAIN_ID=42"
            echo "export RMW_IMPLEMENTATION=rmw_fastrtps_cpp"
            echo "[ -f ${WS_DIR}/install/setup.bash ] && source ${WS_DIR}/install/setup.bash"
            echo "# <<< hexapod provision_pi.sh <<<"
        } >> "${rc}"
        c_ok "bashrc-Block angehaengt"
    fi
    c_manual "ROS_DOMAIN_ID in ~/.bashrc (Default 42) muss mit dem Desktop uebereinstimmen — am Desktop 'echo \$ROS_DOMAIN_ID' pruefen."
}

# ---------------------------------------------------------------------------
# 7. rosdep (Phase 12 Stufe E.3)
# ---------------------------------------------------------------------------
provision_rosdep() {
    c_info "rosdep sicherstellen ..."
    if [[ ! -f /etc/ros/rosdep/sources.list.d/20-default.list ]]; then
        sudo rosdep init || c_warn "rosdep init bereits gemacht oder fehlgeschlagen"
    else
        c_skip "rosdep bereits initialisiert"
    fi
    rosdep update
    c_ok "rosdep aktuell"
}

# ---------------------------------------------------------------------------
# 8. hexapod_gazebo vom Pi-Build ausschliessen (Phase 12 Stufe E.2)
# ---------------------------------------------------------------------------
provision_colcon_ignore() {
    c_info "hexapod_gazebo via COLCON_IGNORE ausschliessen ..."
    local ign="${WS_DIR}/src/hexapod_gazebo/COLCON_IGNORE"
    if [[ -f "${ign}" ]]; then
        c_skip "COLCON_IGNORE vorhanden"
    else
        touch "${ign}"
        c_ok "COLCON_IGNORE gesetzt (kein ros-gz auf Pi)"
    fi
}

# ---------------------------------------------------------------------------
# 9. udev-Rule fuer Servo2040 (stabiler /dev/servo2040-Symlink)
#    Servo2040 = Pimoroni RP2040-Board, USB-VID typ. 2e8a (Raspberry Pi).
#    Die PID haengt von der FW ab und MUSS am Pi verifiziert werden.
# ---------------------------------------------------------------------------
provision_udev_servo2040() {
    c_info "udev-Rule fuer Servo2040 sicherstellen ..."
    local rule="/etc/udev/rules.d/99-servo2040.rules"

    if [[ -f "${rule}" ]]; then
        c_skip "udev-Rule vorhanden (${rule})"
        return
    fi

    # VERIFY@PI: echte VID:PID ermitteln, solange die Servo2040 angesteckt ist:
    #   lsusb        -> Zeile des Boards finden
    #   udevadm info -a -n /dev/ttyACM0 | grep -E 'idVendor|idProduct'
    # Default-Annahme VID 2e8a (Raspberry Pi RP2040). Wenn die echte ID
    # abweicht, diese Funktion korrigieren.
    echo 'SUBSYSTEM=="tty", ATTRS{idVendor}=="2e8a", SYMLINK+="servo2040"' \
        | sudo tee "${rule}" > /dev/null
    sudo udevadm control --reload-rules
    sudo udevadm trigger || true
    c_ok "udev-Rule angelegt -> /dev/servo2040"
    c_manual "udev-Rule 99-servo2040.rules: echte USB-VID:PID mit 'lsusb' + 'udevadm info -a -n /dev/ttyACM0' verifizieren (Default-VID 2e8a angenommen)."
    c_manual "Nach Anstecken der Servo2040 pruefen: 'ls -l /dev/servo2040' muss auf /dev/ttyACMx zeigen."
}

# ---------------------------------------------------------------------------
# 10. D4/D5 (OLED + GPIO-Button) — NOCH NICHT AKTIV
#     Wird erst mit dem Autonom-Betrieb-Doc befuellt. Hier nur als
#     Platzhalter, damit der rote Faden im Skript sichtbar bleibt.
# ---------------------------------------------------------------------------
provision_oled_button() {
    c_skip "OLED/Button (D4/D5): noch nicht aktiv — kommt mit Autonom-Doc"
    # TODO (D4/D5): I2C aktivieren (SSD1306 @ 0x3C ueber EKM002-QWIIC),
    #   pip-Deps luma.oled / gpiozero / lgpio (venv), systemd-Service-Paar
    #   hexapod-supervisor + hexapod-stack. Siehe kuenftiges D4/D5-Doc.
}

# ---------------------------------------------------------------------------
# Manuelle Schritte, die das Skript prinzipiell nicht wissen kann
# ---------------------------------------------------------------------------
register_known_manual_steps() {
    c_manual "Pi Imager: SSH-Public-Key + WLAN-Credentials werden beim Flashen gesetzt — nicht durch dieses Skript."
    c_manual "GitHub-Zugang des Pi ist nach SD-Tod weg: clone via HTTPS+PAT ODER neuen SSH-Deploy-Key am Pi erzeugen + bei GitHub hinterlegen (siehe Skript-Header Recovery-Pfad)."
    c_manual "PS4-Bluetooth-Bonding ist System-State und geht bei SD-Tod verloren -> Controller neu pairen (siehe reference_ps4_bluetooth / C4)."
    c_manual "Workspace bauen ist eigener Schritt: 'cd ${WS_DIR} && colcon build --symlink-install' (ARM-Build, dauert)."
}

# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------
main() {
    c_info "Hexapod-Pi-Provisioning startet (arm64 verifiziert) ..."
    sudo apt-get update

    provision_locale
    provision_universe
    provision_ros_repo
    provision_base_tools
    provision_ros_packages
    provision_bashrc
    provision_rosdep
    provision_colcon_ignore
    provision_udev_servo2040
    provision_oled_button

    register_known_manual_steps

    echo ""
    echo "============================================================"
    c_ok "Automatisierte Provisionierung abgeschlossen."
    echo "============================================================"
    if [[ ${#MANUAL_STEPS[@]} -gt 0 ]]; then
        echo ""
        printf '\033[1;35mMANUELLE SCHRITTE — bitte pruefen/erledigen:\033[0m\n'
        local i=1
        for step in "${MANUAL_STEPS[@]}"; do
            printf '  %2d. %s\n' "${i}" "${step}"
            ((i++))
        done
    fi
    echo ""
    echo "Naechster Schritt:"
    echo "  cd ${WS_DIR}"
    echo "  rosdep install --from-paths src --ignore-src -r -y"
    echo "  colcon build --symlink-install"
    echo "  source install/setup.bash"
}

main "$@"
