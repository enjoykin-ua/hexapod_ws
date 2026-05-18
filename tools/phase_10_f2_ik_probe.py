#!/usr/bin/env python3
# Copyright 2026 enjoykin
# Licensed under the Apache License, Version 2.0
"""
Phase 10 Stage F.2 — direct IK probe for leg_6.

Calls hexapod_kinematics.leg_ik() directly with two foot-target points
in base_link frame, generates a 2-point JointTrajectory (foot lifts
vertically by ~3 cm), and sends it via the FollowJointTrajectory action
to leg_6_controller.

This is a diagnostic probe — it isolates IK + JTC + plugin + firmware
+ servo from the gait_node layer. If F.2 works but F.3 (gait_node)
doesn't, the issue is in gait_node, not the IK pipeline.

Usage:
    source ~/hexapod_ws/install/setup.bash
    # In another terminal: ros2 launch hexapod_bringup real.launch.py loopback_mode:=false
    python3 ~/hexapod_ws/tools/phase_10_f2_ik_probe.py
"""

import sys

import rclpy
from rclpy.action import ActionClient
from rclpy.node import Node

from builtin_interfaces.msg import Duration
from control_msgs.action import FollowJointTrajectory
from trajectory_msgs.msg import JointTrajectory, JointTrajectoryPoint

from hexapod_kinematics.config import HEXAPOD
from hexapod_kinematics.geometry import base_to_leg_frame
from hexapod_kinematics.leg_ik import IKError, leg_ik


# Foot target points in base_link frame (meters).
#
# Phase 10 Stage F.2 targets — picked to land in the middle of leg_6's
# reachable workspace with the post-2026-05-17 leg geometry
# (L_TIBIA = 0.200 m). The first set of defaults from the parent plan
# (0.15, 0.10, -0.10) was too close to the leg root after the tibia
# update — IK rejected it as below the |L_t - L_f| = 0.120 m lower
# reach bound.
#
# These values mirror the Phase-5/HW gait stand pose geometry
# (radial_distance=0.27 m in leg frame, body_height=-0.047 m) projected
# back into base_link via leg_6's mount transform (yaw=+pi/4).
GOAL_A_BASE = (0.278, 0.256, -0.047)  # Stand pose for leg_6
GOAL_B_BASE = (0.278, 0.256, -0.017)  # +3 cm vertical (tripod foot lift)


def main() -> int:
    rclpy.init()
    node = Node("phase_10_f2_ik_probe")
    log = node.get_logger()

    leg6 = HEXAPOD.by_name("leg_6")

    # IK works in the leg-local frame, so we transform the base-frame
    # targets first.
    try:
        a_leg = base_to_leg_frame(GOAL_A_BASE, leg6)
        b_leg = base_to_leg_frame(GOAL_B_BASE, leg6)
        angles_a = leg_ik(*a_leg, leg6)
        angles_b = leg_ik(*b_leg, leg6)
    except IKError as exc:
        log.error(f"IK failed: {exc}")
        log.error(
            "Target point out of reach. Either the leg geometry doesn't "
            "match URDF (F.1 check), or pick different GOAL_A_BASE / "
            "GOAL_B_BASE values."
        )
        rclpy.shutdown()
        return 1

    log.info(f"Goal A (base={GOAL_A_BASE}, leg={a_leg}) -> {angles_a}")
    log.info(f"Goal B (base={GOAL_B_BASE}, leg={b_leg}) -> {angles_b}")

    client = ActionClient(
        node,
        FollowJointTrajectory,
        "/leg_6_controller/follow_joint_trajectory",
    )
    if not client.wait_for_server(timeout_sec=5.0):
        log.error(
            "Action server /leg_6_controller/follow_joint_trajectory not "
            "available after 5s. Is real.launch.py running?"
        )
        rclpy.shutdown()
        return 2

    traj = JointTrajectory()
    traj.joint_names = [
        "leg_6_coxa_joint",
        "leg_6_femur_joint",
        "leg_6_tibia_joint",
    ]

    p_a = JointTrajectoryPoint()
    p_a.positions = list(angles_a)
    p_a.time_from_start = Duration(sec=2, nanosec=0)

    p_b = JointTrajectoryPoint()
    p_b.positions = list(angles_b)
    p_b.time_from_start = Duration(sec=4, nanosec=0)

    traj.points = [p_a, p_b]

    goal_msg = FollowJointTrajectory.Goal()
    goal_msg.trajectory = traj

    log.info("Sending goal...")
    send_future = client.send_goal_async(goal_msg)
    rclpy.spin_until_future_complete(node, send_future)
    goal_handle = send_future.result()
    if goal_handle is None or not goal_handle.accepted:
        log.error("Goal rejected by JTC.")
        rclpy.shutdown()
        return 3
    log.info("Goal accepted, waiting for result...")

    result_future = goal_handle.get_result_async()
    rclpy.spin_until_future_complete(node, result_future)
    result = result_future.result()
    log.info(f"Result status: {result.status}, error_code: {result.result.error_code}")

    rclpy.shutdown()
    return 0


if __name__ == "__main__":
    sys.exit(main())
