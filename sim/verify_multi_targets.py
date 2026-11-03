"""Controlled synthetic verification. No synthetic image is fed to the live camera."""
import itertools
import json
import math
from pathlib import Path
import sys
import time
import cv2
import numpy as np

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
ROOT = Path(__file__).resolve().parents[1]
CODE = ROOT / 'src' / 'ps' if (ROOT / 'src' / 'ps').exists() else ROOT
sys.path.insert(0, str(CODE))
from app_ps import DEFAULTS, State, load_badges, validate
from multi_tracking import MultiTracker, assign
from multi_vision import detect_all, prepare_badges, process_frame

cv2.setNumThreads(2)
output_dir = ROOT / 'data' / 'results' / 'multi_target'
output_dir.mkdir(parents=True, exist_ok=True)
checks = []
rng = np.random.default_rng(31)
for rows, columns in ((1, 3), (2, 4), (3, 5), (4, 6)):
    for _ in range(8):
        costs = rng.uniform(0, 2, (rows, columns)).tolist()
        assignment = assign(costs)
        actual = sum(costs[row][column] for row, column in enumerate(assignment))
        optimum = min(sum(costs[row][column] for row, column in enumerate(permutation))
                      for permutation in itertools.permutations(range(columns), rows))
        assert abs(actual - optimum) < 1e-7
checks.append('Global assignment matches exhaustive optimal assignments on 32 small matrices')

settings = validate(dict(DEFAULTS, thr=150, pol=0, auto=False, min_area=250, max_objects=8))
badges = prepare_badges(load_badges())
colors = [(25, 25, 25), (25, 30, 205), (30, 140, 30), (200, 45, 25)]
expected = {'black', 'red', 'green', 'blue'}
tracker = MultiTracker()
ids = None
timings = []

def scene(step, skip=None):
    frame = np.full((480, 640, 3), 230, np.uint8)
    positions = [(105 + step * 3, 135), (285 + step * 2, 145), (510 - step * 2, 185), (315, 340 - step * 2)]
    for index, (center, color) in enumerate(zip(positions, colors)):
        if index == skip:
            continue
        radius = 32 + ((step + index * 3) % 6)
        cv2.ellipse(frame, center, (radius, 23), step * 2 + index * 18, 0, 360, color, -1)
    return frame

for step in range(18):
    before = time.perf_counter()
    annotated, mask, status = process_frame(scene(step), settings, tracker, badges, step * .1, 10)
    timings.append((time.perf_counter() - before) * 1000)
    assert status['target_count'] == 4
    mapping = {item['classification']['key']: item['id'] for item in status['objects']}
    assert set(mapping) == expected, mapping
    if ids is None:
        ids = mapping
    assert mapping == ids, (step, mapping, ids)
    assert len(set(item['id'] for item in status['objects'])) == 4
checks.append('Four colored objects: separate labels, stable IDs across motion and area-rank changes')
cv2.rectangle(annotated, (0, 451), (640, 480), (25, 25, 25), -1)
cv2.putText(annotated, 'SYNTHETIC VALIDATION - NOT LIVE CAMERA', (8, 471), cv2.FONT_HERSHEY_SIMPLEX, .55, (100, 190, 255), 1, cv2.LINE_AA)
ok, encoded = cv2.imencode('.jpg', annotated)
assert ok
(output_dir / 'synthetic_four_objects.jpg').write_bytes(encoded.tobytes())
(output_dir / 'synthetic_four_objects.json').write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding='utf-8')

_, _, missing = process_frame(scene(17, skip=1), settings, tracker, badges, 1.9, 10)
assert missing['target_count'] == 3 and all(item['id'] != ids['red'] for item in missing['objects'])
_, _, restored = process_frame(scene(17), settings, tracker, badges, 2.1, 10)
assert {item['classification']['key']: item['id'] for item in restored['objects']} == ids
_, _, expired = process_frame(scene(17, skip=1), settings, tracker, badges, 3.1, 10)
_, _, returned = process_frame(scene(17), settings, tracker, badges, 3.2, 10)
assert next(item['id'] for item in returned['objects'] if item['classification']['key'] == 'red') != ids['red']
checks.append('Missing targets disappear immediately; short gaps keep IDs; expired tracks get new IDs')

cross_tracker = MultiTracker()
lane_ids = None
for step in range(41):
    frame = np.full((480, 640, 3), 230, np.uint8)
    for center in ((100 + step * 10, 170), (500 - step * 10, 295)):
        cv2.ellipse(frame, center, (30, 20), 10, 0, 360, (25, 25, 25), -1)
    _, _, status = process_frame(frame, settings, cross_tracker, badges, step * .1, 10)
    current = {round(item['y'] / 100): item['id'] for item in status['objects']}
    if lane_ids is None:
        lane_ids = current
    assert current == lane_ids
checks.append('Same-color objects keep IDs when horizontal order reverses in separate lanes')

grid = np.full((480, 640, 3), 230, np.uint8)
for y in (100, 240, 380):
    for x in (80, 240, 400, 560):
        cv2.ellipse(grid, (x, y), (30, 22), 0, 0, 360, (25, 25, 25), -1)
_, _, limited = process_frame(grid, settings, MultiTracker(), badges, 1, 10)
assert limited['target_count'] == 8 and limited['candidate_count'] == 12 and limited['limit_reached']
_, _, full = process_frame(grid, dict(settings, max_objects=12), MultiTracker(), badges, 1, 10)
assert full['target_count'] == 12 and not full['limit_reached']
checks.append('Twelve separated contours are detected; configured limit is reported explicitly')

touching = np.full((480, 640, 3), 230, np.uint8)
for center in ((270, 240), (320, 240)):
    cv2.ellipse(touching, center, (45, 30), 0, 0, 360, (25, 25, 25), -1)
assert len(detect_all(touching, settings)[0]) == 1
empty = np.full((480, 640, 3), 230, np.uint8)
assert not detect_all(empty, settings)[0]
cv2.rectangle(empty, (0, 80), (120, 200), (25, 25, 25), -1)
assert not detect_all(empty, settings)[0]
checks.append('Empty/clipped objects excluded; merged silhouettes honestly remain a single contour')

state = State()
state.sequence, state.updated = 1, time.monotonic()
state.source_frames = {'raw': grid, 'mask': mask}
first = state.get_jpeg('raw')
second = state.get_jpeg('raw')
assert first[1] is second[1]
assert cv2.imdecode(np.frombuffer(first[1], np.uint8), cv2.IMREAD_COLOR).shape == (480, 640, 3)
state.metrics = full
state.updated = 0
stale = state.status()
assert stale['objects'] == [] and stale['target_count'] == 0 and not stale['detected']
assert state.get_jpeg('raw')[1] is None
checks.append('On-demand JPEG cache works; stale images, target lists and counts clear together')

for value in (0, 13, 2.5, True):
    try:
        validate(dict(settings, max_objects=value))
        raise AssertionError('Invalid target limit accepted')
    except ValueError:
        pass
checks.append('Invalid limits rejected; original color-name mapping remains compatible')
report = {'checks': checks, 'synthetic_processing_median_ms': round(float(np.median(timings)), 2),
          'limitation': 'Controlled synthetic verification, not physical multi-stone accuracy or end-to-end FPS.'}
(output_dir / 'verification.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
print(json.dumps(report, indent=2), flush=True)
