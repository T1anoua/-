"""Multi-contour measurement, per-object color labels and annotated frames."""
import math
import cv2
import numpy as np
from color_labels import classify_color
from specimen_catalog import apply_name

PALETTE = [(100, 235, 140), (245, 190, 85), (90, 175, 255), (230, 140, 225),
           (65, 230, 235), (240, 210, 180), (170, 130, 255), (180, 245, 65)]


def detect_all(frame, settings):
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (3, 3), 0)
    flag = cv2.THRESH_BINARY if settings['pol'] else cv2.THRESH_BINARY_INV
    if settings['auto']:
        flag |= cv2.THRESH_OTSU
    used, mask = cv2.threshold(gray, settings['thr'], 255, flag)
    kernel = np.ones((3, 3), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
    contours = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)[-2]
    height, width = gray.shape
    candidates = []
    for contour in contours:
        area = cv2.contourArea(contour)
        x, y, w, h = cv2.boundingRect(contour)
        if (settings['min_area'] <= area <= width * height * settings['max_fraction']
                and x > 1 and y > 1 and x + w < width - 1 and y + h < height - 1):
            candidates.append((area, contour, (x, y, w, h)))
    observations = []
    for area, contour, bbox in sorted(candidates, key=lambda item: item[0], reverse=True)[:settings.get('max_objects', 8)]:
        moments = cv2.moments(contour)
        if moments['m00'] <= 0:
            continue
        cx, cy = moments['m10'] / moments['m00'], moments['m01'] / moments['m00']
        xx, yy, xy = (moments[key] / moments['m00'] for key in ('mu20', 'mu02', 'mu11'))
        angle = 0.5 * math.atan2(2 * xy, xx - yy)
        eigenvalues = np.linalg.eigvalsh(np.array([[xx, xy], [xy, yy]]))
        axes = tuple(max(1, int(2 * math.sqrt(max(0, float(value))))) for value in eigenvalues[::-1])
        ratio = float(eigenvalues[1] / max(eigenvalues[0], 1e-6))
        observations.append(dict(center=(cx, cy), angle=angle, area=area, bbox=bbox,
                                 contour=contour, axes=axes, angle_reliable=ratio >= 1.15))
    return observations, mask, used, len(candidates)


def detect(frame, settings):
    """Compatibility wrapper for the single-object geometry checks."""
    observations, mask, used, _ = detect_all(frame, settings)
    return (observations[0] if observations else None), mask, used


def prepare_badges(badges):
    return {key: cv2.resize(image, (round(image.shape[1] * 26 / image.shape[0]), 26), interpolation=cv2.INTER_AREA)
            for key, image in badges.items()}


def overlap(a, b):
    return max(0, min(a[0] + a[2], b[0] + b[2]) - max(a[0], b[0])) * max(0, min(a[1] + a[3], b[1] + b[3]) - max(a[1], b[1]))


