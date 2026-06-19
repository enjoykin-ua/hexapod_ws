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

## 3. Verdrahtung (BCM-Nummerierung / physische Pins)

| MAX98357A | Pi-Signal | BCM | Physischer Pin |
|---|---|---|---|
| `Vin` | 5 V | — | Pin 2 oder 4 |
| `GND` | GND | — | z.B. Pin 6 |
| `DIN` | I2S Data Out | GPIO21 | Pin 40 |
| `BCLK` | I2S Bit Clock | GPIO18 | Pin 12 |
| `LRC` | I2S Word Select | GPIO19 | Pin 35 |
| `GAIN` | **offen lassen** | — | — (floating = 9 dB) |
| `SD` | **offen lassen** | — | — (floating = an, Mono-Mix) |

**Hinweise:**
- **`Vin` auf 5 V** für volle Leistung (am 4-Ω-Speaker ~3 W). Akzeptiert 2,5–5,5 V.
- **`SD` NICHT auf GND** ziehen — das ist Shutdown. Floating = eingeschaltet + Mono-Mix `(L+R)/2`.
- **`GAIN`** floating = 9 dB (reicht). Lauter/leiser über GAIN-Beschaltung (3–15 dB) erst bei Bedarf.
- **GPIO-Konflikt:** GPIO18/19/21 sind frei — Servo2040 hängt am USB, der F-Block-Shutdown-Schalter
  sitzt am Servo2040 (GP27), nicht am Pi-GPIO. Kein Konflikt mit der Roboter-Funktion.

> **Strom abgeschaltet verdrahten.** Erst stecken, dann Pi booten.

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

- [ ] Verdrahtung nach §3 (SD/GAIN floating, Vin=5 V)
- [ ] I2S aktiviert (`config.txt`), Overlay vorhanden, Pi rebootet
- [ ] `aplay -l` listet die Hifiberry-/MAX98357A-Karte — *Kartennummer N notiert*
- [ ] `speaker-test` hörbar
- [ ] WAV (`aplay`) hörbar
- [ ] MP3 (`mpg123`) hörbar

Alle Bullets `[x]` → Audio-Hello-World **verifiziert**, Status in `00_overview.md` auf 🟢.

## 8. Troubleshooting

| Symptom | Ursache / Fix |
|---|---|
| `aplay -l` zeigt keine Karte | Overlay nicht geladen: `config.txt`-Zeilen / Reboot prüfen; Overlay-Datei vorhanden? (§5.1) |
| Overlay fehlt in `/boot/firmware/overlays/` | Kernel-/Firmware-Paket unvollständig → Fallback-Overlay `googlevoicehat-soundcard` probieren |
| Karte da, aber kein Ton | `SD` versehentlich auf GND (= Shutdown) → floating lassen; Speaker-Polung/Lötstellen prüfen |
| Ton verzerrt/leise | GAIN anpassen; Vin wirklich 5 V?; Speaker 4 Ω an Class-D ok |
| `aplay`/`speaker-test`: „Device or resource busy" | anderer Prozess belegt die Karte; oder falsche `plughw:N,0`-Nummer (per `aplay -l` prüfen) |
| Nur auf einem „Kanal" / Mono-Frage | MAX98357A ist Mono; `(L+R)/2`-Mix bei SD floating ist gewollt |

## 9. Offene Punkte / spätere Integration

- **ROS-Sprachausgabe:** späterer Node (z.B. `sound_play` oder eigener Player-Node) für
  Status-/Warn-Töne. Erst bei echter Integration → **dann** in reguläre Docs.
- **Lautstärke in Software:** ALSA-`softvol`-Plugin (`~/.asoundrc`), da der MAX98357A keine
  HW-Lautstärke hat. Für Hello-World nicht nötig.
- **Einbau-Pegel:** finale GAIN-Beschaltung erst nach Gehäuse-/Einbau-Test festlegen.
