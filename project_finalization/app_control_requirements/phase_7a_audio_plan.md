# Phase 7A — Audio (`hexapod_audio`) — Plan

> **Ziel:** ein kleiner ROS2-Node auf dem Roboter spielt **kurze mp3s auf dem Roboter-Speaker**
> (MAX98357A) — **automatische** Sounds bei Bewegungs-Ereignissen (Aufstehen / Hinsetzen /
> Höhenwechsel / Freeze) **und** drei **manuelle** Sounds aus der App. Sound spielt **nur auf dem
> Hexapod**, nie auf dem Handy ([D5]).
>
> **Seite:** ROS + App. **Status: 🟡 Plan.** Self-contained für einen frischen Chat.
> Contract: [`interface_contract.md`](interface_contract.md) (§2/§3/§6, `[TBD-Phase 7]`).
> HW-Hello-World (verifiziert): [`../peripherals_tests/audio_max98357a.md`](../peripherals_tests/audio_max98357a.md).

---

## 0. Ziel + Abgrenzung

**Bestand (schon da):**
- **Audio-HW verifiziert** (`peripherals_tests/audio_max98357a.md`): MAX98357A I2S-Mono-Amp →
  ALSA-Karte `snd_rpi_hifiberry_dac` (card 0). MP3 hörbar via `mpg123 -a plughw:0,0 datei.mp3`.
  Feste Lautstärke (GAIN 9 dB, kein HW-Regler). Leichtes Knarzen = HW-Nachrüstung (Stützelko), kein
  Funktions-Blocker.
- **`gait_node`** kennt alle Bewegungs-Sequenzen (Aufstehen/Hinsetzen/Stance-Switch/Freeze) an
  definierten Stellen (Service-Handler + `_trigger_safety_freeze`).
- **`/hexapod/status`** (Phase 5) publisht `state` + `safety_frozen` — hier NICHT als Trigger genutzt
  (siehe [D-Audio-1]), aber als Kontext relevant.

**Neu in Phase 7A:**
1. **Audio-Cues im `gait_node`:** ein neuer Publisher `/hexapod/audio_cue` (`std_msgs/String`), der
   an den **Sequenz-Startpunkten** einen Cue-Namen feuert (`standup`/`sitdown`/`reposition`/`freeze`).
   `_on_recover` feuert **bewusst keinen** → **Recovery-Aufstehen ist stumm** (RA2).
2. **Neues Paket `hexapod_audio`** mit einem Node, der:
   - `/hexapod/audio_cue` abonniert → **Auto-Sound** (mutbar via `sound_enable`).
   - `/hexapod/play_sound` (`std_msgs/String`) abonniert → **manueller Sound** (spielt **immer**).
   - mp3s via `mpg123`-Subprozess spielt (neuer Sound bricht den alten ab).
   - `sound_enable`-Param (Mute **nur** der Auto-Sounds) + latched `/hexapod/sound_enabled` (Bool)
     für die App-Anzeige.

**Bewusst NICHT in Phase 7A:**
- **Lautstärke-Regelung** (Softvol/App-Slider) — feste Lautstärke (RA4). Später optional.
- **Sprachausgabe/TTS**, Sound-**Mixing** (Mono, genau **einer** zur Zeit), Sound-Queue.
- **Knarzen-Fix** (HW-Stützelko, `peripherals_tests` §8/§9).
- **Kamera** — Phase 7B.

---

## 1. Logik-Skizze / Pseudocode

### 1a. Audio-Cues im `gait_node` (Sequenz-Logik triggert, [D-Audio-1])
Neuer Publisher im `__init__` (bei den anderen Publishern) + Helper. Cue-Topic ist **nicht latched**
(Events, kein Zustand):
```python
# __init__:
self._audio_cue_pub = self.create_publisher(String, '/hexapod/audio_cue', 10)

def _emit_audio_cue(self, name: str) -> None:
    """Ein Bewegungs-/Freeze-Audio-Event feuern (fire-and-forget, Phase 7A)."""
    msg = String(); msg.data = name
    self._audio_cue_pub.publish(msg)
```
Emit-Punkte (jeweils NACH bestätigtem Erfolg der jeweiligen Aktion):

