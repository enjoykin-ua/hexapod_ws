# Phase 7B — Test-Befehle: echte Raspi-Cam (Desktop-E2E + Pi-HW)

> Du führst aus, knappe Status-Meldung zurück. **Kontext-Tags:** **▶ ROS** = Desktop-Terminal ·
> **▶ Pi** = auf dem Roboter (ssh) · **▶ App** = *echte App (Android-Session)*.
>
> **Ziel:** die echte OV5647 publisht `/camera/image_raw/compressed` (JPEG) → `web_video_server`
> streamt es (HW: `type=ros_compressed`). Der **`source:=test`**-Modus macht die ganze Kette schon
> **am Desktop** prüfbar (ohne Pi/Kamera). Plan:
> [`phase_7b_camera_plan.md`](phase_7b_camera_plan.md) · Progress:
> [`phase_7b_camera_progress.md`](phase_7b_camera_progress.md).

---

## Unit-Tests (▶ ROS)
```bash
cd ~/hexapod_ws
source /opt/ros/jazzy/setup.bash && source ~/hexapod_ws/install/setup.bash
colcon build --packages-select hexapod_sensors hexapod_bringup
colcon test --packages-select hexapod_sensors hexapod_bringup
colcon test-result --test-result-base build/hexapod_sensors
colcon test-result --test-result-base build/hexapod_bringup
```
**✅ Erwartung:** hexapod_sensors 20/0/0/1, hexapod_bringup 46/0/0/0, Lint grün.

---

## Desktop-E2E (▶ ROS) — `source:=test` → web_video_server → Bild (ohne Pi)

**Terminal 1** — Kamera-Node (Test-Quelle) + web_video_server:
```bash
source /opt/ros/jazzy/setup.bash && source ~/hexapod_ws/install/setup.bash
ros2 launch hexapod_bringup camera.launch.py source:=test
```
> Startet `hexapod_camera` (synthetisches SMPTE-JPEG @15 Hz) + `web_video_server` :8080.

**Terminal 2** — prüfen:
```bash
source /opt/ros/jazzy/setup.bash && source ~/hexapod_ws/install/setup.bash
ros2 topic hz /camera/image_raw/compressed          # ~15 Hz
```
**Browser (am Desktop):**
```
http://localhost:8080/stream?topic=/camera/image_raw&type=ros_compressed
```
**✅ Erwartung (T7B.5):** die **SMPTE-Farbbalken** erscheinen flüssig im Browser (das ist der
`ros_compressed`-Weg = derselbe wie später auf HW). Alternativ headless per curl:
```bash
curl -s "http://localhost:8080/stream?topic=/camera/image_raw&type=ros_compressed" -o /tmp/s.bin & \
  sleep 3; kill %1 2>/dev/null; \
  python3 -c "d=open('/tmp/s.bin','rb').read(); print('bytes',len(d),'| JPEGs',d.count(b'\xff\xd8'),'| multipart',b'boundarydonotcross' in d)"
```
**✅ Erwartung:** `bytes` > 0, mehrere `JPEGs`, `multipart True`.

**camera_enable (Desktop, Terminal 2):**
```bash
ros2 param set /hexapod_camera camera_enable false   # Publish stoppt (topic hz versiegt)
ros2 param set /hexapod_camera camera_enable true    # kommt zurück
```

---

## Pi-HW (▶ Pi / ▶ App, User) — echte OV5647 (T7B.6–8)

**Vorbereitung (▶ Pi):** rpicam-Userland aus dem Hello-World vorausgesetzt (libcamera-Fork +
rpicam-apps, `~/camera_build/`, siehe `peripherals_tests/camera_ov5647_v13.md`). Gegencheck:
```bash
rpicam-hello --list-cameras     # OV5647 gelistet
ros2 run hexapod_sensors hexapod_camera        # source:=rpicam (Default)
```

**Stream + Anzeige:**
```bash
ros2 topic hz /camera/image_raw/compressed      # ~15 Hz (T7B.6)
# Browser/App: http://<Pi-IP>:8080/stream?topic=/camera/image_raw&type=ros_compressed  (T7B.7)
```
> Im **App-Betrieb** kommt der Node + web_video_server automatisch mit `bringup_start` (mode:=real);
> die App wählt für den Pi-Host `type=ros_compressed` (Variante A).

**camera_enable (▶ Pi, T7B.8):**
```bash
ros2 param set /hexapod_camera camera_enable false   # rpicam-vid-Subprozess aus (Sensor/ISP idle)
ros2 param set /hexapod_camera camera_enable true    # Stream kommt zurück
```
**✅ Erwartung:** echtes Kamerabild flüssig im Browser + in der App; `camera_enable` stoppt/startet
den Stream (Strom/Wärme plausibel runter/rauf).

---

## Was NICHT in Phase 7B (scope-out)
- App-URL-`type`-je-Host (P7B.13) = **Android-Session** gegen §5 (Variante A).
- H264/RTSP/WebRTC; Auflösungs-/Latenz-Tuning; `camera_ros` (Weg b); IPA/Belichtung.

## Melde-Vorlage
Unit 20+46 grün? · Desktop-E2E: topic ~15 Hz + SMPTE-Bild im Browser (ros_compressed)? · camera_enable
stoppt/startet? · (Pi) echtes Bild + FPS + camera_enable Strom/Wärme? Plus Auffälligkeiten.
