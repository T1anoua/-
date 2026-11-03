"""Exercise color rules on controlled synthetic objects, separate from live imagery."""
import json
from pathlib import Path
import sys
import cv2
import numpy as np

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src' / 'ps'))
from app_ps import DEFAULTS, State, detect, draw_name_badge, load_badges
from color_labels import classify_color
from specimen_catalog import SPECIMENS, BY_ID, DEFAULT_MAPPING, apply_name

samples = {
    'black': (0, 0, 30), 'red': (0, 210, 210), 'white': (0, 0, 235),
    'gray': (0, 0, 130), 'yellow': (28, 200, 220), 'brown': (18, 180, 140),
    'green': (60, 200, 190), 'blue': (110, 200, 200), 'purple': (150, 200, 190),
}
checks = []
badges = load_badges()
assert len(SPECIMENS) == 42 and len(BY_ID) == 42
assert len(set(item['name'] for item in SPECIMENS)) == 42
assert len(badges) == 52
for specimen in SPECIMENS:
    mapped = apply_name(dict(key='red'), dict(DEFAULT_MAPPING, red=specimen['id']))
    assert mapped['name'] == specimen['name']
    assert mapped['specimen_id'] in badges
for key, hsv in samples.items():
    color = tuple(int(v) for v in cv2.cvtColor(np.uint8([[hsv]]), cv2.COLOR_HSV2BGR)[0, 0])
    foreground_gray = int(cv2.cvtColor(np.uint8([[color]]), cv2.COLOR_BGR2GRAY)[0, 0])
    background = 20 if foreground_gray > 160 else 225
    frame = np.full((480, 640, 3), background, np.uint8)
    cv2.ellipse(frame, (320, 240), (105, 70), 28, 0, 360, color, -1)
    observation, _, _ = detect(frame, dict(DEFAULTS, auto=True, pol=int(background == 20)))
    assert observation is not None, key
    classification = classify_color(frame, observation)
    assert classification['key'] == key, (key, classification)
    assert classification['method'] == 'color_rule_demo'
    assert classification['dominant_ratio'] >= 0.95
    draw_name_badge(frame, classification, badges)
    cv2.putText(frame, 'SYNTHETIC COLOR RULE TEST', (8, 25), cv2.FONT_HERSHEY_SIMPLEX, .6, (100, 130, 160), 1)
    (ROOT / 'data' / 'results' / 'synthetic_colors').mkdir(parents=True, exist_ok=True)
    ok, encoded = cv2.imencode('.jpg', frame)
    assert ok
    (ROOT / 'data' / 'results' / 'synthetic_colors' / (key + '.jpg')).write_bytes(encoded.tobytes())
    checks.append({'expected': key, 'actual': classification})

# Mixed red/blue target must not confidently map to one mineral/example name.
frame = np.full((480, 640, 3), 230, np.uint8)
cv2.rectangle(frame, (220, 160), (320, 320), (20, 20, 200), -1)
cv2.rectangle(frame, (321, 160), (420, 320), (200, 20, 20), -1)
observation, _, _ = detect(frame, dict(DEFAULTS, auto=True, pol=0))
assert observation is not None
assert classify_color(frame, observation)['reason'] == 'mixed_colors'
dark = np.zeros((480, 640, 3), np.uint8)
assert classify_color(dark, observation)['reason'] == 'scene_too_dark'

# Stale camera measurements must clear a previously assigned name.
state = State()
state.metrics = dict(status='tracking', detected=True, classification=checks[0]['actual'])
assert state.status()['classification'] is None
assert not state.status()['detected']
report = {'synthetic_color_cases': checks, 'mixed_color_rejection': 'PASS',
          'dark_scene_rejection': 'PASS', 'stale_name_cleared': 'PASS',
          'note': 'These are synthetic color-rule checks, not mineral identification or real sample accuracy.'}
(ROOT / 'data' / 'results' / 'color_rules_verification.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
print('PASS: 42 catalog names and name badges; nine colors; mixed/dark rejection; stale-name clearing.')
