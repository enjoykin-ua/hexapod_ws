// Copyright 2026 enjoykin
// Licensed under the Apache License, Version 2.0
//
// Servo-mapping YAML loader and rad↔pulse-µs conversion.
// Conversion is piecewise-linear about pulse_zero — see
// docs_raspi/phase_9_progress.md "Design-Entscheidung Option C" for the
// rationale and formula.

#include "hexapod_hardware/calibration.hpp"

#include <chrono>
#include <cmath>
#include <ctime>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <mutex>
#include <sstream>
#include <stdexcept>

#include <yaml-cpp/yaml.h>

namespace hexapod_hardware
{

namespace
{

// Tiny helper: pick a field from a YAML node, falling back to a default
// when the field is missing. yaml-cpp throws on type mismatch — we let
// that propagate as the schema error it is.
template<typename T>
T yaml_get_or(const YAML::Node & node, const std::string & key, T fallback)
{
  if (!node || !node[key]) {
    return fallback;
  }
  return node[key].as<T>();
}

}  // namespace

void Calibration::load_from_file(const std::string & path)
{
  std::ifstream in(path);
  if (!in.is_open()) {
    throw std::runtime_error("Calibration: cannot open YAML file: " + path);
  }
  std::stringstream buf;
  buf << in.rdbuf();
  load_from_string(buf.str());
}

void Calibration::load_from_string(const std::string & yaml_text)
{
  // Strong exception guarantee: build everything in local structures, only
  // commit to member state at the very end via no-throw moves. If we throw
  // mid-parse, `servos_` and `joint_name_to_idx_` stay untouched — callers
  // can retry or fall back to their previous calibration without ending up
  // with a half-loaded Frankenstein.
  //
  // (yaml-cpp wraps its own errors as YAML::Exception : public std::runtime_error,
  //  so type-mismatches from .as<T>() naturally propagate as std::runtime_error.
  //  The Calibration header promises that — verified by
  //  YamlLoader.RejectsTypeMismatchAsRuntimeError.)

  YAML::Node root;
  try {
    root = YAML::Load(yaml_text);
  } catch (const YAML::Exception & e) {
    throw std::runtime_error(std::string("Calibration: YAML parse error: ") + e.what());
  }
  if (!root || !root.IsMap()) {
    throw std::runtime_error("Calibration: top-level YAML must be a map");
  }

  // Read the defaults block (optional — if absent, hard-coded defaults
  // from ServoCalibration{} apply).
  const YAML::Node defaults = root["defaults"];
  const int16_t default_pulse_min = yaml_get_or<int16_t>(defaults, "pulse_min", 500);
  const int16_t default_pulse_zero = yaml_get_or<int16_t>(defaults, "pulse_zero", 1500);
  const int16_t default_pulse_max = yaml_get_or<int16_t>(defaults, "pulse_max", 2500);
  const int default_direction_raw = yaml_get_or<int>(defaults, "direction", 1);
  if (default_direction_raw != 1 && default_direction_raw != -1) {
    throw std::runtime_error(
            "Calibration: defaults.direction must be +1 or -1, got " +
            std::to_string(default_direction_raw));
  }
  const int8_t default_direction = static_cast<int8_t>(default_direction_raw);

  // Read the per-servo map.
  const YAML::Node servo_map = root["servo2040_output_to_joint"];
  if (!servo_map || !servo_map.IsMap()) {
    throw std::runtime_error(
            "Calibration: top-level `servo2040_output_to_joint` map is required");
  }

  // Local working copies — members stay untouched until commit at the end.
  std::array<ServoCalibration, NUM_SERVOS> new_servos{};
  std::unordered_map<std::string, int> new_joint_name_to_idx{};

  for (std::size_t i = 0; i < NUM_SERVOS; ++i) {
    const YAML::Node entry = servo_map[static_cast<int>(i)];
    if (!entry) {
      throw std::runtime_error(
              "Calibration: servo2040_output_to_joint missing entry for index " +
              std::to_string(i));
    }
    const std::string joint_name = yaml_get_or<std::string>(entry, "joint", "");
    if (joint_name.empty()) {
      throw std::runtime_error(
              "Calibration: servo " + std::to_string(i) + " has no `joint` name");
    }

    ServoCalibration s;
    s.joint_name = joint_name;
    s.pulse_min = yaml_get_or<int16_t>(entry, "pulse_min", default_pulse_min);
    s.pulse_zero = yaml_get_or<int16_t>(entry, "pulse_zero", default_pulse_zero);
    s.pulse_max = yaml_get_or<int16_t>(entry, "pulse_max", default_pulse_max);
    const int direction_raw = yaml_get_or<int>(entry, "direction", default_direction);
    if (direction_raw != 1 && direction_raw != -1) {
      throw std::runtime_error(
              "Calibration: servo " + std::to_string(i) +
              " direction must be +1 or -1, got " + std::to_string(direction_raw));
    }
    s.direction = static_cast<int8_t>(direction_raw);

    // Sanity-check the pulse triplet — degenerate ordering would yield
    // negative or zero slope and NaN/inf during conversion. Catch here
    // with a clear message instead of producing junk later.
    if (!(s.pulse_min < s.pulse_zero && s.pulse_zero < s.pulse_max)) {
      throw std::runtime_error(
              "Calibration: servo " + std::to_string(i) +
              " requires pulse_min < pulse_zero < pulse_max, got " +
              std::to_string(s.pulse_min) + "/" + std::to_string(s.pulse_zero) + "/" +
              std::to_string(s.pulse_max));
    }

    // joint_lower/joint_upper keep their default values (±1.57) until
    // set_joint_limits() injects the real URDF limits. Default is sized
    // to the URDF defaults for our hexapod (see docs/00_conventions.md §11.4).

    new_servos[i] = s;
    new_joint_name_to_idx[joint_name] = static_cast<int>(i);
  }

  // Commit. std::array and std::unordered_map move-assignment from
  // rvalues are no-throw, so once we get here the object will be fully
  // consistent.
  //
  // Phase 11 Stage B: lockt mutex_ damit ein eventueller paralleler
  // radians_to_pulse_us-Call konsistente Werte sieht. load_from_string
  // ist zwar normal nur in on_init aufgerufen, aber defensive Lock
  // schadet nicht (one-shot lock contention auf init).
  {
    std::lock_guard<std::mutex> lock(mutex_);
    servos_ = std::move(new_servos);
    joint_name_to_idx_ = std::move(new_joint_name_to_idx);
  }
}

void Calibration::set_joint_limits(
  const std::string & joint_name, double lower,
  double upper)
{
  std::lock_guard<std::mutex> lock(mutex_);
  auto it = joint_name_to_idx_.find(joint_name);
  if (it == joint_name_to_idx_.end()) {
    // URDF may have joints we don't drive; ignore silently.
    return;
  }
  servos_[it->second].joint_lower = lower;
  servos_[it->second].joint_upper = upper;
}

double Calibration::radians_to_pulse_us(int output_idx, double rad) const
{
  if (output_idx < 0 || static_cast<std::size_t>(output_idx) >= servos_.size()) {
    throw std::out_of_range(
            "Calibration::radians_to_pulse_us: output_idx=" +
            std::to_string(output_idx) + " not in [0, " +
            std::to_string(NUM_SERVOS) + ")");
  }
  // Phase 11 Stage B: Lock gegen parallel update_servo_cal.
  // Hot-path-Overhead: ~50ns/lock × 18 Joints × 50 Hz = 45 µs/s. Vernachlässigbar.
  std::lock_guard<std::mutex> lock(mutex_);
  const ServoCalibration & s = servos_[output_idx];

  // Two slopes meet at pulse_zero. Which one we use depends on the sign
  // of the (mechanical, not signed-by-direction) joint side.
  double slope;
  if (rad >= 0.0) {
    slope = static_cast<double>(s.pulse_max - s.pulse_zero) / s.joint_upper;
  } else {
    slope = static_cast<double>(s.pulse_zero - s.pulse_min) / std::abs(s.joint_lower);
  }
  return static_cast<double>(s.pulse_zero) + s.direction * rad * slope;
}

double Calibration::pulse_us_to_radians(int output_idx, double pulse_us) const
{
  if (output_idx < 0 || static_cast<std::size_t>(output_idx) >= servos_.size()) {
    throw std::out_of_range(
            "Calibration::pulse_us_to_radians: output_idx=" +
            std::to_string(output_idx) + " not in [0, " +
            std::to_string(NUM_SERVOS) + ")");
  }
  // Phase 11 Stage B: Lock gegen parallel update_servo_cal.
  std::lock_guard<std::mutex> lock(mutex_);
  const ServoCalibration & s = servos_[output_idx];
  const double dp = pulse_us - static_cast<double>(s.pulse_zero);

  // Pick the slope by which side of pulse_zero we ended up on *in joint
  // space*. direction · dp >= 0 ⇔ joint_rad >= 0 ⇔ use slope_right.
  double slope;
  if (s.direction * dp >= 0.0) {
    slope = static_cast<double>(s.pulse_max - s.pulse_zero) / s.joint_upper;
  } else {
    slope = static_cast<double>(s.pulse_zero - s.pulse_min) / std::abs(s.joint_lower);
  }
  return dp / (s.direction * slope);
}

const ServoCalibration & Calibration::at(int output_idx) const
{
  if (output_idx < 0 || static_cast<std::size_t>(output_idx) >= servos_.size()) {
    throw std::out_of_range("Calibration::at: output_idx out of range");
  }
  return servos_[output_idx];
}

int Calibration::output_idx_for_joint(const std::string & joint_name) const
{
  auto it = joint_name_to_idx_.find(joint_name);
  if (it == joint_name_to_idx_.end()) {
    throw std::out_of_range("Calibration: joint not in calibration: " + joint_name);
  }
  return it->second;
}

// ─── Phase 11 Stage B — Live-Cal-Update + Persistenz ───────────────────

ServoCalibration Calibration::snapshot(int output_idx) const
{
  if (output_idx < 0 || static_cast<std::size_t>(output_idx) >= servos_.size()) {
    throw std::out_of_range(
            "Calibration::snapshot: output_idx=" +
            std::to_string(output_idx) + " not in [0, " +
            std::to_string(NUM_SERVOS) + ")");
  }
  std::lock_guard<std::mutex> lock(mutex_);
  return servos_[output_idx];  // copy under lock
}

void Calibration::update_servo_cal(int output_idx, const ServoCalibration & c)
{
  if (output_idx < 0 || static_cast<std::size_t>(output_idx) >= servos_.size()) {
    throw std::out_of_range(
            "Calibration::update_servo_cal: output_idx=" +
            std::to_string(output_idx) + " not in [0, " +
            std::to_string(NUM_SERVOS) + ")");
  }
  // Validate BEFORE locking — strong exception guarantee: bei Fehler
  // bleibt servos_ unverändert.
  if (!(c.pulse_min < c.pulse_zero && c.pulse_zero < c.pulse_max)) {
    throw std::runtime_error(
            "Calibration::update_servo_cal: requires "
            "pulse_min < pulse_zero < pulse_max, got " +
            std::to_string(c.pulse_min) + "/" + std::to_string(c.pulse_zero) +
            "/" + std::to_string(c.pulse_max));
  }
  if (c.direction != 1 && c.direction != -1) {
    throw std::runtime_error(
            "Calibration::update_servo_cal: direction must be ±1, got " +
            std::to_string(static_cast<int>(c.direction)));
  }

  std::lock_guard<std::mutex> lock(mutex_);
  servos_[output_idx] = c;
}

namespace
{

// ISO-8601-style timestamp without colons (for use in filenames).
// Returns e.g. "2026-05-20T14-30-15".
std::string filesystem_safe_timestamp()
{
  const auto now = std::chrono::system_clock::now();
  const auto tt = std::chrono::system_clock::to_time_t(now);
  std::tm tm_local{};
  localtime_r(&tt, &tm_local);
  std::ostringstream oss;
  oss << std::put_time(&tm_local, "%Y-%m-%dT%H-%M-%S");
  return oss.str();
}

// ISO-8601 timestamp with colons (for YAML calibrated_at field).
std::string iso8601_timestamp()
{
  const auto now = std::chrono::system_clock::now();
  const auto tt = std::chrono::system_clock::to_time_t(now);
  std::tm tm_local{};
  localtime_r(&tt, &tm_local);
  std::ostringstream oss;
  oss << std::put_time(&tm_local, "%Y-%m-%dT%H:%M:%S");
  return oss.str();
}

}  // namespace

void Calibration::save_to_file(const std::string & path) const
{
  // 1) Snapshot der gesamten Cal unter Lock — danach kein Lock mehr
  //    nötig für die YAML-Emission.
  std::array<ServoCalibration, NUM_SERVOS> snap;
  {
    std::lock_guard<std::mutex> lock(mutex_);
    snap = servos_;
  }

  // 2) Backup der existierenden Datei (wenn vorhanden) als
  //    <path>.bak-YYYYMMDD-HHMMSS. Jeder Save = neuer eindeutiger
  //    Backup-Filename → kein Überschreiben älterer Backups.
  namespace fs = std::filesystem;
  if (fs::exists(path)) {
    const std::string bak_path = path + ".bak-" + filesystem_safe_timestamp();
    try {
      fs::rename(path, bak_path);
    } catch (const fs::filesystem_error & e) {
      throw std::runtime_error(
              std::string("Calibration::save_to_file: could not move ") +
              path + " → " + bak_path + ": " + e.what());
    }
  }

  // 3) YAML emit. yaml-cpp kann keine Comments mit-emit-en — Header
  //    schreiben wir als raw-String prepend, dann YAML-Body via Emitter.
  YAML::Emitter out;
  out << YAML::BeginMap;
  out << YAML::Key << "version" << YAML::Value << 1;
  out << YAML::Key << "phase" << YAML::Value << 11;
  out << YAML::Key << "status" << YAML::Value << "calibrated";
  out << YAML::Key << "calibrated_at" << YAML::Value << iso8601_timestamp();

  // defaults bleibt für Schema-Compat mit existing loader. Werte
  // entsprechen den hard-coded Defaults in load_from_string.
  out << YAML::Key << "defaults";
  out << YAML::Value << YAML::BeginMap
      << YAML::Key << "pulse_min" << YAML::Value << 500
      << YAML::Key << "pulse_max" << YAML::Value << 2500
      << YAML::Key << "pulse_zero" << YAML::Value << 1500
      << YAML::Key << "direction" << YAML::Value << 1
      << YAML::EndMap;

  // Pro Pin alle 4 Cal-Felder explizit (keine Implicit-Inheritance).
  // joint_lower/joint_upper sind URDF-Source-of-Truth → nicht geschrieben.
  out << YAML::Key << "servo2040_output_to_joint";
  out << YAML::Value << YAML::BeginMap;
  for (std::size_t pin = 0; pin < NUM_SERVOS; ++pin) {
    const auto & s = snap[pin];
    out << YAML::Key << static_cast<int>(pin);
    out << YAML::Value << YAML::BeginMap
        << YAML::Key << "joint" << YAML::Value << s.joint_name
        << YAML::Key << "pulse_min" << YAML::Value << s.pulse_min
        << YAML::Key << "pulse_zero" << YAML::Value << s.pulse_zero
        << YAML::Key << "pulse_max" << YAML::Value << s.pulse_max
        << YAML::Key << "direction" << YAML::Value
        << static_cast<int>(s.direction)
        << YAML::EndMap;
  }
  out << YAML::EndMap;
  out << YAML::EndMap;

  // 4) Datei schreiben mit Header-Template + YAML-Body.
  std::ofstream ofs(path);
  if (!ofs.is_open()) {
    throw std::runtime_error(
            "Calibration::save_to_file: could not open for write: " + path);
  }
  ofs << "# =============================================================================\n"
      << "# Auto-generated by /save_calibration (Phase 11 Stage B)\n"
      << "# Saved at: " << iso8601_timestamp() << "\n"
      << "# Original (pre-save) is preserved as: " << path << ".bak-<timestamp>\n"
      << "# Schema: version 1, phase 11 — defaults-block kept for loader compat;\n"
      << "# alle 18 Pins haben explizite Cal-Felder (keine Implicit-Inheritance).\n"
      << "# =============================================================================\n"
      << out.c_str() << "\n";
  if (!ofs) {
    throw std::runtime_error(
            "Calibration::save_to_file: write failure on " + path);
  }
}

}  // namespace hexapod_hardware
