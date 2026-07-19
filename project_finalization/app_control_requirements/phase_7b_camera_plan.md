# Phase 7B — Echte Raspi-Cam am Roboter — Plan

> **Ziel:** die **echte Raspberry-Pi-Kamera v1.3 (OV5647)** am Pi publisht **`/camera/image_raw`** —
> dasselbe Topic, das in der Sim der Gazebo-Kamera-Sensor liefert. Damit greifen der bestehende
> **`web_video_server` (:8080, MJPEG)** und die **App-Video-View** (Phase 4) **unverändert**: je nach
> gestartetem Stack (Sim **oder** Real) sieht die App automatisch das Sim- bzw. das Raspi-Bild.
> Dazu ein **`camera_enable`**-Schalter (Kamera-Node an/aus, Strom/Wärme).
>
> **Seite:** primär ROS (Pi), minimale App-Justierung möglich. **Status: 🟡 Plan.** Self-contained.
> Contract: [`interface_contract.md`](interface_contract.md) (§5 Video, §6 `camera_enable [TBD-Phase 7]`).
> HW-Hello-World (verifiziert): [`../peripherals_tests/camera_ov5647_v13.md`](../peripherals_tests/camera_ov5647_v13.md).

---

## 0. Ziel + Abgrenzung

**Bestand (schon da):**
- **Kamera-HW verifiziert** (`peripherals_tests/camera_ov5647_v13.md`): OV5647 (5 MP, CSI) am Pi 5,
  Kernel-Treiber + `/dev/video0` da. Userland = **Pi-Fork `libcamera` + `rpicam-apps` from source**
  (Build in `~/camera_build/`, Install `/usr/local`, **kein** Kernel-/PPA-Eingriff). **MJPEG** (Pi 5
  hat **keinen** HW-H264-Encoder). Live-Stream via `rpicam-vid --codec mjpeg` verifiziert.
- **Sim-Video-Pipeline** (Phase 4, existiert): gz-Kamera-Sensor (`hexapod.camera.xacro`, Topic
  `/camera/sim`) → `ros_gz_bridge` (`bridge_camera.yaml`) → **`/camera/image_raw`** (`sensor_msgs/Image`)
  → **`web_video_server` :8080** (MJPEG). `sim.launch.py`-Arg **`enable_camera`** (Default `true`)
  startet Bridge + `web_video_server` conditional.
- **Contract §5:** URL `http://<host>:8080/stream?topic=/camera/image_raw&type=mjpeg`; „real =
  Raspi-Cam v1.3 → **gleiches Topic**, Stream-Server + App unverändert".

