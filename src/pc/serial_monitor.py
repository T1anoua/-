"""Receive board UART only; never sends input to the board login shell."""
import argparse
from pathlib import Path
import sys
import serial
from serial.tools import list_ports
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'board'))
from configuration import load_config


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', help='COM12 on Windows, /dev/ttyUSB0 on Linux')
    parser.add_argument('--list', action='store_true', help='List available ports and exit')
    parser.add_argument('--all', action='store_true', help='Show all console lines, not just ORE results')
    args = parser.parse_args()
    config = load_config()
    ports = list(list_ports.comports())
    if args.list or not (args.port or config['serial_port']):
        for number, port in enumerate(ports, 1):
            print('{}: {} - {}'.format(number, port.device, port.description))
        if args.list:
            return
        if not ports:
            raise RuntimeError('No serial port found. Connect the board debug USB cable and install its USB-UART driver.')
        choice = input('Board port number or name (e.g. COM12): ').strip()
        if choice.isdigit():
            number = int(choice)
            if not 1 <= number <= len(ports):
                raise ValueError('Invalid port selection')
            port_name = ports[number - 1].device
        else:
            port_name = choice
    else:
        port_name = args.port or config['serial_port']
    print('{} / {} / 8N1 / no flow control; Ctrl+C to close.'.format(port_name, config['serial_baud']))
    print('If nothing arrives: close other serial tools; use --all for Linux console output.')
    # No writes, no flow control; pre-set DTR/RTS low before opening.
    connection = serial.Serial(port=None, baudrate=config['serial_baud'], timeout=.5,
                               xonxoff=False, rtscts=False, dsrdtr=False)
    connection.dtr = False
    connection.rts = False
    connection.port = port_name
    buffer = b''
    try:
        connection.open()
        while True:
            buffer += connection.read(max(1, connection.in_waiting))
            while b'\n' in buffer:
                line, buffer = buffer.split(b'\n', 1)
                text = line.decode('utf-8', errors='replace').rstrip('\r')
                if args.all or 'ORE ' in text:
                    print(text, flush=True)
            if len(buffer) > 65536:
                buffer = b''
    finally:
        connection.close()


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    try:
        main()
    except KeyboardInterrupt:
        print('\nSerial closed.')
    except Exception as error:
        print('Serial error:', error, file=sys.stderr)
        sys.exit(1)
