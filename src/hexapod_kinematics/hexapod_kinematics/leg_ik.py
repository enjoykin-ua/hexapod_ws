"""
Inverse kinematics per leg.

Implementiert in Stufe B von Phase 5 (siehe ``docs/phase_5_progress.md``).
Erwartete API (Konzept-Stand, finalisiert in Stufe-B-Konzept):

- ``leg_ik(x, y, z, leg_cfg) -> (theta_coxa, theta_femur, theta_tibia)``
- ``leg_fk(theta_coxa, theta_femur, theta_tibia, leg_cfg) -> (x, y, z)``
- ``IKError`` (Exception) bei out-of-reach.
"""
