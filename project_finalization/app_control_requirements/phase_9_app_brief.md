# Phase 9 — Start-Brief für die App-Session (zwei Lifecycle-Buttons)

> **Für die zweite Claude-Session im Android-Repo** (`~/AndroidStudioProjects/hexapod_app`).
> Self-contained. **Beide Services existieren ROS-seitig bereits** — es gibt **keinen**
> Interface-Change, du verdrahtest nur zwei Buttons.
>
> Contract: [`interface_contract.md`](interface_contract.md) §2a (v0.13.1) — nur lesen, nie ändern.

---

## 1. Worum es geht

Der Roboter soll **im Feld ohne Laptop** benutzbar sein: Pi einschalten → App verbinden → fahren →
sauber herunterfahren. Die ROS-Seite ist so weit; was fehlt, sind **zwei Knöpfe in der App**:

| Button | Service | Warum |
|---|---|---|
| **„Pi herunterfahren"** | `/hexapod_pi_shutdown` | Bisher gibt es nur den Hardware-Schalter am Roboter — und der wird vom Servo2040 gelesen, funktioniert also **nur bei laufendem Stack**. Ist der Stack gestoppt oder hängt er, bleibt heute nur „Akku abreißen". |
| **„Stack neu starten"** | `/hexapod_bringup_stop` + `/hexapod_bringup_start` | Wenn der schwere Stack hakt, kommt man ohne SSH nicht mehr weiter. Der Stop killt hart durch und wirkt auch auf einen hängenden Stack. |

**Beide gehören in die Verbinden-/Start-Sicht**, ausdrücklich **nicht** in die Fahr-Sicht
(User-Vorgabe) — es sind Lifecycle-Aktionen, und ein Fehlgriff auf „herunterfahren" wäre beim
Fahren teuer.

---

## 2. Die Frames (kopierbar)

Beide sind `std_srvs/Trigger` mit leerem Request:

```jsonc
// (a) Pi herunterfahren — NACH einem Bestätigungs-Dialog:
{"op":"call_service","service":"/hexapod_pi_shutdown","type":"std_srvs/srv/Trigger","args":{}}

// (b) Stack neu starten — zwei Aufrufe nacheinander:
{"op":"call_service","service":"/hexapod_bringup_stop","type":"std_srvs/srv/Trigger","args":{}}
// ... auf die Antwort warten, ~2 s Pause, dann:
{"op":"call_service","service":"/hexapod_bringup_start","type":"std_srvs/srv/Trigger","args":{}}

// (c) Läuft der Stack? (latched, für Button-Zustand und Erfolgskontrolle):
{"op":"subscribe","topic":"/hexapod/bringup_running","type":"std_msgs/msg/Bool",
 "qos":{"history":"keep_last","depth":1,"durability":"transient_local","reliability":"reliable"}}
```

### ⚠️ Response-Semantik von `/hexapod_pi_shutdown` — bitte genau lesen

**`success=true` bedeutet „Anfrage angenommen", NICHT „der Pi fährt jetzt herunter".** Der eigentliche
Poweroff läuft durch drei Sicherheits-Guards (Dev-Rechner hart geblockt, Master-Schalter,
Hostname-Vergleich) und passiert asynchron. Das Ergebnis steht in **`message`**:

| Situation | `success` | `message` (Beispiel) | Was die App zeigen sollte |
|---|---|---|---|
| Stack läuft, Anfrage raus | `true` | `shutdown requested (stack running → controlled sit-down + guarded poweroff …)` | „Roboter setzt sich hin, Pi fährt herunter …" |
| Kein Stack, Poweroff feuert (echter Pi) | `true` | `idle poweroff: performed=True (executed)` | „Pi fährt herunter …" |
| Kein Stack, **Poweroff blockiert** | `true` | `idle poweroff: performed=False (dev-host)` bzw. `(host-mismatch)` / `(disabled)` | **Kein Herunterfahren!** Hinweis anzeigen, Verbindung bleibt |
| `shutdown_supervisor` fehlt | `false` | `/hexapod_request_shutdown not available …` | Fehler anzeigen |

**Beim Testen in der Sim wirst du genau den dritten Fall sehen**
(`performed=False (dev-host)`) — das ist **korrekt und erwartet**, der Desktop darf sich nicht
abschalten. Werte es nicht als Bug, aber zeige auch nicht „Pi fährt herunter", wenn
`performed=False` in der Message steht. Ein simples `message.contains("performed=False")` genügt für
die Unterscheidung.

Antwort auswerten also: `success` **und** `message` (Klartext, in beiden Fällen anzeigenswert).

---

## 3. Verhalten — was du wissen musst

**„Pi herunterfahren"**
- Funktioniert in **beiden** Zuständen: läuft der Stack → der Roboter **setzt sich erst hin**, das
  Relay geht aus, dann fährt der Pi herunter (dauert insgesamt ~15–25 s). Läuft er nicht → der Pi
  fährt **sofort** herunter.
