# Peripherie-Inbetriebnahme — Gesamt-Plan (Hello-World-Tests)

> **Zweck:** Funktionsnachweis („Hello World") von drei neuen Peripherie-Geräten
> **vor** dem Einbau in den Hexapod. **Keine** End-Integration ins Projekt — das sind
> isolierte Wegwerf-Tests. Daher bewusst **kein** Eintrag in `00_backlog.md`,
> `ai_navigation.md`, `architecture.md`, `PHASE.md` o.ä. Erst wenn ein Gerät *wirklich*
> integriert wird (z.B. IMU → Block A5 Balance), wandert es in die regulären Docs.

## Geräte & Reihenfolge

| # | Gerät | Schnittstelle | Status | Doku |
|---|---|---|---|---|
| 1 | **IMU BNO-055** | I2C / Qwiic | ⚪ offen | [`imu_bno055.md`](imu_bno055.md) |
| 2 | **AI-Kamera IMX500** (SC1174) | CSI / MIPI | ⚪ offen — **Machbarkeit zu klären** | `camera_imx500.md` (folgt) |
| 3 | **Audio MAX98357A** + 4 Ω/3 W Speaker | I2S | ⚪ offen | [`audio_max98357a.md`](audio_max98357a.md) |

Reihenfolge nach Risiko/Aufwand: **IMU → Kamera → Audio**.
Status-Legende: ⚪ offen — 🟡 läuft teilweise — 🟢 verifiziert.

## Rahmenbedingungen (gelten für alle drei)

- **Recheneinheit:** Raspberry Pi 5, **Ubuntu Server 24.04 LTS arm64**, headless.
- **Zugang:** `ssh hexapod-pi` (Pi ist normalerweise aus → vor jedem Test einschalten).
- **OS-Schnittstellen** (I2C/I2S) werden über `/boot/firmware/config.txt` aktiviert —
  **kein `raspi-config`** (das gibt es auf Ubuntu Server nicht).
- **Reboots macht der User** (CLAUDE.md §5). Die Docs markieren jeden nötigen Reboot klar;
  ausgeführt wird er von dir, nicht automatisch.
- **Keine** zweite Paketquelle / PPA ohne explizites „GENEHMIGT" (CLAUDE.md §5) — relevant
  v.a. für die Kamera.

## ⚠️ Kamera-Vorbehalt (wichtig, vorab geklärt)

Ubuntu 24.04 hat **keinen IMX500-Sensor-Treiber** (bestätigt von einem Raspberry-Pi-Ingenieur
im offiziellen Forum: Canonical-Kernel + Userland unterstützen den Sensor nicht). Die Kamera
wird auf 24.04 **gar nicht erkannt** — kein `/dev/video0`, `rpicam-hello` findet nichts.
Das `imx500-all`-Paket (Firmware + NN-Modelle + Postprocessing) ist **RPi-OS-only**.
Ubuntu 25.04 hat den Kamera-Stack zwar nachgerüstet, ist aber **keine** ROS-2-Jazzy-Plattform
(Jazzy = 24.04 LTS) → ein OS-Upgrade würde die ROS-Grundlage des Roboters brechen.

**Konsequenz:** Die Kamera braucht einen eigenen **Machbarkeits-/from-source-Pfad**
(libcamera/rpicam-apps + Sensor-Treiber selbst bauen auf 24.04). Das wird **zuerst
recherchiert** (Aufwand + Erfolgschance), bevor irgendetwas am Pi angefasst wird. Der
schwere Weg ist akzeptiert, *sofern* er zum Ziel führt.

**Build-Ablage Kamera:** falls kompiliert werden muss, gehört Quellcode/Build **NICHT** ins
`hexapod_ws`-Repo, sondern in einen separaten Ordner (z.B. `~/imx500_camera_build/` auf dem Pi,
analog zu `~/pimoroni_servo_fix/`). Die `camera_imx500.md` ist dann nur die **Anleitung**, die
dorthin verweist.

## Doku-Format

Eine in sich geschlossene Datei pro Gerät mit den Abschnitten:
**1. Ziel/Hardware → 2. Plan-Skizze → 3. Tests-Liste → 4. Installation/Config →
5. Test-Befehle → 6. Done-Kriterien → 7. Troubleshooting → 8. Offene Punkte.**
Alle operativen Befehle stehen vollständig + ausführbar im Doc (User führt aus dem Doc aus).
