# Deployment-Workflow Desktop → Raspberry Pi

**Status:** Querschnitts-Doku, kein eigenes Phasen-Done-Kriterium
**Wird referenziert von:** Phase 12 (Pi-Plattform) und allen späteren Phasen
**Letztes Update:** Erst-Anlage in Phase-7-Planung, finalisiert in Phase 12

---

## Zweck

Code, der am Ubuntu-Desktop entwickelt wird, muss zuverlässig und schnell
auf dem Raspberry Pi 5 ankommen — sowohl für stabile Commits als auch für
schnelle „eben mal testen"-Iterationen.

Dieses Doc beschreibt die Werkzeuge und Konventionen dafür. Wird in Phase 12
Stufe G konkret durchgespielt und finalisiert.

---

## Hintergrund: warum nicht einfach `install/` rüberkopieren?

- Desktop ist **x86_64**, Pi ist **arm64**.
- `colcon build` produziert architektur-spezifische Binaries.
- `install/`-Verzeichnis des Desktops läuft auf dem Pi **nicht**.
- Konsequenz: **Source rüber, Build dort.** Immer.

---

## Empfohlene Werkzeuge

### Primär: Git als Source of Truth

- Für jeden stabilen Stand (= Phase-Done-Kriterium erfüllt, Commit-würdig):
  Commit am Desktop → Push → Pull am Pi → Build am Pi.
- Macht Versionierung sauber, ermöglicht Tags pro Phasen-Abschluss
  (`phase-N-done`).

### Sekundär: rsync für schnelle Iteration

- Für „eben mal testen" zwischen Commits.
- Verhindert Commit-Lärm bei jeder kleinen Code-Änderung.
- Wichtig: `build/`, `install/`, `log/` **ausschließen**.

### Tertiär: VSCode Remote-SSH

- Für direktes Editieren von Files am Pi (z. B. udev-Rules, Pi-spezifische
  Configs).
- VSCode öffnet den Workspace auf dem Pi, baut auch dort.
- IDE-Komfort wie lokal, aber Build/Run passiert am Pi.

### Anti-Pattern

- ❌ `install/` rüberkopieren (Architektur-Mismatch)
- ❌ NFS-Mount des Desktop-Workspace am Pi mit gemeinsamem `build/` (Konflikt
  zwischen Desktop- und Pi-Builds)
- ❌ sshfs als Build-Verzeichnis (Latenz, IO-Probleme)

---

## SSH-Setup

### Schlüssel-Auth statt Passwort

Am Desktop, falls noch kein Key:
```bash
ssh-keygen -t ed25519 -C "desktop-to-hexapod-pi"
ssh-copy-id enjoykin@hexapod-pi.local
```

### `~/.ssh/config`-Alias

```
Host hexapod-pi
    HostName hexapod-pi.local
    User enjoykin
    IdentityFile ~/.ssh/id_ed25519
    ServerAliveInterval 60
    ServerAliveCountMax 3
```

Dann reicht überall `ssh hexapod-pi` als Kommando.

### Multiplexing für schnelle Subsequent-SSH

```
Host hexapod-pi
    ...
    ControlMaster auto
    ControlPath ~/.ssh/cm-%r@%h:%p
    ControlPersist 10m
```

Vorteil: zweiter `ssh hexapod-pi` öffnet sofort, ohne Key-Auth-Handshake.

---

## Workflow 1: Git (für Stable Stände)

### Desktop

```bash
cd ~/hexapod_ws
git add -A
git commit -m "phase<N>: <description>"
git push
```

### Pi

```bash
ssh hexapod-pi
cd ~/hexapod_ws
git pull
colcon build --symlink-install
source install/setup.bash
```

Helper-Alias am Desktop:
```bash
alias hexapod-deploy='ssh hexapod-pi "cd ~/hexapod_ws && git pull && colcon build --symlink-install"'
```

---

## Workflow 2: rsync (für schnelle Iteration)

### Befehl

```bash
rsync -avz --delete \
  --exclude=build \
  --exclude=install \
  --exclude=log \
  --exclude=.git \
  --exclude=__pycache__ \
  --exclude='*.pyc' \
  ~/hexapod_ws/ hexapod-pi:~/hexapod_ws/
```

`--delete` synchronisiert auch Löschungen. Vorsicht: kann unbeabsichtigt
Dateien am Pi löschen, die nur dort existieren. Bei Bedarf weglassen.

### Helper-Alias

