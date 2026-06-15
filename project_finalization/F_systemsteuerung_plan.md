# Block F — Systemsteuerung / Lifecycle — Phasen-Übersicht

> **Master-Plan dieser Gruppe.** Fasst das Gesamt-Feature zusammen und gliedert es
> in Stages F1…F5. Jede Stage bekommt ihren eigenen Detail-Plan (`F<n>_*_plan.md`)
> nach CLAUDE.md §4 (Plan → Freigabe → Code → Tests → Self-Review), erst dann Code.
> Referenz-Navigation: [`../project_architecture/ai_navigation.md`](../project_architecture/ai_navigation.md).
> Backlog-Eintrag: [`00_backlog.md`](00_backlog.md) Block F.

---

## 1. Zweck

Ein **zweiter Hardware-Schalter** am Servo2040 (A1/GP27) löst einen **kontrollierten
Shutdown** des Roboters aus: Hexapod setzt sich hin, Servo-Rail wird stromlos, der
Raspberry Pi fährt sauber herunter (SD-Karte wird nicht beschädigt).

**Abgrenzung zum vorhandenen Power-Schalter:** Schalter 1 (nicht hier) gibt dem Pi
physisch Strom. Dieser **Schalter 2** ist der *Soft-Shutdown-Auslöser* — er kappt
keinen Strom, sondern meldet „bitte sauber runterfahren".

**LED-Feedback (lokal, am Servo2040, unabhängig von der Verbindung):**
- Schalter **zu** → grün → „läuft, alles gut"
- Schalter **auf** → rot → „Shutdown angefordert"

---

## 2. Gesamt-Sequenz (Soll)

```
Schalter ≥3 s auf "rot/offen"
   │  (3-s-Halten + Arm-Logik in der FW)
   ▼
servo2040 setzt status_flags Bit 7 (SHUTDOWN_REQUEST)
   │  (in jeder STATE_RESPONSE mitgesendet)
   ▼
hexapod_hardware liest Bit 7 → publisht Bool (latched) /hexapod/shutdown_request
   │
   ▼
hexapod_supervisor (neuer Node):
   1. Flanken-Erkennung + Arm (Defense-in-Depth, ignoriert Bit beim eigenen Start)
   2. /hexapod_shutdown rufen — RETRY bis Erfolg
        (Service akzeptiert nur STANDING/SAT → im WALKING lehnt er ab = K2)
   3. warten auf /hexapod/shutdown_complete (latched Bool von gait_node)
        … ODER Timeout-Backstop (F4: Sit-Fehler → trotzdem stromlos + runterfahren)
   4. guarded OS-Shutdown (Param enable_os_shutdown + Hostname-Guard)
```

`/hexapod_shutdown` selbst (existiert bereits) erledigt: *steht* → hinsetzen →
Relay-Aus **sofort bei SAT** (K1) → latch. *sitzt* → sofort Relay-Aus + latch.

---

## 3. Architektur-Entscheidungen (mit verworfenen Alternativen)

