# Audio MAX98357A + Lautsprecher — Hello-World-Inbetriebnahme

> Isolierter Funktionsnachweis. Verstärker + 4 Ω/3 W-Speaker liegen **neben** dem Roboter.
> Gesamt-Kontext: [`00_overview.md`](00_overview.md).

## 1. Ziel & Hardware

- **Gerät:** MAX98357A — I2S-Class-D-Mono-Verstärker (digitaler Eingang, kein analoger Pin).
- **Speaker:** Quarkzman 3 W / 4 Ω Mini, bereits an die `+`/`–`-Klemmen des MAX98357A gelötet.
- **Ziel:** Pi erkennt den Verstärker als ALSA-Soundkarte → Testton + WAV/MP3 kommt hörbar
  aus dem Lautsprecher.

## 2. Plan-Skizze (Logik)

1. **Verdrahtung** MAX98357A ↔ Pi-GPIO (I2S-Bus = 3 Taktsignale + Strom + GND), siehe §3.
2. **I2S aktivieren** in `/boot/firmware/config.txt`: `dtparam=i2s=on` +
   `dtoverlay=hifiberry-dac`. → **Reboot durch User.**
3. **Karte verifizieren** mit `aplay -l` (Karte muss auftauchen).
4. **Ton ausgeben:** `speaker-test` (generierter Testton) → dann WAV (`aplay`) → MP3 (`mpg123`).

**Design-Entscheidung — warum `hifiberry-dac`-Overlay:**
Der MAX98357A hat **keine** Steuer-Schnittstelle (kein I2C, keine Register) → er ist ein simpler
I2S-DAC. Das bewährte `hifiberry-dac`-Overlay beschreibt genau so ein Gerät und wird breit dafür
genutzt. Alternativen (`googlevoicehat-soundcard`, gerätespezifisches `max98357a`) sind Fallbacks,
falls `hifiberry-dac` auf Pi 5/RP1 nicht greift (§7).

## 3. Verdrahtung — KRITISCH, sorgfältig prüfen

> ⚠️ **Nach Beschriftung (Silkscreen) verdrahten, nicht nach Position.** MAX98357A-Breakouts
> haben unterschiedliche Pin-Reihenfolgen und teils andere Namen. Gleiche immer das **Label auf
> deiner Platine** mit der Tabelle ab. Es sind genau **5 Drähte** (2× Strom, 3× Signal) +
> Lautsprecher.

### 3.1 Verbindungstabelle (5 Drähte)

| Amp-Pin (auch beschriftet als …) | → Pi physischer Pin | Pi-Funktion (BCM) | Richtung |
|---|---|---|---|
| `Vin` (auch `VIN`, `5V`, `V+`) | **Pin 2** (oder 4) | **5 V** | Versorgung |
| `GND` (auch `G`, `−`, `GND`) | **Pin 6** (oder 9/14/39) | GND | Versorgung |
| `BCLK` (auch `BLCK`, `SCK`, `SCLK`, `CLK`) | **Pin 12** | GPIO18 / PCM_CLK | **Pi → Amp** |
| `LRC` (auch `LRCLK`, `WS`, `FS`) | **Pin 35** | GPIO19 / PCM_FS | **Pi → Amp** |
| `DIN` (auch `SDIN`, `DATA`, `DAC`) | **Pin 40** | GPIO21 / PCM_DOUT | **Pi → Amp** |
| `GAIN` | *offen lassen* | — | (9 dB Default) |
| `SD` (auch `SD_MODE`, `SHUTDOWN`) | *offen lassen* (s. 3.4) | — | (an, (L+R)/2) |

Speaker an die `+`/`–`-Klemmen des Amp (bei dir schon gelötet).

### 3.2 Pi-Header eindeutig identifizieren (nicht „von links" raten!)

- Der Pi 5 hat denselben 40-Pin-Header wie Pi 4. **Pin 1** erkennst du am **quadratischen Lötpad**
  (alle anderen rund) und sitzt an der Ecke nahe der microSD-Karte.
