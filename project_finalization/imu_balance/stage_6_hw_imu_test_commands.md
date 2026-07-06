# Stufe 6 / IP1 — Bringup + Test-Befehle (HW-IMU am Pi)

> **Eigenständiges Bringup-Doc für den IMU-Track** (bewusst hier im imu_balance-Abschnitt, nicht nur
> Verweis auf [`docs_raspi/dev_workflow_desktop_to_pi.md`](../../docs_raspi/dev_workflow_desktop_to_pi.md)
> — dort darf man Interessantes nachlesen, aber dies ist self-contained). Du führst die Schritte aus,
> knappe Status-Meldung zurück.
>
> **Warum ein Pi-Deploy-Schritt:** Der BNO-055 hängt **nur am Pi** (Qwiic/I2C `0x28`) — der Dev-Rechner
> erreicht ihn **nicht**. Also: am Dev bauen + Unit-Tests (CI), dann **Code auf den Pi**, dort mit echtem
> Sensor testen. **Kein Logging auf die Pi-SD-Karte** — Diagnose läuft über DDS zum Dev-Rechner.
>
> ✅ Stand: **IP1.1–IP1.6 am Dev fertig** (Node `bno055_imu` + reine Konvertierung + Unit-Tests grün,
> CI ohne HW). Dieser Lauf = **IP1.7** (Deploy Dev→Pi + Kipp-Test am echten Sensor).

## Voraussetzungen

- IMU-Hello-World 🟢 (`../peripherals_tests/imu_bno055.md`): I2C an, `0x28` sichtbar, `CHIP_ID=0xA0`.
- Pi erreichbar: `ssh hexapod-pi`. Dev + Pi im **selben Netz**, **gleiche `ROS_DOMAIN_ID`** (für DDS).
- Git: **du** committest/pushst am Dev, pullst am Pi (Agent macht kein git).

---

## Schritt 1 — smbus2 dem ROS-Python am Pi verfügbar machen (einmalig)

Der Node importiert `smbus2` im **System-Python** (dort wohnt ROS2/rclpy) — **nicht** im
Hello-World-venv `~/bno055_venv`. Beide Varianten installieren **systemweit**; **Variante A ist die
bevorzugte** (paketverwaltet, sauber, keine PEP-668-Umgehung), Variante B nur der Fallback, falls das
apt-Paket fehlt:

```bash
ssh hexapod-pi
# Variante A (BEVORZUGT — apt, paketverwaltet, sauber):
sudo apt update && sudo apt install -y python3-smbus2 || \
# Variante B (Fallback — pip system-wide, umgeht PEP 668 auf Ubuntu 24.04):
  pip install --break-system-packages smbus2
python3 -c "import smbus2; print('smbus2 ok', smbus2.__name__)"
```

> Der `i2c`-Gruppen-Zugriff auf `/dev/i2c-1` ist aus der Hello-World schon eingerichtet (sonst:
> `sudo usermod -aG i2c $USER` + Re-Login).

## Schritt 2 — Code Dev → Pi bringen

> ⚠️ **Branch-Diskrepanz:** Der Pi kann auf einem anderen Branch stehen (z. B. `leg_changes`), der
> IP1-Code liegt auf `imu_balance`. Daher am Pi gezielt auf den Dev-Branch wechseln und **hart** auf
> den origin-Stand setzen. `git reset --hard`/`checkout` lassen **untracked** Dateien unangetastet →
> `src/hexapod_gazebo/COLCON_IGNORE` (schließt Gazebo vom Pi-Build aus) bleibt erhalten. **`git clean`
> NICHT ausführen** (würde COLCON_IGNORE löschen).

```bash
# Am DEV (du): IP1-Code + Docs committen + pushen (falls noch nicht geschehen)
cd ~/hexapod_ws
git add .
git commit -m "imu balance stage 6 IP1: bno055_imu HW-IMU-Treiber"
git push                                                                             # DU

# Am PI: auf den Dev-Branch wechseln + hart auf origin setzen (überschreibt lokal)
ssh hexapod-pi
cd ~/hexapod_ws
git fetch origin
git checkout -B imu_balance origin/imu_balance    # Branch anlegen/wechseln, auf origin-Stand
git reset --hard origin/imu_balance               # sicherheitshalber hart überschreiben
git status                                         # -> up to date; nur COLCON_IGNORE untracked

# bauen — NUR die betroffenen Pakete; hexapod_gazebo ist per COLCON_IGNORE ausgeschlossen,
# es wird KEIN Gazebo/RViz gebaut oder gestartet (RViz läuft später am Dev, Schritt 5).
source /opt/ros/jazzy/setup.bash
colcon build --symlink-install --packages-select hexapod_sensors hexapod_bringup
```

