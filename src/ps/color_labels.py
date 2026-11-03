"""Color-rule demo labels, never mineral identification probabilities."""
import cv2
import numpy as np

LABELS = {
    'black': {'color': '黑色', 'name': '黑曜石', 'swatch': '#525a65'},
    'red': {'color': '红色', 'name': '红碧玉', 'swatch': '#e85959'},
    'white': {'color': '白色', 'name': '白水晶', 'swatch': '#dce2e8'},
    'gray': {'color': '灰色', 'name': '拉长石', 'swatch': '#909ca7'},
    'yellow': {'color': '黄色', 'name': '黄玉', 'swatch': '#e2bd4e'},
    'brown': {'color': '褐色', 'name': '虎眼石', 'swatch': '#b88251'},
    'green': {'color': '绿色', 'name': '绿东陵', 'swatch': '#55b780'},
    'blue': {'color': '蓝色', 'name': '青金石', 'swatch': '#5e9ade'},
    'purple': {'color': '紫色', 'name': '紫水晶', 'swatch': '#aa7bd7'},
    'unknown': {'color': '未确定', 'name': '颜色未确定', 'swatch': '#82909d'},
}


def result(key, ratio=0.0, reason='dominant_color', hsv=None):
    label = LABELS[key]
    return dict(key=key, color=label['color'], name=label['name'],
                display_name=label['name'] + ('（颜色示例）' if key != 'unknown' else ''),
                swatch=label['swatch'], method='color_rule_demo',
                dominant_ratio=round(float(ratio), 3), reason=reason,
                median_hsv=hsv)


def classify_color(frame, observation, scene_p90=None):
    # Sample inside the measured contour; erosion excludes blurred background edges.
    x, y, width, height = observation['bbox']
    roi = frame[y:y + height, x:x + width]
    mask = np.zeros((height, width), np.uint8)
    contour = observation['contour'] - np.array([[[x, y]]], dtype=np.int32)
    cv2.drawContours(mask, [contour], -1, 255, -1)
    mask = cv2.erode(mask, np.ones((5, 5), np.uint8))
    pixels = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)[mask > 0]
    if len(pixels) < 40:
        return result('unknown', reason='too_few_pixels')
    # A uniformly dark scene cannot distinguish dark material from missing light.
    if scene_p90 is None:
        scene = cv2.cvtColor(frame[::8, ::8], cv2.COLOR_BGR2GRAY)
        scene_p90 = np.percentile(scene, 90)
    if scene_p90 < 65 and np.percentile(pixels[:, 2], 75) < 80:
        return result('unknown', reason='scene_too_dark')
    pixels = pixels[::max(1, len(pixels) // 6000)]
    hue, saturation, value = pixels.T
    dark = value <= 65
    neutral = (saturation < 60) & ~dark
    chromatic = (saturation >= 60) & ~dark
    votes = {
        'black': dark,
        'white': neutral & (value >= 190),
        'gray': neutral & (value < 190),
        'red': chromatic & ((hue < 10) | (hue >= 170)),
        'brown': chromatic & (hue >= 10) & (hue < 28) & (value < 170),
        'yellow': chromatic & (hue >= 10) & (hue < 38) & ((value >= 170) | (hue >= 28)),
        'green': chromatic & (hue >= 38) & (hue < 90),
        'blue': chromatic & (hue >= 90) & (hue < 135),
        'purple': chromatic & (hue >= 135) & (hue < 170),
    }
    counts = {key: int(np.count_nonzero(value)) for key, value in votes.items()}
    winner = max(counts, key=counts.get)
    ratio = counts[winner] / len(pixels)
    median = [round(float(v), 1) for v in np.median(pixels, axis=0)]
    if ratio < 0.55:
        return result('unknown', ratio, reason='mixed_colors', hsv=median)
    return result(winner, ratio, hsv=median)
