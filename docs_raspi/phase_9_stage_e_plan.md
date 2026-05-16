# Phase 9 — Stufe E — Plan

> **Status:** Plan, noch nicht implementiert. **Code/Tests beginnen erst
> nach User-Freigabe** (CLAUDE.md §4).
>
> **Parent-Plan:** [`phase_9_hexapod_hardware.md`](phase_9_hexapod_hardware.md)
> Stufe E — Plugin-Registrierung verifizieren.
>
> **Test-Anleitung:** wird nach Implementations-Freigabe finalisiert
> (`phase_9_stage_e_test_commands.md`).

---

## Ziel der Sub-Stage

Verifizieren, dass das Plugin `hexapod_hardware/HexapodSystemHardware`
zur Laufzeit über **pluginlib** geladen werden kann und das Manifest +
die `package.xml` so verdrahtet sind, dass `controller_manager` bzw.
`hardware_interface::ResourceManager` es findet und instanziiert.

**Was schon aus Stage A da ist (nicht zu wiederholen):**
- `hexapod_hardware.xml` (pluginlib-Manifest mit korrektem
  base_class_type)
- `package.xml`-Export `<hardware_interface plugin="..."/>`
- `CMakeLists.txt`-Aufruf `pluginlib_export_plugin_description_file(...)`
- Installed `share/ament_index/resource_index/hardware_interface__pluginlib__plugin/hexapod_hardware`
  zeigt auf das richtige XML
- shared library `libhexapod_hardware.so` installiert
- alle Symbole exportiert (sonst hätten alle 200 Tests in Stage A–D nicht
  gebaut)

**Was Stage E neu macht:**
- gtest, der pluginlib::ClassLoader nutzt → das Plugin **runtime
  geladen** wird (= das Manifest + die Installation tatsächlich
  zusammenpassen)
- gtest, der das geladene Plugin als `SystemInterface` interpretiert
  und einen einfachen Lifecycle-Tick durchläuft
- (optional, siehe Frage unten) manuelle CLI-Verifikation per
  `ros2 control list_hardware_components`, dokumentiert in
  `phase_9_stage_e_test_commands.md`

---

## Was Stage E NICHT macht

- **Keine URDF-Switch-Logik** — kommt in **Stage F**.
- **Kein `real.launch.py`** — kommt in **Stage G**.
- **Kein echter Servo2040-Anschluss** — Stage H.
- **Kein launch_testing mit ros2_control_node** — überzogen für die
  „kann pluginlib das Plugin laden"-Frage. Stage F/G/H bringen den
  echten Stack mit; Stage E beweist nur die Plugin-Verdrahtung.

---

## Logik-Skizze

### Was wir bauen

Eine **neue Test-Datei** `test/test_plugin_registration.cpp` mit ~3 Tests.

```cpp
#include <pluginlib/class_loader.hpp>
#include <hardware_interface/system_interface.hpp>

TEST(PluginRegistration, PluginIsLoadableViaPluginlib)
{
  // pluginlib::ClassLoader scannt alle installierten
  // hardware_interface__pluginlib__plugin-Resource-Index-Einträge.
  // Wenn unser Manifest, package.xml und Library zusammenpassen,
  // taucht "hexapod_hardware/HexapodSystemHardware" auf.
  pluginlib::ClassLoader<hardware_interface::SystemInterface> loader(
    "hardware_interface", "hardware_interface::SystemInterface");

  // Die Klasse muss in der Liste sein.
  const auto classes = loader.getDeclaredClasses();
  EXPECT_NE(
    std::find(classes.begin(), classes.end(),
              "hexapod_hardware/HexapodSystemHardware"),
    classes.end())
    << "Plugin not in pluginlib registry — check hexapod_hardware.xml + package.xml";

  // Und sie muss tatsächlich instanziierbar sein.
  auto plugin = loader.createSharedInstance(
    "hexapod_hardware/HexapodSystemHardware");
  ASSERT_NE(plugin, nullptr);
}

TEST(PluginRegistration, LoadedPluginPassesOnInit)
{
  // Nachweis: das via pluginlib geladene Objekt ist nicht nur typkorrekt,
  // sondern auch lebensfähig — on_init mit unserer make_valid_info()
  // (loopback_mode=true) muss SUCCESS liefern.
  pluginlib::ClassLoader<hardware_interface::SystemInterface> loader(...);
  auto plugin = loader.createSharedInstance("hexapod_hardware/HexapodSystemHardware");

  // Wir nutzen denselben HardwareInfo-Builder wie in test_hexapod_system,
  // also brauchen wir eine kleine Inline-Kopie davon — oder wir
  // refactoren make_valid_info() in eine gemeinsame Test-Helper-Datei.
  // (Siehe Frage 3 unten.)
  auto info = make_valid_info();
  auto params = make_params(info);

  EXPECT_EQ(
    plugin->on_init(params),
    hardware_interface::CallbackReturn::SUCCESS);
}

TEST(PluginRegistration, LoadedPluginExposes18Interfaces)
{
  // Same setup, then verify export_*_interfaces gives us exactly 18 each.
  // Pinnt den Vertrag, dass das aus dem Manifest geladene Plugin
  // funktional identisch zum direkt-instanziierten ist (sonst stimmt
  // irgendwo das ABI/das Symbol-Loading nicht).
  ...
}
```

