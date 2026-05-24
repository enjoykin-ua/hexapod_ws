# Servo-Real-Cal — Test Commands

> Manuelle Verifikation pro Stage. Stages 0/0.5/0.6/A sind eh durch
> `colcon test` gedeckt — die Snippets hier sind für **live-Smoke**
> mit echtem Plugin + Sim, falls man die ROS-Service-Pipeline auch
> end-to-end sehen will.
>
> User führt aus, gibt kurze Status-Meldungen zurück (z.B. „✓ Service
> antwortet success=true, message='...'"). Keine Vollausgabe nötig.
>
> Updated nach jeder Stage. Stages B-E folgen dann sie implementiert sind.

---

## Setup: Workspace gebaut + gesourct

```bash
cd ~/hexapod_ws
colcon build
source install/setup.bash
```

---

## Stage 0 — Plugin-Math-Fix

### Test 0.A: Unit-Tests grün

```bash
colcon test --packages-select hexapod_hardware
colcon test-result --test-result-base build/hexapod_hardware --verbose
```

**Erwartung:** 229+ tests, 0 errors, 0 failures (PTY-skip ok).

### Test 0.B: Roundtrip-Sanity in einem Python-Snippet (optional)

```bash
python3 -c "
import sys; sys.path.insert(0, 'install/hexapod_kinematics/lib/python3.12/site-packages')
# Stage 0 lives in C++ — siehe gtest. Hier kein extra manual check nötig.
print('Stage 0 verifiziert durch colcon test hexapod_hardware')
"
```

---

## Stage 0.5 — Plugin-Hard-Stop bei Pulse-OoR

### Test 0.5.A: Plugin im Loopback starten

In Terminal 1:
```bash
ros2 launch hexapod_bringup real.launch.py \
  serial_port:=/dev/null loopback_mode:=true
```

**Erwartung:**
- Log-Zeile: `Stage 0.5: /hexapod_safety_reset service ready`
- Plus Stage-0.6: `Stage 0.6: /hexapod_safety_freeze service ready`

### Test 0.5.B: Services sichtbar

In Terminal 2:
```bash
ros2 service list | grep hexapod_safety
```

**Erwartung:** zwei Einträge:
- `/hexapod_safety_reset`
- `/hexapod_safety_freeze`

### Test 0.5.C: Reset-Service ohne Freeze (idempotent)

```bash
ros2 service call /hexapod_safety_reset std_srvs/srv/Trigger
```

**Erwartung:**
- `success: True`
- `message: "safety_freeze was not active — nothing to clear"`

### Test 0.5.D: OoR triggern via Param + Reset

PWM-out-of-range manuell triggern ist schwer ohne URDF-Mismatch. Wenn
du das echt sehen willst:

```bash
# 1. Setze pulse_max für pin_0 auf einen winzigen Wert via Live-Param:
ros2 param set /hexapodsystem pin_0.pulse_max 1505

# 2. Kommandiere rad=+0.5 für leg_1_coxa via Joint-Trajectory:
ros2 topic pub --once /leg_1_controller/joint_trajectory \
  trajectory_msgs/msg/JointTrajectory \
  '{joint_names: ["leg_1_coxa_joint", "leg_1_femur_joint", "leg_1_tibia_joint"],
    points: [{positions: [0.5, 0.0, 0.0], time_from_start: {sec: 2}}]}'

# 3. Logs prüfen — SAFETY FREEZE-Log sollte erscheinen.

# 4. Reset:
ros2 service call /hexapod_safety_reset std_srvs/srv/Trigger
# Erwartung: success=True, message="safety_freeze cleared ..."

# 5. pulse_max zurücksetzen:
ros2 param set /hexapodsystem pin_0.pulse_max 2500
```

**Erwartung:** ERROR-Log mit `SAFETY FREEZE: joint 'leg_1_coxa_joint'`,
nach Reset success=True mit `cleared`-Message.

---

## Stage 0.6 — IK-Joint-Limit-Check + Freeze-Service

### Test 0.6.A: Unit-Tests grün

```bash
colcon test --packages-select hexapod_kinematics hexapod_gait
colcon test-result --test-result-base build/hexapod_kinematics --test-result-base build/hexapod_gait
```

**Erwartung:** alle pytest grün (32 + 27, je 1 skipped).

### Test 0.6.B: Freeze-Service direkt rufen

Plugin im Loopback (siehe 0.5.A):
```bash
ros2 service call /hexapod_safety_freeze std_srvs/srv/Trigger
```

**Erwartung:**
- `success: True`
- `message: "safety_freeze activated externally ..."`
- ERROR-Log: `SAFETY FREEZE: ... activated externally ...`

Dann reset:
```bash
ros2 service call /hexapod_safety_reset std_srvs/srv/Trigger
```

### Test 0.6.C: gait_node + IK-Joint-Limit-Bruch via Sim

Sim-Stack ohne hexapod_hardware-Plugin (gait nutzt sim-Plugin):
```bash
ros2 launch hexapod_bringup sim.launch.py
```

In zweitem Terminal: extreme `cmd_vel`, die IK out-of-Joint-Limit zwingt:
```bash
ros2 topic pub --rate 10 /cmd_vel geometry_msgs/Twist '{linear: {x: 0.5}}'
```

**Erwartung:**
- gait_node ERROR-Log: `gait_engine: IK failed for leg_X ...: joint limit ...`
- ERROR-Log: `/hexapod_safety_freeze service not available — proceeding with local stop only ...`
- gait stoppt lokal (keine neuen Trajectories) → JTC hält Beine

Diese Test verifiziert dass:
1. IK den joint-limit-Bruch wirft
2. gait_node das catched, lokal stoppt
3. Service-Fallback funktioniert (Sim ohne Plugin)

---

## Stage A — URDF-Macro-Refactor

### Test A.A: Unit-Tests grün

```bash
colcon test --packages-select hexapod_description
colcon test-result --test-result-base build/hexapod_description
```

**Erwartung:** 10/0/0.

### Test A.B: xacro-Output unverändert (Backwards-Compat)

```bash
# Diff gegen committed Reference (z.B. den nächsten Stage-A-Commit-Tag).
# Ohne Reference: Vorher xacro vor Commit + nachher xacro nach Commit
# diffen, beide identisch.
source install/setup.bash
xacro src/hexapod_description/urdf/hexapod.urdf.xacro | grep "<limit" | sort > /tmp/limits.txt
cat /tmp/limits.txt | head -5
```

**Erwartung:** 18 `<limit lower="-1.57" upper="1.57">` (Coxa+Femur) und
`<limit lower="-1.50" upper="1.50">` (Tibia) — globale Defaults greifen.

### Test A.C: Sim-Smoke (optional)

```bash
ros2 launch hexapod_bringup sim.launch.py
```

**Erwartung:** Hexapod spawnt in Stand-Pose, alle 6 Beine radial sichtbar
in Gazebo/RViz. Keine xacro-Errors in Launch-Logs.

---

## Stage B-E — folgen wenn implementiert

- B: `servo_mapping.yaml`-Smoke (Plugin-Init mit echten Cal-Werten)
- C: Direction-Cal interaktiv (HW + RViz parallel)
- D: URDF mit finalen rad-Limits + xacro-Diff vs vorher
- E: Sim-Walking + HW-Walking aufgebockt
