# Phase 13 Stage 0.1 — Test-Commands (Relay-Frame + Fail-safe)

> **Plan:** [`phase_13_stage_0_1_relay_plan.md`](phase_13_stage_0_1_relay_plan.md).
> **Form:** User führt aus, meldet knappe Status (Memory
> `feedback_interactive_stage_test_doc`). Verifikations-Outputs **nicht**
> trimmen (Memory `feedback_no_trim_verification_output`).
> **Status:** ⚪ Test-Liste vorab; finale Befehle nach Implementierung.

⚠️ **Sicherheit:** Roboter aufgebockt, PSU-Kill-Switch griffbereit. Beim
Relay-On-Test nur prüfen, dass der Relay **klickt** — Servos müssen noch
nicht sinnvoll fahren (Mech-Umbau erst 0.2).

---

## Vorbereitung

```bash
# FW-Build + Flash (User)
cd ~/hexapod_servo_driver/build
cp Hexapod_servo_driver.uf2 Hexapod_servo_driver.uf2.pre-0.1   # Rollback-Sicherung
cmake .. && make -j$(nproc)
sudo picotool load Hexapod_servo_driver.uf2 && sudo picotool reboot

# Plugin-Build
cd ~/hexapod_ws
colcon build --packages-select hexapod_hardware
source install/setup.bash
```

## T1 — FW-Host-Test (ohne Plugin, ohne PSU)

```bash
cd ~/hexapod_servo_driver
python3 tools/test_servo2040.py            # erwartet: RELAY_CONTROL-Tests grün
```
**Erfolg:** RELAY_CONTROL → ACK; len≠1 → ERROR PAYLOAD_LEN; (falls Bit)
GET_STATE RELAY_ON spiegelt on/off.

## T2 — Plugin Unit-Tests (CI-tauglich, ohne HW)

```bash
cd ~/hexapod_ws
colcon test --packages-select hexapod_hardware --event-handlers console_direct+
colcon test-result --verbose
```
**Erfolg:** alle grün inkl. `EncodeRelayControl*`, `RelaySetServiceSendsFrame`,
`OnDeactivateSendsRelayOff`.

## T3 — Live: Relay klickt via Service (PSU AN, aufgebockt)

```bash
ros2 launch hexapod_bringup real.launch.py use_sim_time:=false
# anderes Terminal:
ros2 service call /hexapod_relay_set std_srvs/srv/SetBool "{data: true}"   # Relay klickt EIN
ros2 service call /hexapod_relay_set std_srvs/srv/SetBool "{data: false}"  # Relay klickt AUS
```
**Erfolg:** hörbarer/messbarer Relay-Klick bei beiden Calls; Service-Response
`success: true`.

## T4 — Watchdog-Trip droppt Relay

```bash
ros2 service call /hexapod_relay_set std_srvs/srv/SetBool "{data: true}"   # Relay EIN
pkill -9 -f ros2     # Host hört abrupt auf zu senden → FW-Watchdog nach 200 ms
```
**Erfolg:** ~200 ms nach pkill klickt der Relay **selbstständig AUS**
(FW-autonom, kein Plugin nötig).

## T5 — RESET-Frame droppt Relay

```bash
ros2 launch hexapod_bringup real.launch.py use_sim_time:=false
ros2 service call /hexapod_relay_set std_srvs/srv/SetBool "{data: true}"   # Relay EIN
ros2 service call /hexapod_safety_reset std_srvs/srv/Trigger {}            # sendet RESET
```
**Erfolg:** Relay klickt bei RESET AUS.

## T6 — on_deactivate droppt Relay

```bash
# Plugin läuft, Relay via T3 EIN, dann sauber stoppen:
# Strg+C im real.launch.py-Terminal
```
**Erfolg:** beim sauberen Shutdown klickt der Relay AUS (on_deactivate-Pfad).

---

## Findings-Tabelle (User füllt aus)

| Test | Status | Beobachtung |
|---|---|---|
| T1 FW-Host | | |
| T2 Plugin-Unit | | |
| T3 Service-Klick | | |
| T4 Watchdog-Drop | | |
| T5 RESET-Drop | | |
| T6 Deactivate-Drop | | |

## Rollback (falls FW Probleme macht)

```bash
sudo picotool load ~/hexapod_servo_driver/build/Hexapod_servo_driver.uf2.pre-0.1
sudo picotool reboot
```
