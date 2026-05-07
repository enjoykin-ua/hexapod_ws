# Änderungen v2 gegenüber v1

Datum: 2026-05-07
Auslöser: `bericht.md` von Claude Code, Diskussion über Box-Geometrie,
verifizierte Joint-Limits, Default-Welt-Strategie.

---

## Geänderte Dateien

### `docs/00_conventions.md` — größere Überarbeitung

- **§1 Bein-Nummerierung:** Aus „Vorschlag, vom User zu bestätigen" wird
  verbindliche Konvention. Tabelle mit yaw-Werten ergänzt.
- **§3 Frames:** `leg_<n>_foot_link` ist jetzt **echter Link mit
  Kollisionsgeometrie** (Kugel), nicht nur TF-Frame. Begründung
  ausdrücklich dokumentiert: Punktkontakt statt Kantenkontakt der
  dünnen Tibia-Box.
- **§11 NEU — Verifizierte Geometrie und Joint-Limits:** Komplette
  Tabelle aller Maße, Massen, Joint-Limits aus dem alten Workspace
  übernommen. Joint-Limits als „physisch verifiziert" markiert.
- **§11.5 NEU — Inertia-Mindestschranke:** `1e-5` als globale Untergrenze,
  Begründung mit dünner Tibia-Geometrie dokumentiert.
- **§12 NEU — Naming-Konventionen Zusammenfassung:** Tabelle mit
  expliziten Verboten (`fr/fl/...`, `_base_to_coxa_joint`) als
  Erinnerung gegen den Konventionsbruch aus dem alten Workspace.

### `docs/phase_2_description.md` — größere Überarbeitung

- **Neue Verzeichnisstruktur:** `hexapod_physical_properties.xacro` als
  Single Source of Truth für alle Maße/Limits.
- **Konkrete Maße eingebaut:** Aus Konventionen §11 übernommen,
  keine TODOs mehr.
- **Stufenplan reduziert:** „Primitive → Mesh"-Iteration entfällt
  (Box-only Designentscheidung).
- **Foot-Link als Kugel mit Kollision:** Vollständiger Xacro-Code für
  `leg.xacro` mit allen 4 Links pro Bein (coxa, femur, tibia, foot).
- **`inertials.xacro`:** `box_inertia` und neu `sphere_inertia` Macros,
  beide mit `max(..., inertia_min)` Schranke.
- **`package.xml` ohne TODO-Stubs:** `--maintainer-email` beim
  `pkg create` setzen.
- **Done-Kriterium 5 erweitert:** tf-Tree muss bis `foot_link` reichen.
- **Done-Kriterium 6 NEU:** README ist Pflicht.
- **Stolperfallen-Tabelle:** Foot-Link-spezifische Fehler ergänzt.

### `docs/phase_3_gazebo.md` — größere Überarbeitung

- **Welt-Strategie geändert:** Default-Welt (`empty.sdf` aus gz-sim)
  statt eigener Welt-Datei. Eigene Welt nur als Fallback dokumentiert.
- **Klärung „durchsichtiger Boden":** Erklärung was `empty.sdf` vs.
  „komplett leere Szene" bedeutet.
- **Reibung an Foot-Kugeln** statt an Tibia-Link, wegen neuem
  Foot-Design aus Phase 2.
- **`kp/kd`-Kontakt-Parameter** dokumentiert, weil Kugel-Punktkontakt
  damit besser stabilisierbar ist.
- **Spawn-Höhe von 0.15 auf 0.20 m erhöht** — etwas mehr Reserve.
- **Stolperfallen ergänzt:** „Tibia hängt statt Fuß-Kugel", „Roboter
  springt beim Spawn", Box-Roboter-spezifische Punkte.
- **Kein Verzeichnis `worlds/`** in der Soll-Struktur.

---

## Unveränderte Dateien

Die folgenden Dateien sind 1:1 aus v1 übernommen:

- `CLAUDE.md`
- `PHASE.md`
- `docs/phase_0_setup.md`
- `docs/phase_1_ros2_basics.md`
- `docs/phase_4_ros2_control.md`
- `docs/phase_5_kinematics_gait.md`
- `docs/phase_6_teleop.md`
- `docs/phase_7_pi_port.md`

> Diese werden in späteren Iterationen ggf. nochmal angepasst, sobald
> Phase 4+ konkret in Arbeit ist und sich Bedarf zeigt.
