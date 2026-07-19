# hexapod_audio

Audio-Ausgabe für den Hexapod (Block I **Phase 7A**). Ein dünner ROS2-Node spielt kurze **mp3s auf
dem Roboter-Speaker** (MAX98357A, I2S). **Sound spielt nur auf dem Roboter, nie am Handy** ([D5]).

## Was der Node macht

`hexapod_audio` (Node `hexapod_audio`) abonniert zwei Topics und spielt mp3s via `mpg123`-Subprozess:

| Topic | Typ | Quelle | Verhalten |
|---|---|---|---|
| `/hexapod/audio_cue` | `std_msgs/String` | **gait_node** (Sequenz-Logik) | **Auto-Sounds** bei Bewegung: `standup`/`sitdown`/`reposition`/`freeze`. **Mutbar** via `sound_enable`. |
| `/hexapod/play_sound` | `std_msgs/String` | **App** (rosbridge) | **Manuelle Sounds** (`sound_01`/`02`/`03`). Spielen **immer** (auch bei `sound_enable=false`). |

Publiziert **`/hexapod/sound_enabled`** (`std_msgs/Bool`, latched) = aktueller Mute-Zustand für die
App-Anzeige. Ein neuer Sound **bricht den laufenden ab** (letzter Trigger gewinnt).

## Auto-Sounds — woher die Cues kommen

Die Bewegungs-Sounds werden **nicht** aus dem Status-Topic abgeleitet, sondern der `gait_node` feuert
an den Sequenz-Startpunkten einen expliziten Cue auf `/hexapod/audio_cue` ([D-Audio-1]):

| Cue | gait_node-Stelle | Auslöser |
|---|---|---|
| `standup` | `_on_stand_up` | Aufstehen vom Boden (Y-Taste / App-Button). **Boot-Auto-Standup + Recovery feuern KEINEN** → stumm. |
| `sitdown` | `_start_sitdown_sequence` | Hinsetzen (sit_down / Shutdown / Comms-Loss). |
| `reposition` | `_on_cycle_stance` | Höhenwechsel (Stance-Switch L2/R2). Interner Switch beim Hinsetzen feuert **keinen**. |
| `freeze` | `_trigger_safety_freeze` | Safety-Freeze / E-Stop / Tip-CRIT / Slip / IK-joint-limit — **nur beim Übergang** (nicht doppelt). |

**Warum explizite Cues statt status-basiert:** so ist „Recovery-Aufstehen stumm" trivial (Recovery
feuert keinen Cue), und die mehrdeutige `REPOSITION` (kommt beim Auf- UND Hinsetzen vor) triggert nie
fälschlich. D5-konform („die Sequenz-Logik triggert die Auto-Sounds").

## Parameter

| Param | Default | Zweck |
|---|---|---|
| `sound_enable` | `true` | Auto-Sounds an/aus (**mutet NUR die Cues**, nicht die manuellen `play_sound`). Live togglebar → re-publisht `/hexapod/sound_enabled`. |
| `playback_enabled` | `true` | `true` = echte Wiedergabe (`mpg123`); `false` = **log-only** (Sim/Dev ohne Speaker, kein ALSA/mpg123 nötig). Wird vom Launch gesetzt (real=true, sim=false). |
| `alsa_device` | `plughw:0,0` | ALSA-Device des MAX98357A. Robuster: `plughw:CARD=sndrpihifiberry`. |
| `sound_dir` | `<share>/sounds` | Ordner mit den mp3s. |
| `sound_map_file` | `<share>/config/sound_map.yaml` | Mapping Key → Dateiname. |

## Sounds austauschen (mp3s im Paket, git-versioniert)

Die mp3s liegen in **`sounds/`** und sind **in git** (User-Wunsch: SD-Karte kaputt → nur ROS aus git
einspielen, keine mp3s separat kopieren). Zum Ändern eines Sounds die mp3 **gleichen Namens** ersetzen
und `colcon build --packages-select hexapod_audio` (kopiert `sounds/` ins `install/`) — oder mit
`--symlink-install` bauen, dann ist der Tausch sofort wirksam. Das Mapping steht in
[`config/sound_map.yaml`](config/sound_map.yaml). Die aktuell eingecheckten mp3s sind **Platzhalter-
Töne** (verschiedene Frequenzen, damit im Test hörbar ist, welcher spielt).

## HW-Voraussetzung

`mpg123` als System-Binary (`sudo apt install mpg123`) + der MAX98357A als ALSA-Karte
`snd_rpi_hifiberry_dac` — Setup + Verifikation in
[`project_finalization/peripherals_tests/audio_max98357a.md`](../../project_finalization/peripherals_tests/audio_max98357a.md).
Fehlt `mpg123` → einmal WARN, kein Crash; in Sim (`playback_enabled=false`) wird beides nicht gebraucht.

## Launch

Startet automatisch mit dem gait-Stack (`hexapod_gait/launch/gait.launch.py`, Arg `audio_enable`
Default `true`). `audio_playback` steuert echte Wiedergabe (`bringup_ondemand mode:=real` setzt es auf
`true`; Sim-Läufe bleiben bei `false` = log-only). `audio_enable:=false` lässt den Node ganz weg.

## Tests

`test/test_audio_node.py` (Mute-Logik Auto vs. manuell, neuer-bricht-alten-ab, Robustheit bei
unbekanntem Key / fehlender Datei / fehlendem mpg123, Sim-log-only, latched Mute-Status). Die
Cue-Emit-Seite ist in `hexapod_gait/test/test_audio_cue.py`.

## Interface-Contract

App-Nähte festgezurrt in
[`interface_contract.md §6b`](../../project_finalization/app_control_requirements/interface_contract.md)
(v0.11).
