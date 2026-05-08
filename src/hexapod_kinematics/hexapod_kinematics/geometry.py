"""
Geometric helpers (rotation, translation, frame conversions).

Implementiert in Stufe B von Phase 5 (siehe ``docs/phase_5_progress.md``).
Erwartete API (Konzept-Stand):

- ``rotate_z(point, yaw)`` — Punkt um Z-Achse rotieren.
- ``base_to_leg_frame(point_in_base, leg_cfg)`` — Punkt von base_link
  ins Bein-Frame transformieren (für IK-Eingabe).
- ``leg_to_base_frame(point_in_leg, leg_cfg)`` — Inverse (für Debug-Output).
"""
