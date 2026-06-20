# Kamera Raspberry Pi v1.3 (OV5647) auf Ubuntu 24.04 — Inbetriebnahme

> Bild + Stream auf den Dev-Rechner mit der **Camera Module v1.3 (Sensor OV5647)** auf
> **Ubuntu Server 24.04 / Pi 5**. Gesamt-Kontext: [`00_overview.md`](00_overview.md).
> **Reines Userland-Vorgehen** (Pi-Fork `libcamera` + `rpicam-apps` from source) — **kein**
> Kernel-Eingriff, Install nach `/usr/local`, reversibel, **kein** Risiko fürs Roboter-/ROS-System.

## 1. Ziel & Hardware

- **Gerät:** Raspberry Pi Camera Module **v1.3** (OmniVision **OV5647**, 5 MP), CSI/MIPI.
- **Kabel:** Standard-15-pol-FFC ↔ Pi-5-Mini-Port über das „standard–mini"-Adapterkabel
  (Standard-Ende an die Kamera, Mini-Ende in den CAM-Port am Pi 5, näher an USB).
- **Ziel:** `rpicam-hello` erkennt die Kamera → Einzelbild (JPEG) → Video → **Live-Stream auf den
  Dev-Rechner**.

## 2. Plan-Skizze (Logik & Design-Entscheidungen)

**Ausgangslage (bereits verifiziert, s. §4):** Kernel-Treiber `ov5647` + CFE/PiSP-Pipeline sind
im Ubuntu-Kernel vorhanden, Sensor bindet, `/dev/video0` registriert. **Aber** Ubuntus
Upstream-`libcamera` (0.2.0, noble) hat **weder den Raspberry-Pi-Pipeline-Handler noch die IPA**
→ `cam -l` ist leer. Es fehlt also nur das Userland.

**Lösung:** Pi-Fork von `libcamera` + `rpicam-apps` **from source** bauen und nach `/usr/local`
installieren. Der Fork bringt den `rpi/pisp`-Pipeline-Handler + IPA (Auto-Belichtung/-Weißabgleich).

**Design-Entscheidungen:**
- **Install-Prefix `/usr/local`** (Standard für source-Builds) — getrennt von `/opt/ros` (ROS) und
  den Distro-Libs in `/usr/lib`. Beeinflusst den Roboter-Stack nicht; reversibel (uninstall).
- **Headless-Build:** Preview (Qt/EGL/DRM) **aus** — es gibt kein Display; wir capturen in Dateien
  und streamen.
