"""
Unit-Tests fuer die reine Konvertierung in bno055_imu (Block A5 Stufe 6 / IP1).

HW-frei: keine I2C/smbus2, nur die reinen Funktionen (``s16``/``parse_quat``/
``parse_gyro``/``build_imu``). Laeuft in CI am Dev ohne Sensor.
"""

import math

from builtin_interfaces.msg import Time
from hexapod_sensors.bno055_imu import (
    build_imu,
    DEG2RAD,
    euler_to_quat,
    parse_gyro,
    parse_quat,
    s16,
)


def _le_bytes(value):
    """Signed int -> 2 Bytes little-endian (wie das BNO-Register liefert)."""
    u = value & 0xFFFF
    return [u & 0xFF, (u >> 8) & 0xFF]


def _quat_to_raw(x, y, z, w):
    """ROS (x,y,z,w) -> 8 Roh-Bytes in BNO-Reihenfolge W,X,Y,Z (/16384)."""
    out = []
    for comp in (w, x, y, z):
        out += _le_bytes(int(round(comp * 16384.0)))
    return out


def _quat_to_roll_pitch(x, y, z, w):
    """Quaternion -> (roll, pitch) rad (identisch zu tip_monitor)."""
    roll = math.atan2(2.0 * (w * x + y * z), 1.0 - 2.0 * (x * x + y * y))
    pitch = math.asin(max(-1.0, min(1.0, 2.0 * (w * y - z * x))))
    return roll, pitch


def test_s16_signed():
    """s16 dekodiert LE-Bytes vorzeichenrichtig."""
    assert s16(0x00, 0x40) == 16384       # +2^14
    assert s16(0x00, 0x00) == 0
    assert s16(0xF0, 0xFF) == -16         # 0xFFF0
    assert s16(0x00, 0x80) == -32768      # kleinster int16


def test_parse_quat_identity():
    """W=1 (raw 16384), Rest 0 -> ROS (0,0,0,1)."""
    data = _le_bytes(16384) + _le_bytes(0) + _le_bytes(0) + _le_bytes(0)
    x, y, z, w = parse_quat(data)
    assert (x, y, z, w) == (0.0, 0.0, 0.0, 1.0)


def test_parse_quat_order_and_scale():
    """BNO-Reihenfolge W,X,Y,Z wird korrekt auf ROS x,y,z,w gemappt + /16384."""
    # W=0, X=16384, Y=-16384, Z=8192  ->  x=1, y=-1, z=0.5, w=0
    data = _le_bytes(0) + _le_bytes(16384) + _le_bytes(-16384) + _le_bytes(8192)
    x, y, z, w = parse_quat(data)
    assert math.isclose(x, 1.0)
    assert math.isclose(y, -1.0)
    assert math.isclose(z, 0.5)
    assert math.isclose(w, 0.0)


def test_parse_gyro_scale_and_sign():
    """dps/16 * pi/180 -> rad/s, Vorzeichen erhalten."""
    # X=+16 LSB = +1 dps, Y=-16 LSB = -1 dps, Z=+160 LSB = +10 dps
    data = _le_bytes(16) + _le_bytes(-16) + _le_bytes(160)
    gx, gy, gz = parse_gyro(data)
    assert math.isclose(gx, 1.0 * DEG2RAD)
    assert math.isclose(gy, -1.0 * DEG2RAD)
    assert math.isclose(gz, 10.0 * DEG2RAD)


def test_build_imu_fields():
    """frame_id/stamp, Gyro->angular_velocity, linear_acceleration nicht geliefert."""
    quat = _quat_to_raw(0.0, 0.0, 0.0, 1.0)
    gyro = _le_bytes(16) + _le_bytes(0) + _le_bytes(-32)   # gx=+1dps, gz=-2dps
    stamp = Time(sec=42, nanosec=7)
    msg = build_imu(quat, gyro, 0.0, 0.0, 'imu_link', stamp)

    assert msg.header.frame_id == 'imu_link'
    assert msg.header.stamp.sec == 42 and msg.header.stamp.nanosec == 7
    assert math.isclose(msg.angular_velocity.x, 1.0 * DEG2RAD)
    assert math.isclose(msg.angular_velocity.y, 0.0)
    assert math.isclose(msg.angular_velocity.z, -2.0 * DEG2RAD)
    # Konvention „nicht geliefert": cov[0] == -1.
    assert msg.linear_acceleration_covariance[0] == -1.0
    assert msg.linear_acceleration.x == 0.0
    # Orientierung unveraendert durchgereicht (Offset 0).
    assert math.isclose(msg.orientation.w, 1.0)


def test_zero_offset_identity():
    """roll0=pitch0=0 -> Quaternion bit-genau wie parse_quat (keine Drehung)."""
    # Beliebige gekippte Quaternion (roll=0.2, pitch=-0.1).
    x, y, z, w = euler_to_quat(0.2, -0.1, 0.0)
    quat = _quat_to_raw(x, y, z, w)
    gyro = _le_bytes(0) + _le_bytes(0) + _le_bytes(0)
    msg = build_imu(quat, gyro, 0.0, 0.0, 'imu_link', Time())

    ref_x, ref_y, ref_z, ref_w = parse_quat(quat)
    assert msg.orientation.x == ref_x
    assert msg.orientation.y == ref_y
    assert msg.orientation.z == ref_z
    assert msg.orientation.w == ref_w


def test_zero_offset_cancels_mounting_tilt_any_yaw():
    """
    Body-frame-Offset dreht die Montage-Restschraege bei JEDEM yaw auf ~0.

    Regressionstest fuer den IP2-Bug: eine World-frame-/Links-Komposition wuerde
    bei yaw != 0 die pitch verschlimmern (HW-Befund: pitch 3.3 -> 6.5 bei
    yaw -112 Grad). Die Rechts-Komposition in build_imu ist yaw-unabhaengig.
    """
    r0, p0 = 0.05, -0.03   # Montage-Restschraege (rad)
    gyro = _le_bytes(0) + _le_bytes(0) + _le_bytes(0)
    for yaw in (-3.0, -1.95, -1.0, 0.0, 1.2, 2.7):
        # ebene Basis (physisch roll=pitch=0), Sensor meldet r0/p0 bei diesem yaw
        x, y, z, w = euler_to_quat(r0, p0, yaw)
        quat = _quat_to_raw(x, y, z, w)
        msg = build_imu(quat, gyro, r0, p0, 'imu_link', Time())
        roll, pitch = _quat_to_roll_pitch(
            msg.orientation.x, msg.orientation.y,
            msg.orientation.z, msg.orientation.w,
        )
        assert abs(roll) < 1e-2, f'yaw={yaw}: roll={roll}'
        assert abs(pitch) < 1e-2, f'yaw={yaw}: pitch={pitch}'
