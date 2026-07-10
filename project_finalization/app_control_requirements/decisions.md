# Architektur-Entscheidungen — Mobile Teleop / HMI (Block I)

> **Entscheidungs-Log** (ADR-Stil), mit **verworfenen Alternativen + Begründung**, damit
> ein späteres Re-Design ohne Erinnerung möglich ist (Projekt-Konvention). Jede
> Entscheidung: Kontext → Entscheidung → Alternativen (verworfen) → Konsequenzen.
> Änderungen hier ziehen ggf. [`interface_contract.md`](interface_contract.md) + die
> Phasen-Pläne nach.

---

## D1 — Native Android-App statt Web-PWA

**Kontext:** Die App soll Gamepad lesen, Video im Vollbild zeigen, wach bleiben, robust im
Feld laufen. User-Hintergrund: Embedded/Java, **kein** HTML/CSS/JS.

**Entscheidung:** **Native Android-App (Kotlin).** Hardware-Zugriff über Android-System-
APIs (`InputManager`/Gamepad, `Media3`/ExoPlayer für Video, `OkHttp`-WebSocket für rosbridge).

**Verworfen:**
- **Web-PWA (roslibjs + Gamepad-API + `<video>`):** schneller Dev-Zyklus, kein Toolchain,
  vom Pi ausgeliefert — aber Browser-Quirks bei Gamepad/Fullscreen/Wake-Lock, und
  HTML/JS ist dem User fremd. Robustheit + Embedded-Nähe gewinnen.
- **Flutter (Dart):** ein Codebase, gute Plugins — aber weitere neue Sprache, für
  Single-Target Android kein Gewinn.
- **ROS2 auf Android (rclandroid/rcljava):** schwer, schlecht gepflegt → raus.

**Konsequenzen:** Android-Studio/Gradle-Toolchain + APK-Build. Lernkurve = Android-
Lifecycle, nicht die Sprache. **Wichtig:** die Roboter-Seite (rosbridge) ist bei native
ODER web identisch → die Entscheidung ist **isoliert + reversibel** (nur die App-Impl.).

---

## D2 — rosbridge als Naht (WebSocket + JSON), Video getrennt

**Kontext:** Wie spricht die App mit ROS2, ohne ROS auf dem Handy?

**Entscheidung:** **`rosbridge_server` auf dem Pi** exponiert Topics/Services über
WebSocket+JSON. Die App ist ein WebSocket-Client. **Video läuft NICHT über rosbridge**,
sondern über einen **eigenen Stream-Server** (Kanal 2).

**Verworfen:**
- **Video durch rosbridge** (base64-JSON über WebSocket) — grauenhaft für Framerate/
  Latenz/Bandbreite. Deshalb zweiter Kanal.
- **Bespoke UDP/TCP-Protokoll + eigener Bridge-Node** — volle Kontrolle, aber Neuerfindung
  von rosbridge. Overkill.

**Konsequenzen:** Zwei parallele Strecken (Steuerung/Status über rosbridge, Video separat).
**Bonus:** rosbridge = **Unicast-TCP** → umgeht das frühere DDS-Multicast-Problem am
Hotspot ([[project_ros2_param_set_node_not_found_daemon]]-Umfeld). Security: rosbridge ist
per Default ohne Auth → nur im privaten Hotspot, nicht ins Internet (bewusst, [requirements.md](requirements.md) §6).

---

## D3 — `/joy`-Reuse: die App emuliert einen Joystick

**Kontext:** Die App braucht die volle Fahr-Logik (Deadzone, Scaling, Dead-Man, Sit/Stand,
Stance, Gait, Tempo, Show). Neu implementieren wäre Doppelarbeit + Drift-Risiko.

**Entscheidung:** Die App liest den Kishi, **normalisiert auf das PS4-Achsen-/Button-
Layout** und publisht `sensor_msgs/Joy`. Damit läuft die **komplette bestehende
`joy_to_twist`-Kette unverändert** — kein neuer Steuer-Code am Roboter. On-Screen-Aktionen
(Parameter, Menüs) gehen dagegen als **direkte Service-/Param-Calls** (nicht über `/joy`).

**Verworfen:**
- **Eigene cmd-Schnittstelle in der App** (App rechnet `/cmd_vel` + ruft alle Services
  selbst) — würde Deadzone/Scaling/Tempo/Dead-Man in der App duplizieren; jede Roboter-
  seitige Änderung müsste in der App nachgezogen werden. Verworfen.
- **Neue `kishi.yaml`-Mapping-Config am Roboter** statt App-Normalisierung — verschiebt die
  controller-spezifische Zuordnung an die falsche Stelle (Roboter statt App), wo auch die
  Portabilitäts-Profile leben. App-normalisiert bevorzugt (D8).

**Konsequenzen:** Roboter-Config (`ps4_usb.yaml`) bleibt stabil. Die App ist „nur" ein
Joy-Publisher + UI + Video + Status. **Hybrid:** physische Tasten → `/joy`; Touch → direkte
Calls. **NF1 (Comms-Loss):** stetiges `/joy`-Publishing ist zugleich das Sicherheitsnetz.

