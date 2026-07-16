#!/usr/bin/env python3
# Copyright 2026 enjoykin — Apache-2.0
"""
Block I Phase 2 (T2.2) — /joy über rosbridge, ohne Handy.

Publisht ``sensor_msgs/Joy`` über rosbridge (WebSocket + JSON), damit die
Steuerkette

    rosbridge → /joy → joy_to_twist → /cmd_vel → gait → Sim

**ohne die Android-App** getestet werden kann (App-Ersatz). Beweist T2.2
(Meilenstein) und T2.5 (NF1 Comms-Loss): nach ``--duration`` Sekunden stoppt
der Client → /joy verstummt → ``cmd_vel_timeout`` sollte den Roboter anhalten.

Simuliert (Layout = interface_contract.md §1 v0.2):
  - R1 Dead-Man gehalten            → buttons[5] = 1  (Fahren freigegeben)
  - linker Stick vorwärts           → axes[1]   = +forward
  - rechter Stick drehen (optional) → axes[3]   = +turn
  - Trigger idle                    → axes[2]/[5] = +1  (kein Fehl-Stance)

Voraussetzung:
    sudo apt install python3-websocket     # Ubuntu 24.04 (PEP 668, kein pip)
    ros2 launch hexapod_bringup app_teleop.launch.py     # rosbridge :9090
    # + ein Sim-Walk-Bringup läuft (Roboter steht)

Aufruf:
    python3 tools/joy_ws_test_client.py --host 127.0.0.1 --duration 5
    python3 tools/joy_ws_test_client.py --host <Desktop-IP> --turn 0.5
    python3 tools/joy_ws_test_client.py --no-deadman   # Gegentest: darf NICHT fahren
"""

import argparse
import json
import sys
import time

try:
    import websocket  # Paket: python3-websocket (liefert das websocket-Modul)
except ImportError:
    sys.exit("Fehlt: sudo apt install python3-websocket  (Ubuntu 24.04, PEP 668 → kein pip)")

# Voll-Länge nach Contract §1 v0.2: 8 Achsen, 15 Buttons (13 PS4 + L4/R4).
PS4_AXES = 8
PS4_BUTTONS = 15

# Indizes (aus ps4_usb.yaml, siehe Contract §1)
AX_LY = 1   # linker Stick Y  → vor/zurück (axis_ly)
AX_RX = 3   # rechter Stick X → drehen (axis_rx)
AX_L2 = 2   # L2 (idle = +1)
AX_R2 = 5   # R2 (idle = +1)
BTN_R1 = 5  # Dead-Man


def make_joy(forward: float, turn: float, deadman: bool) -> dict:
    axes = [0.0] * PS4_AXES
    axes[AX_LY] = forward
    axes[AX_RX] = turn
    axes[AX_L2] = 1.0   # Trigger idle = +1 (sonst Fehl-Stance)
    axes[AX_R2] = 1.0
    buttons = [0] * PS4_BUTTONS
    buttons[BTN_R1] = 1 if deadman else 0
    return {
        'header': {'stamp': {'sec': 0, 'nanosec': 0}, 'frame_id': ''},
        'axes': axes,
        'buttons': buttons,
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--host', default='127.0.0.1',
                   help='rosbridge-Host (Sim: 127.0.0.1 oder Desktop-IP).')
    p.add_argument('--port', type=int, default=9090)
    p.add_argument('--rate', type=float, default=30.0, help='Publish-Rate Hz (NF1: ~30).')
    p.add_argument('--duration', type=float, default=5.0, help='Sekunden fahren, dann Stopp.')
    p.add_argument('--forward', type=float, default=0.6, help='Linker Stick Y (−1..+1).')
    p.add_argument('--turn', type=float, default=0.0, help='Rechter Stick X (−1..+1).')
    p.add_argument('--no-deadman', action='store_true',
                   help='R1 NICHT halten → Gegentest, Roboter darf NICHT fahren.')
    a = p.parse_args()

    url = f'ws://{a.host}:{a.port}'
    print(f'[joy-test] verbinde {url} ...')
    try:
        ws = websocket.create_connection(url, timeout=5)
    except Exception as exc:  # noqa: BLE001
        sys.exit(f'[joy-test] Verbindung fehlgeschlagen: {exc}\n'
                 f'  rosbridge läuft? Port {a.port} offen (ufw)? Host korrekt?')

    ws.send(json.dumps({'op': 'advertise', 'topic': '/joy',
                        'type': 'sensor_msgs/Joy'}))
    # rosbridge muss den Publisher erst registrieren + DDS-Discovery zu
    # joy_to_twist abschließen, sonst gehen die ersten Frames verloren.
    time.sleep(0.5)
    deadman = not a.no_deadman
    print(f'[joy-test] /joy advertised → {a.rate} Hz für {a.duration}s '
          f'(forward={a.forward}, turn={a.turn}, Dead-Man={"AN" if deadman else "AUS"})')

    msg = make_joy(a.forward, a.turn, deadman)
    dt = 1.0 / a.rate
    n = int(a.duration * a.rate)
    try:
        for _ in range(n):
            ws.send(json.dumps({'op': 'publish', 'topic': '/joy', 'msg': msg}))
            time.sleep(dt)
    except KeyboardInterrupt:
        print('\n[joy-test] abgebrochen.')
    finally:
        print('[joy-test] Publish gestoppt → /joy verstummt '
              '(NF1: cmd_vel_timeout sollte greifen → Roboter hält).')
        try:
            ws.send(json.dumps({'op': 'unadvertise', 'topic': '/joy'}))
            ws.close()
        except Exception:  # noqa: BLE001
            pass
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
