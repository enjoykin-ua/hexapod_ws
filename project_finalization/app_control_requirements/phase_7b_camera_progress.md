# Phase 7B — Echte Raspi-Cam am Roboter — Progress (ROS-Seite)

> **Done-Vertrag** (CLAUDE.md §4). Bullets 1:1 aus
> [`phase_7b_camera_plan.md`](phase_7b_camera_plan.md) §3.
> Status: 🟢 **ROS-Seite implementiert + Desktop-E2E verifiziert** (hexapod_sensors 20 +
> hexapod_bringup 46, 0 failures; Lint clean); Contract **v0.12**. Pi-HW (P7B.11/12) +
> App-URL (P7B.13) offen.

```
Phase 7B (Echte Raspi-Cam):
- [x] P7B.1 [ROS] hexapod_sensors: RpicamNode (source rpicam|test) -> CompressedImage auf /camera/image_raw/compressed (T7B.1/T7B.2 ✅)
- [x] P7B.2 [ROS] JPEG-Framing (FFD8..FFD9, Rest-Puffer, Sanity-Cap) + monotone stamps + frame_id=camera_link
- [x] P7B.3 [ROS] source:=test (synth. JPEG in framerate-Loop) + assets/test_pattern.jpg (T7B.4 ✅)
- [x] P7B.4 [ROS] camera_enable-Param: Subprozess/Timer start/stop live (T7B.3 ✅)
- [x] P7B.5 [ROS] Robustheit: rpicam fehlt / Subprozess-Exit -> kein Crash, Cleanup (T7B.4 ✅)
- [x] P7B.6 [ROS] web_video_server im real-Pfad (camera.launch.py, via bringup_ondemand mode:=real)
- [x] P7B.7 [ROS] Unit-Tests + Lint gruen; Sim-Cam (Phase 4, sim.launch.py) unveraendert (T7B.9 ✅)
- [x] P7B.8 [ROS/Desktop] Desktop-E2E: source:=test -> web_video_server type=ros_compressed -> Bild (T7B.5 ✅)
- [x] P7B.9 [ROS] Contract §5/§6 festgezurrt (Real=CompressedImage, App-URL Variante A, camera_enable, source), v0.12
- [x] P7B.10 [ROS] Self-Review + Doku (README/architecture/ai_navigation, test_commands)
- [ ] P7B.11 [Pi-Verify, User] rpicam-Node am Pi: /camera/image_raw/compressed ~FPS (T7B.6)
- [ ] P7B.12 [Integration, User+App] web_video_server :8080 -> Bild in Browser + App (type=ros_compressed); camera_enable an/aus (T7B.7/T7B.8)
- [ ] P7B.13 [App] Video-URL: type je Host (Sim mjpeg / HW ros_compressed)   [Android-Session]
```

> **P7B.11/12** = User (echter Pi + Kamera). **P7B.13** = Android-Session (§5 Variante A).

---

## Stand — ROS-Seite implementiert + Desktop-E2E verifiziert

**Fertig + verifiziert** (`colcon build` grün, `colcon test` **hexapod_sensors 20/0/0/1** +
**hexapod_bringup 46/0/0/0**, flake8/pep257/copyright clean; 10 neue Unit-Tests):

- **`hexapod_sensors/rpicam_node.py`** (Node `hexapod_camera`): publisht `CompressedImage` (`format:
  jpeg`, `frame_id: camera_link`) auf `/camera/image_raw/compressed`. **`source:=rpicam`** =
  `rpicam-vid --codec mjpeg -o -`-Subprozess → JPEG-Framing (FFD8…FFD9, Rest-Puffer, 4-MB-Sanity-Cap).
  **`source:=test`** = statisches `assets/test_pattern.jpg` in der `framerate`-Loop. **`camera_enable`**
  (Param) startet/stoppt die Quelle live. Robust: fehlt `rpicam-vid` → einmal ERROR, kein Crash.
- **`hexapod_bringup/launch/camera.launch.py`** (neu): `hexapod_camera` + `web_video_server` (:8080),
  conditional `enable_camera`, Arg `source`/`framerate`/`width`/`height`/`port`. Vom real-Pfad
  (`bringup_ondemand mode:=real`) inkludiert (`source:=rpicam`). **Sim unverändert** (gz-Bridge +
  web_video_server bleiben in `sim.launch.py`).
- **`assets/test_pattern.jpg`** (SMPTE-Farbbalken, 1280×720, git-versioniert) + `setup.py`-data_files.
- **Tests:** `test_rpicam_node.py` (JPEG-Framing inkl. Split-über-read-Grenze, Publish-Kontrakt,
  source=test, camera_enable, Robustheit).

