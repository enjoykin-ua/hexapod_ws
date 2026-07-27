# Phase 8 — Start-Brief für die App-Session (Show-Menü „Look-Around")

> **Für die zweite Claude-Session im Android-Repo** (`~/AndroidStudioProjects/hexapod_app`).
> Self-contained: alles Nötige steht hier bzw. im Contract. **Die ROS-Seite ist fertig,
> implementiert und unit-getestet** (1014 Tests grün) — die Naht ist in
> [`interface_contract.md`](interface_contract.md) **v0.13 §6c** festgezurrt.
>
> **Contract nur lesen, nie kopieren, nie ändern.** Änderungswünsche an die ROS-Seite melden.

---

## 1. Was dazukommt

Der Roboter kann jetzt eine **Show**: **„Kamera-Umschauen" (Look-Around)**. Er steht dabei still —
**alle sechs Füße bleiben fix am Boden** — und bewegt nur den **Körper**: hoch/runter und
links/rechts schauen, in der Ebene wandern, Höhe verstellen. Lässt man los, federt alles sanft in
die Ausgangs-Pose zurück. Weil die Kamera am Körper sitzt, **schwenkt das Live-Bild mit** — das ist
der eigentliche Effekt der Show.

**Deine Aufgabe: ein Show-Menü mit vier Einträgen.** Zwei davon sind bewusst **Platzhalter** — die
ROS-Seite nimmt sie schon an, tut aber noch nichts. So baust du das Menü **einmal** vollständig;
wenn Dancing und Free-Leg später ROS-seitig kommen, ist **kein App-Eingriff mehr nötig**.

| Menü-Eintrag | `show_mode` | Status |
|---|---|---|
| **Kamera-Umschauen** | `look_around` | ✅ implementiert |
| **Dancing** | `dancing` | ⏳ Platzhalter (akzeptiert, tut noch nichts) |
| **Free-Leg** | `free_leg` | ⏳ Platzhalter |
| **Normalbetrieb** | `none` | ✅ Show verlassen |

> ⚠️ **Das Show-Menü ist ein eigener Menüpunkt — NICHT das Config-Panel.** `show_mode` steht
> bewusst **nicht** im `config_manifest` (sonst würde das Panel es automatisch als Dropdown
> mitrendern und die Show wäre an zwei Stellen bedienbar).

---

## 2. Was die App tun muss — und was nicht

**Tun:** den Parameter `show_mode` auf `/gait_node` setzen. Das ist derselbe Aufruf-Pfad, den du
fürs Config-Panel schon hast (native rosbridge-`set_parameters`), nur an anderer UI-Stelle.

**Nicht tun:** die Steuerung selbst. Die Sticks laufen über `/joy` wie bisher — **die App publisht
dafür nichts Neues**. Sobald der Modus gesetzt ist, wirken die Sticks auf den Körper statt aufs
Fahren. Du brauchst nur einen **Hinweistext** im Menü.

**Bedienung (nur als Hinweis anzeigen):**

| Eingabe | Wirkung |
|---|---|
| **R1 halten** | Dead-Man — ohne R1 federt der Körper zurück |
| rechter Stick | **umschauen** (hoch/runter, links/rechts) |
| linker Stick | **wandern** (vor/zurück, seitwärts) |
| L2 / R2 | **Höhe** |
| loslassen | federt sanft zurück |

---

## 3. Die Frames (kopierbar)

