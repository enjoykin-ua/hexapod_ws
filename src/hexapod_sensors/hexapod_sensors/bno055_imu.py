"""
bno055_imu — HW-IMU-Treiber (BNO-055 -> ``/imu/data``), Block A5 Stufe 6 / IP1.

Liest die BNO-055 (Bosch 9-DOF, On-Chip-Fusion) am Pi ueber I2C (smbus2, NDOF-
Modus) und publisht ``sensor_msgs/Imu`` auf ``/imu/data`` — dasselbe Topic, das
in der Sim der gz-IMU-Sensor + ros_gz-Bridge erzeugt. Damit bleibt die komplette,
sim-verifizierte Balance-Pipeline (gait_node, tip_monitor, balance_controller,
imu_monitor) auf HW **unveraendert**.

Die Naht: der Konsument zieht roll/pitch direkt aus ``orientation`` und die
Kipprate aus ``angular_velocity.x/y`` — ``linear_acceleration`` wird NICHT
genutzt. Daher liest dieser Node nur **Quaternion + Gyro** (spart I2C-Last) und
laesst ``linear_acceleration`` leer (Kovarianz ``[0] = -1`` = „nicht geliefert").

Architektur (bewusste Trennung wie hexapod_kinematics):
- **Reine Konvertierung** (``s16``/``parse_quat``/``parse_gyro``/``build_imu``) —
  ROS-frei bzgl. I2C, unit-testbar ohne Hardware und ohne smbus2.
- **Node** (``Bno055Imu``) — smbus2-Init (NDOF, AXIS_MAP), 50-Hz-Timer,
  Robustheit (I2C-Fehler -> Tick droppen, kein Crash).

``smbus2`` wird **lazy** (erst im Node) importiert, damit die reinen Funktionen +
Unit-Tests am Dev ohne installiertes smbus2 laufen. Bereitstellung am Pi:
siehe ``project_finalization/imu_balance/stage_6_hw_imu_test_commands.md``.
"""

import math

import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import Imu
from std_msgs.msg import UInt8MultiArray


DEG2RAD = math.pi / 180.0

# --- BNO-055 Register + Konstanten (aus der Hello-World, imu_bno055.md) ---
REG_CHIP_ID = 0x00
REG_GYR_DATA = 0x14        # 6 B, X/Y/Z int16 LE, /16 -> dps
REG_QUA_DATA = 0x20        # 8 B, W/X/Y/Z int16 LE, /16384 -> einheitslos
REG_CALIB_STAT = 0x35      # 1 B: sys/gyr/acc/mag je 2 bit
REG_UNIT_SEL = 0x3B
REG_OPR_MODE = 0x3D
REG_PWR_MODE = 0x3E
REG_SYS_TRIGGER = 0x3F
REG_AXIS_MAP_CONFIG = 0x41
REG_AXIS_MAP_SIGN = 0x42

CHIP_ID_BNO055 = 0xA0
MODE_CONFIG = 0x00
MODE_NDOF = 0x0C
PWR_NORMAL = 0x00
UNIT_SEL_SI = 0x00         # m/s^2, dps, Grad, Celsius, Windows-Orientierung

QUAT_SCALE = 16384.0       # LSB pro Einheit (2^14)
GYR_LSB_PER_DPS = 16.0     # LSB pro dps


def s16(lsb, msb):
    """Zwei Bytes (LE) -> signed int16."""
    v = (msb << 8) | lsb
    return v - 65536 if v > 32767 else v


def parse_quat(data):
    """8 Roh-Bytes (BNO-Reihenfolge W,X,Y,Z, /16384) -> ROS (x, y, z, w)."""
    w = s16(data[0], data[1]) / QUAT_SCALE
    x = s16(data[2], data[3]) / QUAT_SCALE
    y = s16(data[4], data[5]) / QUAT_SCALE
    z = s16(data[6], data[7]) / QUAT_SCALE
    return x, y, z, w


def parse_gyro(data):
    """6 Roh-Bytes (X,Y,Z int16 LE, dps) -> (gx, gy, gz) in rad/s."""
    gx = s16(data[0], data[1]) / GYR_LSB_PER_DPS * DEG2RAD
    gy = s16(data[2], data[3]) / GYR_LSB_PER_DPS * DEG2RAD
    gz = s16(data[4], data[5]) / GYR_LSB_PER_DPS * DEG2RAD
    return gx, gy, gz


def euler_to_quat(roll, pitch, yaw):
    """(roll, pitch, yaw) in Radiant -> Quaternion (x, y, z, w), ZYX."""
    cr, sr = math.cos(roll * 0.5), math.sin(roll * 0.5)
    cp, sp = math.cos(pitch * 0.5), math.sin(pitch * 0.5)
    cy, sy = math.cos(yaw * 0.5), math.sin(yaw * 0.5)
    x = sr * cp * cy - cr * sp * sy
    y = cr * sp * cy + sr * cp * sy
    z = cr * cp * sy - sr * sp * cy
    w = cr * cp * cy + sr * sp * sy
    return x, y, z, w