---

## D4 — Netz: Handy-Hotspot (A) zuerst, Pi-AP (B) als Reserve

**Kontext:** App (Handy) ↔ Roboter (Pi) brauchen ein lokales Netz. Kein Internet nötig.

**Entscheidung:** **Variante A — Handy = Hotspot, Pi tritt bei.** Das SIM-lose Handy ist
eine saubere lokale Insel. **Variante B — Pi = eigener Access Point (hostapd)** erst, wenn
A sich nicht bewährt (feste IP, weniger Handy-Last).

**Verworfen (vorerst):**
- **Pi-AP von Anfang an** — sauberere feste IP + entlastet das Handy, aber hostapd-Setup.
  Als Ziel-/Reserve-Variante notiert, nicht als Start.
- **Gemeinsamer Router** — braucht Infrastruktur, für untethered-Feldbetrieb unpraktisch.

**Konsequenzen:** Pi bekommt eine **feste IP** im Hotspot-Range (in der App hinterlegt).
Prüfen: kann das Alt-Handy den Hotspot **ohne SIM** aktivieren (manche Androids grauen es
aus). Ein Handy macht Hotspot + App + Video → Last/Wärme/Akku (Alt-Handy: egal; Kishi-
Ladeport hilft). Reichweite ~10–30 m Freifeld.

---

## D5 — Sound: Roboter-Speaker, Handy nur Auslöser

**Kontext:** Speaker ist **im Roboter** verbaut (getestet). Auto-Sounds in Sequenzen +
manuelle Trigger + Mute-Option gewünscht.

**Entscheidung:** Sound spielt auf dem **Roboter-Speaker** (der Roboter äußert sich zur
Umwelt). Die App ist nur **Auslöser** (`hexapod_audio`-Service). Auto-Sounds triggert die
Sequenz-Logik; **Mute = Roboter-seitiger Param** (`sound_enable`), den die App togglet.
**Zweitrangig** — eigener Node, hängt an nichts, jederzeit nachziehbar (Phase 7).

**Verworfen:**
- **Sound auf dem Handy-Speaker** — wäre Bediener-Feedback, nicht „Roboter äußert sich".
  Nicht die Absicht. (Kann später als Nice-to-have dazukommen, wenn Bediener-Töne gewünscht.)

**Konsequenzen:** Kleiner `hexapod_audio`-Node + Param. Unabhängig vom Rest.

---

## D6 — Recovery: Joint-Space-Ramp in den Stand (nicht Hinsetzen)

**Kontext:** Nach IK-/Tip-/Slip-Freeze soll der Roboter mit **einem Klick** zurück in den
Lauf, ohne System-Neustart. Hinsetzen ist aus verkrümmter Pose nicht immer gut.

**Entscheidung:** Recovery = **ursachen-agnostischer Reset + Joint-Space-Ramp aus der
aktuell gelesenen (eingefrorenen) Pose in den Stand.** Ein Roboter-seitiger Service:
`/joint_states` lesen → Plugin-Freeze lösen (`/hexapod_safety_reset` [E]) → gait-Latches +
Monitore reset → **Smooth-Step-Lerp im Joint-Space** (Reuse der Startup-Ramp-Maschinerie)
gelesene Pose → Stand-Pose → STANDING → normal. Die App macht nur *ein Button → ein Call*.

**Warum Joint-Space-Ramp:** Lerp zwischen zwei **gültigen** Posen kann **kein Joint-Limit
verletzen** (konvexe Kombination pro Gelenk) → **keine IK, kein Re-Freeze-durch-Limit**
während des Rückwegs. Die Stand-Pose ist per Definition gültig.

**Verworfen:**
- **Recovery = Hinsetzen** (`sit_down`) — aus verkrümmter/gekippter Pose evtl. schlechter;
  User-Entscheid: in den Stand, nicht sitzen.
- **Cartesian-Rückweg** — bräuchte IK, könnte re-freezen; Joint-Space ist sicherer.

**Konsequenzen / Grenzen (Software kann Physik nicht):**
- **Umgekippt / auf der Seite / zu steiler Hang:** kein Bein-Ramp richtet das → **Mensch
  stellt den Roboter grob aufrecht/bauchseits auf ebeneren Boden**, *dann* Recover-Knopf.
- Joint-Space-Ramp ist **nicht scrape-/kollisions-bewusst** (Füße fahren beliebige Bögen);
  auf flachem Boden + grob aufrecht unkritisch (v1).
- Bei weiter schlechten Params freezt er nach dem Loslaufen wieder — Recovery fixt nur den
  Zustand, nicht die Params (akzeptiert).
- **„out of reach"** (Sim-Fall) triggert gar keinen Plugin-Freeze (nur „joint limit" auf
  HW) → Recovery zielt v. a. auf den Joint-Limit-Freeze; out-of-reach erholt sich schon
  beim Kommandieren einer gültigen Pose.

---

