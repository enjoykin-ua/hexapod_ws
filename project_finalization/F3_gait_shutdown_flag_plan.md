# Stage F3 — gait_node: latched Bool `/hexapod/shutdown_complete`

> Teil von [Block F](F_systemsteuerung_plan.md). Detail-Plan nach CLAUDE.md §4.
> Code: `~/hexapod_ws/src/hexapod_gait` (rclpy Node).
> Voraussetzung: F2 🟢. Test-Anleitung: [`F3_gait_shutdown_flag_test_commands.md`](F3_gait_shutdown_flag_test_commands.md).

---

## 1. Logik-Skizze / Pseudocode

**Zweck:** Der Supervisor (F4) muss wissen, **wann Hinsetzen + Relay-Aus fertig**
sind, bevor er das OS herunterfährt — ohne magische Wartezeit (Master-Plan E5,
Option B). Genau dieser Moment existiert schon intern als `_shutdown_latched`,
gesetzt in `_do_relay_off_and_latch` ([gait_node.py:1582](../src/hexapod_gait/hexapod_gait/gait_node.py#L1582)) —
er wird nur **nicht** als Topic publiziert. F3 schließt das.

**Befund (verifiziert):** `_shutdown_latched` geht **False→True genau einmal**
(in `_do_relay_off_and_latch`), wird sonst nie zurückgesetzt (nur `__init__`=False,
Recovery via Reboot). → Topic-Semantik: einmaliger `false → true`-Flip pro Session.

### 1.1 Importe
```python
from std_msgs.msg import Bool                 # zusätzlich zu Float64, Float64MultiArray
from rclpy.qos import QoSProfile, DurabilityPolicy, ReliabilityPolicy
```

### 1.2 Latched Publisher (in `__init__`, beim Publisher-Setup ~Z.759)
```python
latched_qos = QoSProfile(
    depth=1,
    durability=DurabilityPolicy.TRANSIENT_LOCAL,
    reliability=ReliabilityPolicy.RELIABLE)        # F2-Vertrag: reliable+transient_local
self._shutdown_complete_pub = self.create_publisher(
    Bool, '/hexapod/shutdown_complete', latched_qos)
self._publish_shutdown_complete(False)             # definierter Startwert (latched)
```

### 1.3 Helper + Auslöser
```python
def _publish_shutdown_complete(self, done: bool) -> None:
    self._shutdown_complete_pub.publish(Bool(data=done))

# in _do_relay_off_and_latch(), nach self._shutdown_latched = True:
self._publish_shutdown_complete(True)
```

### Begründung
- **Latched + reliable + transient_local:** identischer QoS-Vertrag wie F2
  ([[project_latched_topic_qos_reliable]]); der F4-Supervisor matcht beide Topics gleich.
- **Vorhandenes `_shutdown_latched` wiederverwenden:** keine neue Mechanik, nur ein
  Publisher + ein publish-Aufruf am exakten „fertig"-Moment.
- **false → true einmalig:** spiegelt den `_shutdown_latched`-Lebenszyklus; der
  Supervisor reagiert auf die `true`-Flanke. Kein Reset nötig (Recovery = Reboot).
- **Helper `_publish_shutdown_complete`:** DRY (Init-false + Latch-true), testbar.

---

## 2. Tests-Liste mit Begründung

| ID | Test | Erwartung | Warum |
|---|---|---|---|
| F3-U1 | Unit (`test_sitdown_node.py`): nach `__init__` | `_shutdown_complete_pub` existiert, Init publisht `false` | Startwert definiert |
| F3-U2 | Unit: `_on_shutdown` aus **SAT** (Spy auf Publisher) | `_shutdown_complete_pub.publish` mit `Bool(data=True)` aufgerufen | Kern: Flag beim Latch |
| F3-U3 | Unit: `_on_shutdown` aus **STANDING** (noch nicht SAT) | **kein** `true` (erst wenn `_tick` SAT erreicht → `_do_relay_off_and_latch`) | kein verfrühtes „fertig" |
| F3-U4 | `colcon test --packages-select hexapod_gait` (+ flake8/pep257) | grün | Regression + Lint |
| F3-L1 | Live: `ros2 topic echo … shutdown_complete` (reliable+transient_local) nach Launch | `data: false` | latched Init real |
| F3-L2 | Live (aufgebockt): `ros2 service call /hexapod_shutdown` → sitzt + Relay-Aus | Topic flippt auf `data: true` | echte „fertig"-Meldung |

**Bewusst NICHT getestet (deferred):**
- Switch→`/hexapod_shutdown`-Verkettung → **F4** (Supervisor existiert noch nicht;
  F3-L2 triggert den Service manuell).
- End-to-End Schalter→Shutdown→OS → **F5**.

---

## 3. Progress-Checkliste (Done-Vertrag — 1:1 ins Progress-File)

```
- [ ] F3.1  Importe: Bool + QoSProfile/DurabilityPolicy/ReliabilityPolicy
- [ ] F3.2  __init__: latched Publisher /hexapod/shutdown_complete + Init false
- [ ] F3.3  _publish_shutdown_complete(done) Helper
- [ ] F3.4  _do_relay_off_and_latch: nach Latch _publish_shutdown_complete(True)
- [ ] F3.5  Unit-Tests F3-U1..U3 in test_sitdown_node.py
- [ ] F3.6  colcon test + flake8 + pep257 grün (hexapod_gait)
- [ ] F3.7  Live F3-L1 (false) + F3-L2 (true bei Shutdown, aufgebockt)
- [ ] F3.8  Self-Review-Tabelle (CLAUDE.md §4)
```

---

## 4. Entscheidungen (User-Review erledigt, vor Code-Beginn)

Alle drei vom User bestätigt — keine offenen Punkte mehr:

1. **Topic-Name `/hexapod/shutdown_complete`** (analog `/hexapod/shutdown_request`).
2. **Semantik: Flag bleibt `true` nach Latch** — kein Reset, spiegelt den
   `_shutdown_latched`-Lebenszyklus. Der F4-Supervisor reagiert auf die `true`-Flanke;
   Recovery via Relay-On/Reboot. *Verworfen:* Reset-auf-false (unnötig, kein Konsument
   braucht es).
3. **F3-L2 wird jetzt aufgebockt getestet** (echte Aktion: Roboter setzt sich hin +
   Relay aus). *Verworfen:* F3-L2 auf F5 schieben — wir verifizieren die `true`-Flanke
   gleich mit.
