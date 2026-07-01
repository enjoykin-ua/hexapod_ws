# Plan — Teleop-Scales live-tunbar (`joy_to_twist` Parameter-Callback)

> **Status: 🟢 umgesetzt + getestet** (User-Freigabe „gehs an"; Vorschläge übernommen:
> `deadzone` mit drin, negative Scales abgelehnt, strukturelle Params nicht live).
> **Ziel:** die Tuning-Parameter des Teleop-Nodes (`linear_x_scale` usw.) per `ros2 param set`
> **im Lauf** verstellbar machen — heute werden sie nur beim Start gelesen, ein `param set`
> bleibt wirkungslos. Damit entfällt das `--params-file`-Override- bzw. yaml-Edit-Gehampel beim
> Tempo-/Schrittgefühl-Tunen.

---

## 0. Kontext / warum

`joy_to_twist` (`hexapod_teleop/hexapod_teleop/joy_to_twist.py`) liest seine Parameter **einmal in
`__init__`** in gecachte Attribute (`self._linear_x_scale = float(g('linear_x_scale').value)` …) und
nutzt im Hot-Path (`_twist_from_joy`) nur diese Attribute. Es gibt **keinen**
`add_on_set_parameters_callback`. Folge: `ros2 param set /joy_to_twist linear_x_scale 0.2` ändert nur
die Param-Registry, **nicht** das Attribut → kein Effekt (verifiziert: 0.01 vs 999.9 identisch).

Der `gait_node` hat genau dieses Live-Muster bereits (`_on_param_change`, validate-then-apply) — wir
spiegeln es 1:1 in den Teleop.

## 1. Logik-Skizze / Pseudocode

**Eine Datei:** `joy_to_twist.py`. Drei additive Bausteine, kein Eingriff in den Twist-Hot-Path außer
dass er die aktualisierten Werte sieht.

```
# (a) in __init__, NACH dem Lesen der Params:
self.add_on_set_parameters_callback(self._on_param_change)

# (b) neue Methode — erst validieren (kein Fail-mid-apply), dann anwenden:
def _on_param_change(params):
    # 1. VALIDATE — bei Ungültigem sofort raus, nichts angewandt
    for p in params:
        if p.name in ('linear_x_scale','linear_y_scale','angular_z_scale') and p.value < 0:
            return SetParametersResult(successful=False, reason=f'{p.name} must be >= 0')
        if p.name == 'slow_factor' and not 0.0 <= p.value <= 1.0:
            return SetParametersResult(successful=False, reason='slow_factor must be in [0,1]')
        if p.name == 'deadzone' and not 0.0 <= p.value < 1.0:
            return SetParametersResult(successful=False, reason='deadzone must be in [0,1)')
    # 2. APPLY — kein Fail mehr möglich
    for p in params:
        if   p.name == 'linear_x_scale':  self._linear_x_scale  = float(p.value)
        elif p.name == 'linear_y_scale':  self._linear_y_scale  = float(p.value)
        elif p.name == 'angular_z_scale': self._angular_z_scale = float(p.value)
        elif p.name == 'slow_factor':     self._slow_factor     = float(p.value)
        elif p.name == 'deadzone':        self._deadzone        = float(p.value)
    return SetParametersResult(successful=True)
```

- **Welche Params live (Vorschlag):** die **Tuning-Werte** —
  `linear_x_scale` (0.05), `linear_y_scale` (0.05), `angular_z_scale` (0.46), `slow_factor` (0.5),
  optional `deadzone` (0.10).
- **Bewusst NICHT live:** die **strukturellen** Params (`axis_*`, `*_button`, `sign_*`, D-Pad-Achsen).
  Die ändert man praktisch nie im Lauf; sie draußen zu lassen hält die Validierung simpel. Ein
  unbekannter/nicht-behandelter Param im Callback wird einfach ignoriert (Wert in der Registry ändert
  sich, Hot-Path nutzt weiter den Startwert — wie heute, kein Regress).
- **Defaults/Verhalten unverändert** — rein additiv.

## 2. Tests-Liste (mit Begründung)

