# Phase 7 Stufe A — Hello-World-Flash Test

**Ziel:** Validieren, dass die in Stufe A gebaute Firmware
(`Hexapod_servo_driver.uf2`) auf dem realen Servo2040 startet, USB-CDC
aufkommt und die Boot-Message sendet.

**Voraussetzungen (Hardware):**

- Servo2040 mit USB-Kabel an Desktop
- **KEINE Servos angeschlossen** (siehe Abschnitt 0)
- User in `dialout`-Gruppe (Check: `id | grep dialout`)
- Build-Artefakt vorhanden:
  `/home/enjoykin/hexapod_servo_driver/build/Hexapod_servo_driver.uf2`

> Bitte Befehle einzeln ausführen, kurze Status-Rückmeldungen reichen
> (kein voller Output nötig).

---

## Abschnitt 0 — Netzteil-Setup (vor Anschluss)

### Brauchen wir das Netzteil für Hello-World? — **Nein.**

Der Trace-Cut auf dem Servo2040 trennt Servo-Rail vom USB-Power. Der
RP2040 + Pimoroni-Hardware bekommen ihre 3.3V/5V aus dem **USB-Kabel**.
Für den reinen Flash-Test reicht das.

Wenn du das externe Netzteil trotzdem mit anschließen willst (Akku-Setup
schon mal üben), folgende Werte einstellen **bevor** der XT60-Stecker am
Board sitzt:

| Parameter | Wert | Begründung |
|---|---|---|
| Spannung | **6.0 V** | Sicher unter LiPo-2S-Voll (8.4 V), über LiPo-Cutoff (6.0 V). Kompatibel mit allen deinen Test-Servos. Schützt MG90S (max 6 V) und MG996R (max 7.2 V) falls versehentlich angeschlossen. |
| Strom-Limit | **1.0 A** | Board ohne Servos zieht <300 mA. 1 A gibt 3–4× Reserve und regelt bei Kurzschluss schnell ab. |
| PSU-Modus | Single-Channel | Parallel-Modus braucht's hier nicht — Last ist klein. |

> **Akku-Kontext für später:** Der geplante Zeee 2S LiPo (7.4 V nominal,
> 8.4 V voll, 6.0 V Cutoff) wird mit dem Netzteil simuliert. 6.0 V ist
> der konservative Test-Wert. Späteres Hochfahren auf 7.4 V kommt in
> Stufe D/E, wenn Strom-Limits + LV-Cutoff schon drin sind.

### Vor Anschluss am Servo2040

1. PSU **aus**.
2. Spannung auf 6.0 V einstellen (PSU-Display kontrollieren).
3. CC-Limit auf 1.0 A.
4. PSU **kurz einschalten**, mit Multimeter an den XT60-Stecker-Pins
   verifizieren: **6.0 V ±0.05 V**.
5. PSU **aus**.
6. XT60-Stecker am Servo2040 einstecken (Polung beachten!).
7. PSU **erst nach** Flash-Test einschalten (Schritt 7 dieser Anleitung).

### Warum keine Servos beim Hello-World

- Die Firmware fährt aktuell ohne Sicherheits-Ebenen (Hard-Clamp,
  Watchdog, Soft-Ramp fehlen — kommen in Stufe C).
- MG90S verträgt max 6.0 V, MG996R max 7.2 V. LiPo voll wäre 8.4 V → bei
  späterem Akku-Test ohne Beschränkung sofort Schaden.
- Erst wenn die Sicherheits-Schicht drauf ist und kalibriert wurde, dürfen
  Servos dran.

---

## Schritt 1 — Vor-Anschluss-Check

```bash
ls -la ~/hexapod_servo_driver/build/Hexapod_servo_driver.uf2
id | grep -o 'dialout' || echo "NICHT in dialout-Gruppe"
ls /dev/ttyACM* 2>/dev/null || echo "(keine ttyACM-Devices vor Anschluss)"
```

**Erwartet:**
- `.uf2` existiert (~131 KB)
- `dialout` ausgegeben
- Vor Anschluss: keine ttyACM-Devices

---

## Schritt 2 — Servo2040 in BOOTSEL-Mode bringen

1. USB-Kabel **abziehen** vom Servo2040
2. **BOOTSEL-Knopf gedrückt halten**
3. USB-Kabel einstecken (BOOTSEL noch gedrückt)
4. BOOTSEL loslassen
5. Verifikation:

```bash
lsusb | grep -i 'raspberry\|2e8a'
ls /media/$USER/RPI-RP2 2>/dev/null && echo "BOOTSEL-Mount sichtbar"
```

**Erwartet:**
- `lsusb`: ein Eintrag mit Vendor `2e8a` (Raspberry Pi)
- entweder `/media/$USER/RPI-RP2` ist gemountet, oder picotool kann's
  später sehen

---

## Schritt 3 — Flash (eine Variante wählen)

### Variante A: picotool (empfohlen)

