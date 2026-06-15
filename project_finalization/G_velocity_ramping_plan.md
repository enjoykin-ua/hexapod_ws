# Block G — Velocity-Ramping (sanfte Start/Stop)

**Zweck:** Elimine ruckartige Beschleunigungen beim Laufen. Standing → Start und Brems-Bewegungen sollen sanft und kontinuierlich laufen statt abrupt.

**User-Wunsch:** 
- Beim Standing-Start: Geschwindigkeit rampt sanft über ~1 Sekunde von 0 auf die Ziel-Geschwindigkeit
- Beim Bremsen: Geschwindigkeit rampt schneller über ~0,5 Sekunden herunter (responsiv)
- Gilt für alle Achsen (vx, vy, ωz) symmetrisch
- Soll **immer** laufen (auch bei State-Übergängen), nicht nur während WALKING

---

## 1. Logik-Skizze

### Ramping-Prinzip (linear interpolation)

**Input:** Jeder Tick (50 Hz) bekommt `(target_vx, target_vy, target_omega)` aus `_resolve_command()`.

**Speicher:** `gait_node` hält aktuell gerampte Geschwindigkeit `(ramp_vx, ramp_vy, ramp_omega)`.

**Pro Tick (dt = 0.02 s):**
```python
def _apply_velocity_ramp(target_vx, target_vy, target_omega, dt=0.02):
    # Ramp-Zeiten (hart kodiert)
    RAMP_UP_TIME = 1.0      # sec, für Beschleunigung
    RAMP_DOWN_TIME = 0.5    # sec, für Bremsen
    
    # Pro Achse:
    for axis in [vx, vy, omega]:
        target = target_value
        current = ramp_value
        
        if target > current:
            # Beschleunigen (langsam)
            max_change = (target - current) * dt / RAMP_UP_TIME
            new = current + min(max_change, target - current)
        elif target < current:
            # Bremsen (schnell)
            max_change = (current - target) * dt / RAMP_DOWN_TIME
            new = current - min(max_change, current - target)
        else:
            new = current
        
        ramp_value = new
    
    return (ramp_vx, ramp_vy, ramp_omega)
```

**In `_tick()` Integration:**
```python
def _tick(self):
    ...
    v_x, v_y, omega_z = self._resolve_command(now)
    # ← NEU: Ramping anwenden
    v_x, v_y, omega_z = self._apply_velocity_ramp(v_x, v_y, omega_z, dt=1.0/self._tick_rate)
    
    clamped = self._engine.set_command(v_x, v_y, omega_z, t)
    ...
```

---

## 2. Tests-Liste (mit Begründung)

### Desktop (Sim)

| # | Test | Beschreibung | Validation |
|---|---|---|---|
| G.1.1 | **Standing → Start (vx=0.05)** | Stick nach vorne, beobachte rampen über 1 sec | RViz: Hexapod startet sanft, nicht abrupt |
| G.1.2 | **Running → Stop (vx=0 nach Fahrt)** | Stick loslassen, beobachte Stopp über 0.5 sec | RViz: sanfter Bremsvorgang, kein Ruck |
| G.1.3 | **Richtungswechsel (vx: +0.05 → -0.05)** | Stick nach hinten, bei laufender Fahrt | Verhält sich wie: Fast-Stop (0.5s) + Ramp-Start rückwärts (1s) = flüssiger Wechsel |
| G.1.4 | **Omnidir. (vx+vy gleichzeitig)** | Stick diagonal, beobachte X+Y gleichzeitig rampen | Beide Achsen folgen individuellem Profil, unabhängig |
| G.1.5 | **Drehung (omega nur)** | Rechts drehen (ωz), dann loslassen | Ramp-Profile gelten auch für Drehung (1s up, 0.5s down) |
| G.1.6 | **Schneller Stick-Wechsel** | Stick schnell von +vx zu -vy zu 0 | Ramping followt kontinuierlich, keine Diskontinuitäten |
| G.2.1 | **State-Übergänge** | STANDING → WALKING (Auto-Standup aktiv), Ramping läuft immer | Ramping setzt nicht aus während Aufstehen, smooth weiter |
| G.2.2 | **Sitdown-Sequenz** | Während Walk → Sit-Intent, rampt Geschwindigkeit → 0 (über 0.5s) | Sit-Sequenz startet sauber mit v=0, nicht abrupt |
| G.3.1 | **cmd_vel_timeout** | Nach 0.5s keine cmd_vel, rampt auf default (meist 0) | Smooth Bremsen zu Defaults, nicht ruckartig |

### Hardware (aufgebockt, USB-Controller)

| # | Test | Beschreibung | Validation |
|---|---|---|---|
| G.4.1 | **Standing → Start (real)** | Aufgebockter Hexapod, Stick vorne, beobachte Bewegung | Servo-Last-Spitzenwerte < ohne Ramping (oszilloskop/logs) |
| G.4.2 | **Running → Stop (real)** | Fahren, Stick losgelassen, beobachte Stop | Sanft, kein Servo-Zittern beim Bremsen |
| G.4.3 | **Dauer-Ramping (5+ Sekunden)** | Lang fahren, Stick variieren, kein Freeze/Stutter | Ramping läuft stabil über längere Zeit |