| Stelle (gait_node) | Cue | Bedingung |
|---|---|---|
| `_on_stand_up` (~2381) | `standup` | nach erfolgreichem `start_ramp`/`start_cartesian_standup` (response.success=True) |
| `_start_sitdown_sequence` (~2329) | `sitdown` | nach erfolgreichem Sequenz-Start (return True) |
| `_on_cycle_stance` (~2692) | `reposition` | nach erfolgreichem Stance-Switch-Start (response.success=True) |
| `_trigger_safety_freeze` (~1802) | `freeze` | **nur beim Übergang** `not _safety_frozen → frozen` (nicht wiederholt) |
| `_on_recover` (~2444) | — | **kein Cue** → Recovery-Aufstehen stumm (RA2) |

Freeze-Cue-Übergang (in `_trigger_safety_freeze`, damit `_on_estop`+Tip-CRIT+Slip+IK-joint-limit
alle über **einen** Pfad laufen):
```python
def _trigger_safety_freeze(self):
    if not self._safety_frozen:
        self._emit_audio_cue('freeze')   # nur beim Eintritt in den Freeze
    self._safety_frozen = True
    ...  # (Rest unverändert)
```
⚠️ `_on_estop` setzt heute `_safety_frozen=True` **vor** `_trigger_safety_freeze()` → der Guard oben
würde den Cue schlucken. **Fix:** in `_on_estop` das direkte `_safety_frozen=True` entfernen und den
Freeze allein über `_trigger_safety_freeze()` setzen lassen (das setzt es ohnehin). Verhalten sonst
identisch. Im Self-Review prüfen.

### 1b. `hexapod_audio`-Node
```python
class AudioNode(Node):
    def __init__(self):
        super().__init__('hexapod_audio')
        # Params
        self._sound_enable = declare('sound_enable', True)         # mutet NUR Auto-Cues
        self._sound_dir    = declare('sound_dir', <pkg_share>/sounds)
        self._alsa_device  = declare('alsa_device', 'plughw:0,0')
        self._playback     = declare('playback_enabled', True)     # HW=true, Sim=false (log-only)
        self._sound_map    = load_yaml(<pkg_share>/config/sound_map.yaml)  # cue/key -> dateiname
        self._proc = None  # aktueller mpg123-Popen

        self.create_subscription(String, '/hexapod/audio_cue',  self._on_cue,  10)
        self.create_subscription(String, '/hexapod/play_sound', self._on_play, 10)
        # latched Mute-Status für die App
        self._enabled_pub = create_pub('/hexapod/sound_enabled', Bool, latched)
        self._publish_enabled()
        self.add_on_set_parameters_callback(self._on_param)  # sound_enable live

    def _on_cue(self, msg):                       # AUTO-Sound (mutbar)
        if not self._sound_enable:
            return                                # gemutet → still
        self._play_key(msg.data)                  # 'standup'/'sitdown'/'reposition'/'freeze'

    def _on_play(self, msg):                      # MANUELLER Sound (immer)
        self._play_key(msg.data)                  # 'sound_01'/'sound_02'/'sound_03'

    def _play_key(self, key):
        fname = self._sound_map.get(key)
        if fname is None:
            self.get_logger().warn(f'unknown sound key {key!r}'); return
        self._play_file(os.path.join(self._sound_dir, fname))
```

### 1c. Playback (mpg123-Subprozess, neuer bricht alten ab, [D-Audio-3])
```python
    def _play_file(self, path):
        if not os.path.isfile(path):
            self.get_logger().warn(f'sound file missing: {path}'); return
        if not self._playback:                    # Sim/log-only
            self.get_logger().info(f'[dry-run] would play {path}'); return
        # neuer Sound bricht laufenden ab (RA/F5)
        if self._proc is not None and self._proc.poll() is None:
            self._proc.terminate()
        try:
            self._proc = subprocess.Popen(
                ['mpg123', '-q', '-a', self._alsa_device, path])
        except FileNotFoundError:
            self.get_logger().error('mpg123 not installed')  # einmal, dann still
```

