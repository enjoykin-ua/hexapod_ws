# Teleop Live-Scales (TLS) — Test-Befehle (Rubicon-Welt)

> Du führst die Tests aus, knappe Status-Meldung zurück. **Ziel:** belegen, dass die Tempo-Parameter
> des Teleop (`linear_x_scale` usw.) jetzt **live** wirken — `ros2 param set /joy_to_twist …` ändert das
> Verhalten **sofort, ohne Teleop-Neustart**, und ungültige Werte werden sauber abgelehnt. Getestet
> direkt in der **Rubicon-Welt** mit PS4-Controller.

## Konventionen
- **Sourcing** je Terminal: `source /opt/ros/jazzy/setup.bash && source ~/hexapod_ws/install/setup.bash`
- **Daemon:** vor dem ersten `param set` einmal `ros2 daemon stop`.
- **Bauen vorab** (falls noch nicht): `colcon build --packages-select hexapod_teleop --symlink-install`
- Live-Params (neu): `linear_x_scale`, `linear_y_scale`, `angular_z_scale`, `slow_factor`, `deadzone`.

## Setup (3 Terminals, granular — du parametrisierst selbst)

**T1 — Welt + Spawn:**
```bash
ros2 launch hexapod_bringup rubicon.launch.py
```

**T2 — Aufstehen (mit Reserve fürs Tempo, damit die Scale-Änderung sichtbar wird):**
```bash
ros2 launch hexapod_gait gait.launch.py cycle_time:=1.5 step_length_max:=0.15
```
> `cycle_time 1.5` hebt die Tempo-Decke `linear_max` auf ~0.19 m/s — sonst clamped die Engine und die
> Scale-Änderung wäre nicht spürbar. Weitere Gang-Werte nach Belieben (`step_height:=…` usw.).

**T3 — PS4-Teleop (ganz normal, KEIN Override mehr nötig):**
```bash
ros2 launch hexapod_teleop joy_teleop.launch.py controller:=ps4_bt
#   USB: controller:=ps4_usb
```

---

## Presets (zum Rauskopieren)

> `cycle_time` ist **standing_only** → nur im **STANDING** setzen (Stick los) **oder** beim
> `gait.launch.py`-Start als Arg. Der Rest (`step_length_max`, `step_height`, alle Scales) ist **live**.

### „Nice" — flott + große Schritte (User-Befund, Sim)
```bash
ros2 daemon stop
ros2 param set /gait_node cycle_time 1.5
ros2 param set /gait_node step_length_max 0.15
ros2 param set /gait_node step_height 0.04
ros2 param set /joy_to_twist linear_x_scale 0.2
ros2 param set /joy_to_twist linear_y_scale 0.14
ros2 param set /joy_to_twist angular_z_scale 1.2
```
> ⚠️ Aggressiv: `step_length_max 0.15` + schnelles Drehen (`angular_z_scale 1.2`) schiebt den Fuß bei
> „voll vor **und** hart drehen" gelegentlich ~1–3 mm über die Bein-Reichweite → vereinzelte
> `IK failed … out of reach`-Meldungen (harmlos, s. u.). Wenn dich das stört: `step_length_max 0.12`
> oder `angular_z_scale 0.9`, oder Füße reinholen (`gait.launch.py radial_distance:=0.150`, standing_only).

### Zurück auf Default (Original)
```bash
ros2 daemon stop
ros2 param set /gait_node step_length_max 0.05
ros2 param set /gait_node step_height 0.04
ros2 param set /joy_to_twist linear_x_scale 0.05
ros2 param set /joy_to_twist linear_y_scale 0.05
ros2 param set /joy_to_twist angular_z_scale 0.46
# cycle_time nur im STANDING (oder beim Launch weglassen = Default 2.0):
ros2 param set /gait_node cycle_time 2.0
```

---

## T1 — Live-Tempo am Stick (der Kern-Beweis)

**▶ niedrig → langsam:**
```bash
ros2 daemon stop
ros2 param set /joy_to_twist linear_x_scale 0.05
```
→ R1 halten + linker Stick **voll vor**: er läuft **langsam** (kleine Schritte).

