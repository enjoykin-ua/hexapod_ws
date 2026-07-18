# Phase 4 — Test-Befehle: Video-Pipeline (Sim)

> Du führst aus, knappe Status-Meldung zurück. **Kontext-Tags:**
> **▶ ROS (hexapod_ws)** = Desktop-Terminal · **▶ Browser** = Desktop-Firefox/Chrome bzw.
> Handy-Browser · **▶ App** = *echte App = Integration P4.11 (Android-Session)*.
>
> **Ziel:** Gazebo-Kamera → Bridge (`/camera/image_raw`, ~15 Hz) → `web_video_server`
> (:8080, MJPEG) → Bild im **Desktop- und Handy-Browser** sichtbar.
> Plan: [`phase_4_video_shell_plan.md`](phase_4_video_shell_plan.md) · Progress:
> [`phase_4_video_shell_progress.md`](phase_4_video_shell_progress.md).

---

## Vorbereitung

**▶ ROS — einmalig `web_video_server` installieren (Stock-Paket):**
```bash
sudo apt install -y ros-jazzy-web-video-server
```
> Ohne dieses Paket startet der `web_video_server`-Node nicht (Build bricht **nicht** — es ist
> eine Runtime-Dependency, kein Build-Dep).

**▶ ROS — bauen + sourcen:**
```bash
cd ~/hexapod_ws && colcon build --packages-select hexapod_description hexapod_gazebo hexapod_bringup
source /opt/ros/jazzy/setup.bash && source ~/hexapod_ws/install/setup.bash
```

---

## Sim starten — Variante A: On-Demand-Stack (= der App-Pfad, empfohlen)

Das ist die Kette, die die App später fährt (`bringup_ondemand mode:=sim` → `ramp_walk` →
`ramp.launch.py`). Sie lädt `ramp.sdf.xacro` (flach, slope 0) **mit** Sensors-System.

**Terminal 1 (▶ ROS):**
```bash
source /opt/ros/jazzy/setup.bash && source ~/hexapod_ws/install/setup.bash
ros2 launch hexapod_bringup ramp_walk.launch.py slope_deg:=0.0
```
> Startet Gazebo + Spawn + (nach `gait_delay` ~12 s) Auto-Standup. **`web_video_server` +
> `camera_bridge` kommen mit** (`enable_camera` Default `true`). Warte, bis der Roboter steht.

**Terminal 2 (▶ ROS)** = Prüf-Befehle (jeweils zuerst sourcen).

### Sim starten — Variante B: direkter Bringup (ohne Laufen, für reinen Video-Check)
```bash
ros2 launch hexapod_bringup sim.launch.py            # Default-Welt empty_imu.sdf (+ Sensors-System)
```
> Reicht für T4.1–T4.3, wenn du nur die Video-Pipeline (nicht das Laufen) prüfen willst.

---

## T4.1 — `/camera/image_raw` wird published (~15 Hz)

```bash
ros2 topic list | grep camera
ros2 topic hz /camera/image_raw
```
**✅ Erwartung:** `/camera/image_raw` (+ `/camera/camera_info`) gelistet; `hz` pendelt um **~15 Hz**
(gz-Sensor `update_rate` 15). Bei 0 Hz → Sensors-System fehlt in der Welt oder `enable_camera` ist aus.

## T4.1b — Verifizierungs-Punkte (einmalig gegenchecken, nicht raten)

```bash
gz topic -l | grep -i camera                          # echten gz-camera_info-Topicnamen sehen
ros2 param list /web_video_server                      # bestaetigt port/address-Param-Namen
ros2 node info /web_video_server | grep -i image       # subscribt es /camera/image_raw?
```
**✅ Erwartung:** gz listet `/camera/sim` **und** den camera_info-Topic (erwartet `/camera/sim/camera_info`
— falls abweichend, `bridge_camera.yaml` `gz_topic_name` anpassen). `web_video_server` hat `port`/`address`.

## T4.2 — `web_video_server` liefert MJPEG (Desktop-Browser)