**Neu in Phase 7B:**
1. **HW-Kamera-Publisher-Node** (auf dem Pi): liest die OV5647 via **`rpicam-vid --codec mjpeg`**
   (Subprozess, [D-Cam-1] „Weg a") und publisht die JPEG-Frames als **`sensor_msgs/CompressedImage`**
   auf **`/camera/image_raw/compressed`** (`format: "jpeg"`).
2. **`web_video_server` im real-Pfad** (bisher nur sim) → :8080-MJPEG auch auf HW.
3. **`camera_enable`** — Kamera-Node/Subprozess an/aus (Strom/Wärme sparen, wenn kein Video gebraucht).

**Bewusst NICHT in Phase 7B:**
- **H264/WebRTC** — MJPEG v1 (Pi 5 kein HW-H264; RTSP/H.264 später, Contract §5 „Upgrade später").
- **On-Sensor-AI / Objekt-Erkennung** (OV5647 hat keine NPU).
- **Auflösungs-/FPS-Feintuning**, Belichtungs-Tuning (IPA-Automatik reicht v1).
- **`camera_ros`-Weg** — als optionale Evaluation notiert ([D-Cam-1] „Weg b"), nicht v1.
- **Audio** — Phase 7A.

---

## 1. Logik-Skizze / Pseudocode

### 1a. HW-Kamera-Publisher (`rpicam-vid` → CompressedImage, [D-Cam-1] Weg a)
`rpicam-vid --codec mjpeg -o -` schreibt einen **fortlaufenden Strom kompletter JPEGs** auf stdout
(jeder Frame = ein JPEG, Grenze `FFD8…FFD9`). Der Node liest stdout, zerlegt in Frames, publisht jeden
als `CompressedImage`:
```python
class RpicamNode(Node):
    def __init__(self):
        super().__init__('hexapod_camera')
        self._w   = declare('width', 1280)
        self._h   = declare('height', 720)
        self._fps = declare('framerate', 15)
        self._topic = declare('image_topic', '/camera/image_raw')   # -> .../compressed
        self._frame_id = declare('frame_id', 'camera_link')
        self._enabled  = declare('camera_enable', True)             # Start/Stop des Subprozesses
        self._pub = self.create_publisher(CompressedImage, self._topic + '/compressed', 10)
        self._proc = None
        self.add_on_set_parameters_callback(self._on_param)         # camera_enable live
        if self._enabled:
            self._start()

    def _start(self):
        cmd = ['rpicam-vid', '-t', '0', '-n', '--codec', 'mjpeg',
               '--framerate', str(self._fps), '--width', str(self._w),
               '--height', str(self._h), '--inline', '-o', '-']
        self._proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, bufsize=0)
        self._reader = Thread(target=self._read_loop, daemon=True); self._reader.start()

    def _read_loop(self):
        buf = b''
        while rclpy.ok() and self._proc and self._proc.poll() is None:
            chunk = self._proc.stdout.read(4096)
            if not chunk: break
            buf += chunk
            # vollständige JPEGs (FFD8..FFD9) herausschneiden + publishen
            while True:
                soi = buf.find(b'\xff\xd8'); eoi = buf.find(b'\xff\xd9', soi + 2)
                if soi < 0 or eoi < 0: break
                jpeg = buf[soi:eoi + 2]; buf = buf[eoi + 2:]
                self._publish(jpeg)

    def _publish(self, jpeg: bytes):
        msg = CompressedImage()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = self._frame_id
        msg.format = 'jpeg'
        msg.data = jpeg
        self._pub.publish(msg)

    def _stop(self):
        if self._proc and self._proc.poll() is None:
            self._proc.terminate()
        self._proc = None
```

### 1b. `camera_enable` (Strom/Wärme, [D-Cam-3])
```python
    def _on_param(self, params):
        for p in params:
            if p.name == 'camera_enable':
                if p.value and not self._enabled: self._start()
                elif not p.value and self._enabled: self._stop()
                self._enabled = bool(p.value)
        return SetParametersResult(successful=True)
```
> `camera_enable=false` → `rpicam-vid`-Subprozess **beendet** (Sensor/ISP idle → Strom/Wärme runter).
> Die App entlädt zusätzlich die MJPEG-URL (Phase 4 macht das schon app-seitig). `camera_enable`
> ist der **echte** Node-seitige Aus-Schalter.

### 1c. `web_video_server` im real-Pfad
`web_video_server` abonniert das Bild über **`image_transport`** und serviert `…&type=mjpeg`. Es
findet `/camera/image_raw` sowohl als **raw** (Sim, `sensor_msgs/Image`) als auch als **compressed**
(HW, `/camera/image_raw/compressed`) — `image_transport` wählt den passenden Transport automatisch.
→ **Kein** App-/URL-Change: die URL bleibt `…/stream?topic=/camera/image_raw&type=mjpeg`.
⚠️ **Pi-Verifikationspunkt (§4.1):** bestätigen, dass `web_video_server` bei **nur** vorhandenem
`/camera/image_raw/compressed` (kein raw-Publisher) sauber streamt.

### 1d. Sim vs. Real — dasselbe Topic, ein Stack zur Zeit
| Modus | Bildquelle | `/camera/image_raw` | Stream-Server | App |
|---|---|---|---|---|
| **Sim** | gz-Kamera-Sensor | raw (`sensor_msgs/Image`) via Bridge | `web_video_server` :8080 | unverändert |
| **Real** | OV5647 (`rpicam-vid`) | compressed (`/…/compressed`) | `web_video_server` :8080 | unverändert |

→ Es läuft immer **genau ein** Stack; die App zeigt automatisch das Bild des aktiven Stacks.

---

## 2. Tests-Liste (+ was NICHT)

| Test | Prüft | Warum |
|---|---|---|
| **T7B.1** JPEG-Framing: aus einem `rpicam-vid`-MJPEG-Bytestrom werden vollständige JPEGs korrekt geschnitten (Unit, Fixture-Bytes) | Kern-Parsing | keine kaputten Frames |
| **T7B.2** Node publisht `CompressedImage` (`format:"jpeg"`, `frame_id`, monotone stamps) je Frame (Unit, gemockter Subprozess-Stream) | Publish-Kontrakt | web_video_server-kompatibel |
| **T7B.3** `camera_enable=false` → Subprozess `terminate`, kein Publish; `=true` → (re)start (Unit, gemockt) | An/Aus | Strom/Wärme |
| **T7B.4** fehlendes `rpicam-vid` / Subprozess-Exit → **kein Crash**, WARN, sauberes Cleanup | Robustheit | Feld |
| **T7B.5 (HW, User)** `rpicam-vid`-Node läuft am Pi, `ros2 topic hz /camera/image_raw/compressed` ~ FPS | HW-Publisher | am echten Roboter |
| **T7B.6 (HW, User)** `web_video_server` :8080 → Bild im Browser **und** in der App (`…&type=mjpeg`) | E2E-Video | Kern-Deliverable |
| **T7B.7 (HW, User)** `camera_enable` false/true → Stream stoppt/kommt zurück; Strom/Wärme plausibel | camera_enable | HW |
| **T7B.8** `colcon test` + Lint grün | keine Regression | §4-Pflicht |

**Bewusst offen/später:** H264/RTSP/WebRTC; Auflösungs-/Bitraten-/Latenz-Tuning (live justierbar);
`camera_ros`-Weg (Weg b); IPA/Belichtungs-Feintuning; Mehrkamera.

---

## 3. Progress-Checkliste (→ `phase_7b_camera_progress.md`, Done-Vertrag)
```
Phase 7B (Echte Raspi-Cam):
- [ ] P7B.1 [ROS] Paket hexapod_camera (oder Node in hexapod_sensors): RpicamNode = rpicam-vid MJPEG-Subprozess -> CompressedImage (T7B.1/T7B.2)
- [ ] P7B.2 [ROS] JPEG-Framing (FFD8..FFD9) robust + monotone stamps + frame_id=camera_link
- [ ] P7B.3 [ROS] camera_enable-Param: Subprozess start/stop live (T7B.3)
- [ ] P7B.4 [ROS] Robustheit: rpicam fehlt / Subprozess-Exit -> kein Crash, Cleanup (T7B.4)
- [ ] P7B.5 [ROS] web_video_server im real-Launch (conditional camera_enable), :8080 gleiche URL
- [ ] P7B.6 [ROS] Launch-Wiring real-Pfad (Node + web_video_server); Sim-Pfad unverändert
- [ ] P7B.7 [ROS] Unit-Tests + Lint gruen (T7B.8)
- [ ] P7B.8 [ROS] Contract §5/§6 festgezurrt (Real-Quelle CompressedImage, camera_enable), Version-Bump
- [ ] P7B.9 [ROS] Self-Review + Doku (README/architecture/ai_navigation, test_commands)
- [ ] P7B.10 [Pi-Verify, User] rpicam-Node am Pi: /camera/image_raw/compressed ~FPS (T7B.5)
- [ ] P7B.11 [Integration, User+App] web_video_server :8080 -> Bild in Browser + App; camera_enable an/aus (T7B.6/T7B.7)
- [ ] P7B.12 [App, optional] Justierung falls compressed-Transport eine Anpassung braucht (sonst unverändert)
```

---

## 4. Offene Punkte / Risiken (vor/beim Code entscheiden)
1. **`web_video_server` + nur-compressed** (§1c-⚠️): am Pi verifizieren, dass `…&type=mjpeg` streamt,
   wenn **nur** `/camera/image_raw/compressed` existiert (kein raw). Falls nicht: (a) URL auf
   `topic=/camera/image_raw/compressed` umstellen (App-Justierung P7B.12), oder (b) im Node zusätzlich
   ein raw-`Image` publishen (CPU-Decode — teurer, letzter Ausweg).
2. **Weg a vs. Weg b** ([D-Cam-1]): Weg a (rpicam-Subprozess) zuerst — nutzt den verifizierten
   Hello-World-Pfad, kein Linken gegen den Fork. Weg b (`camera_ros`) nur, falls a sich als
   untauglich zeigt (Latenz/Stabilität) — braucht Bau gegen den `/usr/local`-libcamera-Fork.
3. **Paket-Ort:** `hexapod_camera` (eigenes Paket) **oder** Node in `hexapod_sensors` (dort leben
   `bno055_imu`/`foot_contact_publisher`). Empfehlung: **`hexapod_sensors`** (Kamera = Sensor, kein
   neues Paket-Gerüst). Alternative: eigenes Paket, falls die Kamera stärker wächst (RTSP etc.).
4. **`rpicam-vid` nur auf dem Pi** — in Sim/Desktop existiert es nicht. Der Node läuft **nur im
   real-Pfad** (Launch-Arg); der Sim-Pfad nutzt weiter die gz-Bridge. (Kein „log-only" nötig wie bei
   Audio, weil der Sim-Pfad die Kamera schon anders bedient.)
5. **framerate/Auflösung** als Params (Default 1280×720@15, wie Sim). Live justierbar; höher = mehr
   CPU/Bandbreite.
6. **`/usr/local`-libcamera im systemd-Kontext:** sicherstellen, dass der ROS-Launch die
   `ld.so.conf.d/rpicam.conf`-Lib findet (bei interaktiver Shell ok; bei systemd-Service ggf.
   Environment prüfen).

---

## 5. App-Seiten-Brief (self-contained)
- **In der Regel keine App-Änderung.** Die Video-View lädt weiter
  `http://<host>:8080/stream?topic=/camera/image_raw&type=mjpeg` und koppelt sie an
  `/hexapod/bringup_running` (Phase 4/§5 unverändert). Real-Modus = einfach die Pi-IP als Host.
- **Nur falls §4.1 es erzwingt** (web_video_server braucht das compressed-Topic explizit):
  Video-URL auf `topic=/camera/image_raw/compressed` umstellen (P7B.12). Wird beim Contract-Festzurren
  (P7B.8) final entschieden und dort dokumentiert.
- **`camera_enable`** kann die App optional als Toggle anbieten (Param `set_parameters` auf den
  Kamera-Node) — Strom/Wärme sparen. Sonst reicht das app-seitige URL-Laden/-Entladen (Phase 4).

## 6. Contract-Touchpoints (→ festzurren)
- **§5 (Video):** „Bildquelle real" präzisieren — OV5647 via `rpicam-vid` MJPEG → **`CompressedImage`**
  auf `/camera/image_raw/compressed`; URL bleibt (oder `+/compressed`, je nach §4.1-Verify).
- **§6:** `camera_enable` (Param/Service auf dem Kamera-Node) von `[TBD-Phase 7]` → **erledigt**.
- **Version-Bump** (v0.12, nach 7A v0.11).

## 7. Doku-Nachzug (nach Umsetzung)
- `phase_7b_camera_progress.md` + `phase_7b_camera_test_commands.md` (mit ▶ ROS / ▶ Pi / ▶ App-Tags).
- README des Ziel-Pakets (`hexapod_sensors` erweitern **oder** neues `hexapod_camera/README.md`):
  rpicam-Weg, JPEG-Framing, camera_enable, HW-Setup-Verweis auf `peripherals_tests`.
- `architecture.md` (Real-Kamera-Quelle) + `ai_navigation.md` („Kamera/Video ändern"-Eintrag ergänzen).

---

## 8. Implementierungs-Leitfaden (self-contained — für einen frischen Chat)

### Schritt 1 — Kamera-Node
- Ziel-Paket **`hexapod_sensors`** (empfohlen, §4.3): `hexapod_sensors/rpicam_node.py` = §1a–1b.
  entry_point in `setup.py` (`hexapod_camera = hexapod_sensors.rpicam_node:main`). Deps `rclpy`,
  `sensor_msgs`. `rpicam-vid` = **System-Binary** (`/usr/local/bin`, aus dem HW-Hello-World) → im
  README als Voraussetzung, **kein** rosdep-key.
- JPEG-Framing (§1a `_read_loop`) sauber: Rest-Puffer über `read`-Grenzen behalten; sehr große Frames
  nicht endlos puffern (Sanity-Cap).

### Schritt 2 — web_video_server real
- `web_video_server` liegt heute in `sim.launch.py` (Phase 4). Für real: entweder in den realen
  Bringup-Pfad ziehen **oder** ein gemeinsames `camera.launch.py` (Node + web_video_server),
  eingebunden aus sim- und real-Launch mit `enable_camera`/`camera_enable`-Arg.
- Muster = die bestehende conditional `web_video_server`-Einbindung in `sim.launch.py`
  (`IfCondition(LaunchConfiguration('enable_camera'))`).

### Schritt 3 — Tests
- `hexapod_sensors/test/test_rpicam_node.py`: (a) JPEG-Framing gegen einen Fixture-Bytestrom mit
  2–3 zusammengeklebten JPEGs (inkl. Split über `read`-Grenze); (b) `_publish` setzt `format='jpeg'`
  + `frame_id` + monotone stamps (gemockter `create_publisher`); (c) `camera_enable`-Toggle
  start/stop (gemockter `Popen`); (d) Subprozess-Exit → Cleanup. Muster = `test_foot_contact_node.py`
  / `test_sitdown_node.py` (rclpy-Fixture, Handler direkt).

### Schritt 4 — Pi-Verifikation (User, HW)
```bash
# ▶ Pi (ssh hexapod-pi), rpicam-Userland aus dem Hello-World vorausgesetzt:
ros2 run hexapod_sensors hexapod_camera            # oder via real-Launch
ros2 topic hz /camera/image_raw/compressed          # ~15 Hz
# ▶ Browser/App: http://<Pi-IP>:8080/stream?topic=/camera/image_raw&type=mjpeg
ros2 param set /hexapod_camera camera_enable false   # Stream stoppt
ros2 param set /hexapod_camera camera_enable true    # Stream kommt zurück
```

---

## 9. Design-Entscheidungen (mit Alternativen)

- **[D-Cam-1] Weg a: `rpicam-vid`-MJPEG-Subprozess → `CompressedImage`** (nicht `camera_ros`).
  **Warum:** nutzt den **bereits verifizierten** Hello-World-Pfad (`peripherals_tests`), **kein**
  Linken/Bauen gegen den `/usr/local`-libcamera-Fork, MJPEG ist ohnehin das Zielformat (web_video_server,
  Pi 5 kein H264). **Verworfen (v1):** `camera_ros` (libcamera→ROS2, „sauberer" ROS-nativ, aber
  Bau-/Link-Risiko auf Ubuntu 24.04 gegen den Fork) — als Weg b notiert, falls a nicht trägt.
- **[D-Cam-2] `CompressedImage` (JPEG) statt raw `Image`.** Der Node reicht die JPEGs **durch** (kein
  CPU-Decode); `web_video_server` streamt sie direkt als MJPEG. **Verworfen:** JPEG→raw dekodieren
  und `sensor_msgs/Image` publishen (unnötiger CPU-Decode auf dem Pi; nur nötig, falls ein
  raw-Consumer dazukommt).
- **[D-Cam-3] `camera_enable` = Subprozess-Start/Stop** (echter Aus-Schalter, Strom/Wärme). Ergänzt
  das app-seitige URL-Laden/-Entladen (Phase 4). **Verworfen:** Lifecycle-Node (mehr Zeremonie, kein
  Mehrwert v1) / immer-an (Sensor/ISP zieht dauerhaft Strom).
- **[D-Cam-4] Gleiches Topic `/camera/image_raw` wie Sim.** So bleiben `web_video_server` + App
  identisch (Contract §5). **Verworfen:** eigenes HW-Topic (würde App/Stream-Server-Umschaltung
  erzwingen — genau das, was §5 vermeidet).
- **[D-Cam-5] Node im real-Pfad, Sim unverändert.** `rpicam-vid` existiert nur am Pi; kein „log-only"
  nötig, weil der Sim-Pfad die Kamera schon über die gz-Bridge bedient.
