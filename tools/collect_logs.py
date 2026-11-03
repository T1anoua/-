"""Read-only API sampling; timestamps use Asia/Shanghai UTC+08:00."""
import argparse
import csv
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import time
import urllib.request

parser = argparse.ArgumentParser()
parser.add_argument('--url', default='http://192.168.2.99:8000')
parser.add_argument('--samples', type=int, default=30)
parser.add_argument('--interval', type=float, default=1.0)
parser.add_argument('--out', default='logs')
args = parser.parse_args()
if not 2 <= args.samples <= 10000 or args.interval < 0.1:
    parser.error('Use 2..10000 samples and interval >= 0.1 seconds.')
folder = Path(args.out)
folder.mkdir(parents=True, exist_ok=True)
zone = timezone(timedelta(hours=8))
tag = datetime.now(zone).strftime('%Y%m%d_%H%M%S_%f')
fields = ['sample', 'pc_time', 'elapsed_s', 'frame', 'status',
          'target_count', 'reported_fps', 'age_s', 'threshold',
          'width', 'height', 'error']
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
start = time.monotonic()
with (
    (folder / (tag + '.csv')).open('w', encoding='utf-8-sig',
                                 newline='') as csv_file,
    (folder / (tag + '.jsonl')).open('w', encoding='utf-8') as raw,
):
    writer = csv.DictWriter(csv_file, fieldnames=fields)
    writer.writeheader()
    for index in range(args.samples):
        delay = start + index * args.interval - time.monotonic()
        if delay > 0:
            time.sleep(delay)
        stamp = datetime.now(zone).isoformat(timespec='milliseconds')
        row = dict.fromkeys(fields, '')
        row.update(sample=index + 1, pc_time=stamp,
                   elapsed_s=round(time.monotonic() - start, 3))
        try:
            url = args.url.rstrip('/') + '/api/status'
            with opener.open(url, timeout=4) as response:
                status = json.load(response)
            for key in ('frame', 'status', 'target_count', 'age_s',
                        'threshold', 'width', 'height'):
                row[key] = status.get(key)
            row['reported_fps'] = status.get('fps')
            raw.write(json.dumps({'pc_time': stamp, 'status': status},
                                 ensure_ascii=False) + '\n')
        except Exception as error:
            row['error'] = str(error)
            raw.write(json.dumps({'pc_time': stamp, 'error': str(error)},
                                 ensure_ascii=False) + '\n')
        writer.writerow(row)
        csv_file.flush()
        raw.flush()
        print(row, flush=True)
print('Saved logs to', folder.resolve())
