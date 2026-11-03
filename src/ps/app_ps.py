#!/usr/bin/env python3
"""B220 USB camera -> threshold/contour moments -> alpha-beta tracking -> MJPEG.

Runs entirely on ARM. Measurements are image-plane pixels and degrees, not 3-D.
"""
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import threading
import time
from urllib.parse import urlsplit

import cv2
import numpy as np
from color_labels import LABELS, classify_color
from specimen_catalog import SPECIMENS, PHOTO_ROWS, BY_ID, DEFAULT_MAPPING, apply_name
from multi_tracking import Tracker, MultiTracker, wrap_angle
from multi_vision import detect, detect_all, process_frame, prepare_badges


DEFAULTS = dict(thr=100, pol=1, auto=False, min_area=250, max_fraction=0.6, max_objects=8, label_mapping=DEFAULT_MAPPING)
ROOT = Path(__file__).resolve().parent
VERSION = '3.0-multi-target'


def load_badges():
    badges = {}
    for path in (ROOT / 'badges').glob('*.png'):
        badge = cv2.imdecode(np.frombuffer(path.read_bytes(), np.uint8), cv2.IMREAD_COLOR)
        if badge is not None:
            badges[path.stem] = badge
    return badges


def draw_name_badge(frame, classification, badges):
    badge = badges.get(classification.get('specimen_id', classification['key']))
    if badge is not None:
        height, width = badge.shape[:2]
        frame[57:57 + height, 8:8 + width] = badge
    else:
        cv2.putText(frame, classification['key'].upper() + ' / COLOR DEMO', (8, 77),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (100, 230, 255), 1, cv2.LINE_AA)


def validate(values):
    result = dict(DEFAULTS)
    if not isinstance(values, dict) or set(values) - set(DEFAULTS):
        raise ValueError('Unknown setting')
    result.update(values)
    for key in ('thr', 'pol', 'min_area', 'max_objects'):
        if type(result[key]) is not int:
            raise ValueError(key + ' must be an integer')
    if not 0 <= result['thr'] <= 255 or result['pol'] not in (0, 1):
        raise ValueError('Invalid threshold/polarity')
    if not 10 <= result['min_area'] <= 100000:
        raise ValueError('min_area must be 10..100000')
    if not 1 <= result['max_objects'] <= 12:
        raise ValueError('max_objects must be 1..12')
    if type(result['auto']) is not bool:
        raise ValueError('auto must be boolean')
    if type(result['max_fraction']) not in (int, float) or not 0.01 <= result['max_fraction'] <= 0.95:
        raise ValueError('max_fraction must be 0.01..0.95')
    mapping = result['label_mapping']
    if not isinstance(mapping, dict) or set(mapping) != set(DEFAULT_MAPPING):
        raise ValueError('Exactly nine color-name mappings are required')
    if any(not isinstance(value, str) or value not in BY_ID for value in mapping.values()):
        raise ValueError('Unknown specimen name')
    result['label_mapping'] = dict(mapping)
    return result






class State:
    def __init__(self):
        self.condition = threading.Condition()
        self.settings = validate({})
        if (ROOT / 'settings.json').exists():
            self.settings = validate(json.loads((ROOT / 'settings.json').read_text()))
        self.jpeg = None
        self.source_frames = {}
        self.image_cache = {}
        self.sequence = 0
        self.updated = 0
        self.metrics = dict(status='waiting_camera', detected=False, objects=[], target_count=0)
        self.reset_tracker = False

    def status(self):
        with self.condition:
            result = dict(self.metrics)
            age = time.monotonic() - self.updated if self.updated else None
            result.update(frame=self.sequence, age_s=round(age, 3) if age is not None else None,
                          settings=dict(self.settings), version=VERSION)
            if age is None or age > 3:
                result.update(status='camera_unavailable', detected=False,
                              x=None, y=None, angle_deg=None, area_px=None, classification=None,
                              objects=[], target_count=0, candidate_count=0, limit_reached=False, primary_id=None)
            return result

    def get_jpeg(self, kind='main'):
        with self.condition:
            sequence = self.sequence
            if not self.updated or time.monotonic() - self.updated > 3:
                return sequence, None
            if kind == 'main':
                return sequence, self.jpeg
            cached = self.image_cache.get(kind)
            if cached is not None and cached[0] == sequence:
                return cached
            frame = self.source_frames.get(kind)
        if frame is None:
            return sequence, None
        ok, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 75])
        if not ok:
            return sequence, None
        data = buffer.tobytes()
        with self.condition:
            if self.sequence == sequence:
                self.image_cache[kind] = (sequence, data)
        return sequence, data