- **Gerade** Pin-Nummern (2,4,6,…40) liegen in **einer** Reihe, **ungerade** (1,3,…39) in der anderen;
  Pin 1 und 2 sind am selben Ende.
- Gegencheck (optional, sicherste Methode — zeigt ASCII-Diagramm deiner Platine):
  ```bash
  sudo apt install -y python3-gpiozero && pinout
  ```
- Merke: **5 V = Pin 2 & 4** (beide am Pin-1-Ende). **Signal-Pins 12 / 35 / 40.**

### 3.3 ⚠️ Sicherheit — so zerschießt du nichts

1. **5 V GEHÖRT AUSSCHLIESSLICH AN `Vin`.** Landet die 5 V versehentlich an `BCLK`/`LRC`/`DIN`
   (= GPIO), ist der **GPIO sofort zerstört** — Pi-GPIO sind **3,3 V** und **nicht 5-V-tolerant**.
2. **`Vin`/`GND` nicht vertauschen.** Verpolung kann den Verstärker zerstören.
3. **Kein verrutschter Draht** auf einen Nachbar-Pin (z.B. Pin 2 = 5 V neben Pin 1 = 3,3 V; Pin 4 = 5 V
   neben Pin 6 = GND). Jeder Draht **einzeln** kontrollieren.
4. **Lautsprecher = BTL (brückenverstärkt):** **keiner** der beiden `+`/`–`-Ausgänge ist Masse!
   **Niemals** eine Lautsprecher-Klemme an `GND` oder an einen anderen Verstärker-Ausgang legen →
   Amp-Schaden. (Deine +/−-Lötung ist ok — nur nicht nachträglich nach GND brücken.)
5. **`SD` nie an GND** (= Shutdown — *kein* Schaden, aber kein Ton).
6. Info, kein Risiko: Die Signal-Pins sind **3,3-V-Logik**; der MAX98357A akzeptiert 3,3-V-Logik
   → **kein Level-Shifter nötig**.

### 3.4 `SD` / `GAIN` — Verhalten + Fallback

- **`GAIN` offen lassen** = 9 dB (reicht). Andere Stufen (3–15 dB) per Beschaltung — später, kein Risiko.
- **`SD` offen lassen**: auf den meisten Breakouts (inkl. Adafruit) = **an, Mono-Mix (L+R)/2**.
  Das Verhalten ist aber **board-spezifisch** (hängt vom Pull-Widerstand auf der Platine ab).
- **Falls kein Ton** (aber Karte in `aplay -l` da → §6): `SD` ist der erste Verdächtige. Dann
  `SD` fest auf **3,3 V** (Pin 1 oder 17) legen → **garantiert an** (dann Links-Kanal statt Mix).
  Das ist **sicher** (Logik-Pin, innerhalb Vdd). Lieber Links-Kanal als versehentlicher Shutdown.

### 3.5 GPIO-Konflikt-Check

GPIO18/19/21 sind nach Projektstand frei (Servo2040 über USB; F-Block-Shutdown-Schalter am
Servo2040 GP27, nicht am Pi-GPIO). **Vor dem Verdrahten kurz gegenprüfen**, dass keine andere
Overlay-Zeile diese Pins belegt:

```bash
grep -nE 'dtoverlay|gpio|i2s' /boot/firmware/config.txt
```

### 3.6 Reihenfolge + Doppelprüfung VOR dem Einschalten

> ⚠️ **Pi herunterfahren und vom Strom trennen, bevor du an die GPIO-Pins gehst.** Ungekeyte
> Stiftleiste → ein Fehler kann den Pi beschädigen.

1. `sudo shutdown -h now` → **Netzteil ziehen**.
2. Die 5 Drähte + Lautsprecher nach 3.1 stecken.
3. **Checkliste vor dem Einschalten** (am besten zusätzlich mit Multimeter/Durchgangsprüfer):
   - [ ] `Vin` → Pin 2/4 (5 V) — **nicht** an einem GPIO
   - [ ] `GND` → ein GND-Pin (z.B. 6)
   - [ ] `BCLK` → Pin 12, `LRC` → Pin 35, `DIN` → Pin 40 — jeweils gegen das **Amp-Label** geprüft
   - [ ] `Vin`/`GND` nicht vertauscht; kein Draht auf Nachbar-Pin verrutscht
   - [ ] Lautsprecher an `+`/`–`, **nicht** an GND
