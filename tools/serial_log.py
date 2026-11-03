"""Receive UART only; save original text without sending shell commands."""
import argparse
from datetime import datetime, timedelta, timezone
from pathlib import Path
import serial
from serial.tools import list_ports

parser = argparse.ArgumentParser()
parser.add_argument('--port')
parser.add_argument('--out', default='serial_live.txt')
args = parser.parse_args()
if not args.port:
    for item in list_ports.comports():
        print(item.device, item.description)
    parser.error('Choose the board UART with --port COM12, for example.')
destination = Path(args.out)
destination.parent.mkdir(parents=True, exist_ok=True)
connection = serial.Serial(port=None, baudrate=115200, timeout=0.5,
                           xonxoff=False, rtscts=False, dsrdtr=False)
connection.dtr = False
connection.rts = False
connection.port = args.port
buffer = b''
zone = timezone(timedelta(hours=8))
try:
    with destination.open('a', encoding='utf-8') as output, connection:
        while True:
            buffer += connection.read(max(1, connection.in_waiting))
            while b'\n' in buffer:
                line, buffer = buffer.split(b'\n', 1)
                text = line.decode('utf-8', errors='replace').rstrip('\r')
                stamp = datetime.now(zone).isoformat(timespec='milliseconds')
                output.write(stamp + ' ' + text + '\n')
                output.flush()
                print(text, flush=True)
            if len(buffer) > 65536:
                buffer = b''
except KeyboardInterrupt:
    print('Serial log closed.')
