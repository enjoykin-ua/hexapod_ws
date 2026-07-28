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
# 0b. APT-Pocket-Check: noble-updates MUSS aktiv sein
#     Manche Pi-Images (so das aktuelle) kommen nur mit 'noble' +
#     'noble-security' -> die aktualisierten -dev-Pakete (in <codename>-updates)
#     fehlen, und die ROS-Installation scheitert an Versions-Mismatches
#     (libdrm-dev = base, aber libdrm2 = security usw.).
#     Das Skript aendert /etc/apt NICHT selbst (CLAUDE.md §5) -> es prueft
#     nur und bricht mit Anleitung ab, falls das Pocket fehlt.
# ---------------------------------------------------------------------------
check_apt_updates_pocket() {
    c_info "APT-Pocket '<codename>-updates' pruefen ..."
    local codename
    codename="$(. /etc/os-release && echo "${VERSION_CODENAME}")"
    if apt-cache policy 2>/dev/null | grep -q "${codename}-updates"; then
        c_ok "${codename}-updates ist aktiv"
        return
    fi
    c_warn "${codename}-updates fehlt in den APT-Quellen — Abbruch."
    cat >&2 <<EOF

Die ROS-Installation wuerde sonst an Versions-Mismatches scheitern
(libdrm-dev, zlib1g-dev, ...). Fix (einmalig, aendert /etc/apt — CLAUDE.md §5):

  sudo cp /etc/apt/sources.list.d/ubuntu.sources \\
          /etc/apt/sources.list.d/ubuntu.sources.bak
  sudo sed -i '/^Suites: ${codename}\$/s/.*/Suites: ${codename} ${codename}-updates/' \\
          /etc/apt/sources.list.d/ubuntu.sources
  sudo apt update

Danach dieses Skript erneut ausfuehren.
EOF
    exit 1
}

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
# 4b. Bluetooth (bluez) fuer PS4-Teleop ueber BT
#     Fehlt auf dem frischen Ubuntu-Server-Image; ohne bluez kein
#     bluetoothctl -> kein DS4-Pairing -> kein ps4_bt-Teleop.
# ---------------------------------------------------------------------------
provision_bluetooth() {
    c_info "Bluetooth (bluez) fuer PS4-Teleop sicherstellen ..."
    sudo apt-get install -y bluez
    sudo systemctl enable --now bluetooth \
        || c_warn "bluetooth.service nicht gestartet — ggf. 'rfkill unblock bluetooth'"
    c_ok "bluez installiert, bluetooth.service aktiv"
    c_manual "PS4-BT-Pairing ist System-State (nach SD-Tod weg): DS4 neu pairen — 'bluetoothctl' -> scan/pair/trust/connect (MAC D0:27:88:3D:68:9A)."
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
#    VERIFIZIERT am Pi: Servo2040 = RP2040-Board, meldet sich als
#    "Raspberry Pi Pico", ID_VENDOR_ID=2e8a, ID_MODEL_ID=000a,
#    Serial z.B. E6617C93E3494428. -> /dev/servo2040 -> ttyACM0 funktioniert.
#    Match auf VID 2e8a reicht, solange nur EIN RP2040-Geraet am Pi haengt;
#    bei mehreren ggf. auf ATTRS{serial} verfeinern.
# ---------------------------------------------------------------------------
provision_udev_servo2040() {
    c_info "udev-Rule fuer Servo2040 sicherstellen ..."
    local rule="/etc/udev/rules.d/99-servo2040.rules"

    if [[ -f "${rule}" ]]; then
        c_skip "udev-Rule vorhanden (${rule})"
        return
    fi

    # VID 2e8a am Pi verifiziert (Servo2040 meldet sich als RP2040/"Pico").
    # Pruefen: udevadm info -n /dev/ttyACM0 | grep -i vendor
    echo 'SUBSYSTEM=="tty", ATTRS{idVendor}=="2e8a", SYMLINK+="servo2040"' \
        | sudo tee "${rule}" > /dev/null
    sudo udevadm control --reload-rules
    sudo udevadm trigger || true
    c_ok "udev-Rule angelegt -> /dev/servo2040"
    c_manual "Nach Anstecken der Servo2040 pruefen: 'ls -l /dev/servo2040' muss auf /dev/ttyACMx zeigen (VID 2e8a am Pi verifiziert)."
}

# ---------------------------------------------------------------------------
# 10. Feld-Autonomie (Block I Phase 9): sauberer Shutdown + Always-On ab Boot
#
#     Ziel: der Roboter ist OHNE Dev-Rechner benutzbar — Pi einschalten, App
#     verbinden, fahren, per Schalter ODER App sauber herunterfahren.
#
#     Zwei Dinge sind dafuer noetig, die NICHT im Workspace-Git liegen koennen:
#
#     a) sudo-Recht fuer den Poweroff. Der shutdown_supervisor ruft
#        'sudo -n shutdown -h now' aus einem systemd-Dienst — also ohne
#        Terminal. Ohne NOPASSWD-Eintrag scheitert das (mit -n sofort und mit
#        Logzeile, statt still auf eine Passwort-Eingabe zu warten).
#        Befund vor Phase 9: der Schalter setzte den Roboter hin und schaltete
#        das Relay, der Pi lief aber weiter und wurde am Hauptschalter HART
#        getrennt (SD-Karten-Risiko).
#
#     b) Die Always-On-Schicht als User-Dienst (rosbridge + shutdown_supervisor
#        + bringup_launcher). Ohne sie laeuft kein rosbridge -> die App findet
#        nichts -> Feld-Start nur per SSH. Der SCHWERE Stack startet bewusst
#        NICHT mit ([D7]): beim Einschalten soll sich nichts bewegen, die App
#        entscheidet.
#
#     Die dritte Zutat (pi_hostname + shutdown_command) liegt im Git und kommt
#     ueber 'git pull' mit: hexapod_supervisor/config/{supervisor,launcher.real}.yaml.
# ---------------------------------------------------------------------------
provision_shutdown_sudoers() {
    c_info "sudo-Recht fuer den Poweroff sicherstellen ..."
    local sudoers="/etc/sudoers.d/hexapod-shutdown"
    local shutdown_bin
    shutdown_bin="$(command -v shutdown || echo /usr/sbin/shutdown)"

    if sudo test -f "${sudoers}"; then
        c_skip "sudoers-Eintrag vorhanden (${sudoers})"
        return
    fi

    # Nur DAS eine Binary, kein NOPASSWD:ALL. visudo -cf prueft die Syntax,
    # BEVOR die Datei aktiv wird — ein kaputtes sudoers sperrt sonst aus.
    local tmp
    tmp="$(mktemp)"
    printf '%s ALL=(root) NOPASSWD: %s\n' "${USER}" "${shutdown_bin}" > "${tmp}"
    if ! sudo visudo -cf "${tmp}" > /dev/null; then
        rm -f "${tmp}"
        c_warn "sudoers-Syntaxpruefung fehlgeschlagen — Eintrag NICHT gesetzt"
        c_manual "sudoers manuell setzen: sudo visudo -f ${sudoers} -> '${USER} ALL=(root) NOPASSWD: ${shutdown_bin}'"
        return
    fi
    sudo install -m 0440 -o root -g root "${tmp}" "${sudoers}"
    rm -f "${tmp}"
    c_ok "sudoers-Eintrag gesetzt (${sudoers}, nur ${shutdown_bin})"
}

provision_always_on_service() {
    c_info "Always-On-Dienst (rosbridge + supervisor + launcher) einrichten ..."
    local unit="hexapod_always_on.service"
    local target_dir="${HOME}/.config/systemd/user"
    local src
    src="$(ros2 pkg prefix hexapod_bringup 2>/dev/null)/share/hexapod_bringup/systemd/${unit}"

    if [[ ! -f "${src}" ]]; then
        c_warn "Unit-Vorlage nicht gefunden (${src}) — Workspace gebaut + gesourced?"
        c_manual "Nach 'colcon build' erneut ausfuehren: ${0} (Schritt 10 richtet den Always-On-Dienst ein)."
        return
    fi

    mkdir -p "${target_dir}"
    if cmp -s "${src}" "${target_dir}/${unit}"; then
        c_skip "Unit aktuell (${target_dir}/${unit})"
    else
        cp "${src}" "${target_dir}/${unit}"
        systemctl --user daemon-reload
        c_ok "Unit installiert/aktualisiert -> ${target_dir}/${unit}"
        # Bewusst KEIN automatischer Restart: laeuft gerade der schwere Stack
        # (Subprozess in derselben Control-Group), reisst ein Restart ihn mit —
        # das Relay faellt und ein stehender Roboter sackt zusammen. Der Mensch
        # entscheidet, wann das passt.
        if systemctl --user is-active --quiet "${unit}"; then
            c_manual "Unit wurde GEAENDERT, der Dienst laeuft noch mit der alten: 'systemctl --user restart ${unit}'. ACHTUNG: das reisst einen laufenden schweren Stack mit (Relay faellt) — vorher den Roboter hinsetzen."
        fi
    fi

    if systemctl --user is-enabled --quiet "${unit}"; then
        c_skip "Dienst bereits enabled"
    else
        systemctl --user enable "${unit}"
        c_ok "Dienst enabled (startet beim Boot)"
    fi

    # Starten — aber NICHT blind 'enable --now': laeuft die Always-On-Schicht
    # gerade manuell (ros2 launch ... always_on.launch.py), kollidieren zwei
    # rosbridge auf Port 9090 und zwei bringup_launcher auf denselben
    # Service-Namen. Deshalb erst pruefen, dann starten.
    # Der Port ist die eigentliche Kollisionsbedingung — praeziser als ein
    # Prozessnamen-Match (das haette auch auf einen Editor/grep mit dem String
    # in der Kommandozeile angeschlagen).
    if systemctl --user is-active --quiet "${unit}"; then
        c_skip "Dienst laeuft bereits (active)"
    elif ss -ltn 2>/dev/null | grep -q ':9090[[:space:]]'; then
        c_warn "Port 9090 ist belegt — die Always-On-Schicht laeuft schon (manuell gestartet?). Dienst NICHT gestartet"
        c_manual "Doppelstart vermeiden: den manuellen Start beenden, dann 'systemctl --user start ${unit}' (oder rebooten)."
    else
        systemctl --user start "${unit}"
        c_ok "Dienst gestartet (active)"
    fi

    # Linger: ohne das startet eine User-Unit erst beim ersten LOGIN — also im
    # headless Feld-Betrieb nie.
    if loginctl show-user "${USER}" 2>/dev/null | grep -q '^Linger=yes'; then
        c_skip "Linger bereits aktiv"
    else
        sudo loginctl enable-linger "${USER}"
        c_ok "Linger aktiviert (User-Dienst startet ohne Login)"
    fi

    c_manual "Ab jetzt laeuft die Always-On-Schicht als Dienst: NICHT zusaetzlich manuell per SSH starten (zwei rosbridge auf Port 9090 kollidieren). Vorher: systemctl --user stop ${unit}"
    c_manual "Nach einem Update der Always-On-Schicht (rosbridge-Launch, bringup_launcher, hmi_status inkl. hmi_config_manifest.yaml): 'systemctl --user restart ${unit}'. Aendert sich nur der schwere Stack (gait/Engine/Teleop), genuegt in der App 'stoppen -> starten'."
}

# ---------------------------------------------------------------------------
# 10b. D4/D5 (OLED) — NOCH NICHT AKTIV
#      Der GPIO-Button-Teil ist durch den Servo2040-Schalter abgeloest (der
#      Schalter wird vom hexapod_hardware-Plugin gelesen). Offen bleibt nur das
#      OLED-Display.
# ---------------------------------------------------------------------------
provision_oled() {
    c_skip "OLED (D4): noch nicht aktiv"
    # TODO (D4): I2C aktivieren (SSD1306 @ 0x3C ueber EKM002-QWIIC),
    #   pip-Deps luma.oled (venv). Der Shutdown-Schalter laeuft bereits ueber
    #   den Servo2040 (GET_INPUTS -> Plugin -> /hexapod/shutdown_request).
}

# ---------------------------------------------------------------------------
# 11. Self-Check Feld-Autonomie (Block I Phase 9)
#
#     Laeuft als LETZTER Block, bewusst nach der Manuell-Liste: beim ersten
#     echten Lauf am Pi ging die einzelne '[warn] Unit-Vorlage nicht gefunden'-
#     Zeile in der langen Ausgabe unter — sichtbar wurde der Fehler erst, als
#     der Dienst spaeter schlicht nicht existierte. Eine Ampel am Schluss
#     kostet nichts und beantwortet die einzige Frage, die zaehlt:
#     "kann ich damit ins Feld?"
#
#     Geprueft werden die vier Dinge, die den Feld-Zyklus tragen:
#       1. sudoers      -> ohne ihn faehrt der Pi nicht herunter
#       2. Unit         -> ohne sie kein rosbridge ab Boot (die App findet nichts)
#       3. Linger       -> ohne ihn startet eine User-Unit ohne Login nie
#       4. Host-Guard   -> pi_hostname != hostname => 'host-mismatch', der
#                          Poweroff feuert NIE (genau der Phase-9-Ausgangsbefund)
#     Alles read-only ausser 'sudo -k' (verwirft nur den Timestamp-Cache).
# ---------------------------------------------------------------------------
verify_field_autonomy() {
    local unit="hexapod_always_on.service"
    local failed=0
    local shutdown_bin
    shutdown_bin="$(command -v shutdown || echo /usr/sbin/shutdown)"

    echo ""
    echo "============================================================"
    printf '\033[1;36mSELF-CHECK Feld-Autonomie (Phase 9)\033[0m\n'
    echo "============================================================"

    # 1. Poweroff-Recht. 'sudo -k' ist Pflicht: der Timestamp-Cache (~15 min)
    #    winkt JEDEN 'sudo -n' durch, auch wenn der sudoers-Eintrag fehlt — der
    #    shutdown_supervisor hat diesen Cache spaeter nicht.
    sudo -k
    if sudo -n "${shutdown_bin}" --help > /dev/null 2>&1; then
        c_ok "Poweroff: '${shutdown_bin}' laeuft passwortlos (sudoers greift)"
    else
        c_warn "Poweroff: 'sudo -n ${shutdown_bin}' scheitert -> der Pi wuerde NICHT herunterfahren"
        echo "         Fix: sudo visudo -f /etc/sudoers.d/hexapod-shutdown"
        echo "              ${USER} ALL=(root) NOPASSWD: ${shutdown_bin}"
        failed=1
    fi

    # 2. Always-On-Dienst: enabled (ab Boot) UND aktiv (jetzt).
    if systemctl --user is-enabled --quiet "${unit}" 2>/dev/null; then
        if systemctl --user is-active --quiet "${unit}"; then
            c_ok "Always-On-Dienst: enabled + active"
        else
            c_warn "Always-On-Dienst: enabled, laeuft aber nicht"
            echo "         Fix: systemctl --user start ${unit}   (oder rebooten)"
            failed=1
        fi
    else
        c_warn "Always-On-Dienst: nicht enabled -> ab Boot kein rosbridge, die App findet nichts"
        echo "         Ursache meist: Unit-Vorlage fehlt (Workspace nicht gebaut/gesourced)."
        echo "         Fix: colcon build --symlink-install && source install/setup.bash && ${0}"
        failed=1
    fi

    # 3. Linger: ohne ihn startet die User-Unit erst beim ersten LOGIN.
    if loginctl show-user "${USER}" 2>/dev/null | grep -q '^Linger=yes'; then
        c_ok "Linger: aktiv (User-Dienst startet ohne Login)"
    else
        c_warn "Linger: inaktiv -> im headless Feld-Betrieb startet der Dienst nie"
        echo "         Fix: sudo loginctl enable-linger ${USER}"
        failed=1
    fi

    # 4. Host-Guard: der dritte Guard in os_shutdown.guarded_shutdown.
    local cfg="${WS_DIR}/src/hexapod_supervisor/config/supervisor.yaml"
    local host_now cfg_host
    host_now="$(hostname)"
    if [[ -f "${cfg}" ]]; then
        cfg_host="$(grep -m1 -E '^[[:space:]]*pi_hostname:' "${cfg}" | tr -d " '\"" | cut -d: -f2)" || true
        if [[ -n "${cfg_host}" && "${cfg_host}" == "${host_now}" ]]; then
            c_ok "Host-Guard: pi_hostname '${cfg_host}' == hostname"
        else
            c_warn "Host-Guard: pi_hostname '${cfg_host:-<leer>}' != hostname '${host_now}' -> 'host-mismatch', der Poweroff feuert NIE"
            echo "         Fix: pi_hostname in supervisor.yaml UND launcher.real.yaml auf '${host_now}' setzen (beide!)."
            failed=1
        fi
    else
        c_skip "Host-Guard: ${cfg} nicht gefunden (Workspace nicht ausgecheckt?)"
    fi

    # 5. Laeuft der DIENST in derselben ROS-Domain wie diese Shell? Das ist der
    #    haeufigste Grund fuer "ros2 node list ist leer, obwohl alles laeuft":
    #    entweder fehlt das Environment= in der Unit, oder die Unit wurde
    #    geaendert und der Dienst nicht neu gestartet (alte Instanz).
    local main_pid svc_domain shell_domain
    main_pid="$(systemctl --user show -p MainPID --value "${unit}" 2>/dev/null || echo 0)"
    shell_domain="${ROS_DOMAIN_ID:-0}"
    if [[ "${main_pid}" != "0" && -r "/proc/${main_pid}/environ" ]]; then
        svc_domain="$(tr '\0' '\n' < "/proc/${main_pid}/environ" | sed -n 's/^ROS_DOMAIN_ID=//p')"
        svc_domain="${svc_domain:-0}"
        if [[ "${svc_domain}" == "${shell_domain}" ]]; then
            c_ok "ROS-Domain: Dienst und Shell beide in Domain ${svc_domain}"
        else
            c_warn "ROS-Domain: Dienst=${svc_domain}, Shell=${shell_domain} -> 'ros2 node list' bleibt leer, Desktop-Tools sehen den Roboter nicht"
            echo "         Meist: Unit geaendert, aber alte Instanz laeuft noch."
            echo "         Fix: systemctl --user restart ${unit}"
            echo "         ACHTUNG: der Restart reisst einen laufenden schweren Stack mit (Relay faellt)."
            failed=1
        fi
    else
        c_skip "ROS-Domain: Dienst laeuft nicht -> nicht pruefbar"
    fi

    echo ""
    if [[ ${failed} -eq 0 ]]; then
        c_ok "FELD-BEREIT: Pi einschalten -> App verbinden -> fahren -> per Schalter ODER App herunterfahren."
    else
        c_warn "NICHT feld-bereit — siehe die [warn]-Zeilen oben."
        echo "       Details: project_finalization/app_control_requirements/phase_9_field_autonomy_test_commands.md"
    fi
    c_info "Der Self-Check hat den sudo-Timestamp verworfen — der naechste sudo-Aufruf fragt wieder nach dem Passwort."
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
    check_apt_updates_pocket
    sudo apt-get update

    provision_locale
    provision_universe
    provision_ros_repo
    provision_base_tools
    provision_bluetooth
    provision_ros_packages
    provision_bashrc
    provision_rosdep
    provision_colcon_ignore
    provision_udev_servo2040
    # Block I Phase 9 — Feld-Autonomie. Der Dienst braucht einen GEBAUTEN
    # Workspace (die Unit-Vorlage kommt aus dem installierten share/); beim
    # allerersten Lauf auf einem frischen Pi meldet der Schritt das und traegt
    # sich als manueller Nachtrag ein — nach 'colcon build' das Skript einfach
    # erneut aufrufen (es ist idempotent).
    provision_shutdown_sudoers
    provision_always_on_service
    provision_oled

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
    echo "  # --skip-keys: rosdep ignoriert COLCON_IGNORE, sonst kommt die"
    echo "  # Gazebo-Bridge (ros_gz_*) aus hexapod_gazebo mit — am Pi unerwuenscht."
    echo "  rosdep install --from-paths src --ignore-src -r -y --skip-keys \"ros_gz_sim ros_gz_bridge\""
    echo "  colcon build --symlink-install"
    echo "  source install/setup.bash"

    # Ganz zum Schluss, damit die Ampel das Letzte auf dem Terminal ist.
    verify_field_autonomy
}

main "$@"