### 1d. `sound_enable` live-Toggle + Mute-Status
```python
    def _on_param(self, params):
        for p in params:
            if p.name == 'sound_enable':
                self._sound_enable = bool(p.value)
        self._publish_enabled()                   # latched Bool re-publish
        return SetParametersResult(successful=True)

    def _publish_enabled(self):
        self._enabled_pub.publish(Bool(data=self._sound_enable))
```

**Warum so ([D-Audio-1..3], §9):** die Auto-Sounds kommen als **explizite Cues aus der
Sequenz-Logik** (nicht status-basiert) → Recovery-Aufstehen ist trivial stumm (kein Cue), und die
mehrdeutige `REPOSITION` (kommt beim Auf- UND Hinsetzen vor) wird nie fälschlich getriggert. Der
Node ist dünn: Topic rein → mp3 raus.

---

## 2. Tests-Liste (+ was NICHT)

| Test | Prüft | Warum |
|---|---|---|
| **T7A.1** gait_node feuert `standup`/`sitdown`/`reposition`/`freeze` an den richtigen Stellen; `_on_recover` feuert **keinen** Cue | Cue-Emit + Recovery-stumm | RA2 / D-Audio-1 |
| **T7A.2** Freeze-Cue nur beim **Übergang** (nicht wiederholt, nicht bei bereits-frozen) | einmaliger Freeze | RA1-Trigger |
| **T7A.3** Auto-Cue bei `sound_enable=true` → `_play_file` gerufen; bei `false` → **nicht** | Mute nur Auto | RA1/F3 |
| **T7A.4** manueller `/hexapod/play_sound` → spielt **auch** bei `sound_enable=false` | manuell immer | F3 |
| **T7A.5** neuer Sound bricht laufenden ab (`terminate` auf altem Popen) | letzter gewinnt | F5 |
| **T7A.6** unbekannter Cue/Key + fehlende Datei → **kein Crash**, WARN | Robustheit | Feld-Robustheit |
| **T7A.7** `sound_enable` live-Toggle → `/hexapod/sound_enabled` (latched Bool) re-publisht | App-Anzeige | RA3 |
| **T7A.8** `playback_enabled=false` (Sim) → **kein** Subprozess, nur Log | Sim-testbar | Dev ohne Speaker |
| **T7A.9 (HW, User)** die 4 Auto-Events + 3 Buttons spielen die echten mp3s hörbar am Speaker | HW-Verifikation | am fertigen Roboter |
| **T7A.10** `colcon test` + Lint grün, **gait-Regression** (Cue-Emit bricht Walking/Sequenzen nicht) | keine Regression | §4-Pflicht |

**Bewusst offen/später:** Lautstärke-Regelung (feste Lautstärke, RA4); Sound-Mixing/Queue (einer zur
Zeit); Knarzen-Fix (HW); reale mp3-Inhalte (User liefert nach); TTS/Sprachausgabe.

---