```bash
sudo ~/.local/bin/picotool info -a
sudo ~/.local/bin/picotool load ~/hexapod_servo_driver/build/Hexapod_servo_driver.uf2
sudo ~/.local/bin/picotool reboot
```

**Erwartet:**
- `info -a` zeigt Board als RP2040, `Application Information` (von der
  alten Firmware drauf)
- `load` zeigt Progress-Bar bis 100 %
- `reboot` ohne Fehler

### Variante B: BOOTSEL Drag-and-Drop

```bash
cp ~/hexapod_servo_driver/build/Hexapod_servo_driver.uf2 /media/$USER/RPI-RP2/
sync
```

**Erwartet:**
- Kopier-Befehl ohne Fehler
- `sync` returnt sofort
- Mount `/media/$USER/RPI-RP2` verschwindet automatisch (Board rebootet)

---

## Schritt 4 — Boot verifizieren

Nach dem Flash bootet das Board in die Firmware. Diese:
- Initialisiert USB-CDC
- Wartet 2 Sekunden, dann auf USB-Connect-Erkennung
- Sendet `Servo2040 USB-UART Communication Started...\n`

```bash
sleep 3
ls /dev/ttyACM* 2>&1
dmesg | grep -i 'cdc_acm\|ttyACM' | tail -5
```

**Erwartet:**
- `/dev/ttyACM0` (oder ACM1, je nach freiem Slot)
- `dmesg`: `cdc_acm ... ttyACM0: USB ACM device`

---

## Schritt 5 — Boot-Message lesen

```bash
sudo cat /dev/ttyACM0 &
CAT_PID=$!
sleep 4
kill $CAT_PID 2>/dev/null
```

**Erwartet (eine der folgenden):**

- Sichtbare Zeile: `Servo2040 USB-UART Communication Started...`
- Oder leere Ausgabe (Boot-Message wurde gesendet, bevor `cat` lauschte)

Falls leer: kurz `sudo picotool reboot` und Schritt 5 wiederholen — beim
Re-Boot wird die Message neu gesendet.

---

## Schritt 6 — Aufräumen

```bash
sudo killall cat 2>/dev/null
ls /dev/ttyACM*
```

USB-Kabel kann angesteckt bleiben — Board braucht für Stufe B/C ohnehin
USB.

---

## Schritt 7 (optional) — Netzteil einschalten

**Nur** wenn Abschnitt 0 mit Spannung/Strom korrekt eingestellt wurde und
der XT60 schon am Board sitzt:

```bash
# PSU einschalten, dann Last-Strom ablesen
```

**Erwartet:**
- Strom-Anzeige am PSU < 100 mA (Board ohne Servos zieht praktisch nichts
  aus dem Servo-Rail, weil über USB versorgt — der Servo-Rail-Bezug ist
  nur für Servos da, die nicht angeschlossen sind).
- Spannung bleibt stabil bei 6.0 V.

Falls Strom-Anzeige **plötzlich am Limit** (1 A) klebt: PSU sofort
**aus**, Verkabelung prüfen (XT60-Polung!).

---

## Was zu mir zurückmelden

Knapp:
1. **Welche Flash-Variante** (A picotool oder B BOOTSEL)?
2. **Flash erfolgreich?** (Ja/Nein, ggf. Fehlermeldung)
3. **`/dev/ttyACM*` da?** (Ja/Nein, welche Nummer)
4. **Boot-Message gelesen?** (Ja/Nein/leer)
5. **Netzteil verwendet?** (Ja/Nein) — falls ja: PSU-Strom-Anzeige bei
   eingeschaltetem PSU mit angeschlossenem Board

Damit hake ich Stufe-A-Done-Kriterium 3 ab und wir gehen in Stufe B.

---

## Stolperfallen

| Symptom | Ursache | Fix |
|---|---|---|
| `picotool: command not found` | `~/.local/bin` nicht in PATH | absoluten Pfad nutzen: `~/.local/bin/picotool` |
| `picotool info`: `No accessible RP-series devices in BOOTSEL mode were found` | Board nicht im BOOTSEL-Mode oder schon geflashed | Schritt 2 wiederholen, oder Board ist bereits gebootet — nutze `picotool info -f` (force reboot to BOOTSEL via USB) |
| `Permission denied` auf `/dev/ttyACM0` | nicht in `dialout`-Gruppe oder neu eingeloggt | `id \| grep dialout` prüfen, ggf. `sudo usermod -aG dialout $USER` + neu einloggen |
| Mount `/media/$USER/RPI-RP2` fehlt | Auto-Mount aus, oder Board nicht im BOOTSEL | `lsblk` prüfen — wenn Block-Device da, manuell mounten |
| Boot-Message kommt nicht | `stdio_usb_connected()` wartet noch — `cat` zu früh oder zu spät | `picotool reboot`, sofort `cat` neu starten |
| PSU-Strom plötzlich am Limit | XT60 falsch gepolt oder Kurzschluss | PSU **sofort aus**, Polung am XT60-Stecker am Board mit Multimeter prüfen |