4. Netzteil dran, einschalten. **Der Verstärker darf NICHT sofort heiß werden** — wird er's,
   **sofort ausschalten** → Fehlverdrahtung (meist Verpolung).

## 4. Tests-Liste

| Test | Prüft | Done wenn |
|---|---|---|
| T1 `aplay -l` | Overlay geladen, Karte da | Karte (z.B. `snd_rpi_hifiberry_dac`) gelistet |
| T2 `speaker-test` | I2S-Datenpfad + Verstärker + Speaker | Testton/Rauschen hörbar |
| T3 WAV (`aplay`) | echte Audio-Datei spielbar | WAV hörbar, sauber |
| T4 MP3 (`mpg123`) | MP3-Wiedergabe | kurze MP3 hörbar |

**Bewusst NICHT getestet (scope-out):** ROS-Anbindung (Sprachausgabe-Node / `sound_play`),
Lautstärke-Regelung in Software (Softvol), gleichzeitige HDMI-Audio-Nutzung, Klangqualität/
Verzerrung am Limit, Dauerlast/Temperatur.

## 5. Installation & Config

> **Vorab:** Verdrahtung nach §3 prüfen, dann Pi einschalten: `ssh hexapod-pi`

### 5.1 I2S aktivieren (idempotent)

```bash
grep -q '^dtoverlay=hifiberry-dac' /boot/firmware/config.txt \
  || printf 'dtparam=i2s=on\ndtoverlay=hifiberry-dac\n' | sudo tee -a /boot/firmware/config.txt
```

Kontrolle:

```bash
grep -nE 'i2s|hifiberry' /boot/firmware/config.txt
```

Prüfen, dass das Overlay überhaupt vorhanden ist (sollte mit dem Kernel kommen):

```bash
ls /boot/firmware/overlays/ | grep -i hifiberry
```

### 5.2 Reboot — **durch den User**

```bash
sudo reboot
```

> ⚠️ Reboot führst **du** aus (CLAUDE.md §5). Danach neu einloggen: `ssh hexapod-pi`

### 5.3 Audio-Tools installieren

```bash
sudo apt update
sudo apt install -y alsa-utils mpg123
```

## 6. Test-Befehle

### T1 — Karte erkannt?

```bash
aplay -l
```

Erwartung: eine Karte wie `card 0: sndrpihifiberry [snd_rpi_hifiberry_dac] ...`.
**Kartennummer notieren** (hier als `N` bezeichnet; meist `0`).

> Tipp: Statt der Nummer kannst du in allen folgenden Befehlen auch den **Kartennamen**
> verwenden (robuster, ändert sich nicht): z.B. `-D plughw:CARD=sndrpihifiberry` statt
> `-D plughw:N,0`. Den genauen Namen zeigt dir `aplay -l` in den eckigen Klammern.

### T2 — Testton

```bash
speaker-test -D plughw:N,0 -c2 -twav -l1
```

Erwartung: kurzer Sprach-/Rausch-Testton aus dem Lautsprecher. (`-c2` mischt auf den Mono-Kanal,
das ist ok.)

### T3 — WAV abspielen

Eine systemeigene Test-WAV (falls vorhanden) oder eine eigene Datei:

```bash
aplay -D plughw:N,0 /usr/share/sounds/alsa/Front_Center.wav
```

> Falls die Datei fehlt: eine WAV per `scp` vom Dev-Rechner kopieren, z.B.
> `scp meine.wav hexapod-pi:~/` und dann `aplay -D plughw:N,0 ~/meine.wav`.

### T4 — MP3 abspielen

```bash
mpg123 -a plughw:N,0 ~/test.mp3
```

