# Phase 7B — Echte Raspi-Cam am Roboter — Plan (finalisiert)

> **Ziel:** die **echte Raspberry-Pi-Kamera v1.3 (OV5647)** am Pi publisht **`/camera/image_raw`**
> (als `CompressedImage`/JPEG) — dasselbe Topic, das in der Sim der Gazebo-Kamera-Sensor liefert (dort
> roh). Der bestehende **`web_video_server` (:8080)** streamt es; die App wählt den Stream-`type` je
> Host (**Variante A**). Dazu ein **`camera_enable`**-Schalter (Kamera-Node an/aus, Strom/Wärme) und
> ein **`source:=rpicam|test`**-Param, der die Kette schon **am Desktop** verifizierbar macht.
>
> **Seite:** primär ROS (Pi), minimale App-Justierung (URL-`type` je Host). **Status: 🟢 ROS-Seite
> umgesetzt + Desktop-E2E verifiziert** (Contract v0.12; Progress:
> [`phase_7b_camera_progress.md`](phase_7b_camera_progress.md)). Offen: Pi-HW + App-URL.
> Contract: [`interface_contract.md`](interface_contract.md) (§5 Video, §6, festgezurrt v0.12).
> HW-Hello-World (verifiziert): [`../peripherals_tests/camera_ov5647_v13.md`](../peripherals_tests/camera_ov5647_v13.md).

---

## 0. Ziel + Abgrenzung

**Bestand (schon da):**
- **Kamera-HW verifiziert** (`peripherals_tests/camera_ov5647_v13.md`): OV5647 (5 MP, CSI) am Pi 5,
  Userland = Pi-Fork `libcamera` + `rpicam-apps` (Build `~/camera_build/`, `/usr/local`). **MJPEG**
  (Pi 5 hat **keinen** HW-H264). `rpicam-vid --codec mjpeg` verifiziert.
- **Sim-Video-Pipeline** (Phase 4, existiert, **bleibt unverändert**): gz-Kamera-Sensor
  (`hexapod.camera.xacro`, Topic `/camera/sim`) → `ros_gz_bridge` (`bridge_camera.yaml`) →
  **`/camera/image_raw`** (`sensor_msgs/Image`, **roh**) → **`web_video_server` :8080** (nur im
  `sim.launch.py`), URL `…&type=mjpeg`.