## D7 — Zweistufiger Start (Always-On + On-Demand)

**Kontext:** Die App soll den Roboter „starten" — aber dafür muss schon etwas laufen
(Henne-Ei).

**Entscheidung:** **Stufe 1 (Always-On, systemd ab Boot):** `rosbridge_server` + schlanker
**Launcher-Node** (Services `bringup_start`/`bringup_stop`/`shutdown`). **Stufe 2 (On-
Demand):** der schwere Gait-/HW-Stack, von der App gestartet. App-Flow: **Verbinden**
(WebSocket zur Always-On-Schicht) → **Hexapod starten** (Bringup) → volle Steuer-UI.

**Verworfen:**
- **Schwerer Stack auch auto-start beim Boot** — bequemer, aber der Roboter würde ggf.
  losbewegen, bevor man bereit ist. On-Demand ist der sichere Default (später optional
  auto-start für einen „einschalten → steht auf"-Modus).

**Konsequenzen:** Der `hexapod_supervisor` (Block F, macht schon Shutdown + OS-Guard) ist
der natürliche Ort für den Launcher. **Realitäts-Haken:** `ros2 launch` als Subprozess
sauber starten/stoppen (keine Zombie-Prozesse) braucht Sorgfalt im Launcher-Node.

---

## D8 — Controller-Mapping in der App + Portabilitäts-Profile

**Kontext:** Anforderung NF5 — auf einen anderen Controller mit geringem Aufwand wechseln.

**Entscheidung:** Die Eingabe-Schicht baut auf einem **abstrakten Action-Set** auf
(„translate", „rotate", „sit_stand", „stance_up"…), entkoppelt von physischen Tasten. Pro
Controller ein **Profil (JSON)**, das Achsen-/Button-Indizes → Actions mappt. Die App
normalisiert die aktive Action-Belegung auf das PS4-`/joy`-Layout (D3).

**Verworfen:**
- **Fixe Kishi-Verdrahtung im Code** — Wechsel würde Code-Umbau bedeuten.
- **Mapping am Roboter** (`kishi.yaml`) — falsche Stelle (D3).

**Konsequenzen:** Kishi-Profil zuerst; anderer Controller = neues Profil (+ optional Remap-
Screen). Die in Phase 1 notierten Kishi-Achsen-/Button-Indizes sind die Basis des ersten
Profils.

---

## D9 — Zwei-Repo-/Zwei-Sessions-Entwicklung, Kopplung über den Contract

**Kontext:** ROS-Seite (hexapod_ws) und App-Seite (Android-Repo) sind getrennte Codebasen
+ Toolchains. Frage war: „durch zwei Agents, die sich absprechen"?

**Entscheidung:** **Split by side als zwei Sessions/Kontexte**, gekoppelt über den
**versionierten `interface_contract.md` (Single Source), NICHT über Live-Agent-
Verhandlung.** Das ist das klassische Frontend/Backend-Muster: **einmal Contract einigen,
dann unabhängig dagegen bauen, am Ende integrieren.** Der User ist Integrator/Architekt;
der Contract wird **einmal, menschlich-geführt** designt, beide Seiten *konsumieren* ihn.

**Verworfen:**
- **Zwei persistente, autonom verhandelnde Peer-Agents** — Tooling dafür unzuverlässig
  (driftende Kontexte, brüchige Abstimmung); man debuggt die Agent-Kommunikation statt den
  Roboter. Zudem weicht Live-Kopplung die saubere Contract-Naht wieder auf.

**Konsequenzen:** Diese Session = ROS + Contract-Autorschaft. Zweite Claude-Code-Session im
Android-Repo = App-Seite, liest denselben Contract read-only. Subagents nur für abgegrenzte
Einzeltasks (Recherche/Review), nicht als Dauer-Peers. Contract bekommt **Version +
Changelog**, damit die App-Seite Änderungen sieht.

---

## D10 — Doku unified in hexapod_ws mit Kontext-Tags

**Kontext:** Manche Befehle laufen in hexapod_ws (ROS), manche in Android Studio, manche am
Handy. Wie ablegen, ohne Verwirrung?

**Entscheidung:** **Alle Spec-/Phasen-Doku bleibt in `hexapod_ws`** (ein Gehirn). Jeder
Befehlsblock in test_commands trägt einen **Kontext-Tag** (`▶ ROS (hexapod_ws)` / `▶ App
(Android Studio)` / `▶ Handy`). Der App-Repo bekommt nur **dünne, mechanische** Doku
(Build/Emulator) + einen **Zeiger** auf `interface_contract.md`. Der Contract wird **nie
dupliziert** (Duplikate driften), nur referenziert.

**Verworfen:**
- **test_commands physisch nach ROS/App splitten** — aber ein Phasen-Test ist end-to-end
  (App + ROS zusammen); Split zerreißt die „wie teste ich diese Phase"-Story.

**Konsequenzen:** Eine test_commands-Datei pro Phase (hexapod_ws) mit Tags; Contract single-
source mit Changelog.