| # | Entscheidung | Gewählt | Verworfen / Warum |
|---|---|---|---|
| E1 | Bit-Transport FW→Host | **Pegel-Bit in `status_flags` Bit 7**, in jeder STATE_RESPONSE | Unsolicited Event-Frame (Push): mehr bewegliche Teile, Edge-Verlust bei Frame-Drop möglich → 100-ms-Nachsenden nötig. Polling ist idempotent + selbstheilend. |
| E2 | 3-s-Halten | **in der FW** (Hold-to-confirm gegen Fehlauslösung) | Im Supervisor: ginge auch, aber FW-seitig ist das Bit dann ein sauberes „bewusster Wunsch", Host bleibt dumm. |
| E3 | Arm-Logik („erst wenn zu gesehen") | **auf BEIDEN Ebenen** (FW + Supervisor-Flanke) | Nur FW: ein Supervisor-Neustart bei schon gesetztem Bit würde sofort runterfahren. Defense-in-Depth. |
| E4 | Bit nach ROS exponieren | **latched Bool-Publisher** in `hexapod_hardware/read()` auf `/hexapod/shutdown_request` | ros2_control GPIO-State-Interface + Broadcaster: korrekt, wenn ein *Controller* konsumiert — hier konsumiert ein *Node* → Broadcaster wäre nur Durchreiche-Boilerplate. Direkter Publisher ist im Codebase schon idiomatisch (`publish_servo_pulses`). |
| E5 | „Hinsetzen fertig?" | **latched Confirm-Flag** `/hexapod/shutdown_complete` (Option B) | Feste Wartezeit (Option A): magische Zeitkonstante an zwei Stellen; ändert sich `sitdown_duration`, droht „zu früh runterfahren" → Relay-Drop mitten im Hinsetzen → Beine kollabieren. Flag ist selbst-synchronisierend. Timeout bleibt nur als **Notnetz** (F4). |
| E6 | Relay-Aus-Timing | **sofort bei Erreichen von SAT** (K1) | 1 s nach Hinsetzen: unnötig, sofort ist sogar besser (Servos früher stromlos, kein Haltemoment). |
| E7 | Konsum nur in STANDING/SAT | **ja** (K2): während WALKING/Transition kein Shutdown | Mid-Walk-Force-Relay-Off: verworfen, Supervisor wartet stattdessen bis konsumierbarer State (via `/hexapod_shutdown`-Retry, der sonst ablehnt). |
| E8 | OS-Shutdown-Sicherung | **Param `enable_os_shutdown` (Default false) + Hostname-Guard** | Ungeschützter `sudo shutdown`: Lebensgefahr für den Dev-Rechner. Dev-Host `enjoykin-ubuntu` darf den Befehl **nie** sehen. Siehe [[feedback_no_shutdown_on_dev_host]]. |

---

## 4. Was existiert schon — was ist neu

**Schon fertig (wird NICHT neu gebaut):**
- `/hexapod_shutdown` (Trigger): sitzt→Relay-Aus; steht→hinsetzen→Relay-Aus-bei-SAT→latch — `gait_node.py:1353`
- Sit-Down-Sequenz + GaitEngine-States (STANDING/SAT) — `gait_node.py`, `gait_engine.py`
- Relay-Service `/hexapod_relay_set` (SetBool) — `hexapod_system.cpp:420`
- `status_flags`-Dekodierung inkl. freiem Bit 7 — `servo2040_protocol.{hpp,cpp}`
- Comms-Loss-Failsafe (`comms_loss_sitdown_timeout`) — `gait_node.py:353` (komplementärer Unfall-Pfad)
- LED-Rohpegel-Anzeige (grün/rot) am Servo2040 — `main.cpp` `poll_switch`

**Neu (diese Phase):**
- FW: Schalter → Bit 7 (3-s-Halten + Arm)
- HW: `status_flags` Bit 7 konsumieren (`latest_state()` wird heute **nirgends** gelesen!) → latched Bool publishen
- gait_node: `/hexapod/shutdown_complete` latched Bool publishen (vorhandenes `_shutdown_latched` rausgeben)
- Supervisor-Node + Guard-Modul
- Bringup-Integration + Pi-Deployment (Shutdown-Privileg, Branch-Sync)

---

## 5. Stage-Unterteilung

| Stage | Scope | Test-Ebene | Plan-Doc |
|---|---|---|---|
| **F1** | servo2040 FW: Schalter → `status_flags` Bit 7 (3-s-Halten + Arm). LED-Rohpegel bleibt. | FW-Bench (LED + `log_state.py` flags) | `F1_fw_switch_bit_plan.md` |
| **F2** | `hexapod_hardware`: Bit 7 in `read()` konsumieren → latched Bool `/hexapod/shutdown_request` | Loopback/Unit + `ros2 topic echo` | (folgt) |
| **F3** | `gait_node`: latched Bool `/hexapod/shutdown_complete` bei `_do_relay_off_and_latch` | Unit (test) + `ros2 topic echo` | (folgt) |
| **F4** | `hexapod_supervisor` (neues rclpy-Paket): Sub + Arm/Flanke + `/hexapod_shutdown`-Retry + Confirm/Backstop + Guard-Modul | Mock-Services + **Dry-Run-Shutdown** | (folgt) |
| **F5** | Integration: Bringup-Launch, Pi-Deployment (polkit/sudoers, Branch `leg_changes`), End-to-End | Sim (Guard aus) → Pi aufgebockt → Pi echt (Guard an) | `F5_integration_plan.md` |
| **F6** | Pi-Update Ablaufplan (Runbook): Branch-Wechsel + Subset-Rebuild + F5b-Scharfschalten am Pi | Smoke aufgebockt → End-to-End | `F6_pi_update_checklist.md` |

> **Phasenweise:** Nur F1 ist jetzt detailliert geplant. F2–F5 werden je bei Beginn
> als eigener `F<n>_*_plan.md` ausgearbeitet (Plan → Freigabe → Code).

---

## 6. Test-Strategie (Staffelung)

1. **F1 FW-Bench** — Board an USB-Strom, Schalter umlegen, `log_state.py` `flags`-Spalte beobachten (Bit 7 = `0x80`). Arm-/3-s-Verhalten verifizieren. Kein ROS.
2. **F2/F3 ROS-Unit + Loopback** — Bit-Decode + Publisher, `ros2 topic echo`.
3. **F4 Supervisor** — Mock-`/hexapod_shutdown` + Mock-Topics, **Shutdown im Dry-Run** (nur Log), Arm/Flanke/Retry/Backstop testen.
4. **F5 Sim** (Guard **aus**, „würde runterfahren"-Log) → **Pi aufgebockt** → **Pi echt** (Guard **an**, ganz spät).

---

## 7. Sicherheits-Leitplanken

- **Dev-Host `enjoykin-ubuntu` darf den `sudo shutdown` NIE ausführen.** Default
  `enable_os_shutdown=false` **plus** Hostname-Guard. Erst spät auf dem Pi scharf.
- Robot **aufgebockt** bei allen ersten HW-Tests (CLAUDE.md §9).
- Phase-7-FW (`hexapod_servo_driver`) ist abgeschlossen — Progress wird **hier**
  (Block F) getrackt, **nicht** in `phase_7_progress.md`. `PROTOCOL.md` (lebende
  Spec) wird aktualisiert.

---

## 8. Offene Punkte (Master-Ebene)

- **F4 Backstop-Zeit:** Timeout, falls `/hexapod/shutdown_complete` nie kommt
  (Vorschlag ≈ `sitdown_duration` 5 s + Marge) → dann `/hexapod_relay_set false`
  hart + Shutdown (F4-Policy). Wert in F4 festzurren.
- **F4 Backstop-Aktion:** explizit `/hexapod_relay_set false` ODER auf Watchdog
  verlassen (kappt Relay eh bei USB-Verlust beim OS-Halt)? In F4 entscheiden.
- **F5 Shutdown-Mechanismus:** `systemd-logind` (D-Bus `PowerOff` via polkit) vs.
  NOPASSWD-sudoers für genau ein Kommando. Pi-Deployment-Detail.
