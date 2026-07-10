# Phase 1 — Test-Befehle: Controller-Validierung (Kishi Hello-World)

> Du führst die Tests aus, knappe Status-Meldung zurück. **Kontext-Tags** (weil diese Phase
> rein App-seitig ist, aber die Konvention ab hier gilt):
> **▶ Handy** = Bedienung am Gerät · **▶ App (Android Studio)** = Build/Code · **▶ ROS
> (hexapod_ws)** = *in dieser Phase nichts*.
>
> **Ziel:** beweisen, dass der Kishi V2 am S22+ als Gamepad lesbar ist + die Roh-Indizes
> notieren. Kein Netz, kein ROS. Plan: [`phase_1_controller_validation_plan.md`](phase_1_controller_validation_plan.md).

---

## T1.A — Zero-Code-Vorcheck (5 Minuten, KEIN Code)

**▶ Handy:**
1. S22+ (ohne Hülle zuerst, dann mit) in den Kishi V2 einsetzen (USB-C stecken).
2. Chrome öffnen, auf eine Gamepad-Test-Seite gehen, z. B.:
   - `https://html5gamepad.com/` oder `https://hardwaretester.com/gamepad`
3. **Irgendeine Taste am Kishi drücken** (die Gamepad-API meldet ein Gamepad oft erst nach
   der ersten Eingabe).

**✅ Erwartung:**
- Ein Gamepad wird gelistet (Name evtl. „Razer Kishi" o. generisch).
- **Beide Sticks** bewegen die Achsen-Balken (Ruhe ~0, Voll-Ausschlag ~±1).
- **Alle Buttons** (ABXY, L1/R1, L2/R2, Stick-Klicks L3/R3, D-Pad, Menü/Home) lösen aus.

> Melde: Gamepad erkannt? Reagiert **alles**? Falls etwas fehlt/klemmt → welche Eingabe.
> Optionaler Hinweis: L2/R2 — liefern sie einen **Wert 0..1** (analog) oder nur **0/1**
> (digital)? Nur notieren, unkritisch.

> ⚠️ **Wenn hier gar kein Gamepad erkannt wird:** stopp — das ist der Sinn des Vorchecks.
> Dann melden; wir prüfen Kishi-USB-Modus / anderes Handy (S26+), bevor Code entsteht.

---

## T1.B–T1.E — Minimale native App (das Hello-World)

> Reihenfolge: Projekt anlegen → App bauen/installieren → am Handy die Eingaben ablesen +
> Roh-Indizes notieren. Die App entsteht im **eigenen Repo** `hexapod_app` (nicht in
> hexapod_ws).

**▶ App (Android Studio):**
1. Android Studio → neues Projekt, **Empty Activity, Kotlin**, min. SDK moderat (z. B.
   API 26+). Repo-Name-Vorschlag `hexapod_app`.
2. Die minimale Gamepad-Lese-App implementieren (Umfang siehe Plan §1 Stufe B):
   - `InputManager` → verbundene Gamepads auflisten (Anzeige „Kishi gefunden: ja/nein").
   - `onGenericMotionEvent` → alle Achsen als Live-Zahlen/Balken.
   - `onKeyDown/onKeyUp` → alle Buttons als Indikatoren.
   - Jede Eingabe **mit ihrer Android-Konstante/Keycode beschriften** (für die Roh-Index-Tabelle).
3. Bauen: Gradle-Sync + Build (Android Studio „Run", oder `./gradlew assembleDebug`).

**▶ Handy:**
4. S22+ per USB an den Dev-Rechner (ADB-Debugging an) ODER die APK direkt installieren,
   dann S22+ in den Kishi.
   ```
   # ▶ App (Android Studio / Terminal im hexapod_app-Repo), falls per Kabel installiert:
   adb devices                 # S22+ sichtbar?
   adb install -r app/build/outputs/apk/debug/app-debug.apk
   ```
5. App starten, S22+ in den Kishi, jede Eingabe durchgehen.

**✅ Erwartung + was zu notieren ist:**
- **T1.B:** App zeigt „Kishi als Gamepad gefunden".
- **T1.C:** beide Sticks → Live-Achswerte, zentriert ~0, Voll ~±1.
- **T1.D:** jeder Button + D-Pad-Richtung + L1/R1 + L2/R2 löst sichtbar aus.
- **T1.E — die wichtige Ausbeute:** eine **Roh-Index-Tabelle** je physischer Eingabe →
  Android-Konstante. Grobes Format zum Zurückmelden:

  | Physisch (Kishi) | Android-Achse/Keycode | Wertebereich |
  |---|---|---|
  | Linker Stick X | `AXIS_X` | −1..+1 |
  | Linker Stick Y | `AXIS_Y` | −1..+1 |
  | Rechter Stick X | `AXIS_Z` (?) | −1..+1 |
  | Rechter Stick Y | `AXIS_RZ` (?) | −1..+1 |
  | D-Pad X/Y | `AXIS_HAT_X/Y` (?) | −1/0/+1 |
  | A / B / X / Y | `KEYCODE_BUTTON_A/B/X/Y` | 0/1 |
  | L1 / R1 | `KEYCODE_BUTTON_L1/R1` | 0/1 |
  | L2 / R2 | `KEYCODE_BUTTON_L2/R2` bzw. `AXIS_LTRIGGER/RTRIGGER` | 0/1 oder 0..1 |

  (Die `(?)` sind die typischen Vermutungen — genau das misst die App, statt es anzunehmen.)

> Melde: erkennt die App den Kishi? Reagieren alle Eingaben? **Die ausgefüllte Roh-Index-
> Tabelle** ist das Deliverable — sie wandert in [`interface_contract.md`](interface_contract.md)
> §1 als Phase-2-Vorbereitung.

---

## Eignungs-Fazit (T1.8)

Nach dem Durchlauf kurz festhalten: **Kishi V2 am S22+ tauglich — ja/nein?** (erwartet: ja),
plus die zwei mechanischen Randnotizen (Passform mit Hülle, Trigger analog/digital). Danach
ist Phase 1 abgeschlossen und Phase 2 (Steuer-Grundstrecke) plan-reif.

---

## Was NICHT in Phase 1 (scope-out)

- Kein rosbridge, kein `/joy`, kein Netz, keine Roboter-Steuerung.
- Keine Video-/Touch-UI, kein Controller-Profil-System (nur Roh-Indizes notieren).
- Keine Latenz-Messung (kommt in Phase 2 im echten Steuer-Kontext).