### Wo lebt der Code?

```
src/hexapod_hardware/
└── test/
    └── test_plugin_registration.cpp   # NEU (~80 Zeilen mit Boilerplate)
```

Plus eine kleine `CMakeLists.txt`-Ergänzung:
```cmake
ament_add_gtest(test_plugin_registration test/test_plugin_registration.cpp)
target_link_libraries(test_plugin_registration ${PROJECT_NAME})
target_compile_definitions(test_plugin_registration PRIVATE
  SOURCE_DIR_FOR_TESTS="${CMAKE_CURRENT_SOURCE_DIR}")
ament_target_dependencies(test_plugin_registration pluginlib)
```

`SOURCE_DIR_FOR_TESTS` wieder für das `servo_mapping.yaml`-Lookup im
on_init-Test (gleiche Konvention wie `test_calibration` und
`test_hexapod_system`).

---

## Manuelle CLI-Verifikation (in `phase_9_stage_e_test_commands.md`)

Zusätzlich zur gtest-Suite dokumentieren wir, **wie der User das Plugin
manuell verifizieren kann** — nützlich für Bringup-Sessions:

```bash
# 1. Resource-Index-Eintrag sichtbar?
cat ~/hexapod_ws/install/hexapod_hardware/share/ament_index/resource_index/\
hardware_interface__pluginlib__plugin/hexapod_hardware

# Erwartet: "share/hexapod_hardware/hexapod_hardware.xml"

# 2. Manifest selber lesbar + valid XML?
xmllint --noout ~/hexapod_ws/install/hexapod_hardware/share/hexapod_hardware/hexapod_hardware.xml

# 3. ldd zeigt alle Symbole resolved?
ldd ~/hexapod_ws/install/hexapod_hardware/lib/libhexapod_hardware.so | grep -v "linux-vdso\|ld-linux"
# Keine "not found"-Zeilen erwartet
```

(`ros2 control list_hardware_components` braucht einen laufenden
controller_manager; das kommt mit Stage F/G. Daher noch nicht hier.)

---

## Tests

**Suite `PluginRegistration`** (3 Tests, ~50 ms gesamt):

| # | Test | Was wird geprüft |
|---|---|---|
| 1 | `PluginIsLoadableViaPluginlib` | pluginlib::ClassLoader findet `hexapod_hardware/HexapodSystemHardware` UND kann es instanziieren |
| 2 | `LoadedPluginPassesOnInit` | Das via pluginlib geladene Plugin passiert on_init mit valid HardwareInfo (loopback_mode=true) → SUCCESS |
| 3 | `LoadedPluginExposes18Interfaces` | export_state_interfaces() und export_command_interfaces() liefern jeweils 18 Einträge (Servoanzahl-Vertrag bleibt durch pluginlib-Load erhalten) |

### Test-Helper-Frage (siehe Frage 3)

Die Tests brauchen die `make_valid_info()` + `make_params()`-Helper, die
aktuell privat (anonymer Namespace) in `test_hexapod_system.cpp` leben.
Drei Optionen:
- **A: Inline-Kopie in `test_plugin_registration.cpp`** — Duplikation,
  aber lokal verständlich, ~30 Zeilen extra.
- **B: gemeinsamer Test-Helper-Header** `test/test_helpers.hpp` — DRY,
  aber bedingt eine kleine Refactoring-Aktion in `test_hexapod_system.cpp`.
- **C: Test-Library** in CMake — overkill für eine Funktion.

Mein Vorschlag: **B** (Refactor in `test/test_helpers.hpp`), klein
und sauber. Aber: zusätzlicher Diff im D.x-Test-File. Wenn dir das
zu invasiv ist: A.

---

## Progress-Checkliste (geht 1:1 in `phase_9_progress.md`)

Done-Vertrag — alle `[x]` = Stage fertig:

- [ ] E.1 Test-Helper-Frage (Frage 3) entschieden → A oder B umsetzen
- [ ] E.2 Test-Datei `test/test_plugin_registration.cpp` mit 3 Tests
- [ ] E.3 `CMakeLists.txt`: `ament_add_gtest(test_plugin_registration ...)` +
  `ament_target_dependencies(... pluginlib)` + `SOURCE_DIR_FOR_TESTS`-Define
- [ ] E.4 `colcon build`: grün, keine Warnings
- [ ] E.5 `colcon test`: alle Tests grün, total mind. **203 tests, 0 errors, 0 failures**
  (3 neue PluginRegistration-Tests + bestehende 200)