def camera_loop(state, device):
    cv2.setNumThreads(2)
    badges = prepare_badges(load_badges())
    tracker = MultiTracker()
    cap = None
    previous = time.monotonic()
    fps = 0.0
    logged = 0
    failures = 0
    try:
        while True:
            if cap is None:
                cap = cv2.VideoCapture(device, cv2.CAP_V4L2)
                if not cap.isOpened():
                    cap.release()
                    cap = None
                    print('ORE status=camera_unavailable device=' + str(device), flush=True)
                    time.sleep(2)
                    continue
                cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                cap.set(cv2.CAP_PROP_FPS, 30)
                cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                tracker.reset()
            ok, frame = cap.read()
            if not ok:
                failures += 1
                if failures >= 5:
                    cap.release()
                    cap = None
                    failures = 0
                time.sleep(0.1)
                continue
            failures = 0
            if frame.shape[:2] != (480, 640):
                frame = cv2.resize(frame, (640, 480))
            now = time.monotonic()
            elapsed = max(now - previous, 0.001)
            fps = 1 / elapsed if fps == 0 else 0.9 * fps + 0.1 / elapsed
            previous = now
            with state.condition:
                settings = dict(state.settings)
                if state.reset_tracker:
                    tracker.reset()
                    state.reset_tracker = False
            output, mask, metrics = process_frame(frame, settings, tracker, badges, now, fps)
            success, buffer = cv2.imencode('.jpg', output, [cv2.IMWRITE_JPEG_QUALITY, 75])
            if not success:
                raise RuntimeError('JPEG encoding failed')
            with state.condition:
                state.jpeg = buffer.tobytes()
                state.source_frames = {'raw': frame, 'mask': mask}
                state.image_cache = {}
                state.sequence += 1
                state.updated = time.monotonic()
                state.metrics = metrics
                state.condition.notify_all()
            if now - logged >= 1:
                serial_objects = [dict(id=item['id'], name=item['classification']['display_name'],
                                       color=item['classification']['color'], x=item['x'], y=item['y'],
                                       angle_deg=item['angle_deg'], area_px=item['area_px'])
                                  for item in metrics['objects']]
                print('ORE ' + json.dumps(dict(count=metrics['target_count'], fps=metrics['fps'],
                                               objects=serial_objects, method='color_rule_demo'),
                                         separators=(',', ':'), ensure_ascii=False), flush=True)
                logged = now
    except Exception as exc:
        print('ORE camera_error=' + repr(exc), flush=True)
        with state.condition:
            state.updated = 0
            state.metrics = dict(status='camera_error', detected=False, objects=[], target_count=0, error=str(exc))
    finally:
        if cap is not None:
            cap.release()



