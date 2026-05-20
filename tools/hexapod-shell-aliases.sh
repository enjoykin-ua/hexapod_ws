# =============================================================================
# Hexapod convenience shell helpers — Phase 11 Stage D (D-Q3 Option A)
# =============================================================================
#
# Optional source-able Bash functions, die wiederkehrende ros2-Befehle
# rund um Gait-Tuning und Plugin-Cal-Persistenz verkürzen. Speziell
# nützlich bei intensiven Cal-Sessions (Phase 13 Voll-Bringup) und bei
# Demos / Workshops, wo Tippfehler unter Zeitdruck vermieden werden
# sollen.
#
# ─────────────────────────────────────────────────────────────────────────────
# Einbinden in ~/.bashrc (einmaliger Setup-Schritt, opt-in):
#
#   echo 'source ~/hexapod_ws/tools/hexapod-shell-aliases.sh' >> ~/.bashrc
#
# Oder pro Session:
#
#   source ~/hexapod_ws/tools/hexapod-shell-aliases.sh
#
# ─────────────────────────────────────────────────────────────────────────────
# Verfügbare Funktionen:
#
#   hexapod-save-walking-params <name>
#       Speichert die aktuellen /gait_node-Parameter als Preset-YAML.
#       File landet unter src/hexapod_gait/config/presets/<name>.yaml.
#
#   hexapod-load-walking-preset <name>
#       Startet gait_node mit dem benannten Preset-File. Roboter sollte
#       vorher in Standing-Pose stehen (sim oder real_launch).
#
#   hexapod-save-cal
#       Triggert den Plugin-/save_calibration-Service (Stage B). Schreibt
#       aktuelle Cal-Werte zurück in servo_mapping.yaml, mit Timestamp-
#       Backup als .bak-YYYY-MM-DDTHH-MM-SS.
#
#   hexapod-list-presets
#       Listet vorhandene Gait-Presets im Stage-D-Verzeichnis.
#
#   hexapod-list-cal-backups
#       Listet alle servo_mapping.yaml.bak-*-Backups mit Timestamps.
#
# ─────────────────────────────────────────────────────────────────────────────
# Beispiel-Cal-Session-Workflow:
#
#   1. Sim/Bench starten:
#        ros2 launch hexapod_bringup real.launch.py loopback_mode:=true
#
#   2. rqt aufmachen + Pin-Slider verschieben (siehe
#      docs_raspi/phase_11_rqt_setup.md)
#
#   3. Cal speichern:
#        hexapod-save-cal
#
#   4. Backup verifizieren:
#        hexapod-list-cal-backups
#
# ─────────────────────────────────────────────────────────────────────────────
# Bash-only: Funktionen sind weitgehend zsh-kompatibel, fish funktioniert
# nicht. Hardcoded $HOME-relative Pfade (~/hexapod_ws) — bei abweichendem
# Workspace-Pfad muss die HEXAPOD_WS-Variable unten überschrieben werden.
# =============================================================================

# Workspace-Root — override per Environment falls anderer Pfad:
#   export HEXAPOD_WS=/path/to/hexapod_ws
HEXAPOD_WS="${HEXAPOD_WS:-${HOME}/hexapod_ws}"

# Speichere aktuelle /gait_node-Parameter als Preset.
# Hinweis: `ros2 param dump` (Jazzy) gibt ausschließlich auf stdout aus —
# die alten --output-dir/--filename-Args aus früheren ROS-Versionen
# existieren nicht mehr. Daher Redirect via `>`.
hexapod-save-walking-params() {
  local name="${1:?usage: hexapod-save-walking-params <preset-name>}"
  local out="${HEXAPOD_WS}/src/hexapod_gait/config/presets/${name}.yaml"
  ros2 param dump /gait_node > "${out}"
  echo "Saved /gait_node params to ${out}"
}

# Lade ein Preset durch gait.launch.py-params_file-Arg.
hexapod-load-walking-preset() {
  local name="${1:?usage: hexapod-load-walking-preset <preset-name>}"
  ros2 launch hexapod_gait gait.launch.py \
    "params_file:=${HEXAPOD_WS}/src/hexapod_gait/config/presets/${name}.yaml"
}

# Trigger Plugin-Cal-Save (Stage B). Erzeugt .bak-<timestamp> +
# überschreibt servo_mapping.yaml mit Live-Werten.
hexapod-save-cal() {
  ros2 service call /save_calibration std_srvs/srv/Trigger
}

# Liste vorhandene Gait-Presets.
hexapod-list-presets() {
  ls -1 "${HEXAPOD_WS}/src/hexapod_gait/config/presets/" 2>/dev/null \
    | grep -E '\.yaml$' \
    || echo "(no presets found in ${HEXAPOD_WS}/src/hexapod_gait/config/presets/)"
}

# Liste vorhandene Plugin-Cal-Backups mit Größe + Datum.
hexapod-list-cal-backups() {
  ls -lh "${HEXAPOD_WS}/src/hexapod_hardware/config/"servo_mapping.yaml.bak-* 2>/dev/null \
    || echo "(no cal-backups found — no /save_calibration calls yet)"
}