```bash
alias hexapod-sync='rsync -avz --delete \
  --exclude=build --exclude=install --exclude=log \
  --exclude=.git --exclude=__pycache__ --exclude="*.pyc" \
  ~/hexapod_ws/ hexapod-pi:~/hexapod_ws/'
```

### Build am Pi triggern

```bash
ssh hexapod-pi "cd ~/hexapod_ws && colcon build --symlink-install"
```

Oder kombiniert:
```bash
alias hexapod-push-build='hexapod-sync && ssh hexapod-pi "cd ~/hexapod_ws && colcon build --symlink-install"'
```

---

## Workflow 3: VSCode Remote-SSH

### Setup

1. VSCode + Extension „Remote - SSH" installiert
2. F1 → „Remote-SSH: Connect to Host…" → `hexapod-pi`
3. Workspace `~/hexapod_ws/` öffnen

### Vorteile

- Direktes Editieren am Pi
- Terminal in VSCode ist Pi-Terminal
- `colcon build` aus VSCode-Tasks
- Git-Operationen direkt aus VSCode

### Wann sinnvoll

- Pi-spezifische Configs anpassen (udev, systemd, etc.)
- Debugging-Sessions am Pi
- Wenn man nicht ständig zwischen Desktop und Pi hin- und herschalten will

### Wann **nicht** sinnvoll

- Hauptentwicklung — Desktop-IDE ist schneller und Workspace ist primär
  hier verwaltet
- Wenn Sim-Tests parallel laufen sollen (geht auf Pi nicht — kein Gazebo)

---

## Shutdown-Disziplin

Aus Phase 12 Stufe H:

- **Immer** `sudo shutdown -h now` per SSH bevor PSU/Hauptschalter aus.
- Warten bis grüne LED am Pi erlischt.
- **Erst dann** Strom trennen.
- Begründung: Pi 5 + Linux + USB-SSD verzeiht keine schmutzige Abschaltung
  im laufenden Schreibvorgang. SD ist noch empfindlicher.

Alias am Desktop:
```bash
alias hexapod-shutdown='ssh hexapod-pi sudo shutdown -h now'
```

---

## Build-Hinweise

### `--symlink-install` immer benutzen

```bash
colcon build --symlink-install
```

Python-Files werden via Symlink installiert → keine `pip install --user`-
Wiederholung nach jeder Änderung nötig.

### Selektive Builds

```bash
colcon build --packages-select hexapod_hardware --symlink-install
colcon build --packages-up-to hexapod_bringup --symlink-install
```

Beim Iterieren am Pi viel schneller.

### Parallelität auf Pi

Pi 5 hat 4 Cores. Standard ist OK, bei RAM-Problemen runter:

```bash
colcon build --symlink-install --parallel-workers 2
```

---

## Stolperfallen

| Symptom | Ursache | Fix |
|---|---|---|
| `Permission denied (publickey)` | Key nicht auf Pi installiert | `ssh-copy-id` nochmal, oder Passwort-Fallback in Imager-Settings |
| rsync transferiert `build/` mit | Exclude vergessen | Excludes-Block oben kopieren |
| Pi-Build extrem langsam | SD-Karte statt SSD, oder zu wenig RAM | Auf SSD wechseln, `--parallel-workers 2` |
| `colcon build` läuft am Pi aber neue Datei wirkt nicht | `source install/setup.bash` vergessen | erneut sourcen, oder `~/.bashrc` ergänzen |
| `mDNS hexapod-pi.local` nicht auflösbar | avahi-Daemon down, oder Router blockiert | IP statt mDNS verwenden, `avahi-daemon` prüfen |
| VSCode Remote-SSH klemmt | Server-Komponente verteilt sich beim Erstverbinden, kann dauern | abwarten, oder VSCode-Server am Pi manuell aktualisieren |
| Inkonsistente Stände Desktop/Pi | rsync ohne `--delete` und alte Datei rumgeflogen | mit `--delete` syncen, oder manuell aufräumen |

---

## Konvention

Was wird wie deployt?

| Was | Workflow | Begründung |
|---|---|---|
| Phasen-Abschluss-Stände | Git | Tag-bar, reproduzierbar |
| Aktive Iteration in einer Phase | rsync | Schnell, keine Commit-Lärm |
| Pi-spezifische Configs (udev, etc.) | VSCode Remote-SSH | Editieren direkt am Pi sinnvoll |
| URDF / Kalibrierungs-YAML | Git | Versioniert wichtig |
| Test-Skripte für lokale Versuche | rsync | Wegwerf-Code, kein Commit nötig |