> MP3 vorher auf den Pi bringen: `scp test.mp3 hexapod-pi:~/`

**Verifikation:** Bei T2–T4 jeweils klarer, hörbarer Ton ohne starke Verzerrung.

## 7. Done-Kriterien (Checkliste)

- [x] Verdrahtung nach §3 (SD/GAIN floating, Vin=5 V)
- [x] I2S aktiviert (`config.txt`), Overlay (`hifiberry-dac.dtbo`) vorhanden, Pi rebootet
- [x] `aplay -l` listet die Karte `sndrpihifiberry [snd_rpi_hifiberry_dac]` — **Karte N = 0**
- [x] `speaker-test` hörbar („Front Left/Right")
- [x] WAV (`aplay`) hörbar („Front Center")
- [x] MP3 (`mpg123`) hörbar (`ubludok.mp3`)

✅ **Audio-Hello-World verifiziert.** 🟡 Offener Finetune-Punkt: leichtes **Knarzen** (als Hardware
eingegrenzt → Stützelko + saubere Verkabelung im Finalaufbau, s. §8/§9). Kein Funktions-Blocker.
Status in `00_overview.md` = 🟢.

## 8. Troubleshooting

| Symptom | Ursache / Fix |
|---|---|
| `aplay -l` zeigt keine Karte | Overlay nicht geladen: `config.txt`-Zeilen / Reboot prüfen; Overlay-Datei vorhanden? (§5.1) |
| Overlay fehlt in `/boot/firmware/overlays/` | Kernel-/Firmware-Paket unvollständig → Fallback-Overlay `googlevoicehat-soundcard` probieren |
| Karte da, aber kein Ton | `SD` versehentlich auf GND (= Shutdown) → floating lassen; Speaker-Polung/Lötstellen prüfen |
| Ton verzerrt/leise | GAIN anpassen; Vin wirklich 5 V?; Speaker 4 Ω an Class-D ok |
| `aplay`/`speaker-test`: „Device or resource busy" | anderer Prozess belegt die Karte; oder falsche `plughw:N,0`-Nummer (per `aplay -l` prüfen) |
| Nur auf einem „Kanal" / Mono-Frage | MAX98357A ist Mono; `(L+R)/2`-Mix bei SD floating ist gewollt |
| **Knacken/Knarzen** (auch bei reinem Sinus + bei leiser Wiedergabe; Buffer hilft kaum) | **Strom/Verkabelung**, nicht Pegel/Underrun. Fix: **Stützelko 100–470 µF** (Elko, `+`→Vin / `−`→GND, direkt am Amp) **+ 100 nF** parallel; alle Steckverbindungen **fest + kurz**; solide 5 V. Diagnose-Trennung: Sinus-Test (`speaker-test … -t sine`) vs. leiser MP3 (`mpg123 -f 8000 …`) — knarzt beides → Hardware. |

## 9. Offene Punkte / spätere Integration

- **ROS-Sprachausgabe:** späterer Node (z.B. `sound_play` oder eigener Player-Node) für
  Status-/Warn-Töne. Erst bei echter Integration → **dann** in reguläre Docs.
- **Lautstärke in Software:** ALSA-`softvol`-Plugin (`~/.asoundrc`), da der MAX98357A keine
  HW-Lautstärke hat. Für Hello-World nicht nötig.
- **Einbau-Pegel:** finale GAIN-Beschaltung erst nach Gehäuse-/Einbau-Test festlegen.
- **Befund Knarzen (offen, Fix bekannt):** Wiedergabe läuft, aber leichtes Knacken/Knarzen.
  Per Sinus-/Leise-Test als **Hardware** (Strom/Verkabelung) eingegrenzt — *nicht* Pegel/Underrun.
  **Fix für den Finalaufbau:** Stützelko 100–470 µF (+100 nF) direkt an Vin/GND, kurze/feste
  Leitungen, eigene saubere 5-V-Schiene. Aktuell kein Kondensator zur Hand → nachrüsten.