- **Muss auch erreichbar sein, wenn der Stack nicht läuft** — das ist der eigentliche Rettungsanker.
- **Bestätigungs-Dialog ist Pflicht** (Contract §2a): der Weg zurück ist ein Hardware-Schalter.
- **Die Verbindung bricht danach ab. Das ist erwartet** — bitte als „Pi fährt herunter" anzeigen,
  nicht als Verbindungsfehler. Ein Reconnect-Versuch wäre hier kontraproduktiv.
- Hängt der Stack beim Hinsetzen, greift ROS-seitig nach 12 s ein Backstop (Relay-Aus wird
  erzwungen, der Pi fährt trotzdem herunter). Du musst dafür nichts tun — nur nicht ungeduldig
  werden.

**„Stack neu starten"**

> ⚠️ **Der Stop nimmt dem Roboter sofort das Drehmoment — ein stehender Roboter sackt zusammen.**
> Das ist kein Bug, sondern zweifach so gebaut: `on_deactivate` im Hardware-Plugin schickt bewusst
> Disable-Frames („we want the robot to lose torque as fast as possible"), und bei einem harten Kill
> greift der **Firmware-Watchdog nach 200 ms** und schaltet das Relay ab. Aus Standhöhe fällt er
> also ~8–10 cm auf den Bauch.

Daraus folgt die Ablauf-Logik:

| Zustand (`status.state`) | Was die App tun soll |
|---|---|
| `SAT` (liegt schon) | direkt `bringup_stop` → warten → `bringup_start` |
| `STANDING` / `WALKING` / … und der Stack **antwortet** | **erst `/hexapod_sit_down`**, auf `state == SAT` warten (Timeout ~15 s), **dann** stoppen |
| Stack **hängt** (kein Status-Tick, sit_down läuft in den Timeout) | hart stoppen — aber **mit Warnung im UI**: „Roboter sackt zusammen, ggf. vorher festhalten/ablegen" |

- Nach dem Neustart liegt der Roboter **auf dem Bauch** (SAT) — der Nutzer drückt erneut
  „Aufstehen". So gewollt (beim Start soll sich nichts von selbst bewegen).
- **Bestätigungs-Dialog:** nötig, **wenn der Roboter nicht sitzt** (weil dann entweder eine
  Hinsetz-Sequenz läuft oder er fällt). Sitzt er schon, reicht ein direkter Tap.

**Wann ist der Stack nach `start` wirklich bereit?** Zwei Ebenen — bitte nicht verwechseln:
1. **Prozess läuft:** `/hexapod_bringup_status` meldet `running (pid=…)` — das kommt **sofort** nach
   `start` und heißt noch **gar nichts** über die Bedienbarkeit.
2. **Bedienbar:** der `gait_node` startet erst nach `gait_delay` (**Default 12 s**, damit
   controller_manager und die 6 JTCs stehen) und braucht dann selbst noch Init-Zeit. Der belastbare
   Indikator ist **`/hexapod/status`** (5 Hz, kommt aus dem gait_node): tickt es, ist der Stack
   wirklich da.

→ Erst wenn (2) erfüllt ist, „Aufstehen" freigeben. **Timeout großzügig wählen: 40 s** (12 s
`gait_delay` + Controller-/Gait-Init + auf HW langsamer als in der Sim). 20 s wären zu knapp und
würden fälschlich einen Fehlschlag melden.

---

## 4. Empfohlene Button-Zustände

| Situation | „Stack neu starten" | „Pi herunterfahren" |
|---|---|---|
| Nicht verbunden | aus | aus |
| Verbunden, Stack läuft nicht | aus (oder „Starten" zeigen) | **aktiv** |
| Verbunden, Stack läuft | **aktiv** | **aktiv** |
| Während stop/start läuft | aus, bis `bringup_running` stabil ist | aktiv lassen |

---

## 5. Testen (Sim reicht für alles außer dem echten Poweroff)

In der Sim laufen beide Services normal — der Poweroff ist auf dem Dev-Rechner **dreifach geguarded**
und macht dort nur einen Dry-Run-Logeintrag. Du kannst also gefahrlos testen:
1. Verbinden → „Stack neu starten" → Stack geht aus und wieder an, danach „Aufstehen" möglich.
2. Verbinden ohne Stack → „Pi herunterfahren" → `success=true` mit
   `message: idle poweroff: performed=False (dev-host)` → deine UI muss daraus **„nicht ausgeführt"**
   machen, nicht „fährt herunter" (siehe Tabelle oben).
3. Mit laufendem Stack → „Pi herunterfahren" → der Roboter setzt sich in der Sim hin; die Verbindung
   bleibt bestehen (auf dem Desktop wird nichts abgeschaltet).

Der echte Poweroff wird am Pi getestet (macht der User).

---

## 6. Wenn dir etwas fehlt

An die ROS-Seite melden, nicht selbst im Contract ändern. Bekannt und bewusst offen:
- Kein Fortschritts-Feedback während des Herunterfahrens (die Verbindung bricht ja ab).
- Kein „Always-On läuft seit …"-Indikator.
- Automatischer Reconnect nach WLAN-Abriss ist noch nicht bewertet — falls du dazu etwas beitragen
  kannst (verbindet sich die App heute von selbst wieder?), interessiert uns das Ergebnis.
