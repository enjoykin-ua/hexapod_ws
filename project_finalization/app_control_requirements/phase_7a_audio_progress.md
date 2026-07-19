# Phase 7A — Audio (`hexapod_audio`) — Progress (ROS-Seite)

> **Done-Vertrag** (CLAUDE.md §4). Bullets 1:1 aus
> [`phase_7a_audio_plan.md`](phase_7a_audio_plan.md) §3.
> Status: 🟢 **FINALISIERT (ROS-Seite Sim-verifiziert)** — hexapod_gait 477 + hexapod_audio 14
> (0 failures, Lint clean, Runtime-Smoke grün); Contract **v0.11.1** (mit rosbridge-Frames für die
> App). **Deferiert:** App-Buttons (P7A.10/11, Android-Session) + HW-Speaker (P7A.13, echte mp3s).

```
Phase 7A (Audio):
- [x] P7A.1 [ROS] gait_node: /hexapod/audio_cue-Publisher + _emit_audio_cue; Cues standup/sitdown/reposition/freeze; _on_recover feuert KEINEN (T7A.1 ✅)
- [x] P7A.2 [ROS] Freeze-Cue nur beim Übergang (in _trigger_safety_freeze); _on_estop-Reihenfolge gefixt (T7A.2 ✅)
- [x] P7A.3 [ROS] Neues Paket hexapod_audio: Node subscribt audio_cue + play_sound, spielt via mpg123 (T7A.3/T7A.4 ✅)
- [x] P7A.4 [ROS] sound_enable-Param (mutet NUR Auto-Cues) + latched /hexapod/sound_enabled + live-Toggle (T7A.7 ✅)
- [x] P7A.5 [ROS] Playback: neuer bricht alten ab; playback_enabled (Sim log-only); Robustheit (T7A.5/T7A.6/T7A.8 ✅)
- [x] P7A.6 [ROS] config/sound_map.yaml (cue/key->datei) + sounds/ mit 7 Platzhalter-mp3s (unterscheidbare Töne)
- [x] P7A.7 [ROS] Launch-Wiring: hexapod_audio im gait-Stack (gait.launch.py audio_enable/audio_playback; real=true via bringup_ondemand)
- [x] P7A.8 [ROS] Contract §3/§4/§6b festgezurrt (play_sound, sound_enabled, sound_enable, audio_cue intern), Version-Bump v0.11
- [x] P7A.9 [ROS] colcon test (477+14) + Lint gruen + gait-Regression (T7A.10 ✅)
- [ ] P7A.10 [App] 2 Buttons "Fahren mit/ohne Audio" (setzen sound_enable) + Zuschalt-Toggle + Mute-Anzeige aus /hexapod/sound_enabled   [Android-Session]
- [ ] P7A.11 [App] 3 Sound-Buttons -> /hexapod/play_sound "sound_01".."sound_03"   [Android-Session]
- [x] P7A.12 [ROS] Self-Review + Doku (README/architecture/ai_navigation, test_commands)
- [ ] P7A.13 [Integration, User+App/HW] Auto-Sounds bei Bewegung + manuelle Buttons hörbar am echten Speaker (T7A.9)   [User + App]
```

> **P7A.10/11** = **Android-Session** (hexapod_app-Repo) gegen Contract §6b. **P7A.13** = User (echter
> Speaker: mp3s liefern + hörbar verifizieren).

---

## Stand — ROS-Seite implementiert + statisch/unit verifiziert

**Fertig + verifiziert** (`colcon build` grün, `colcon test` **hexapod_gait 477/0/0/28** +
**hexapod_audio 14/0/0/1**, flake8 + pep257 clean; 20 neue Tests):

- **`hexapod_gait/gait_node.py`:** Publisher `/hexapod/audio_cue` + Helper `_emit_audio_cue`. Cues:
  `standup` (`_on_stand_up`), `sitdown` (`_start_sitdown_sequence`, beide Erfolgs-Pfade),
  `reposition` (`_on_cycle_stance`, nur echter Switch), `freeze` (`_trigger_safety_freeze`, **nur beim
  Übergang** not-frozen→frozen). `_on_recover` feuert **keinen** Cue → **Recovery-Aufstehen stumm**.
  `_on_estop` setzt `_safety_frozen` nicht mehr direkt (läuft über `_trigger_safety_freeze` → Cue-Guard
  greift).
- **`hexapod_audio`** (neues Paket): Node subscribt `/hexapod/audio_cue` (Auto, mutbar) +
  `/hexapod/play_sound` (manuell, immer), spielt via `mpg123`-Subprozess (`plughw:0,0`, neuer bricht
  alten ab). Param `sound_enable` (mutet NUR Auto) + latched `/hexapod/sound_enabled` (Bool). Param
  `playback_enabled` (real=true, sim=false log-only), `sound_dir`/`sound_map_file`/`alsa_device`.
  `config/sound_map.yaml` (7 Keys) + `sounds/` (7 Platzhalter-mp3s, unterscheidbare Töne, User ersetzt
  sie später gleichnamig).
- **Launch:** `gait.launch.py` startet `hexapod_audio` mit (Args `audio_enable`=true,
  `audio_playback`=false); `bringup_ondemand mode:=real` reicht `audio_playback:=true` durch.
- **Tests:** `test_audio_cue.py` (9, gait-Cues + Recovery-stumm + Freeze-Übergang) +
  `test_audio_node.py` (11, Mute-Logik, neuer-bricht-alten, Robustheit, Sim-log, latched Status).