```jsonc
// (a) Show starten — type 4 = PARAMETER_STRING:
{"op":"call_service","service":"/gait_node/set_parameters",
 "type":"rcl_interfaces/srv/SetParameters",
 "args":{"parameters":[{"name":"show_mode",
   "value":{"type":4,"string_value":"look_around"}}]}}

// (b) Show verlassen — wird IMMER akzeptiert:
{"op":"call_service","service":"/gait_node/set_parameters",
 "type":"rcl_interfaces/srv/SetParameters",
 "args":{"parameters":[{"name":"show_mode",
   "value":{"type":4,"string_value":"none"}}]}}

// (c) Ist-Zustand (den du im Menü spiegelst) — Status-Topic, 5 Hz:
{"op":"subscribe","topic":"/hexapod/status","type":"std_msgs/msg/String"}
// -> JSON.parse(msg.data).show_mode    ("none"|"look_around"|"dancing"|"free_leg")
// -> JSON.parse(msg.data).state        (während der Show: "BODY_POSE")

// (d) Menü-Einträge generisch rendern (optional) — latched capabilities:
{"op":"subscribe","topic":"/hexapod/capabilities","type":"std_msgs/msg/String",
 "qos":{"history":"keep_last","depth":1,"durability":"transient_local","reliability":"reliable"}}
// -> JSON.parse(msg.data).show_modes == ["none","look_around","dancing","free_leg"]
```

Antwort auswerten: `results[0].successful`. Bei `false` steht in `results[0].reason` ein
Klartext-Grund — **anzeigen**.

---

## 4. Die Regeln (serverseitig durchgesetzt — bitte im UI berücksichtigen)

1. **Show starten geht nur, wenn der Roboter wirklich steht:** `status.state == "STANDING"`,
   **kein** aktiver E-Stop (`status.safety_frozen == false`) und der Stack läuft
   (`/hexapod/bringup_running`). Sonst kommt ein Reject mit Grund. → Menü-Einträge entsprechend
   ausgrauen.
2. **„Normalbetrieb" (`none`) wird IMMER akzeptiert** — auch mitten in der Show. Das ist der
   garantierte Rückweg; dieser Eintrag darf nie ausgegraut sein.
3. **Kein direkter Show-zu-Show-Wechsel.** Wer von „Kamera-Umschauen" zu „Dancing" will: erst
   `none` senden, warten bis `status.state == "STANDING"` (~1 s Zurückfedern), dann den neuen Modus.
   Das kannst du im Menü automatisch machen — der User soll nur einmal tippen.
4. **Der aktive Eintrag folgt `status.show_mode`, nicht dem eigenen Klick.** Der Roboter ist die
   Wahrheit: bei Recovery setzt er `show_mode` selbst auf `none` zurück, und die Platzhalter
   `dancing`/`free_leg` fallen sofort auf `none` zurück (sie werden akzeptiert, aber nicht
   ausgeführt) — dein Menü zeigt dann wieder „Normalbetrieb". Das ist **erwartetes** Verhalten und
   kein Fehler.
5. **Hinsetzen geht aus der Show nicht direkt** — erst `none`, dann `/hexapod_sit_down`. Der
   Reject-Grund sagt es auch. **E-Stop funktioniert jederzeit**, auch mitten in der Show.

---

## 5. Wie du es testest

Die ROS-Seite läuft in der Sim; du brauchst keinen echten Roboter:
1. Stack starten (wie gewohnt über die App: „Hexapod starten" → „Aufstehen").
2. Show-Menü → „Kamera-Umschauen" → `status.state` muss auf `BODY_POSE` springen.
3. Mit dem Kishi umschauen (**R1 halten**) → das **Video schwenkt mit**, die Füße stehen still.
4. „Normalbetrieb" → zurück auf `STANDING`, danach wieder normal fahrbar.
5. „Dancing" antippen → Meldung/„noch nicht implementiert", Roboter bleibt stehen, Menü fällt auf
   „Normalbetrieb" zurück.
6. Während des Fahrens „Kamera-Umschauen" antippen → Reject-Grund wird angezeigt.

---

## 6. Wenn du etwas brauchst, das es nicht gibt

Melde es an die ROS-Seite (dieses Repo) — **nicht selbst im Contract ändern**. Bekannte, bewusst
offene Punkte, die die ROS-Seite auf Zuruf nachziehen kann:
- Komfort: Hinsetzen direkt aus der Show (heute Reject).
- Komfort: direkter Show-zu-Show-Wechsel (heute über `none`).
- Ein Sound beim Betreten/Verlassen der Show (heute keiner).
- Ein latched Topic für `show_mode` (heute nur im 5-Hz-Status) — sag Bescheid, falls dein Menü
  den Wert schon **vor** dem Stack-Start braucht.
