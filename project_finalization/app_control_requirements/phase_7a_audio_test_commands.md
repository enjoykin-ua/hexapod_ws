# Phase 7A — Test-Befehle: Audio (Sim log-only + HW)

> Du führst aus, knappe Status-Meldung zurück. **Kontext-Tags:** **▶ ROS** = Desktop-Terminal ·
> **▶ Pi** = auf dem Roboter (ssh) · **▶ App** = *echte App (Android-Session)*.
>
> **Ziel:** der `hexapod_audio`-Node spielt kurze mp3s auf dem Roboter-Speaker — **automatisch** bei
> Aufstehen/Hinsetzen/Höhenwechsel/Freeze (mutbar via `sound_enable`, **Recovery stumm**) und
> **manuell** über `/hexapod/play_sound` (immer). In Sim ohne Speaker läuft der Node **log-only**
> (Cues + „would play"-Logs sichtbar → testbar ohne Ton). Plan:
> [`phase_7a_audio_plan.md`](phase_7a_audio_plan.md) · Progress:
> [`phase_7a_audio_progress.md`](phase_7a_audio_progress.md).

---

## Unit-Tests (▶ ROS) — ohne Sim/HW
```bash
cd ~/hexapod_ws
source /opt/ros/jazzy/setup.bash && source ~/hexapod_ws/install/setup.bash
colcon build --packages-select hexapod_audio hexapod_gait
colcon test --packages-select hexapod_audio hexapod_gait
colcon test-result --test-result-base build/hexapod_audio
colcon test-result --test-result-base build/hexapod_gait
```
**✅ Erwartung:** hexapod_audio 14/0/0/1, hexapod_gait 477/0/0/28, Lint grün.

---

## Sim-Test (log-only — Cues + „would play", kein Ton)

**Terminal 1 (▶ ROS)** — Sim-Stack hoch (der Audio-Node läuft mit, `playback_enabled=false`):
```bash
source /opt/ros/jazzy/setup.bash && source ~/hexapod_ws/install/setup.bash
ros2 launch hexapod_bringup ramp_walk.launch.py auto_standup_on_start:=false
```
> `hexapod_audio` startet automatisch mit dem gait-Stack (log-only in Sim). Prüfen:
> `ros2 node list | grep hexapod_audio` → genau einer.

**Terminal 2 (▶ ROS)** — Cues + Audio-Logs mitlesen (laufen lassen):
```bash
source /opt/ros/jazzy/setup.bash && source ~/hexapod_ws/install/setup.bash
ros2 topic echo /hexapod/audio_cue
```

**Terminal 3 (▶ ROS)** — Bewegungen auslösen (nach ~12 s, wenn der Stack steht):
```bash
source /opt/ros/jazzy/setup.bash && source ~/hexapod_ws/install/setup.bash
ros2 service call /hexapod_stand_up std_srvs/srv/Trigger {}            # -> cue 'standup'
ros2 service call /hexapod_cycle_stance std_srvs/srv/SetBool "{data: true}"   # -> cue 'reposition'
ros2 service call /hexapod_sit_down std_srvs/srv/Trigger {}           # -> cue 'sitdown'
ros2 service call /hexapod_stand_up std_srvs/srv/Trigger {}           # wieder hoch (-> 'standup')
ros2 service call /hexapod_estop std_srvs/srv/Trigger {}              # -> cue 'freeze'
ros2 service call /hexapod_recover std_srvs/srv/Trigger {}            # KEIN cue (Recovery stumm)
```
**✅ Erwartung (T7A.1/T7A.2):** in Terminal 2 erscheinen die Cues `standup`/`reposition`/`sitdown`/
`standup`/`freeze` — **kein** Cue nach `recover`. Im Stack-Log (Terminal 1) je Cue eine Zeile
`[dry-run] wuerde abspielen: …/sound_*.mp3`.

**T7A.4 — manueller Sound (spielt immer):**
```bash
ros2 topic pub --once /hexapod/play_sound std_msgs/msg/String "{data: 'sound_01'}"
```
**✅ Erwartung:** Log `[dry-run] wuerde abspielen: …/sound_01.mp3`.

**T7A.3/T7A.7 — Mute nur der Auto-Sounds:**
```bash
ros2 param set /hexapod_audio sound_enable false
ros2 topic echo /hexapod/sound_enabled --qos-durability transient_local --once   # data: false
ros2 service call /hexapod_estop std_srvs/srv/Trigger {}     # Auto-Cue -> KEIN Log (gemutet)
ros2 topic pub --once /hexapod/play_sound std_msgs/msg/String "{data: 'sound_02'}"  # manuell -> spielt (Log)
ros2 param set /hexapod_audio sound_enable true              # wieder an
```
**✅ Erwartung:** bei `sound_enable=false` erzeugt der Freeze **kein** „would play"-Log; der manuelle
`sound_02` **schon**. `/hexapod/sound_enabled` folgt dem Param (false/true).

**T7A.6 — Robustheit (unbekannter Key):**
```bash
ros2 topic pub --once /hexapod/play_sound std_msgs/msg/String "{data: 'gibt_es_nicht'}"
```
**✅ Erwartung:** WARN `unbekannter sound key 'gibt_es_nicht'`, kein Crash (Node läuft weiter).

---

## HW-Test (▶ Pi / ▶ App, User) — echte Wiedergabe (T7A.13)

**Vorbereitung (▶ Pi):** echte mp3s ins Paket legen (gleiche Namen wie die Platzhalter) + bauen:
```bash
# echte mp3s nach src/hexapod_audio/sounds/ kopieren (sound_aufstehen.mp3, sound_hinsetzen.mp3,
# sound_repositioning.mp3, sound_freeze.mp3, sound_01.mp3, sound_02.mp3, sound_03.mp3), dann:
cd ~/hexapod_ws && colcon build --packages-select hexapod_audio
sudo apt install -y mpg123        # falls noch nicht da (peripherals_tests/audio_max98357a.md §5.3)
aplay -l                          # Karte 'snd_rpi_hifiberry_dac' (Karte N notieren, meist 0)
```
> Falls die Karte nicht 0 ist: `ros2 param set /hexapod_audio alsa_device plughw:N,0` (oder im Launch).

**Roboter-Stack (▶ Pi / über die App):** `bringup_start` (mode:=real) → der Audio-Node läuft mit
`playback_enabled=true`. Dann:
- **Auto-Sounds:** Aufstehen (Y/App) → `sound_aufstehen` hörbar · Höhenwechsel (L2/R2) →
  `sound_repositioning` · Hinsetzen → `sound_hinsetzen` · E-Stop → `sound_freeze`. Recover → **still**.
- **Manuell (▶ App):** die 3 Soundboard-Buttons → `sound_01..03` hörbar.
- **Mute (▶ App):** „Fahren ohne Audio" → Auto-Sounds still, Soundboard-Buttons weiter hörbar.

**✅ Erwartung:** klare, hörbare mp3s ohne Crash; Auto-Sounds folgen `sound_enable`; Recovery stumm.

---

## Was NICHT in Phase 7A (scope-out)
- App-Buttons (mit/ohne Audio, Zuschalt-Toggle, 3 Soundboard-Buttons) = **Android-Session** gegen §6b.
- Lautstärke-Regelung (feste Lautstärke), TTS, Sound-Mixing/Queue, Knarzen-Fix (HW).
- Reale mp3-Inhalte = User liefert nach (Platzhalter-Töne bis dahin).

## Melde-Vorlage
Unit 477+14 grün? · Sim: Cues standup/reposition/sitdown/freeze + recover-stumm? · manueller Sound
Log? · Mute nur Auto (Freeze still, sound_02 spielt)? · sound_enabled folgt Param? · unbekannter Key
kein Crash? · (HW) alle Sounds hörbar + Recovery still? Plus Auffälligkeiten.
