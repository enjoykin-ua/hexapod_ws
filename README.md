# Hexapod

A six-legged walking robot (18 servos) — fully simulated in **ROS 2 Jazzy** + **Gazebo Harmonic**
and portable 1:1 to real hardware (Servo2040 + Raspberry Pi) via `ros2_control`. Omnidirectional
walking, multiple gaits, switchable stance heights, sit/stand sequences, free-leg "show" poses, and
PS4 control (USB + Bluetooth).

<p align="center">
  <img src="docs/images/gazebo_sim.png" alt="Gazebo simulation" height="400"/>
  &nbsp;
  <img src="docs/images/rviz.png" alt="RViz (model + TF)" height="400"/>
  &nbsp;
  <img src="docs/images/rviz_reachability.png" alt="Reachability visualization" height="400"/>
</p>
<p align="center"><sub>Gazebo simulation &nbsp;·&nbsp; RViz (model + TF) &nbsp;·&nbsp; per-leg reachability visualization</sub></p>

<!-- TODO: add a YouTube demo as a clickable thumbnail (GitHub can't embed a player):
     [![Watch the demo](docs/images/video-thumbnail.png)](https://youtu.be/YOUR_VIDEO_ID) -->
> 🎥 _Video demo coming soon._

---

## Features

- **Omnidirectional walking** via `/cmd_vel` — forward/back, strafe, turn, arcs (analog, proportional).
- **4 gaits**, switchable on the fly: tripod, wave, tetrapod, ripple.
- **3 validated stance heights** (high/mid/low), switchable while standing (coupled reposition + height lerp).
- **Sit / stand / shutdown** as clean sequences (graceful power-off, comms-loss fail-safe).
- **Free-leg "show" pose:** support on 4 legs, 2 front legs steered freely by joystick (incl. tibia reach).
- **PS4 teleop:** USB **and** Bluetooth — omnidirectional sticks, dead-man, intent services.
- **Sim ↔ hardware identical:** the same high-level code runs in Gazebo and on the real servos
  (`ros2_control` abstraction, plugin chosen by a launch argument).
- **Pure-Python closed-form IK/FK** (testable without ROS) + offline validation tools
  (reach / CoG / torque analysis).

## Hardware (target platform)

| Component | Choice |
|---|---|
| Servo controller | Pimoroni **Servo2040** (USB-CDC), custom firmware ([repo](https://github.com/enjoykin-ua/hexapod_servo_driver)) |
| Coxa servos (6×) | Diymore **8120MG**, ~20 kg·cm, 270°, 4.8–8.4 V |
| Femur/Tibia servos (12×) | Miuzei **MS61**, ~35 kg·cm, 270°, 4.8–8.4 V |
| Compute | Raspberry **Pi 5** (8 GB), Ubuntu Server 24.04 arm64 (headless) |
| Power | 2S **LiPo** (7.4 V nom.) → [Power Supply HAT for Pi 5](https://www.electrokit.com/en/stromforsorjningskort-for-raspberry-pi-6-32vin-5a) (electrokit, 6–32 V in, 5 A) powers the Pi 5; the same battery also feeds the **Servo2040** (servo rail) |
| Power cutoff | **Relay Module DC 5 V 1-channel with optocoupler** — gates the servo rail (graceful power-on/off, software-controlled) |
| Input | PS4 **DualShock 4** (USB or Bluetooth) |

> The Servo2040 **firmware** lives in a separate repo:
> [`hexapod_servo_driver`](https://github.com/enjoykin-ua/hexapod_servo_driver)
> (wire protocol: [PROTOCOL.md](https://github.com/enjoykin-ua/hexapod_servo_driver/blob/main/PROTOCOL.md)).

## Software requirements

- **Ubuntu 24.04 LTS** (desktop for sim/dev, Pi Server arm64 for hardware)
- **ROS 2 Jazzy Jalisco**
- **Gazebo Harmonic** — exclusively via `ros-jazzy-ros-gz` (no second Gazebo package source)
- `ros2_control` + `gz_ros2_control`, `rviz2`, `rqt_reconfigure`
- Python 3.12 (rclpy) · C++ (hardware interface, pluginlib)

## Quickstart (simulation)

```bash
cd ~/hexapod_ws
colcon build --symlink-install
source install/setup.bash
```

Each step in its own terminal (`source install/setup.bash` in each):

**1 — Gazebo** (physics + the robot):
```bash
ros2 launch hexapod_bringup sim.launch.py
```

**2 — RViz** (optional — ROS-side view; the `-d` config loads the robot model + TF
automatically, no manual "Add" needed):
```bash
ros2 run rviz2 rviz2 \
  -d $(ros2 pkg prefix hexapod_description)/share/hexapod_description/config/view.rviz \
  --ros-args -p use_sim_time:=true
```

> 💡 **Just want to inspect the model** (no Gazebo / no gait stack)? One command brings up
> RViz fully preconfigured (model + joint sliders):
> ```bash
> ros2 launch hexapod_description display.launch.py
> ```
> _(Standalone only — don't run it together with `sim.launch.py`; it starts its own
> robot_state_publisher + joint_state_publisher_gui.)_

**3 — Gait stack** (the robot stands up; stance mode "mid"):
```bash
ros2 launch hexapod_gait gait.launch.py \
  robot_description_file:=$(ros2 pkg prefix hexapod_description)/share/hexapod_description/urdf/hexapod.urdf.xacro \
  use_sim_time:=true
```

**4 — Drive** (or use a PS4 controller instead, see [Controls](#controls-ps4-dualshock-4)):
```bash
ros2 topic pub --once /cmd_vel geometry_msgs/msg/Twist "{linear: {x: 0.03}}"   # forward
ros2 topic pub --once /cmd_vel geometry_msgs/msg/Twist "{}"                     # stop
```

**PS4 controller** (replaces step 4; USB, or Bluetooth with `controller:=ps4_bt`):
```bash
ros2 launch hexapod_teleop joy_teleop.launch.py controller:=ps4_usb
```

### Useful commands

```bash
# Behaviours (services) — work in STANDING
ros2 service call /hexapod_sit_down     std_srvs/srv/Trigger "{}"            # sit down (rest)
ros2 service call /hexapod_stand_up     std_srvs/srv/Trigger "{}"            # stand up again
ros2 service call /hexapod_cycle_gait   std_srvs/srv/SetBool "{data: true}" # next gait (false = prev)
ros2 service call /hexapod_cycle_stance std_srvs/srv/SetBool "{data: true}" # higher stance (false = lower)
ros2 service call /hexapod_show_toggle  std_srvs/srv/Trigger "{}"           # enter / leave show pose

# Live parameter tuning (step height, cycle time, scales, …)
ros2 run rqt_reconfigure rqt_reconfigure        # GUI; many params are STANDING-only

# Diagnostics
ros2 control list_controllers                   # expect 1 JSB + 6 JTC, all "active"
ros2 topic list                                 # /cmd_vel, /cmd_show, /joint_states, …
```

## Controls (PS4 DualShock 4)

> **R1 is the dead-man** — driving and front-leg control only work while R1 is held.

| Input | Action | Notes |
|---|---|---|
| **Left stick** | Drive omnidirectional — Y = forward/back, X = strafe (analog) | hold R1 |
| **Right stick X** | Turn (yaw) | hold R1 |
| **R1** (hold) | **Dead-man** — motion only while held | safety, required |
| **L1** (hold) | Slow / precise — half speed | teleop-local |
| **L2 / R2** (without R1) | **Stance height** down / up (low ↔ mid ↔ high) | reposition + height lerp; STANDING only |
| **D-pad ←/→** | **Gait** cycle (tripod → wave → tetrapod → ripple) | STANDING only |
| **D-pad ↑/↓** | **Step length** (max) bigger / smaller | 0.02–0.089 m, 0.01 steps |
| **△ Triangle** | **Sit / stand** toggle | resolved by robot state |
| **○ Circle** (long-press) | **Shutdown** (sit down + relay off) | deliberate, terminal |
| **✕ Cross** (long-press) | Enter / leave **show pose** | |
| **In show + R1 — left / right stick** | Move front legs leg_6 / leg_1: X = sideways, Y = up/down | SHOW_ACTIVE only |
| **In show + R1 — L2 / R2** | **Tibia reach** leg_6 / leg_1 (extend leg, tibia opens up) | SHOW_ACTIVE only |

**Stance heights** (cycled with L2/R2): `high` (−0.140 m) · `mid` (−0.100 m, boot default) · `low` (−0.070 m).
Full reference (stance values, gait × height stability sweet-spots, axis/sign tuning):
[`project_finalization/C_teleop.md`](project_finalization/C_teleop.md).

## Packages

| Package | Purpose |
|---|---|
| `hexapod_description` | URDF/Xacro model, RViz display, `ros2_control` + Gazebo config |
| `hexapod_gazebo` | Plain Gazebo sim bringup (physics/friction) |
| `hexapod_control` | `ros2_control` config (`controllers.yaml` + `controllers.real.yaml`: JSB + 6 JTC) |
| `hexapod_bringup` | `sim.launch.py` + `real.launch.py` (sim ↔ HW via `use_sim`) |
| `hexapod_kinematics` | Pure-Python IK/FK + joint-limit check |
| `hexapod_sensors` | Gazebo→ROS foot-contact adapter |
| `hexapod_gait` | Gait engine + `gait_node` (state machine: stand/walk/stop/sit/standup/reposition/show/stance-switch), gaits, stance modes |
| `hexapod_teleop` | PS4 USB + Bluetooth → `/cmd_vel` + `/cmd_show` + intent services |
| `hexapod_hardware` | C++ `HardwareInterface` (pluginlib), Servo2040 USB-CDC |

## Tools (`tools/`)

| Tool | Purpose |
|---|---|
| `walking_envelope_check.py` | Offline walking-envelope check (in-reach / in-limit over radial × height × step length × lift) |
| `standup_envelope_check.py` | Kinematic check of the stand-up / reposition path |
| `show_pose_cog_check.py` | Show support pose: CoG margin + front-leg reach |
| `torque_sweep.py` | Joint holding torques / heat utilization (CoG-based load model) |
| `hexapod-shell-aliases.sh` | Opt-in bash aliases: save/load calibration, walking presets |

## Documentation

| Where | Contents |
|---|---|
| [`PHASE.md`](PHASE.md) | **Current status** + phase / block overview |
| [`PHASE_NOTES.md`](PHASE_NOTES.md) | Phase retros + archived early build reports |
| [`project_finalization/`](project_finalization/00_backlog.md) | Finalization blocks A–E (locomotion, teleop, stance modes, show pose) + backlog |
| [`project_architecture/`](project_architecture/00_overview.md) | Architecture overview, AI-navigation ("I change X → where"), tool catalog |
| [`docs/`](docs/00_conventions.md) | Phases 0–6 (sim), conventions, [hardware-change workflow](docs/01_hardware_change_workflow.md) |
| `docs_raspi/` | Phases 7+ (hardware bench, Pi platform) |
| [`CLAUDE.md`](CLAUDE.md) | Project conventions + working agreement (mainly internal/AI) |

> Internal docs are in German; this README is the English entry point.

## Status

Sim phases (0–6) and hardware bench (7, 9–11) done; locomotion, teleop, stance modes and the show
pose are complete in simulation. **Next up:** hardware bring-up — Pi platform (phase 12) + electronics
(phase 8). Details: [`PHASE.md`](PHASE.md).

## License

[Apache-2.0](LICENSE) — © 2026 enjoykin.