- **web_video_server kann CompressedImage** (Recherche): `RosCompressedStreamer` → URL
  `…&type=ros_compressed` subscribt das `CompressedImage`-Topic und **reicht die JPEGs durch**
  (kein Decode/Re-Encode auf dem Pi). ([RobotWebTools/web_video_server](https://github.com/RobotWebTools/web_video_server/blob/develop/src/ros_compressed_streamer.cpp))

**Neu in Phase 7B:**
1. **Kamera-Node** in **`hexapod_sensors`** (F3): liest die OV5647 via **`rpicam-vid --codec mjpeg`**
   (Subprozess, [D-Cam-1] Weg a) und publisht die JPEG-Frames als **`sensor_msgs/CompressedImage`**
   auf **`/camera/image_raw/compressed`** (`format: "jpeg"`). **`source:=rpicam|test`** (F2): `test`
   publisht statt dessen ein **synthetisches JPEG** → die Kette ist **am Desktop** testbar.
2. **`web_video_server` im real-Pfad** (bisher nur sim) → :8080 auch auf HW.
3. **`camera_enable`** (F4) — Param, der den `rpicam-vid`-Subprozess **startet/stoppt** (Strom/Wärme).
4. **App-URL Variante A** (F1): App wählt den Stream-`type` je Host — **Sim `…&type=mjpeg`** (roh),
   **HW `…&type=ros_compressed`** (JPEG durchgereicht). Effizientest, Sim-Pipeline unverändert.

**Bewusst NICHT in Phase 7B:**
- **H264/WebRTC** (MJPEG v1, Pi 5 kein HW-H264); **On-Sensor-AI** (OV5647 hat keine NPU);
  **Auflösungs-/Belichtungs-Feintuning** (IPA-Automatik reicht v1); **`camera_ros`-Weg** (Weg b,
  optionale Evaluation falls a nicht trägt); **Audio** (Phase 7A).

---

## 1. Logik-Skizze / Pseudocode

### 1a. Kamera-Node (`hexapod_sensors/rpicam_node.py`)
```python
class RpicamNode(Node):
    def __init__(self):
        super().__init__('hexapod_camera')
        self._source  = declare('source', 'rpicam')      # 'rpicam' | 'test'
        self._w       = declare('width', 1280)
        self._h       = declare('height', 720)
        self._fps     = declare('framerate', 15)
        self._frame_id = declare('frame_id', 'camera_link')
        self._enabled = declare('camera_enable', True)
        self._pub = self.create_publisher(
            CompressedImage, '/camera/image_raw/compressed', 10)
        self._proc = None
        self._reader = None
        self._test_jpeg = None
        self.add_on_set_parameters_callback(self._on_param)   # camera_enable live
        if self._enabled:
            self._start()

    def _start(self):
        if self._source == 'test':
            self._test_jpeg = _load_test_jpeg()               # statisches JPEG aus dem Paket
            self._timer = self.create_timer(1.0/self._fps, self._publish_test)
        else:
            self._start_rpicam()

    # --- rpicam-Quelle (HW) ---
    def _start_rpicam(self):
        cmd = ['rpicam-vid', '-t', '0', '-n', '--codec', 'mjpeg',
               '--framerate', str(self._fps), '--width', str(self._w),
               '--height', str(self._h), '--inline', '-o', '-']
        self._proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, bufsize=0)
        self._reader = Thread(target=self._read_loop, daemon=True)
        self._reader.start()

    def _read_loop(self):
        buf = b''
        while rclpy.ok() and self._proc and self._proc.poll() is None:
            chunk = self._proc.stdout.read(4096)
            if not chunk:
                break
            buf += chunk
            buf = self._emit_complete_jpegs(buf)     # FFD8..FFD9 herausschneiden

    def _emit_complete_jpegs(self, buf: bytes) -> bytes:
        while True:
            soi = buf.find(b'\xff\xd8')
            eoi = buf.find(b'\xff\xd9', soi + 2) if soi >= 0 else -1
            if soi < 0 or eoi < 0:
                break
            self._publish(buf[soi:eoi + 2])
            buf = buf[eoi + 2:]
        return buf                                    # Rest-Puffer behalten

    # --- test-Quelle (Desktop) ---
    def _publish_test(self):
        self._publish(self._test_jpeg)                # gleiches JPEG, frischer stamp

    def _publish(self, jpeg: bytes):
        msg = CompressedImage()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = self._frame_id
        msg.format = 'jpeg'
        msg.data = jpeg
        self._pub.publish(msg)
```

### 1b. `camera_enable` (Strom/Wärme, [D-Cam-3])
```python
    def _on_param(self, params):
        for p in params:
            if p.name == 'camera_enable':
                if p.value and not self._enabled:
                    self._start()
                elif not p.value and self._enabled:
                    self._stop()
                self._enabled = bool(p.value)
        return SetParametersResult(successful=True)

    def _stop(self):
        if self._proc and self._proc.poll() is None:
            self._proc.terminate()                    # rpicam-vid runter → Sensor/ISP idle
        self._proc = None
        # test-Modus: Timer canceln
```
> `camera_enable=false` → Subprozess (bzw. test-Timer) aus. Ergänzt das app-seitige URL-Laden/-Entladen
> (Phase 4). Der echte Node-seitige Aus-Schalter.

### 1c. Stream-Weg + App-URL (Variante A, [D-Cam-6])
| Modus | Bildquelle | `/camera/image_raw` | web_video_server-URL |
|---|---|---|---|
| **Sim** | gz-Kamera → Bridge | roh (`sensor_msgs/Image`) | `…?topic=/camera/image_raw&type=mjpeg` |
| **HW** | OV5647 (`rpicam-vid`) | compressed (`/…/compressed`) | `…?topic=/camera/image_raw&type=ros_compressed` |
| **Desktop-Test** | `source:=test` (synth. JPEG) | compressed | `…?topic=/camera/image_raw&type=ros_compressed` |

`web_video_server` läuft in **beiden** Pfaden (Sim: schon da; real/test: neu). Die App **wählt den
`type` je Host** (Sim-IP → `mjpeg`, Pi-IP → `ros_compressed`) — sie kennt den Host ohnehin (§5).

### 1d. Warum `source:=test` (F2, [D-Cam-7])
`rpicam-vid` gibt es nur am Pi → ohne `test`-Modus wäre die Kette **Node → CompressedImage →
web_video_server → Bild** erst am Pi verifizierbar. Mit `source:=test` publisht der Node ein
statisches Test-JPEG (im Paket, `assets/test_pattern.jpg`) in der `framerate`-Loop → **am Desktop**
lässt sich der `ros_compressed`-Stream im Browser prüfen (genau der frühere §4.1-Risikopunkt). Am Pi
nur `source:=rpicam`.

---

## 2. Tests-Liste (+ was NICHT)

| Test | Prüft | Wo | Warum |
|---|---|---|---|
| **T7B.1** JPEG-Framing: aus einem MJPEG-Bytestrom (Fixture, 2–3 zusammengeklebte JPEGs, inkl. Split über `read`-Grenze) werden vollständige JPEGs korrekt geschnitten | Unit | Kern-Parsing (`_emit_complete_jpegs`) |
| **T7B.2** `_publish` setzt `CompressedImage` (`format:"jpeg"`, `frame_id`, monotone stamps) | Unit | web_video_server-Kontrakt |
| **T7B.3** `camera_enable` false→`_stop` (Subprozess/Timer aus), true→`_start` | Unit (gemockt) | An/Aus |
| **T7B.4** `source:=test` publisht das Test-JPEG je Tick; fehlendes `rpicam-vid`/Subprozess-Exit → kein Crash, Cleanup | Unit | Robustheit + test-Modus |
| **T7B.5** **Desktop-E2E:** Node `source:=test` → `web_video_server` `type=ros_compressed` → **Bild im Browser** | **Sim/Desktop** | de-riskt den `ros_compressed`-Weg **ohne Pi** |
| **T7B.6 (HW, User)** `rpicam-vid`-Node am Pi, `ros2 topic hz /camera/image_raw/compressed` ~ FPS | HW | echter Publisher |
| **T7B.7 (HW, User)** `web_video_server` :8080 → Bild im Browser **und** in der App (`type=ros_compressed`) | HW | Kern-Deliverable |
| **T7B.8 (HW, User)** `camera_enable` false/true → Stream stoppt/kommt zurück; Strom/Wärme plausibel | HW | camera_enable |
| **T7B.9** `colcon test` + Lint grün; Sim-Cam (Phase 4) unverändert | Unit/Sim | keine Regression |

**Bewusst offen/später:** H264/RTSP/WebRTC; Latenz-/Bitraten-/Auflösungs-Tuning (live); `camera_ros`
(Weg b); IPA/Belichtung; Mehrkamera.

---

## 3. Progress-Checkliste (→ `phase_7b_camera_progress.md`, Done-Vertrag)
```
Phase 7B (Echte Raspi-Cam):
- [ ] P7B.1 [ROS] hexapod_sensors: RpicamNode (source rpicam|test) -> CompressedImage auf /camera/image_raw/compressed (T7B.1/T7B.2)
- [ ] P7B.2 [ROS] JPEG-Framing (FFD8..FFD9, Rest-Puffer, Sanity-Cap) + monotone stamps + frame_id=camera_link
- [ ] P7B.3 [ROS] source:=test (synth. JPEG in framerate-Loop) + assets/test_pattern.jpg (T7B.4)
- [ ] P7B.4 [ROS] camera_enable-Param: Subprozess/Timer start/stop live (T7B.3)
- [ ] P7B.5 [ROS] Robustheit: rpicam fehlt / Subprozess-Exit -> kein Crash, Cleanup (T7B.4)
- [ ] P7B.6 [ROS] web_video_server im real-Pfad (conditional) + gemeinsames camera-Launch (source/camera_enable/port)
- [ ] P7B.7 [ROS] Unit-Tests + Lint gruen; Sim-Cam (Phase 4) unveraendert (T7B.9)
- [ ] P7B.8 [ROS/Desktop] Desktop-E2E: source:=test -> web_video_server type=ros_compressed -> Bild im Browser (T7B.5)
- [ ] P7B.9 [ROS] Contract §5/§6 festgezurrt (Real=CompressedImage, App-URL Variante A, camera_enable, source), Version-Bump v0.12
- [ ] P7B.10 [ROS] Self-Review + Doku (README/architecture/ai_navigation, test_commands)
- [ ] P7B.11 [Pi-Verify, User] rpicam-Node am Pi: /camera/image_raw/compressed ~FPS (T7B.6)
- [ ] P7B.12 [Integration, User+App] web_video_server :8080 -> Bild in Browser + App (type=ros_compressed); camera_enable an/aus (T7B.7/T7B.8)
- [ ] P7B.13 [App] Video-URL: type je Host (Sim mjpeg / HW ros_compressed)   [Android-Session]
```

---

## 4. Offene Punkte / Risiken
1. **`ros_compressed` am Pi mit echtem `rpicam`-Frame-Rate** — der Desktop-E2E (T7B.5) verifiziert den
   Weg; am Pi ist noch die reale FPS/Latenz zu bestätigen (T7B.6/7). Fallback, falls `ros_compressed`
   unerwartet zickt: `type=mjpeg&default_transport=compressed` (dekodiert+re-encodiert, CPU) — nur
   Notnagel.
2. **`/usr/local`-libcamera im Launch-Kontext:** bei interaktiver Shell ok; falls der Node je über
   systemd läuft, `ld.so.conf.d/rpicam.conf`/Environment gegenchecken (aktuell startet der Stack
   on-demand aus der App, nicht systemd).
3. **framerate/Auflösung** als Params (Default 1280×720@15, wie Sim). Live justierbar.
4. **Test-JPEG-Größe:** ein kleines, klar erkennbares Muster (z.B. Farbbalken + Text „TEST") reicht;
   generiert einmalig mit `ffmpeg`, als `assets/test_pattern.jpg` eingecheckt.

---

## 5. App-Seiten-Brief (self-contained)
- **Video-View lädt weiter** `http://<host>:8080/stream?topic=/camera/image_raw&type=<T>` und koppelt
  an `/hexapod/bringup_running` (Phase 4/§5 unverändert). **Neu (Variante A):** `<T>` hängt vom Host ab
  — **Sim-Host (Desktop-IP) → `mjpeg`**, **HW-Host (Pi-IP) → `ros_compressed`**. Die App kennt den Host
  (Verbinden-Screen) → ein `if` je Modus, kein weiterer Logik-Change.
- **`camera_enable`** kann die App optional als Toggle anbieten (`set_parameters` auf `/hexapod_camera`,
  Muster wie `sound_enable` §6b) — Strom/Wärme sparen. Sonst reicht das app-seitige URL-Laden/-Entladen.
- **Bewusst NICHT:** H264/WebRTC, Aufnahme, Foto-Snapshot.

## 6. Contract-Touchpoints (→ festzurren, v0.12)
- **§5 (Video):** „Bildquelle real" präzisieren — OV5647 via `rpicam-vid` MJPEG → **`CompressedImage`**
  auf `/camera/image_raw/compressed`; **App-URL-`type` je Host** (Sim `mjpeg` / HW `ros_compressed`,
  Variante A). Der `web_video_server` läuft real wie in Sim (:8080).
- **§6:** `camera_enable` (Param auf `/hexapod_camera`) + `source` (`rpicam|test`) — von `[TBD-Phase 7]`
  → **erledigt**.
- **Version-Bump v0.12.**

## 7. Doku-Nachzug (nach Umsetzung)
- `phase_7b_camera_progress.md` + `phase_7b_camera_test_commands.md` (▶ ROS / ▶ Pi / ▶ App-Tags,
  inkl. Desktop-E2E-Befehle für source:=test).
- `hexapod_sensors/README.md` erweitern (rpicam-Node, source-Modi, JPEG-Framing, camera_enable,
  HW-Setup-Verweis auf `peripherals_tests`).
- `architecture.md` (Real-Kamera-Quelle + web_video_server real) + `ai_navigation.md`
  („Kamera/Video ändern"-Eintrag).

---

## 8. Implementierungs-Leitfaden (self-contained — für einen frischen Chat)

### Schritt 1 — Kamera-Node
- `hexapod_sensors/hexapod_sensors/rpicam_node.py` = §1a/1b. entry_point in `setup.py`
  (`hexapod_camera = hexapod_sensors.rpicam_node:main`). Deps: `rclpy`, `sensor_msgs`. `rpicam-vid` =
  **System-Binary** (`/usr/local/bin`) → README-Voraussetzung, **kein** rosdep-key (wie `mpg123`/`smbus2`).
- JPEG-Framing sauber (Rest-Puffer über `read`-Grenzen; Sanity-Cap gegen unbegrenztes Puffern).
- Test-JPEG: `assets/test_pattern.jpg` im Paket, via `data_files` installiert; Pfad über
  `get_package_share_directory`.
- **⚠️ `setup.cfg` nicht vergessen** (`script_dir=$base/lib/hexapod_sensors`) — sonst findet `ros2 run`
  das Executable nicht (Lehre aus 7A). `hexapod_sensors` hat schon eine → nur Node ergänzen.

### Schritt 2 — web_video_server real + gemeinsames Launch
- Ein `camera.launch.py` (in `hexapod_bringup`) startet **conditional** (`camera_enable`/`enable_camera`)
  den `hexapod_camera`-Node (`source`, `framerate`, `width`, `height`) + `web_video_server` (:8080,
  0.0.0.0). Vom real-Pfad (`bringup_ondemand mode:=real`) inkludiert (`source:=rpicam`); der Sim-Pfad
  behält seinen bestehenden `web_video_server` (raw). Muster = die bestehende conditional
  `web_video_server`-Einbindung in `sim.launch.py` (`IfCondition`).

### Schritt 3 — Tests
- `hexapod_sensors/test/test_rpicam_node.py`: (a) `_emit_complete_jpegs` gegen Fixture-Bytes (2–3
  JPEGs + Split über Grenze); (b) `_publish` → `format='jpeg'`/`frame_id`/stamps; (c) `camera_enable`
  start/stop (gemockt); (d) `source:=test` publisht je Tick; Subprozess-Exit → Cleanup. Muster =
  `test_foot_contact_node.py` (rclpy-Fixture, Handler direkt); für den test-Timer ggf. `_publish_test`
  direkt aufrufen statt echten Timer.

### Schritt 4 — Desktop-E2E (T7B.5, ▶ ROS)
```bash
ros2 run hexapod_sensors hexapod_camera --ros-args -p source:=test &
ros2 run web_video_server web_video_server --ros-args -p port:=8080 -p address:=0.0.0.0 &
# Browser: http://localhost:8080/stream?topic=/camera/image_raw&type=ros_compressed  -> Test-Bild
ros2 topic hz /camera/image_raw/compressed    # ~15 Hz
```

### Schritt 5 — Pi-Verifikation (T7B.6/7/8, ▶ Pi/App, User)
```bash
# rpicam-Userland aus dem Hello-World vorausgesetzt (peripherals_tests/camera_ov5647_v13.md):
ros2 run hexapod_sensors hexapod_camera            # source:=rpicam (Default)
ros2 topic hz /camera/image_raw/compressed          # ~15 Hz
# App/Browser: http://<Pi-IP>:8080/stream?topic=/camera/image_raw&type=ros_compressed
ros2 param set /hexapod_camera camera_enable false   # Stream stoppt
ros2 param set /hexapod_camera camera_enable true    # kommt zurück
```

---

## 9. Design-Entscheidungen (mit Alternativen)

- **[D-Cam-1] Weg a: `rpicam-vid`-MJPEG-Subprozess → `CompressedImage`** (nicht `camera_ros`). Nutzt
  den verifizierten Hello-World-Pfad, kein Linken gegen den `/usr/local`-libcamera-Fork, MJPEG ist das
  Zielformat. **Verworfen (v1):** `camera_ros` (Bau-/Link-Risiko auf Ubuntu 24.04) — Weg b, falls a
  nicht trägt. *(F1-bestätigt: „wir probieren a".)*
- **[D-Cam-2] `CompressedImage` (JPEG) durchreichen** statt raw `Image` — kein CPU-Decode auf dem Pi;
  `web_video_server` `ros_compressed` reicht die JPEGs durch. **Verworfen:** raw publishen (Decode auf
  dem Pi, nur nötig für einen raw-Consumer).
- **[D-Cam-3] `camera_enable` = Subprozess-Start/Stop** (echter Aus-Schalter, Strom/Wärme). **Verworfen:**
  Lifecycle-Node (mehr Zeremonie) / immer-an. *(F4-bestätigt.)*
- **[D-Cam-4] Gleiches Topic-**Basis** `/camera/image_raw`** wie Sim → `web_video_server` + App-Grundgerüst
  identisch (Contract §5). **Verworfen:** eigenes HW-Topic.
- **[D-Cam-6] App-URL Variante A: `type` je Host** (Sim `mjpeg` / HW `ros_compressed`). **Effizientest**
  (kein Pi-Decode), Sim-Pipeline unverändert, App-Anpassung trivial (Host ist bekannt). **Verworfen:**
  (B) identische URL via `default_transport=compressed` → Pi dekodiert+re-encodiert (CPU); (C) identische
  URL via Sim-`republish raw→compressed` → ändert die funktionierende Phase-4-Sim-Pipeline. *(F1-Wahl.)*
- **[D-Cam-7] `source:=rpicam|test`** — `test` publisht ein synthetisches JPEG → die
  `CompressedImage → web_video_server → Bild`-Kette ist **am Desktop** verifizierbar (ohne Pi). Deckt
  „erst Sim testen, dann HW" auch für die HW-lastige Kamera ab. **Verworfen:** rein Pi-only (nichts am
  Desktop verifizierbar außer Unit-Tests). *(F2-bestätigt.)*
- **[D-Cam-8] Node in `hexapod_sensors`** (Kamera = Sensor-Input, neben `bno055_imu`/`foot_contact`).
  **Verworfen:** eigenes `hexapod_camera`-Paket (mehr Gerüst; erst sinnvoll, wenn die Kamera stark
  wächst — RTSP etc.). *(F3-bestätigt.)*