**Desktop-E2E (T7B.5) — ✅ verifiziert (der frühere §4.1-Risikopunkt, ohne Pi):**
`hexapod_camera source:=test` → `/camera/image_raw/compressed` **~15,0 Hz** → `web_video_server`
→ `curl …&type=ros_compressed` lieferte einen validen **`multipart/x-mixed-replace`-MJPEG-Stream**:
60 JPEG-Frames in ~4 s (= 15 fps), erstes Frame **10434 Bytes = exakt `test_pattern.jpg`**
(`Content-type: image/jpeg` + `Content-Length: 10434` je Part). Der `ros_compressed`-Weg reicht die
JPEGs **durch** (kein Pi-Decode) — genau wie geplant.

**Doku:** Contract **v0.12** (§5/§6); `hexapod_sensors/README.md`; `architecture.md`;
`ai_navigation.md`; `phase_7b_camera_test_commands.md`.

**Offen:** **Pi-HW** (echte OV5647: `source:=rpicam`, reale FPS/Latenz, `camera_enable`-Strom/Wärme,
T7B.6–8) + **App-URL** (P7B.13, Android: `type` je Host).

---

## Self-Review (P7B.10)

| # | Punkt | Status |
|---|---|---|
| 1 | JPEG-Framing FFD8..FFD9 korrekt (Byte-Stuffing FF00 / Restart-Marker → FFD9 nur echtes EOI); Frame wird beim eigenen EOI emittiert (keine Extra-Latenz) | OK (T7B.1 + E2E: 60 valide Frames) |
| 2 | Sanity-Cap (4 MB ohne Frame → verworfen) gegen unbegrenztes Puffern bei korruptem Strom | OK |
| 3 | CompressedImage-Kontrakt (`format='jpeg'`, `frame_id`, monotone stamps) → web_video_server akzeptiert es | OK (T7B.2 + E2E) |
| 4 | `source:=test` → ganze Kette (CompressedImage → web_video_server → Bild) **am Desktop** verifiziert | OK (T7B.5 ✅) |
| 5 | `camera_enable` start/stop live; beim Stop terminiert der rpicam-Subprozess → reader-Thread endet bei EOF | OK (T7B.3) |
| 6 | Robustheit: kein `rpicam-vid` → ERROR+kein Crash; Subprozess-Exit → Thread-break | OK (T7B.4) |
| 7 | Sim-Cam (Phase 4, `sim.launch.py`) **nicht angefasst** → keine Regression; real-Cam separat (`camera.launch.py`) | OK (T7B.9) |
| 8 | App-URL Variante A (Sim `mjpeg` / HW `ros_compressed`) → **kein Pi-Decode**; Contract §5 präzisiert | OK (E2E) |
| 9 | `setup.cfg` (script_dir) war schon da → `ros2 run hexapod_camera` funktioniert (Runtime-Smoke im E2E) | OK |
| 10 | Bei schnellem `camera_enable`-Toggle könnte der alte reader-Thread kurz mit dem neuen überlappen (1–2 Doppel-Frames) | 🟡 v1 unkritisch (seltener Toggle, harmlos für einen Stream) |
| 11 | `enable_camera` (Launch) = ganzer Video-Stack an/aus; `camera_enable` (Param) = nur rpicam-Subprozess (web_video_server läuft weiter) — zwei Ebenen | 🟡 bewusst (App entlädt zusätzlich die URL) |
| 12 | `/usr/local`-libcamera muss im Launch-Kontext gefunden werden (`ld.so.conf.d/rpicam.conf`) | 🟡 Pi-Verify (on-demand-Launch, nicht systemd) |
| 13 | reale FPS/Latenz + `camera_enable`-Strom/Wärme am echten Sensor | 🟢 T7B.6–8 (User, Pi) |
| 14 | `colcon build` + 20+46 Tests + Lint (flake8/pep257/copyright) grün | OK |

**Keine 🔴.** Die 🟡 sind bewusste v1-Grenzen / Pi-Beobachtungspunkte, die 🟢 der HW-Nachweis
(T7B.6–8 = User). Keine Fixe nötig vor der Fertig-Meldung.

---

## Design-Entscheidungen (mit Alternativen)

Siehe [`phase_7b_camera_plan.md`](phase_7b_camera_plan.md) §9 ([D-Cam-1..8]). Kern: **Weg a**
(rpicam-Subprozess → CompressedImage, kein Fork-Link) · **CompressedImage durchreichen** (kein
Pi-Decode) · **App-URL Variante A** (`type` je Host) · **`source:=test`** (Desktop-E2E ohne Pi) ·
Node in **`hexapod_sensors`** · `camera_enable` = Subprozess-Schalter.
