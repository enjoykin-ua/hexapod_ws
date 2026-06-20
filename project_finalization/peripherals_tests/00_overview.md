# Peripherie-Inbetriebnahme — Gesamt-Plan (Hello-World-Tests)

> **Zweck:** Funktionsnachweis („Hello World") von drei neuen Peripherie-Geräten
> **vor** dem Einbau in den Hexapod. **Keine** End-Integration ins Projekt — das sind
> isolierte Wegwerf-Tests. Daher bewusst **kein** Eintrag in `00_backlog.md`,
> `ai_navigation.md`, `architecture.md`, `PHASE.md` o.ä. Erst wenn ein Gerät *wirklich*
> integriert wird (z.B. IMU → Block A5 Balance), wandert es in die regulären Docs.

## Geräte & Reihenfolge

| # | Gerät | Schnittstelle | Status | Doku |
|---|---|---|---|---|
| 1 | **IMU BNO-055** | I2C / Qwiic | 🟢 verifiziert | [`imu_bno055.md`](imu_bno055.md) |
| 2 | **Kamera Pi v1.3** (OV5647) | CSI / MIPI | 🟢 verifiziert (Bild+Stream, MJPEG, keine AI) | [`camera_ov5647_v13.md`](camera_ov5647_v13.md) |
| 3 | **Audio MAX98357A** + 4 Ω/3 W Speaker | I2S | 🟢 verifiziert (Knarzen offen) | [`audio_max98357a.md`](audio_max98357a.md) |

Reihenfolge nach Risiko/Aufwand: **IMU → Kamera → Audio**.
Status-Legende: ⚪ offen — 🟡 läuft teilweise — 🟢 verifiziert.

## Rahmenbedingungen (gelten für alle drei)

- **Recheneinheit:** Raspberry Pi 5, **Ubuntu Server 24.04 LTS arm64**, headless.
- **Zugang:** `ssh hexapod-pi` (Pi ist normalerweise aus → vor jedem Test einschalten).
- **OS-Schnittstellen** (I2C/I2S) werden über `/boot/firmware/config.txt` aktiviert —
  **kein `raspi-config`** (das gibt es auf Ubuntu Server nicht).
- **Reboots macht der User** (CLAUDE.md §5). Die Docs markieren jeden nötigen Reboot klar;
  ausgeführt wird er von dir, nicht automatisch.
- **Keine** zweite Paketquelle / PPA ohne explizites „GENEHMIGT" (CLAUDE.md §5). Der Kamera-Weg
  braucht keine PPA — nur `apt`-Build-Deps + from-source.

## Kamera (Pi v1.3 / OV5647) — Kurzkontext

Verwendet wird die **Raspberry Pi Camera Module v1.3 (Sensor OV5647)**. Deren Kernel-Treiber
+ CFE/PiSP-Kamera-Pipeline sind im Ubuntu-24.04-Kernel (`6.8.0-…-raspi`) **vorhanden**
(verifiziert: Sensor bindet, `/dev/video0` registriert). Es fehlt nur das **Userland**
(Pi-Fork `libcamera` + `rpicam-apps`), das **from source** gebaut wird — **reines Userland,
kein Kernel-Eingriff, null Risiko** fürs Roboter-System. Ergebnis: Bild + Stream auf den
Dev-Rechner (5 MP). Details: [`camera_ov5647_v13.md`](camera_ov5647_v13.md).

**Build-Ablage:** Quellcode/Build gehört **NICHT** ins `hexapod_ws`-Repo, sondern nach
`~/camera_build/` auf dem Pi (analog zu `~/pimoroni_servo_fix/`); Install nach `/usr/local`.

## Workflow: VS Code Remote-SSH nach Reboot wieder verbinden

Nach jedem Pi-Reboot/Shutdown bricht die Remote-SSH-Verbindung ab. Wieder rein:

1. **Pi-Hochlauf abwarten** (~30–60 s nach Einschalten), sonst läuft der Connect in einen Timeout.
2. Im abgebrochenen VS-Code-Fenster erscheint meist „disconnected" → Button **„Reload Window"**/„Retry".
   Klappt das nicht: Fenster schließen.
3. Neu verbinden: `F1` → **„Remote-SSH: Connect to Host"** → `hexapod-pi`.
4. Falls der Ordner nicht automatisch wieder aufgeht: **File → Open Recent** (bzw. Open Folder)
   → der Arbeitsordner auf dem Pi.
5. Terminal auf dem Pi öffnen: ``Ctrl+` `` — läuft auf dem Pi (nicht auf dem Dev-Rechner).

> Tipp: Reconnect erst versuchen, wenn der Pi wirklich oben ist. Bei „Could not establish
> connection" einfach 10–20 s warten und Schritt 3 wiederholen.

## Doku-Format

Eine in sich geschlossene Datei pro Gerät mit den Abschnitten:
**1. Ziel/Hardware → 2. Plan-Skizze → 3. Tests-Liste → 4. Installation/Config →
5. Test-Befehle → 6. Done-Kriterien → 7. Troubleshooting → 8. Offene Punkte.**
Alle operativen Befehle stehen vollständig + ausführbar im Doc (User führt aus dem Doc aus).