- [ ] E.6 Kritischer Self-Review-Tabelle in `phase_9_progress.md`
- [ ] E.7 Eventuelle Post-Review-Fixes
- [ ] E.8 `phase_9_stage_e_test_commands.md` finalisiert (gtest-Befehle + manuelle CLI-Verifikation)
- [ ] E.9 README.md: Status Stufe E ✅, Tabelle „Was kommt in den nächsten Stufen" updaten
- [ ] E.10 progress.md: E-Sektion mit Bullets + Post-Review-Tabelle + „Was Stage E nicht macht"

---

## Was offen ist und User-Feedback braucht

Bitte einmal kurz absegnen:

1. **Stage-E-Scope:**
   - **A (mein Vorschlag): nur pluginlib::ClassLoader-Tests** (~3 Tests, CI-friendly, schnell). Stage F/G/H verifizieren das real-world-Verhalten mit URDF + controller_manager.
   - B: + launch_testing mit ros2_control_node — zeigt echte Lifecycle-Sicht, aber bringt ~150 Zeilen Boilerplate (ROS-Launch + subprocess + Output-Parsing). Lohnt sich für „Plugin lädt"-Frage nicht.

2. **Manuelle CLI-Verifikation:**
   - **A (mein Vorschlag): in `phase_9_stage_e_test_commands.md` dokumentieren** mit den drei einfachen Befehlen oben (resource-index, xmllint, ldd). `ros2 control list_hardware_components` aber **nicht** hier — braucht laufenden controller_manager (kommt mit Stage F/G).
   - B: Auch `list_hardware_components` schon in Stage E versuchen (User müsste manuell controller_manager starten — Aufwand vs. Nutzen schlecht).

3. **Test-Helper:**
   - A: Inline-Kopie von `make_valid_info()` in `test_plugin_registration.cpp` — Duplikation, aber lokal.
   - **B (mein Vorschlag): Refactor in `test/test_helpers.hpp`** — gemeinsamer Header, DRY. Kleiner Diff in `test_hexapod_system.cpp`.

4. **3 Tests reichen?** Oder soll ich noch was abdecken?
   - z.B. „Plugin destruktiert sauber" (RAII-check für geladenes Plugin)
   - „Mehrere Plugin-Instanzen parallel" (für hypothetisches Multi-Hexapod-Setup) — wahrscheinlich Overkill für Phase 9

5. **Stage E Größenordnung:** kompakt — ~3 Tests, keine Code-Änderungen am Plugin selbst, ~100 Zeilen Test-File + 5 Zeilen CMake + 1 Test-Helper-Refactor. Passt das, oder willst du noch was reinpacken?

---

## Reihenfolge nach Plan-Freigabe

1. ☐ User reviewt diesen Plan + die 5 Fragen → Feedback / Freigabe
2. ☐ Bei Bedarf: Plan anpassen
3. ☐ Test-Helper-Refactor (wenn Variante B in Frage 3)
4. ☐ Test-Datei `test_plugin_registration.cpp`
5. ☐ `CMakeLists.txt`-Update
6. ☐ Build + colcon test grün
7. ☐ Kritischer Self-Review (Pflicht CLAUDE.md §4)
8. ☐ Doku-Update: progress.md, README.md, test_commands.md
9. ☐ Fertig-Meldung für User-Commit

Mit Stage E ist die **Plugin-Registrierung produktiv verifiziert**.
Danach Stage F (URDF-Switch zwischen `gz_ros2_control` Sim und unserem
Plugin), dann Stage G (`real.launch.py`).

---

## Plan-Korrekturen während Implementation (2026-05-16)

Drei Abweichungen vom Vorab-Plan, alle nicht-fachlich:

1. **Test-File ~125 Zeilen statt ~80.** Gründe: ausführlichere Per-Test-
   Header-Kommentare (was wird getestet, welche Drift fängt der Test ab),
   plus expliziter Black-Box-Hinweis im File-Top-Comment. Lesbarkeit
   wichtiger als Zeilenkürze für ein Stage-Beweis-File.

2. **`#pragma GCC diagnostic`-Suppression in Test 3.** Im Plan nicht
   vorhergesehen. Im Build kam die Warnung `export_state_interfaces()`
   ist deprecated raus (jazzy markiert die alte HardwareComponentInterface-
   API als deprecated zugunsten von `on_export_*_interfaces()`). Plugin
   überschreibt aber die alte API (Stage A–D), und laut
   `hardware_component_interface.hpp` Z.177-Doku gewinnt der alte Pfad
   wenn er einen non-empty Vector liefert — ein Migrations-Refactor wäre
   ein eigener, größerer Task außerhalb Stage E. Daher lokaler Pragma-
   Block mit erklärendem Kommentar.

3. **Test-Counter „208 tests" statt „203" im Plan.** 3 neue gtest-Cases
   stimmen, aber der colcon-Counter zählt zusätzliche Lint-Subtests pro
   Test-Target mit. Reine gtest-Cases: **154** (vorher 151), davon **3 neu**
   in der `PluginRegistration`-Suite. Keine fachliche Abweichung.