> Alternativ ohne Git-Roundtrip: `rsync -a ~/hexapod_ws/src/ hexapod-pi:~/hexapod_ws/src/` (siehe
> dev_workflow-Doc), dann am Pi `colcon build`.

## Schritt 3 — Node am Pi starten

> **Kein Servo-Strom nötig:** die BNO-055 hängt am Qwiic/I2C (Pi-3V3), unabhängig vom Servo-Rail.
> Beide Varianten unten schalten das **Relay NICHT** (kein Inrush/Brownout am aktuellen Netzteil):
> Option 1 lädt das `hexapod_hardware`-Plugin gar nicht, Option 2 läuft im `loopback_mode`
> (`send_frame` = No-Op → RELAY_CONTROL wird nie gesendet).

**Option 1 (empfohlen) — IMU isoliert**, ohne controller_manager/Servos. Zwei Pi-Terminals:
```bash
# Terminal A (Pi):
ssh hexapod-pi
source /opt/ros/jazzy/setup.bash && source ~/hexapod_ws/install/setup.bash
ros2 run hexapod_sensors bno055_imu
# Erwartung: "BNO-055 NDOF aktiv ... Cal beim Start ..." + "bno055_imu aktiv ... @ 50 Hz"

# Terminal B (Pi):
ssh hexapod-pi
source /opt/ros/jazzy/setup.bash && source ~/hexapod_ws/install/setup.bash
ros2 run hexapod_sensors imu_monitor
```

**Option 2 — voller Stack für die RViz-Neigung**, aber **`loopback_mode:=true`** (kein Relay/Servo-Power):
```bash
ros2 launch hexapod_bringup real.launch.py loopback_mode:=true enable_imu:=true
```
> ⚠️ **NICHT** `loopback_mode:=false` für den IMU-Test — das würde die on_activate-Relay-Sequenz
> feuern (Servo-Power an → Inrush → Brownout mit dem aktuellen Netzteil). Der IMU-Test braucht keine Servos.

## Schritt 4 — Verifikation (Sensor-Kette lebt)

**Am Pi (oder Dev):**
```bash
ros2 topic hz /imu/data          # -> ~50 Hz
ros2 topic echo /imu/monitor     # Vector3 x=roll y=pitch z=yaw (rad)
ros2 topic echo /imu/calib       # Cal-Status sys/gyr/acc/mag (IP1.3)
```

**Kipp-Test (Achsen + Vorzeichen) — der eigentliche Nachweis:**
- Roboter um die **roll-Achse** kippen (links/rechts) → `/imu/monitor` **roll** folgt (richtiges
  Vorzeichen: rechts-Kippen → definiertes Vorzeichen), **pitch ≈ 0**.
- Um die **pitch-Achse** kippen (vor/zurück) → **pitch** folgt, roll ≈ 0.
- **Damit ist bewiesen, dass AXIS_MAP die Quaternion korrekt auf `base_link` gedreht hat** (§6-Risiko 1
  im Plan). Stimmen Achsen/Vorzeichen nicht → an IP2 / den AXIS_MAP-Werten drehen.

## Schritt 5 — Zum Dev-Rechner streamen (Logging ohne SD-Writes)

Roboter läuft headless am Pi; **du loggst/visualisierst am Dev** (DDS im LAN, null Pi-Disk-Writes):

```bash
# Am DEV — gleiche ROS_DOMAIN_ID:
source /opt/ros/jazzy/setup.bash && source ~/hexapod_ws/install/setup.bash
ros2 topic echo /imu/monitor                 # Live roll/pitch vom Pi
ros2 bag record /imu/data /imu/monitor        # Bag liegt auf dem DEV, nicht auf der SD
rviz2 -d install/hexapod_description/share/hexapod_description/config/view_hw.rviz
#  -> das Roboter-Modell neigt sich mit der echten Lage (imu_monitor world->base_link-tf)
```

