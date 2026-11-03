"""Read-only HTTP health check; no camera replacement or settings changes."""
import json
import sys
import time
import urllib.request
from configuration import ROOT, base_url, load_config


def main():
    base = base_url(load_config())
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    def read(path):
        with opener.open(base + path, timeout=8) as response:
            return response.read()
    before = json.loads(read('/api/status'))
    time.sleep(1)
    after = json.loads(read('/api/status'))
    assert after['frame'] > before['frame'], 'Frame counter did not advance'
    assert after['age_s'] is not None and after['age_s'] < 3, 'Camera frame is stale'
    assert len(after['objects']) == after['target_count'], 'Object count mismatch'
    for route in ('/snapshot.jpg', '/raw.jpg', '/mask.jpg'):
        data = read(route)
        assert data[:2] == b'\xff\xd8' and data[-2:] == b'\xff\xd9', route + ': invalid JPEG'
    catalog = json.loads(read('/api/catalog'))
    assert len(catalog['specimens']) == 42
    report = dict(result='PASS', url=base, version=after['version'],
                  target_count=after['target_count'], frame=after['frame'], age_s=after['age_s'],
                  note='Transport/camera freshness check, not mineral accuracy or multi-stone validation.')
    destination = ROOT / 'data' / 'results' / 'local_live_check.json'
    destination.parent.mkdir(exist_ok=True)
    destination.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print('FAIL:', error, file=sys.stderr)
        sys.exit(1)