- **Runtime-Smoke (log-only, grün):** Node startet real, lädt `sound_map.yaml` aus dem Paket-share
  (7 keys), Auto-Cue `freeze` → `sound_freeze.mp3`, manueller `sound_01` → `sound_01.mp3` (je
  „[dry-run] wuerde abspielen"). **Deckte einen realen Bug auf:** fehlende `setup.cfg` (console_script
  landete nicht in `lib/hexapod_audio/` → `ros2 run: No executable found`) → **behoben**. Die
  Unit-Tests fanden das nicht (sie importieren das Paket, statt das executable zu starten).

**Doku:** Contract **v0.11** (§3/§4/§6b); `hexapod_audio/README.md`; `architecture.md`;
`ai_navigation.md` („Audio/Sounds ändern"); `phase_7a_audio_test_commands.md`.

> ⚠️ **Bekannte Test-Flakiness (nicht Code):** `colcon test hexapod_gait` zeigte einmalig einen
> rclpy-**Teardown-Segfault** (viele GaitNode-Module × rclpy.init/shutdown im selben Prozess). In
> 3 Folgeläufen + Paket-Root-pytest **nicht reproduzierbar** (477 grün). Bekanntes ROS2-Muster,
> kein Produktcode-Bug; bei Bedarf später ein session-scoped `conftest.py` (rclpy einmal init).

**Offen:** App-Shell **P7A.10/11** (Android-Session gegen §6b) · **P7A.13** = User (echte mp3s +
Speaker-Verifikation).

---

## Self-Review (P7A.12)

| # | Punkt | Status |
|---|---|---|
| 1 | Freeze-Cue nur beim Übergang (`not _safety_frozen`) → kein Doppel-Sound bei latched Freeze; Tip-CRIT/Slip/IK-joint-limit/E-Stop laufen alle durch den einen Guard | OK (T7A.2) |
| 2 | `_on_estop` setzt `_safety_frozen` nicht mehr direkt → Verhalten identisch, Cue feuert genau einmal | OK (T7A.2/Phase-6-Regression grün) |
| 3 | `standup`-Cue **nur** bei `_on_stand_up` (Y-Taste/App) — Boot-Auto-Standup + Recovery **stumm** (präziser als Plan) | OK (T7A.1) |
| 4 | `reposition`-Cue nur bei echtem User-Stance-Switch; interner `_do_stance_switch` (Hinsetzen-aus-hoch) feuert **keinen** | OK (T7A.1) |
| 5 | Auto-Sounds mutbar (inkl. Freeze, RA1); manuelle `play_sound` immer | OK (T7A.3/4) |
| 6 | Neuer Sound bricht laufenden ab; Robustheit (unbekannter Key / fehlende Datei / kein mpg123) → kein Crash | OK (T7A.5/6) |
| 7 | Sim log-only (`playback_enabled=false`) → kein Subprozess; Sim-testbar via Cues + „would play"-Log | OK (T7A.8) |
| 8 | latched `/hexapod/sound_enabled` (transient_local+reliable) + re-publish bei Toggle | OK (T7A.7) |
| 9 | `sitdown`-Cue feuert bei **jedem** Hinsetzen (sit_down, Shutdown, Comms-Loss) — bewusst „beim Hinsetzen" | 🟡 v1 bewusst (falls Shutdown stumm gewünscht → dort ausnehmen) |
| 10 | `sitdown`-Cue im „aus hoch"-Pfad feuert beim **Intent-Start** (vor dem eigentlichen Absenken nach dem Switch) | 🟡 v1 bewusst (kurze mp3, „beim Hinsetzen" = Vorgangsbeginn) |
| 11 | `hexapod_audio` läuft auch bei direkten Sim-Läufen (ramp_walk etc.) mit — log-only, harmlos; `audio_enable:=false` schaltet ihn weg | 🟡 v1 bewusst |
| 12 | mp3s im Paket (git-versioniert, User-Wunsch); Tausch braucht `colcon build` (oder `--symlink-install`) | OK (im README dokumentiert) |
| 13 | `colcon build` + 477+14 Tests + flake8 + pep257 grün; keine gait-Regression | OK |
| 14 | rclpy-Teardown-Segfault (Test-Infra) — 3× stabil nachverifiziert | 🟡 vormerken (session-conftest bei Wiederauftreten) |
| 15 | HW-Wiedergabe hörbar (echte mp3s, Speaker) | 🟢 T7A.13 (User + App) |

**Keine 🔴.** Die 🟡 sind bewusste v1-Grenzen bzw. der HW-/App-Nachweis (T7A.13 = User), die 🟢 der
Pflicht-HW-Smoke. Keine Fixe nötig vor der Fertig-Meldung.

---

## Design-Entscheidungen (mit Alternativen)

Siehe [`phase_7a_audio_plan.md`](phase_7a_audio_plan.md) §9 ([D-Audio-1..6]). Kern: **explizite
Audio-Cues vom gait_node** (statt status-basiert → Recovery-stumm trivial + keine REPOSITION-
Mehrdeutigkeit); `play_sound` als String-Topic (kein Custom-msg); neuer bricht alten ab; mp3s im
Paket; `sound_enable` mutet nur Auto-Sounds; `playback_enabled` per Launch-Arg (real/sim).