- **Video = MJPEG (kein H264).** Der **Pi 5 hat keinen HW-H264-Encoder** (BCM2712); H264 ginge nur
  in Software über `libav`. Dessen Build scheitert aber auf noble (ffmpeg 6.1 zu alt für
  `rpicam-apps 1.12` → „libavcodec API version is too old") → `-Denable_libav=disabled`. Für
  Capture + Stream nutzen wir daher den **MJPEG-Encoder** (`--codec mjpeg`) — kein H264 nötig.
- **`pycamera`/`gstreamer` aus** im ersten Build (weniger Deps, schneller). Nachrüstbar, falls
  später `picamera2`/GStreamer gebraucht wird.
- **Build-Ordner `~/camera_build/`** (außerhalb `hexapod_ws`).

## 3. Tests-Liste

| Test | Prüft | Done wenn |
|---|---|---|
| T1 `rpicam-hello --list-cameras` | Userland sieht die Kamera | OV5647 wird gelistet (Modi/Auflösungen) |
| T2 `rpicam-jpeg` | Einzelbild-Capture inkl. ISP | JPEG entsteht, Bild plausibel (am Dev ansehen) |
| T3 `rpicam-vid --codec mjpeg` | Video-Capture (MJPEG) | `.mjpeg`-Datei entsteht |
| T4 Stream → Dev (SSH-Pipe, MJPEG) | Live-Übertragung übers LAN | Bild läuft flüssig in `ffplay`/`mpv` am Dev |

**Bewusst NICHT getestet / scope-out:** On-Sensor-AI (OV5647 hat keine NPU); ROS-Anbindung
(`camera_ros`/Image-Topic — später); Preview am Pi (headless); Foto-Feintuning (Fokus v1.3 ist
fixfokus/manuell, Belichtung via IPA automatisch).

## 4. Voraussetzungen (bereits erledigt & verifiziert)

- `dtoverlay=ov5647` steht in `/boot/firmware/config.txt`, Pi rebootet.
- `dmesg`: `rp1-cfe … Using sensor ov5647 … for capture`, `/dev/video0` registriert. ✓
- `v4l-utils` installiert; `v4l2-ctl --list-devices` zeigt `rp1-cfe`. ✓

> Der `i2c read error … -121` / `probe … failed` betrifft nur den **leeren** zweiten CSI-Port —
> harmlos. Optional-Kosmetik: in `config.txt` `dtoverlay=ov5647` durch `dtoverlay=ov5647,cam0`
> (oder `,cam1`) ersetzen, je nach belegtem Port → Reboot. Nicht nötig für die Funktion.

## 5. Build & Installation (from source)

> **Hinweis §5:** Die `apt`-Installationen unten sind Build-Tools/Libs (erlaubt). `sudo ninja
> install` schreibt nach `/usr/local`, die ld-Conf nach `/etc/ld.so.conf.d/` — beides Standard für
> source-Builds und **reversibel** (s. §8). Kein `apt full-upgrade`, kein Kernel, keine PPA.

### 5.1 libcamera (Pi-Fork) bauen

Build-Abhängigkeiten:
```bash
sudo apt update
sudo apt install -y git meson ninja-build pkg-config
sudo apt install -y python3-yaml python3-ply python3-jinja2
sudo apt install -y libboost-dev libgnutls28-dev openssl libtiff-dev libudev-dev
```

Klonen + bauen + installieren:
```bash
mkdir -p ~/camera_build && cd ~/camera_build
git clone https://github.com/raspberrypi/libcamera.git
cd libcamera
meson setup build --buildtype=release \
  -Dpipelines=rpi/vc4,rpi/pisp \
  -Dipas=rpi/vc4,rpi/pisp \
  -Dv4l2=true \
  -Dgstreamer=disabled \
  -Dpycamera=disabled \
  -Dtest=false \
  -Dlc-compliance=disabled \
  -Dcam=disabled \
  -Dqcam=disabled \
  -Ddocumentation=disabled
ninja -C build
sudo ninja -C build install
```

Library-Pfad bekanntmachen:
```bash
echo "/usr/local/lib/aarch64-linux-gnu" | sudo tee /etc/ld.so.conf.d/rpicam.conf
sudo ldconfig
```

### 5.2 rpicam-apps bauen

Build-Abhängigkeiten:
```bash
sudo apt install -y cmake libboost-program-options-dev libexif-dev
sudo apt install -y libjpeg-dev libtiff-dev libpng-dev
```
> (Die `libav*`-Dev-Pakete sind **nicht** nötig — der libav-Encoder wird auf noble nicht gebaut,
> s. Design-Entscheidung §2.)

Klonen + bauen + installieren (headless: Preview **und** libav aus → nativer H264-Encoder):
```bash
cd ~/camera_build
git clone https://github.com/raspberrypi/rpicam-apps.git
cd rpicam-apps
export PKG_CONFIG_PATH=/usr/local/lib/aarch64-linux-gnu/pkgconfig:/usr/local/lib/pkgconfig
meson setup build --buildtype=release \
  -Denable_libav=disabled \
  -Denable_drm=disabled \
  -Denable_egl=disabled \
  -Denable_qt=disabled \
  -Denable_opencv=disabled \
  -Denable_tflite=disabled \
  -Denable_hailo=disabled
meson compile -C build
sudo meson install -C build
sudo ldconfig
```
> ⚠️ `-Denable_libav=enabled` **scheitert** auf Ubuntu 24.04 (ffmpeg zu alt, s. §8). Deshalb hier
> bewusst `disabled`.

> Falls meson eine `-D…`-Option ablehnt (Versions-Drift): `meson configure build` listet die
> gültigen Optionsnamen → entsprechend anpassen.

## 6. Test-Befehle

### T1 — Kamera erkannt?
```bash
rpicam-hello --list-cameras
```
Erwartung: ein Eintrag mit `ov5647` + verfügbaren Modi/Auflösungen.

> Falls „no cameras available": prüfen, dass rpicam den **Fork** lädt:
> `ldd $(which rpicam-hello) | grep libcamera` → muss auf `/usr/local/...` zeigen (s. §8).

### T2 — Einzelbild (headless, `-n` = keine Vorschau)
```bash
rpicam-jpeg -n -t 2000 -o ~/peripheries/cam_test.jpg
```
Bild am Dev ansehen (Pi ist headless):
```bash
# auf dem DEV-Rechner:
scp hexapod-pi:~/peripheries/cam_test.jpg .
xdg-open cam_test.jpg
```

### T3 — Video (MJPEG — Pi 5 hat kein HW-H264)
```bash
rpicam-vid -n --codec mjpeg -t 5s -o ~/peripheries/cam_test.mjpeg
ls -l ~/peripheries/cam_test.mjpeg
```

### T4 — Live-Stream auf den Dev-Rechner (MJPEG über SSH-Pipe) ✅ verifizierter Weg
Am elegantesten ohne IP/Port/Firewall — **alles auf dem DEV-Rechner** ausführen (nutzt den
`hexapod-pi`-SSH-Alias):
```bash
ssh hexapod-pi "rpicam-vid -t 0 -n --codec mjpeg --framerate 15 -o -" \
 | ffplay -fflags nobuffer -flags low_delay -framedrop -probesize 32 -analyzeduration 0 -i -
```
- **`-framedrop` ist entscheidend** gegen wachsende Verzögerung (sonst spielt ffplay jeden Frame
  ab und hängt zunehmend hinterher).
- `ffmpeg`/`ffplay` muss auf dem **Dev** installiert sein: `sudo apt install -y ffmpeg`.
- Beenden: `q` im ffplay-Fenster (oder Strg-C).

Alternative Player (oft noch direkter):
```bash
ssh hexapod-pi "rpicam-vid -t 0 -n --codec mjpeg --framerate 15 -o -" \
 | mpv --profile=low-latency --no-cache --untimed -
```

> Direkter TCP statt SSH ginge auch (Pi: `rpicam-vid … --listen -o tcp://0.0.0.0:5000`, Dev:
> `ffplay … tcp://<PI-IP>:5000`) — nicht nötig, der SSH-Weg läuft flüssig.

## 7. Done-Kriterien (Checkliste)

- [x] libcamera-Fork gebaut + nach `/usr/local` installiert, `ldconfig` aktualisiert
- [x] rpicam-apps gebaut + installiert (`-Denable_libav=disabled`)
- [x] `rpicam-hello`-Pipeline aktiv: OV5647 erkannt, Tuning `ov5647.json` geladen, `rpi/pisp`
- [x] MJPEG-Capture funktioniert (`cam_test.mjpeg` erzeugt)
- [x] Video als MJPEG (`--codec mjpeg`) — Pi 5 hat kein HW-H264
- [x] Live-Stream läuft **flüssig** am Dev (SSH-Pipe + MJPEG + `-framedrop`)

✅ **v1.3-Kamera verifiziert:** Bild + flüssiger Live-Stream auf Ubuntu 24.04 (5 MP, MJPEG,
**keine** On-Sensor-AI). Status in `00_overview.md` = 🟢.

## 8. Troubleshooting

| Symptom | Ursache / Fix |
|---|---|
| `rpicam-hello`: „no cameras available" | `ldd $(which rpicam-hello) \| grep libcamera` zeigt **nicht** `/usr/local` → `sudo ldconfig`; sicherstellen, dass beim rpicam-Build `PKG_CONFIG_PATH` auf `/usr/local/...` zeigte (5.2). Notfalls Distro-`libcamera-tools` entfernen, um Verwechslung auszuschließen. |
| `/dev/video0` fehlt | Overlay/Kernel: `dmesg \| grep -i ov5647` prüfen; ggf. `dtoverlay=ov5647,cam0`/`,cam1` (richtiger Port) + Reboot. |
| meson lehnt `-D…`-Flag ab | Versions-Drift → `meson configure build` zeigt gültige Optionen. |
| Build-Fehler `libavcodec API version is too old for the libav encoder` | Ubuntu 24.04 (ffmpeg 6.1) ist zu alt für den libav-Encoder von rpicam-apps 1.12. Fix: `-Denable_libav=disabled` (so wie in §5.2). Reconfigure: `meson configure build -Denable_libav=disabled && meson compile -C build`. |
| `rpicam-vid`: „Unable to find an appropriate H.264 codec" | Pi 5 hat **keinen HW-H264-Encoder** und libav ist aus → H264 nicht verfügbar. **MJPEG nutzen:** `--codec mjpeg`. |
| Stream stark verzögert (laggy) | ffplay-Puffer → **`-framedrop`** + `-fflags nobuffer -flags low_delay` setzen; oder `mpv --profile=low-latency`. SSH-Pipe-Weg s. T4. |
| `ffplay`/`rpicam-vid`: „connect to server failed" (TCP) | rpicam-vid ohne `--listen` ist TCP-**Client**. Server-Modus: `--listen`; oder den **SSH-Pipe-Weg** (T4) nehmen (kein Server/Port nötig). |
| Build bricht mit OOM ab | Job-Zahl begrenzen: `ninja -C build -j4` bzw. `meson compile -C build -j4`. |
| Bild grünstichig/dunkel | OV5647-Tuning/IPA: prüfen, dass IPA unter `/usr/local/lib/aarch64-linux-gnu/libcamera/` + Tuning unter `/usr/local/share/libcamera/...` installiert sind (kommt mit dem Fork-Install). |
| Stream ruckelt | WLAN-Bandbreite; niedrigere Auflösung/Bitrate (`--width 1280 --height 720 -b 4000000`) oder Ethernet. |

### Deinstallation (reversibel)
```bash
cd ~/camera_build/rpicam-apps && sudo ninja -C build uninstall
cd ~/camera_build/libcamera   && sudo ninja -C build uninstall
sudo rm -f /etc/ld.so.conf.d/rpicam.conf && sudo ldconfig
# optional: rm -rf ~/camera_build  und  config.txt-Zeile dtoverlay=ov5647 entfernen + Reboot
```

## 9. Offene Punkte / spätere Integration

- **ROS-Pfad:** späterer `camera_ros`-Node (libcamera→ROS2) publisht ein Image-Topic →
  Ansicht via `rqt_image_view` auf dem Dev. Erst bei echter Integration → **dann** in reguläre Docs.
- **Keine On-Sensor-AI:** OV5647 ist eine reine Kamera; Objekt-Erkennung müsste auf der Pi-CPU
  laufen (eigenes Thema, nicht Teil dieses Hello-World).
- **Port-Kosmetik:** `dtoverlay=ov5647,cam<N>` statt nacktem `ov5647` beseitigt die harmlose
  Leerport-Probe-Meldung.