def quat_mul(q1, q2):
    """Hamilton-Produkt q1 (x) q2, beide (x, y, z, w) -> (x, y, z, w)."""
    x1, y1, z1, w1 = q1
    x2, y2, z2, w2 = q2
    return (
        w1 * x2 + x1 * w2 + y1 * z2 - z1 * y2,
        w1 * y2 - x1 * z2 + y1 * w2 + z1 * x2,
        w1 * z2 + x1 * y2 - y1 * x2 + z1 * w2,
        w1 * w2 - x1 * x2 - y1 * y2 - z1 * z2,
    )


def build_imu(quat_raw, gyro_raw, roll_offset, pitch_offset, frame_id, stamp):
    """
    Roh-Bytes + Zero-Offset -> ``sensor_msgs/Imu`` (Fuellen der genutzten Felder).

    Der Zero-Offset dreht eine kleine Montage-Restschraege heraus, sodass eine
    physisch ebene Basis roll/pitch = 0 meldet: eine feste Korrektur-Quaternion
    ``q_corr = R(-roll_offset, -pitch_offset, 0)`` wird **vor** die (bereits
    AXIS_MAP-ausgerichtete) Sensor-Quaternion komponiert. Bei
    ``roll_offset = pitch_offset = 0`` ist ``q_corr`` die Identitaet -> die
    Quaternion wird unveraendert publiziert.

    ``linear_acceleration`` bleibt leer mit Kovarianz ``[0] = -1`` (ROS-Konvention
    „nicht geliefert"), da der Konsument sie nicht nutzt.
    """
    x, y, z, w = parse_quat(quat_raw)
    if roll_offset != 0.0 or pitch_offset != 0.0:
        q_corr = euler_to_quat(-roll_offset, -pitch_offset, 0.0)
        x, y, z, w = quat_mul(q_corr, (x, y, z, w))

    gx, gy, gz = parse_gyro(gyro_raw)

    msg = Imu()
    msg.header.frame_id = frame_id
    msg.header.stamp = stamp
    msg.orientation.x = x
    msg.orientation.y = y
    msg.orientation.z = z
    msg.orientation.w = w
    msg.angular_velocity.x = gx
    msg.angular_velocity.y = gy
    msg.angular_velocity.z = gz
    # Kleine Diagonal-Kovarianzen (der Konsument ignoriert sie; Wert nur damit
    # generische Tools die Message nicht als „ungueltig" verwerfen).
    msg.orientation_covariance[0] = 0.01
    msg.orientation_covariance[4] = 0.01
    msg.orientation_covariance[8] = 0.01
    msg.angular_velocity_covariance[0] = 0.001
    msg.angular_velocity_covariance[4] = 0.001
    msg.angular_velocity_covariance[8] = 0.001
    # linear_acceleration nicht geliefert -> Konvention: cov[0] = -1.
    msg.linear_acceleration_covariance[0] = -1.0
    return msg