**Nicht getestet (bewusst deferiert):**
- HW-Inbetriebnahme mit Bodenfahrt (Phase 13)
- IMU-Feedback während Fahrt (Phase A5 — später)
- Gelenkmomente / Energie-Optimierung (gehört nicht zu G)

---

## 3. Progress-Checkliste

Nach Implementierung + Tests: diese Items in `docs/phase_<n>_progress.md` abhaken.

```
### Block G — Velocity-Ramping (sanfte Start/Stop)

- [ ] G.0 — Logik-Skizze verstanden + User freigegeben
- [ ] G.1 — `_apply_velocity_ramp()` im gait_node.py geschrieben
  - [ ] G.1.1 — Zustandsvariablen (ramp_vx, ramp_vy, ramp_omega) initialisiert
  - [ ] G.1.2 — Ramp-UP (1.0s) + Ramp-DOWN (0.5s) hart kodiert
  - [ ] G.1.3 — In `_tick()` vor `engine.set_command()` eingefügt
- [ ] G.2 — Desktop-Sim-Tests (RViz)
  - [ ] G.2.1 — Standing → Start sanft + G.2.2 — Running → Stop sanft (Sim)
  - [ ] G.2.3 — Richtungswechsel, Omnidir, Drehung (Sim)
  - [ ] G.2.4 — State-Übergänge glatt, cmd_vel_timeout rampdown (Sim)
- [ ] G.3 — Hardware-Tests (aufgebockt)
  - [ ] G.3.1 — Standing → Start aufgebockt, Servo-Last beobachtet
  - [ ] G.3.2 — Running → Stop aufgebockt, sanft
  - [ ] G.3.3 — Dauer-Ramping stabil (5+ sec aufgebockt)
- [ ] G.4 — Dokumentation
  - [ ] G.4.1 — Block-G-Doku aktualisiert (Code-Kommentare)
  - [ ] G.4.2 — Test-Anleitung (G_velocity_ramping_test_commands.md) fertig
- [ ] G.5 — Kritischer Self-Review
  - [ ] G.5.1 — Edge-Cases: abrupte Richtungswechsel, cmd_vel_timeout, State-Übergänge
  - [ ] G.5.2 — Keine Diskontinuitäten bei Ramping-Grenzen
  - [ ] G.5.3 — Performance (1 Methode pro Tick, keine Allocations)
```

---

## 4. Offene Punkte für User-Review (VOR Code-Start)

1. **Ramp-Zeiten verifizieren?**
   - UP: 1,0 sec (langsam, sanftes Anfahren)
   - DOWN: 0,5 sec (schnell, responsives Bremsen)
   - Sind diese Werte intuitiv oder brauchst du andere?

2. **Asymmetrische Achsen?**
   - Derzeit: vx, vy, ωz alle mit gleichen Ramp-Zeiten
   - Oder sollte Drehung (ωz) schneller/langsamer reagieren?

3. **State-Handling in Ramping?**
   - "Immer" bedeutet: auch während STARTUP_RAMP, SITDOWN, etc.
   - Ist das okay, oder soll Ramping nur in STANDING/WALKING laufen?

4. **Rampdown bei SAT?**
   - Wenn Hinsetzen startet (SAT), rampt Geschwindigkeit zu 0
   - Das ist intended, oder brauchst du direktes Sperren?

5. **Test-Umgebung-Bestätigung:**
   - Sim-Tests: RViz-Visual + Log-Output (Geschwindigkeits-Werte pro Tick)
   - Hardware-Tests: USB-PS4-Controller, aufgebockt, Servo-Beobachtung
   - Ist das die richtige Konfiguration?

---

## 5. Datei-Änderungen (Übersicht)

| Datei | Änderung |
|---|---|
| `src/hexapod_gait/hexapod_gait/gait_node.py` | `__init__`: 3x Zustandsvariablen hinzufügen; neue Methode `_apply_velocity_ramp()`; in `_tick()` anwenden |
| (Test-Suite) | Neue Tests für Ramping (Unit + Integration) — optional |
| `docs/...` | Progress-Checkliste in Phase-Doku; Test-Anleitung schreiben |

---

## 6. Zeitschätzung & Ressourcen

- **Code-Schreiben:** ~30 min (Methode + Integration)
- **Sim-Tests:** ~1 h (RViz, verschiedene Szenarien)
- **Hardware-Tests:** ~1.5 h (aufgebockt, USB-PS4, Beobachtung)
- **Doku + Self-Review:** ~30 min
- **Gesamt:** ~3,5 h

---

**Freigabe erhalten?** ✅ (User bestätigt)  
**Nächster Schritt:** Code-Implementierung + Sim-Tests