**▶ Browser (Desktop) — zwei Wege:**
```
http://localhost:8080                                              # Index: Topic-Liste, "Stream" anklicken (stream_viewer, HTML)
http://localhost:8080/stream?topic=/camera/image_raw&type=mjpeg    # roher MJPEG-Endpunkt (= EXAKT die App-URL, §5)
```
**✅ Erwartung:** Beide zeigen das **Live-Gazebo-Bild** (Boden + ggf. vordere Beine im Blickfeld),
flüssig. Der **rohe `…/stream?…&type=mjpeg`-Endpunkt muss direkt funktionieren** — das ist die
URL, die die App lädt (die Index/`stream_viewer`-Seite ist nur ein HTML-Wrapper drumherum).
> Bleibt der rohe Endpunkt schwarz, obwohl der Index/Viewer geht: URL exakt prüfen (das `&type=mjpeg`
> darf nicht abgeschnitten sein; in der Adressleiste 1:1 einfügen). Der Server liefert
> `multipart/x-mixed-replace` — der Browser zeigt es als fortlaufend aktualisiertes Bild.

## T4.3 — Handy-Browser sieht das Bild (Netz-Erreichbarkeit)

**▶ ROS — Desktop-IP ermitteln:**
```bash
hostname -I | awk '{print $1}'                         # z.B. 192.168.x.y
```
**▶ Browser (Handy, gleiches WLAN):**
```
http://<Desktop-IP>:8080/stream?topic=/camera/image_raw&type=mjpeg
```
**✅ Erwartung:** dasselbe Live-Bild auf dem Handy. Falls nichts kommt: Firewall auf dem Desktop
(`sudo ufw status`; Port 8080 muss vom LAN erreichbar sein) bzw. beide im selben Netz.

> **Reihenfolge-Hinweis:** T4.4–T4.6 (App-Fahr-Screen, Center-Toggle, Overlay-Slots) sind
> **App-Tests** (Android-Session, Plan §5) — hier im ROS-test_commands übersprungen. Daher geht
> es von T4.3 direkt zu T4.7 (ROS-beobachtbar) und T4.11-ROS.

## T4.7 — Latenz qualitativ „folgbar" (NF4)

Bewege die Sim (z.B. Roboter laufen lassen, T4.11) und beobachte den Handy-Stream.
**✅ Erwartung:** Bild folgt der Bewegung „ohne störende Verzögerung" (~100–300 ms; harte Zahl später).

## T4.11-ROS — Walking-Smoke mit Kamera an (URDF-Refactor-Gegenprobe)

> [[feedback_urdf_refactor_full_smoke]]: nach dem xacro-Umbau nicht nur Build — echtes Spawn + Laufen.

**Terminal 2 (Variante A läuft, Roboter steht).** Fahren — **direkt auf `/cmd_vel`** (kein
rosbridge nötig; `gait_node` subscribt `/cmd_vel` direkt, umgeht Dead-Man/joy_to_twist):
```bash
ros2 topic pub -r10 /cmd_vel geometry_msgs/msg/Twist '{linear: {x: 0.05}}'   # Ctrl-C zum Stoppen
```
**✅ Erwartung:** Roboter läuft normal vorwärts (Kamera bricht Spawn/tf/Walking **nicht**); der
Stream zeigt das mitlaufende Bild. tf-Baum enthält `camera_link`:
```bash
ros2 run tf2_tools view_frames && echo "frames.pdf: camera_link unter base_link?"
```

> **Alternative (App-Ersatz-Client `joy_ws_test_client.py`):** braucht **zusätzlich rosbridge** —
> `ramp_walk.launch.py` startet es NICHT. In einem dritten Terminal erst
> `ros2 launch hexapod_bringup app_teleop.launch.py` (rosbridge :9090 + joy_to_twist app-Modus),
> dann `python3 ~/hexapod_ws/tools/joy_ws_test_client.py --host 127.0.0.1 --duration 5 --forward 0.6`.
> Für den reinen Video-/Walking-Smoke ist der direkte `/cmd_vel`-Publish oben einfacher.

---

## Was NICHT in Phase 4 (scope-out)
- Echte Raspi-Cam (Pi/Phase 7) — Phase 4 = Gazebo-Kamera.
- App-Fahr-Screen/Center-Toggle/Overlay-Slots (P4.7–P4.9) = **Android-Session** gegen Plan §5.
- Overlay-Inhalte/Dropdowns/3D-Viz/Config/Alerts (Phase 5), E-Stop scharf (Phase 6).
- Harte Latenzzahl + RTSP/H.264/WebRTC (späteres Upgrade).
- ROS-seitiges Kamera-an/aus (`camera_enable`) — Pi/Phase 7 (in Sim app-seitig).

## Melde-Vorlage
T4.1 hz ~15? · T4.1b gz-camera_info-Name + web_video_server-Params? · T4.2 Desktop-Bild? ·
T4.3 Handy-Bild? · T4.7 Latenz folgbar? · T4.11 läuft normal + `camera_link` im tf? Plus Auffälligkeiten.