> Melde: `/imu/data` ~50 Hz? roll/pitch folgt dem Kippen mit richtiger Achse/Vorzeichen? RViz-Neigung
> plausibel? Cal steigt gyr/acc → 3?

## Schritt 6 — IP2: AXIS_MAP-Verifikation + Zero-Offset

> Der `axis_map_config`/`sign` liegt jetzt in `hexapod_sensors/config/imu_calibration.yaml`
> (Startwert `0x21`/`0x01` aus dem IP1.7-Befund: Sensor +90° um Z verdreht). Nach Deploy des IP2-Codes
> den Node **mit** der YAML starten und den Kipp-Test aus Schritt 4 wiederholen — jetzt sollen roll/pitch
> der **physischen** Achse folgen. Plan: [`stage_6b_imu_mounting_cal_plan.md`](stage_6b_imu_mounting_cal_plan.md).

**Node isoliert mit Cal-YAML (Pi), Terminal A:**
```bash
ros2 run hexapod_sensors bno055_imu \
  --params-file ~/hexapod_ws/install/hexapod_sensors/share/hexapod_sensors/config/imu_calibration.yaml
# Startup-Log MUSS zeigen: "AXIS_MAP cfg=0x21 sign=0x01"
```
Terminal B wie gehabt: `ros2 run hexapod_sensors imu_monitor`.

**Kipp-Test — jetzt ERWARTET (base_link-Konvention):**
- rechte Seite (−Y) hoch → **roll negativ**, pitch ≈ 0
- Nase (+X) hoch → **pitch negativ**, roll ≈ 0

- **Passt** → AXIS_MAP korrekt (beweist zugleich: der Chip-Remap dreht die **Quaternion** mit). Vorzeichen
  final gegen die Sim-Konvention prüfen (rechte Seite **runter** → welches roll-Vorzeichen erwartet das
  Leveling?).
- **Passt nicht** (Achsen/Vorzeichen weiter falsch) → Wert in der YAML anpassen (Sign-/Config-Variante),
  Node neu starten, erneut. Bleibt die Quaternion **ganz unverändert** vertauscht → Chip-Remap dreht sie
  nicht → Node-Rotation-Contingency ([`stage_6b`](stage_6b_imu_mounting_cal_plan.md) §2.2).

**Zero-Offset (IP2.2):** Roboter flach auf ebene Fläche → `/imu/monitor` roll/pitch ablesen. < ~1° →
`roll_offset`/`pitch_offset` in der YAML bei `0.0` lassen; sonst gemessenen Wert (rad) eintragen, Node
neu starten, Gegenprobe roll/pitch ≈ 0.

> ⚠️ YAML-Änderung am Pi wirkt erst nach `colcon build` (Symlink-Install) bzw. sofort, wenn du die Datei
> unter `install/…/config/` direkt editierst. Sauber: `src/`-YAML ändern → `colcon build` → neu starten.

## Was NICHT hier getestet wird (→ spätere IP)

- **Leveling bewegt Beine / Gain-Retuning** → IP3 (`stage_6c...`), braucht Servo-Power (Phase 8).

## Troubleshooting

| Symptom | Fix |
|---|---|
| `real.launch.py`: `No such file … hexapod.imu.xacro` (Option 2) | `hexapod_description` am Pi nach dem Branch-Wechsel nicht neu gebaut → neue URDF-Includes fehlen im `install/`. Fix: `colcon build --symlink-install` (ohne `--packages-select`; hexapod_gazebo bleibt per COLCON_IGNORE aus). **Option 1 (isoliert) braucht kein URDF** und umgeht das. |
| `/imu/data` fehlt | Node läuft nicht / `import smbus2` scheitert (Schritt 1) / `enable_imu:=false` |
| `ros2 topic echo` am Dev leer, am Pi da | `ROS_DOMAIN_ID` unterschiedlich / Firewall / nicht selbes Netz |
| roll/pitch-Achsen vertauscht | AXIS_MAP falsch → IP2 (erwartet, dafür ist der Kipp-Test da) |
| roll/pitch bei „flach" ≠ 0 | Montage-Restschräge → Zero-Offset (IP2, „nur ein Parameter") |
| sporadisch `/imu/data`-Aussetzer | Clock-Stretching → Baudrate in `config.txt` senken (`i2c_arm_baudrate=10000`, Reboot) |