| Test | Prüft | Warum |
|---|---|---|
| **Unit: scale live** | `param set linear_x_scale 0.2` → `node._linear_x_scale == 0.2` | Kern-Funktion |
| **Unit: y/angular/slow_factor live** | analog für die anderen Tuning-Params | Vollständigkeit |
| **Unit: negativ abgelehnt** | `linear_x_scale = -0.1` → `successful=False`, Attribut **unverändert** | Validierung + kein Teil-Apply |
| **Unit: slow_factor/deadzone Range** | außerhalb [0,1] bzw. [0,1) → abgelehnt | Range-Guards |
| **Unit: struktureller Param** | `param set` auf z.B. `axis_ly` → akzeptiert/ignoriert, kein Crash | kein Regress |
| colcon test + Lint | grün (ament_flake8/pep257) | 0 Fehler |

**Bewusst NICHT getestet (scope-out):** End-to-End mit echtem Controller (das ist der Live-Sim-Test
durch dich); Live-Tunen der strukturellen Achsen-/Button-Params (nicht im Scope).

## 3. Progress-Checkliste (Done-Vertrag)

```
TLS (Teleop Live Scales):
- [x] TLS.1 add_on_set_parameters_callback in __init__ registriert
- [x] TLS.2 _on_param_change: validate-then-apply für linear_x/y_scale, angular_z_scale, slow_factor + deadzone
- [x] TLS.3 Unit-Tests (live-Update je Param, negativ/Range abgelehnt, struktureller Param kein Crash, Atomar-Reject)
- [x] TLS.4 colcon test + Lint grün  [hexapod_teleop 42 Tests, 0 Fehler; +11 test_live_scales; ament_flake8/pep257 grün]
- [x] TLS.5 kurzer Self-Review (s. unten)
- [x] TLS.6 rubicon_world_commands.md: Hinweis „Scales jetzt live" nachgezogen (Abschnitt PS4)
- [x] TLS.7 Test-Doku teleop_live_scales_test_commands.md (Rubicon-Welt, PS4) — Sim-Verify durch User offen
- [x] TLS.8 project_architecture nachgezogen (ai_navigation Teleop-Eintrag + architecture.md Komponenten-Zeile; ohne Rubicon)
```

## 6. Self-Review

| Punkt | Status |
|---|---|
| validate-then-apply (kein Teil-Apply bei Fehler) | OK (zwei Loops; `test_atomic_reject_keeps_all` via `set_parameters_atomically`) |
| Hot-Path nutzt die aktualisierten Werte | OK (`_twist_from_joy` liest `self._linear_x_scale` … die der Callback setzt) |
| Defaults/Verhalten unverändert (rein additiv) | OK (declare_parameter-Defaults unangetastet) |
| strukturelle Params (axis/button/sign) Start-only | OK (`test_structural_param_accepted_no_crash`: akzeptiert, nicht übernommen, kein Crash) |
| Scales ≥ 0, slow_factor ∈ [0,1], deadzone ∈ [0,1) | OK (parametrisierte Reject-Tests) |
| kein Upper-Bound auf Scales | 🟢 bewusst — die Engine clamped `cmd_vel` ohnehin auf `linear_max`; ein hoher Scale schadet nicht |
| Thread-Sicherheit (Callback vs. Joy-Callback) | OK (Default-SingleThreadedExecutor → keine Race mit `_on_joy`) |
| `ros2 param set /joy_to_twist linear_x_scale …` wirkt sofort | OK (Kern-Ziel; Live-Update-Tests grün) |

## 4. Offene Punkte für User-Review (vor Code entscheiden)

1. **`deadzone` mitnehmen?** (ja = auch Stick-Totzone live; nein = nur die 4 Tempo-Params). *Vorschlag:* ja, harmlos.
2. **Negative Scales erlauben?** Negativ = Achsen-Invertierung über den Scale (statt über `sign_*`).
   *Vorschlag:* **nein** (Scales ≥ 0; Invertierung bleibt Sache der `sign_*`-Params) — sauberere Semantik.
3. **Strukturelle Params (`axis_*`/`*_button`/`sign_*`) auch live?** *Vorschlag:* **nein** (selten gebraucht,
   hält's simpel; später nachrüstbar).

## 5. Aufwand
~20–30 Zeilen, eine Datei, keine neue Dependency, gespiegeltes `gait_node`-Muster. Risiko minimal
(additiv). Test + Build + Lint inklusive.