**▶ live hochsetzen (Teleop läuft weiter!):**
```bash
ros2 param set /joy_to_twist linear_x_scale 0.20
```
**✅ Erwartung:** **ohne** Neustart, **sofort** beim nächsten Stick-Vollausschlag → **deutlich
schneller + große Schritte**. (Früher: 0.05 vs 999 = kein Unterschied, weil nur beim Start gelesen.)

Gegenprobe runter:
```bash
ros2 param set /joy_to_twist linear_x_scale 0.08
```
→ wieder langsamer. Beleg: der Wert wirkt live in beide Richtungen.

---

## T1b — die anderen zwei Geschwindigkeits-Scales live (seitwärts + drehen)

Es gibt **drei** Tempo-Scales (alle live):
- `linear_x_scale` — vor/zurück (linker Stick **Y**)
- `linear_y_scale` — **seitwärts/Strafe** (linker Stick **X**)
- `angular_z_scale` — **drehen** (rechter Stick **X**)

**▶ Seitwärts (`linear_y_scale`):**
```bash
ros2 param set /joy_to_twist linear_y_scale 0.05      # langsam
# R1 + linker Stick voll SEITWÄRTS → langsames Strafen
ros2 param set /joy_to_twist linear_y_scale 0.18      # live hoch
```
**✅ Erwartung:** nächster seitlicher Stick-Vollausschlag → **sofort schnelleres Strafen**, ohne Neustart.

**▶ Drehen (`angular_z_scale`):**
```bash
ros2 param set /joy_to_twist angular_z_scale 0.30     # langsam drehen
# R1 + rechter Stick X → langsames Drehen
ros2 param set /joy_to_twist angular_z_scale 1.00     # live hoch
```
**✅ Erwartung:** rechter Stick → **sofort schnelleres Drehen auf der Stelle**, ohne Neustart.

---

## T2 — Ungültige Werte werden abgelehnt (Wert bleibt erhalten)

```bash
ros2 param set /joy_to_twist linear_x_scale -0.1     # negativ
ros2 param set /joy_to_twist slow_factor 2.0         # außerhalb [0,1]
ros2 param set /joy_to_twist deadzone 1.0            # außerhalb [0,1)
```
**✅ Erwartung:** jeder dieser Aufrufe meldet `Setting parameter failed` (bzw. `successful=False` mit
Begründung). Der vorherige gültige Wert bleibt — prüfen:
```bash
ros2 param get /joy_to_twist linear_x_scale          # zeigt noch 0.08, nicht -0.1
```

---

## T3 — slow_factor & deadzone live

```bash
ros2 param set /joy_to_twist slow_factor 0.3         # L1 = noch langsamer
ros2 param set /joy_to_twist deadzone 0.15           # größere Stick-Totzone
```
**✅ Erwartung:** **L1 halten** + Stick → spürbar langsamer (slow_factor wirkt sofort); mit großer
Deadzone reagiert der Stick erst nach mehr Auslenkung. Beides ohne Neustart.

---

## T4 (optional) — volles „groß + schnell" am Controller

```bash
# im STANDING (Stick los) — cycle_time ist standing_only:
ros2 param set /gait_node cycle_time 1.5
ros2 param set /gait_node step_length_max 0.15
# Stick-Tempo passend zur Tempo-Decke:
ros2 param set /joy_to_twist linear_x_scale 0.20
```
→ R1 + Stick voll: große Schritte UND flott — alles live eingestellt, kein Datei-Edit, kein Neustart.

---

## Rückmeldung an mich (knapp genügt)
- T1: wirkt `linear_x_scale` **live** (0.05 langsam → 0.20 schnell, ohne Neustart)? In beide Richtungen?
- T1b: `linear_y_scale` (seitwärts) **und** `angular_z_scale` (drehen) auch live spürbar?
- T2: werden negative / Out-of-Range-Werte **abgelehnt** und der alte Wert bleibt (`param get`)?
- T3: `slow_factor` (L1) und `deadzone` live spürbar?
- Auffälligkeiten: verzögert, gar nicht, Log-Fehler?