## 3. Progress-Checkliste (→ `phase_7a_audio_progress.md`, Done-Vertrag)
```
Phase 7A (Audio):
- [ ] P7A.1 [ROS] gait_node: /hexapod/audio_cue-Publisher + _emit_audio_cue; Cues standup/sitdown/reposition/freeze; _on_recover feuert KEINEN (T7A.1)
- [ ] P7A.2 [ROS] Freeze-Cue nur beim Übergang (in _trigger_safety_freeze); _on_estop-Reihenfolge gefixt (T7A.2)
- [ ] P7A.3 [ROS] Neues Paket hexapod_audio: Node subscribt audio_cue + play_sound, spielt via mpg123 (T7A.3/T7A.4)
- [ ] P7A.4 [ROS] sound_enable-Param (mutet NUR Auto-Cues) + latched /hexapod/sound_enabled + live-Toggle (T7A.7)
- [ ] P7A.5 [ROS] Playback: neuer bricht alten ab; playback_enabled (Sim log-only); Robustheit (T7A.5/T7A.6/T7A.8)
- [ ] P7A.6 [ROS] config/sound_map.yaml (cue/key->datei) + sounds/ mit 7 Platzhalter-mp3s (unterscheidbare Töne)
- [ ] P7A.7 [ROS] Launch-Wiring: hexapod_audio im On-Demand-Stack (real=playback, sim=log-only)
- [ ] P7A.8 [ROS] Contract §2/§3/§6 festgezurrt (audio_cue intern, play_sound, sound_enable, sound_enabled), Version-Bump
- [ ] P7A.9 [ROS] colcon test + Lint gruen + gait-Regression (T7A.10)
- [ ] P7A.10 [App] 2 Buttons "Fahren mit/ohne Audio" (setzen sound_enable) + Zuschalt-Toggle + Mute-Anzeige aus /hexapod/sound_enabled
- [ ] P7A.11 [App] 3 Sound-Buttons -> /hexapod/play_sound "sound_01".."sound_03"
- [ ] P7A.12 [ROS] Self-Review + Doku (README/architecture/ai_navigation, test_commands)
- [ ] P7A.13 [Integration, User+App/HW] Auto-Sounds bei Bewegung + manuelle Buttons hörbar am echten Speaker (T7A.9)
```

---

## 4. Offene Punkte / Risiken (vor Code entscheiden)
1. **Sound-Dateinamen** (User liefert mp3s nach). Vorschlag Mapping (`config/sound_map.yaml`):
   `standup→sound_aufstehen.mp3`, `sitdown→sound_hinsetzen.mp3`, `reposition→sound_repositioning.mp3`,
   `freeze→sound_freeze.mp3`, `sound_01→sound_01.mp3`, `sound_02→sound_02.mp3`, `sound_03→sound_03.mp3`.
   Platzhalter: 7 kurze, **unterscheidbare** Töne (generiert), damit man beim Test hört, welcher spielt.
2. **`playback_enabled` Default:** HW=true (spielt), Sim=false (log-only). Über Launch-Arg gesetzt
   (real vs sim). Alternativ Auto-Detect via ALSA-Device — Launch-Arg ist deterministischer.
3. **Freeze-Cue-Übergang + `_on_estop`-Reihenfolge** (§1a-⚠️) im Self-Review prüfen (nur beim Eintritt,
   nicht doppelt).
4. **ALSA-Device-Name** (`plughw:0,0`) als Param — falls die Karten-Nummer wechselt, robuster
   `plughw:CARD=sndrpihifiberry` (peripherals_tests §6-Tipp).

---

## 5. App-Seiten-Brief (self-contained)

**Interface = Contract §2/§3/§6** (nach P7A.8 festgezurrt). Alles über rosbridge.

- **Übergang Verbinden → Fahren: zwei Buttons** „**Fahren mit Audio**" / „**Fahren ohne Audio**" →
  setzen `sound_enable` (`true`/`false`) über die nativen rosbridge-`set_parameters` auf `/hexapod_audio`
  (wie das Config-Panel Phase 5). Danach in die Fahr-Ansicht.
- **Im Fahr-Modus: Audio-Zuschalt-Toggle** — togglet `sound_enable`. Der **aktuelle Zustand** kommt
  latched aus **`/hexapod/sound_enabled`** (`std_msgs/Bool`) → Toggle-Anzeige live.
- **3 Sound-Buttons** (Soundboard) → publishen `/hexapod/play_sound` (`std_msgs/String`) mit
  `"sound_01"`/`"sound_02"`/`"sound_03"`. Spielen **immer** (unabhängig von `sound_enable`).
- **Kein** App-Speaker — Sound kommt aus dem Roboter ([D5]). Die App ist nur Auslöser/Umschalter.

---