class Bno055Imu(Node):
    """BNO-055 (I2C/NDOF) -> ``/imu/data`` (best_effort) + ``/imu/calib``."""

    def __init__(self):
        """Params deklarieren, Sensor initialisieren, Publisher + Timer aufsetzen."""
        super().__init__('bno055_imu')

        self.declare_parameter('i2c_bus', 1)
        self.declare_parameter('i2c_addr', 0x28)
        self.declare_parameter('frame_id', 'imu_link')
        self.declare_parameter('publish_rate', 50.0)
        # AXIS_MAP: Default = BNO-Werkseinstellung P1 (Identitaet). Die echte
        # Montage-Ausrichtung setzt IP2 (stage_6b) nach dem Kipp-Test.
        self.declare_parameter('axis_map_config', 0x24)
        self.declare_parameter('axis_map_sign', 0x00)
        # Zero-Offset (rad): Montage-Restschraege. IP1-Default 0, IP2 misst.
        self.declare_parameter('roll_offset', 0.0)
        self.declare_parameter('pitch_offset', 0.0)

        self._bus_num = int(self.get_parameter('i2c_bus').value)
        self._addr = int(self.get_parameter('i2c_addr').value)
        self._frame_id = str(self.get_parameter('frame_id').value)
        rate = float(self.get_parameter('publish_rate').value)
        self._axis_map_config = int(self.get_parameter('axis_map_config').value)
        self._axis_map_sign = int(self.get_parameter('axis_map_sign').value)
        self._roll_offset = float(self.get_parameter('roll_offset').value)
        self._pitch_offset = float(self.get_parameter('pitch_offset').value)

        self._bus = None
        self._init_sensor()   # raise RuntimeError bei Fatal (main faengt)

        self._imu_pub = self.create_publisher(
            Imu, '/imu/data', qos_profile_sensor_data,
        )
        self._calib_pub = self.create_publisher(UInt8MultiArray, '/imu/calib', 10)
        self._read_fail_logged = False
        self._timer = self.create_timer(1.0 / rate, self._tick)

        self.get_logger().info(
            f'bno055_imu aktiv: bus={self._bus_num} addr=0x{self._addr:02X} '
            f'@ {rate:.0f} Hz -> /imu/data (frame_id={self._frame_id}), '
            f'AXIS_MAP cfg=0x{self._axis_map_config:02X} '
            f'sign=0x{self._axis_map_sign:02X}, '
            f'offset roll={self._roll_offset:.4f} pitch={self._pitch_offset:.4f}'
        )

    def _init_sensor(self):
        """smbus2 oeffnen, CHIP_ID pruefen, NDOF + AXIS_MAP scharf schalten."""
        try:
            from smbus2 import SMBus
        except ImportError as exc:
            self.get_logger().fatal(
                'smbus2 nicht verfuegbar — am Pi installieren '
                '(siehe stage_6_hw_imu_test_commands.md, Schritt 1).'
            )
            raise RuntimeError('smbus2 import failed') from exc

        try:
            self._bus = SMBus(self._bus_num)
            chip = self._bus.read_byte_data(self._addr, REG_CHIP_ID)
        except OSError as exc:
            self.get_logger().fatal(
                f'I2C-Bus {self._bus_num} / Adresse 0x{self._addr:02X} nicht '
                f'erreichbar: {exc}. Verkabelung/Adresse pruefen.'
            )
            raise RuntimeError('I2C open failed') from exc

        if chip != CHIP_ID_BNO055:
            self.get_logger().fatal(
                f'CHIP_ID 0x{chip:02X} != 0x{CHIP_ID_BNO055:02X} — kein '
                f'BNO-055 auf 0x{self._addr:02X}. Adresse/Verkabelung pruefen.'
            )
            raise RuntimeError('wrong CHIP_ID')

        b = self._bus
        # CONFIG -> Units -> Normal-Power -> AXIS_MAP (nur in CONFIG!) -> NDOF.
        b.write_byte_data(self._addr, REG_OPR_MODE, MODE_CONFIG)
        self._sleep(0.025)
        b.write_byte_data(self._addr, REG_UNIT_SEL, UNIT_SEL_SI)
        b.write_byte_data(self._addr, REG_PWR_MODE, PWR_NORMAL)
        b.write_byte_data(self._addr, REG_SYS_TRIGGER, 0x00)
        b.write_byte_data(self._addr, REG_AXIS_MAP_CONFIG, self._axis_map_config)
        b.write_byte_data(self._addr, REG_AXIS_MAP_SIGN, self._axis_map_sign)
        b.write_byte_data(self._addr, REG_OPR_MODE, MODE_NDOF)
        self._sleep(0.02)

        calib = b.read_byte_data(self._addr, REG_CALIB_STAT)
        sys_c, gyr, acc, mag = self._split_calib(calib)
        self.get_logger().info(
            f'BNO-055 NDOF aktiv (CHIP_ID 0x{chip:02X}); Cal beim Start '
            f'sys={sys_c} gyr={gyr} acc={acc} mag={mag}'
        )

    @staticmethod
    def _sleep(seconds):
        """Blockierendes Sleep fuer die Init-Sequenz (nur beim Start)."""
        import time
        time.sleep(seconds)

    @staticmethod
    def _split_calib(calib):
        """CALIB_STAT-Byte -> (sys, gyr, acc, mag) je 0..3."""
        return (calib >> 6) & 3, (calib >> 4) & 3, (calib >> 2) & 3, calib & 3

    def _tick(self):
        """Ein Sample: Quaternion + Gyro + Cal lesen, Imu + Calib publishen."""
        try:
            quat_raw = self._bus.read_i2c_block_data(self._addr, REG_QUA_DATA, 8)
            gyro_raw = self._bus.read_i2c_block_data(self._addr, REG_GYR_DATA, 6)
            calib = self._bus.read_byte_data(self._addr, REG_CALIB_STAT)
        except OSError as exc:
            # Sporadisches Clock-Stretching o.ae.: Tick droppen, nie Garbage
            # publishen. Echte Ausfaelle faengt der /imu/data-Live-Guard downstream.
            self.get_logger().warning(
                f'I2C-Read fehlgeschlagen, Tick uebersprungen: {exc}',
                throttle_duration_sec=2.0,
            )
            self._read_fail_logged = True
            return

        stamp = self.get_clock().now().to_msg()
        msg = build_imu(
            quat_raw, gyro_raw, self._roll_offset, self._pitch_offset,
            self._frame_id, stamp,
        )
        self._imu_pub.publish(msg)

        sys_c, gyr, acc, mag = self._split_calib(calib)
        self._calib_pub.publish(
            UInt8MultiArray(data=[sys_c, gyr, acc, mag]),
        )

    def destroy_node(self):
        """Bus schliessen, dann regulaeres Node-Teardown."""
        if self._bus is not None:
            try:
                self._bus.close()
            except OSError:
                pass
            self._bus = None
        super().destroy_node()


def main(args=None):
    """Entry point — Fatal-Init faengt sauber ab (kein Traceback-Spam)."""
    rclpy.init(args=args)
    node = None
    try:
        node = Bno055Imu()
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    except RuntimeError:
        # Fatal wurde bereits geloggt (_init_sensor). Sauber beenden.
        pass
    finally:
        if node is not None:
            node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