def handler_class(state):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def send(self, content, content_type, code=200):
            self.send_response(code)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(content)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.end_headers()
            self.wfile.write(content)

        def do_GET(self):
            path = urlsplit(self.path).path
            try:
                if path == '/':
                    self.send((ROOT / 'index.html').read_bytes(), 'text/html; charset=utf-8')
                elif path == '/api/labels':
                    self.send(json.dumps({'method': 'color_rule_demo', 'labels': LABELS}, ensure_ascii=False).encode('utf-8'), 'application/json; charset=utf-8')
                elif path == '/api/catalog':
                    self.send(json.dumps({'specimens': SPECIMENS, 'photo_rows': PHOTO_ROWS,
                                          'default_mapping': DEFAULT_MAPPING}, ensure_ascii=False).encode('utf-8'), 'application/json; charset=utf-8')
                elif path in ('/api/status', '/health'):
                    data = state.status()
                    code = 503 if path == '/health' and data['status'].startswith('camera_') else 200
                    self.send(json.dumps(data).encode(), 'application/json', code)
                elif path in ('/snapshot.jpg', '/raw.jpg', '/mask.jpg'):
                    _, data = state.get_jpeg({'/snapshot.jpg': 'main', '/raw.jpg': 'raw', '/mask.jpg': 'mask'}[path])
                    if data:
                        self.send(data, 'image/jpeg')
                    else:
                        self.send(b'Camera not ready', 'text/plain', 503)
                elif path in ('/video', '/video/raw', '/video/mask'):
                    self.connection.settimeout(10)
                    self.send_response(200)
                    self.send_header('Content-Type', 'multipart/x-mixed-replace; boundary=frame')
                    self.send_header('Cache-Control', 'no-store')
                    self.end_headers()
                    sequence = -1
                    while True:
                        with state.condition:
                            state.condition.wait_for(lambda: state.sequence != sequence and state.jpeg is not None, timeout=3)
                            if not state.updated or time.monotonic() - state.updated > 3:
                                return
                        next_sequence, data = state.get_jpeg('raw' if path.endswith('/raw') else 'mask' if path.endswith('/mask') else 'main')
                        if data is None:
                            return
                        if next_sequence == sequence:
                            continue
                        sequence = next_sequence
                        self.wfile.write(b'--frame\r\nContent-Type: image/jpeg\r\nContent-Length: ' + str(len(data)).encode() + b'\r\n\r\n' + data + b'\r\n')
                        self.wfile.flush()
                else:
                    self.send(b'Not found', 'text/plain', 404)
            except (BrokenPipeError, ConnectionResetError, TimeoutError):
                pass

        def do_POST(self):
            if self.path != '/api/settings':
                self.send(b'Not found', 'text/plain', 404)
                return
            try:
                origin = self.headers.get('Origin')
                if origin and urlsplit(origin).netloc != self.headers.get('Host'):
                    raise ValueError('Origin mismatch')
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length <= 4096:
                    raise ValueError('Invalid request size')
                incoming = json.loads(self.rfile.read(length))
                if not isinstance(incoming, dict):
                    raise ValueError('Settings must be an object')
                with state.condition:
                    settings = validate(dict(state.settings, **incoming))
                    temporary = ROOT / 'settings.json.tmp'
                    temporary.write_text(json.dumps(settings, indent=2), encoding='utf-8')
                    temporary.replace(ROOT / 'settings.json')
                    state.settings = settings
                    state.reset_tracker = True
                self.send(json.dumps(settings).encode(), 'application/json')
            except (ValueError, TypeError) as exc:
                self.send(json.dumps({'error': str(exc)}).encode(), 'application/json', 400)
    return Handler


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--device', default='/dev/video0')
    parser.add_argument('--port', type=int, default=8000)
    parser.add_argument('--thr', type=int)
    parser.add_argument('--pol', type=int, choices=(0, 1))
    args = parser.parse_args()
    state = State()
    overrides = {key: getattr(args, key) for key in ('thr', 'pol') if getattr(args, key) is not None}
    state.settings = validate(dict(state.settings, **overrides))
    server = ThreadingHTTPServer(('0.0.0.0', args.port), handler_class(state))
    server.daemon_threads = True
    worker = threading.Thread(target=camera_loop, args=(state, args.device), daemon=True)
    worker.start()
    print('B220 direct USB camera: listening on port ' + str(args.port) + ' (use the board IP)', flush=True)
    server.timeout = 1
    try:
        while worker.is_alive():
            server.handle_request()
        raise RuntimeError('Camera worker stopped; service will restart')
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