def annotate(frame, targets, badges, fps, threshold, total):
    output = frame.copy()
    labels = []
    bounds = [item['bbox'] for item in targets]
    for target in targets:
        ident = target['track_id']
        color = PALETTE[(ident - 1) % len(PALETTE)]
        x, y, angle = target['filtered']
        center = (int(round(x)), int(round(y)))
        bx, by, bw, bh = target['bbox']
        cv2.drawContours(output, [target['contour']], -1, color, 2)
        cv2.rectangle(output, (bx, by), (bx + bw, by + bh), color, 1)
        cv2.ellipse(output, center, target['axes'], math.degrees(angle), 0, 360, color, 1)
        length = max(12, min(90, target['axes'][0]))
        delta = (int(length * math.cos(angle)), int(length * math.sin(angle)))
        cv2.line(output, (center[0] - delta[0], center[1] - delta[1]), (center[0] + delta[0], center[1] + delta[1]), (0, 255, 255), 1)
        cv2.circle(output, center, 3, (0, 0, 255), -1)
        if len(target['trail']) > 1:
            cv2.polylines(output, [np.array(target['trail'], np.int32)], False, color, 1)
        classification = target['classification']
        badge = badges.get(classification.get('specimen_id', classification['key']))
        prefix = '#' + str(ident)
        prefix_width = max(37, cv2.getTextSize(prefix, cv2.FONT_HERSHEY_SIMPLEX, .48, 1)[0][0] + 12)
        label_width = prefix_width + (badge.shape[1] if badge is not None else 100)
        label_width = min(label_width, frame.shape[1] - 4)
        height = 26
        positions = [(bx, by - height - 3), (bx, by + bh + 3), (bx + bw + 3, by), (bx - label_width - 3, by)]
        options = []
        for preference, (lx, ly) in enumerate(positions):
            rect = (min(max(2, lx), frame.shape[1] - label_width - 2),
                    min(max(35, ly), frame.shape[0] - height - 2), label_width, height)
            score = sum(overlap(rect, previous) for previous in labels) * 4 + sum(overlap(rect, box) for box in bounds) + preference
            options.append((score, rect))
        _, rect = min(options, key=lambda item: item[0])
        labels.append(rect)
        lx, ly, lw, lh = rect
        cv2.line(output, (lx + min(lw // 2, bw // 2), ly + lh // 2), (bx + bw // 2, by), color, 1)
        output[ly:ly + lh, lx:lx + lw] = (24, 38, 42)
        if badge is not None:
            available = min(badge.shape[1], lw - prefix_width)
            output[ly:ly + lh, lx + prefix_width:lx + prefix_width + available] = badge[:, :available]
        cv2.putText(output, prefix, (lx + 4, ly + 18), cv2.FONT_HERSHEY_SIMPLEX, .48, color, 1, cv2.LINE_AA)
        cv2.rectangle(output, (lx, ly), (lx + lw - 1, ly + lh - 1), color, 1)
    cv2.rectangle(output, (0, 0), (frame.shape[1], 31), (25, 25, 25), -1)
    title = 'TARGETS {}  |  {:.1f} fps  |  thr={}  |  B220 ARM'.format(len(targets), fps, int(threshold))
    if total > len(targets):
        title += '  LIMIT'
    cv2.putText(output, title, (8, 21), cv2.FONT_HERSHEY_SIMPLEX, .49, (210, 240, 235), 1, cv2.LINE_AA)
    return output


def process_frame(frame, settings, tracker, badges, now, fps):
    observations, mask, used, total = detect_all(frame, settings)
    if observations:
        scene_p90 = float(np.percentile(cv2.cvtColor(frame[::8, ::8], cv2.COLOR_BGR2GRAY), 90))
        for observation in observations:
            observation['classification'] = apply_name(classify_color(frame, observation, scene_p90), settings['label_mapping'])
    targets = tracker.update(observations, now)
    objects = []
    for target in targets:
        x, y, angle = target['filtered']
        color = PALETTE[(target['track_id'] - 1) % len(PALETTE)]
        objects.append(dict(id=target['track_id'], x=round(float(x), 1), y=round(float(y), 1),
                            angle_deg=round(math.degrees(angle), 1), angle_reliable=target['angle_reliable'],
                            area_px=round(target['area'], 1), bbox=list(target['bbox']),
                            classification=target['classification'],
                            track_color='#{:02x}{:02x}{:02x}'.format(*color[::-1])))
    primary = max(objects, key=lambda item: item['area_px']) if objects else None
    metrics = dict(status='tracking' if objects else 'no_target', detected=bool(objects),
                   objects=objects, target_count=len(objects), candidate_count=total,
                   limit_reached=total > len(objects), primary_id=primary['id'] if primary else None,
                   fps=round(fps, 2), threshold=round(used, 1), width=640, height=480,
                   processing='B220 ARM / OpenCV')
    for key in ('x', 'y', 'angle_deg', 'area_px', 'bbox', 'classification'):
        metrics[key] = primary[key] if primary else None
    metrics['angle_reliable'] = primary['angle_reliable'] if primary else False
    return annotate(frame, targets, badges, fps, used, total), mask, metrics