## 6. Contract-Touchpoints (→ festzurren, v0.11)
- **§3 (Topics):** `/hexapod/play_sound` (`std_msgs/String`, App→Roboter, Sound-Key) +
  `/hexapod/sound_enabled` (`std_msgs/Bool`, latched, Roboter→App, Mute-Status).
  `/hexapod/audio_cue` (`std_msgs/String`, gait_node→hexapod_audio) = **intern**, nicht App-relevant
  (nur der Vollständigkeit halber notiert).
- **§4 (Params):** `hexapod_audio/sound_enable` (bool) — von der App via `set_parameters` togglebar.
- **§6:** Audio-Zeile `play_sound` + `sound_enable` von `[TBD-Phase 7]` → **erledigt (v0.11)**.

## 7. Doku-Nachzug (nach Umsetzung)
- `phase_7a_audio_progress.md` + `phase_7a_audio_test_commands.md`.
- Neues `hexapod_audio/README.md` (Node, Cues, Mapping, mpg123-Weg, HW-Hinweise).
- `architecture.md` (Node + Topics) + `ai_navigation.md` („Audio/Sounds ändern"-Eintrag).
- App-`CLAUDE.md`-Zeile „Phase 7A".

---

## 8. Implementierungs-Leitfaden (self-contained — für einen frischen Chat)

> Zeilennummern gegen `src/hexapod_gait/hexapod_gait/gait_node.py` (Stand dieser Doku) — vor dem Edit
> per grep gegenchecken (die Phase-6-Edits haben Zeilen verschoben).

### Schritt 1 — gait_node Audio-Cues
- `__init__` (~638): `self._audio_cue_pub = self.create_publisher(String, '/hexapod/audio_cue', 10)`
  (`String` aus `std_msgs.msg` — Import prüfen, ist wg. `/hexapod/status` vermutlich schon da).
- Helper `_emit_audio_cue(name)` (§1a).
- Emit-Punkte: `_on_stand_up` (~2381, vor `return response` bei success), `_start_sitdown_sequence`
  (~2329, bei return True), `_on_cycle_stance` (~2692, bei success), `_trigger_safety_freeze` (~1802,
  Übergangs-Guard). **`_on_recover` NICHT** anfassen (bleibt stumm).
- `_on_estop` (~2423): das direkte `self._safety_frozen = True` **entfernen** (der Freeze läuft über
  `_trigger_safety_freeze()`, das den Übergang + Cue korrekt setzt).

### Schritt 2 — Paket `hexapod_audio`
- `src/hexapod_audio/` (ament_python): `package.xml` (Deps `rclpy`, `std_msgs`, exec-dep
  `mpg123` via `<exec_depend>`-Doku-Hinweis — apt-Paket, nicht rosdep-key-garantiert → im README
  vermerken), `setup.py` (entry_point `hexapod_audio = hexapod_audio.audio_node:main`; `data_files`
  für `config/` + `sounds/`), `resource/hexapod_audio`.
- `hexapod_audio/audio_node.py` = §1b–1d.
- `config/sound_map.yaml` (§4.1-Mapping). `sounds/` mit 7 Platzhalter-mp3s.

### Schritt 3 — Launch-Wiring
- Den Node in den **On-Demand-Stack** hängen (dort, wo `gait_node` startet — `bringup_ondemand`
  bzw. der reale/sim-Pfad). `playback_enabled:=true` im real-Pfad, `:=false` im sim-Pfad (Launch-Arg).
- Muster = ein bestehender Sensor-Node im selben Launch (z.B. `bno055_imu`/`foot_contact_publisher`).

### Schritt 4 — Tests
- `hexapod_gait/test/test_audio_cue.py`: Cue-Emit an den 4 Stellen (Node-Handler direkt aufrufen,
  `_audio_cue_pub.publish` mocken/spy), `_on_recover` feuert **nicht**, Freeze-Cue nur beim Übergang.
- `hexapod_audio/test/test_audio_node.py`: `_on_cue`/`_on_play` mit gemocktem `subprocess.Popen` +
  `os.path.isfile`; Mute-Logik (Auto vs manuell), terminate-alter-Prozess, unbekannter Key, Sim-log,
  latched `/hexapod/sound_enabled` bei Toggle. Muster = `test_sitdown_node.py` (rclpy-Fixture) +
  `test_bno055`/`test_foot_contact_node` (falls vorhanden) für den Sensor-Node-Stil.

### Schritt 5 — Build + Sim-Test
```bash
colcon build --packages-select hexapod_gait hexapod_audio && source install/setup.bash
# Sim-Stack hoch (playback_enabled=false → log-only), dann:
ros2 topic echo /hexapod/audio_cue        # bei stand_up/sit_down/cycle_stance/estop erscheinen Cues
ros2 service call /hexapod_stand_up std_srvs/srv/Trigger {}   # -> audio_cue 'standup' + Node loggt play
ros2 topic pub --once /hexapod/play_sound std_msgs/msg/String "{data: 'sound_01'}"  # manuell
ros2 param set /hexapod_audio sound_enable false               # Auto stumm, manuell spielt weiter
ros2 topic echo /hexapod/sound_enabled --qos-durability transient_local --once      # false
```

---

## 9. Design-Entscheidungen (mit Alternativen)

- **[D-Audio-1] Explizite Audio-Cues vom gait_node** (nicht status-basiert). Der `gait_node` feuert
  an den Sequenz-Startpunkten einen Cue. **Warum:** RA2 verlangt „Recovery-Aufstehen stumm" — bei
  status-basiert (aus `/hexapod/status.state`) sind stand_up und Recovery beide `STARTUP_RAMP` und
  **nicht unterscheidbar** (nur per fragiler safety_frozen-Heuristik). Explizite Cues lösen das
  trivial (`_on_recover` feuert keinen) und umgehen die `REPOSITION`-Mehrdeutigkeit (kommt beim Auf-
  UND Hinsetzen vor). D5-konform („Sequenz-Logik triggert Auto-Sounds"). **Verworfen:** rein
  status-basierter Audio-Node (kein gait-Change, aber Recovery-stumm nur heuristisch + REPOSITION
  mehrdeutig).
- **[D-Audio-2] `/hexapod/play_sound` als Topic** (`std_msgs/String`), kein Custom-Service. Konsistent
  mit der Phase-5-Entscheidung (kein Custom-Message-Paket); fire-and-forget reicht für Sound-Trigger.
  **Verworfen:** Custom-`srv` mit Erfolgs-Feedback (Interface-Paket-Overhead, kein echter Mehrwert).
- **[D-Audio-3] Neuer Sound bricht alten ab** (`terminate` + neuer `Popen`). Mono-Speaker, kurze
  mp3s → letzter Trigger gewinnt (F5). **Verworfen:** Queue / laufenden zu Ende spielen (fühlt sich
  träge an, kann stauen).
- **[D-Audio-4] mp3s im Paket** (`hexapod_audio/sounds/`, git-versioniert), nicht externer Pfad.
  **Warum (User):** SD-Karte kaputt → nur ROS aus git einspielen, keine mp3s separat kopieren.
  `sound_dir`-Param zeigt per Default auf das Paket-share. **Verworfen:** externer konfigurierbarer
  Ordner (flexibler, aber nicht source-controlled).
- **[D-Audio-5] `sound_enable` mutet nur Auto-Cues** (manuelle Buttons spielen immer, inkl. wenn
  gemutet). Der **Freeze-Sound fällt unter die Mute** (RA1: mutbar, kein Alarm-Sonderfall).
  **Verworfen:** Master-Mute (alles still) / nicht-mutbarer Freeze-Alarm.
- **[D-Audio-6] `playback_enabled` per Launch-Arg** (real=true, sim=false log-only) statt Auto-Detect.
  Deterministisch + Sim-testbar (man sieht die Trigger-Logik im Log ohne Speaker).
