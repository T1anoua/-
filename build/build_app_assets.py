"""Render Chinese name badges with an installed font; no font files are copied."""
import ast
import argparse
import os
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
tree = ast.parse((ROOT / 'src' / 'ps' / 'color_labels.py').read_text(encoding='utf-8'))
labels = next(ast.literal_eval(node.value) for node in tree.body
              if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == 'LABELS' for target in node.targets))
import sys
sys.path.insert(0, str(ROOT / 'src' / 'ps'))
from specimen_catalog import SPECIMENS
labels.update({item['id']: {'name': item['name'], 'swatch': '#78cdb5'} for item in SPECIMENS})
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--font', default=os.environ.get('B220_FONT', 'C:/Windows/Fonts/msyh.ttc'),
                    help='Path to an installed font that supports Chinese; font files are not redistributed')
args = parser.parse_args()
if not Path(args.font).is_file():
    parser.error('Chinese font not found; provide --font /path/to/your/font.ttf')
font = ImageFont.truetype(args.font, 19)
destination = ROOT / 'src' / 'ps' / 'badges'
destination.mkdir(exist_ok=True)
for key, label in labels.items():
    text = label['name'] + ('（颜色示例）' if key != 'unknown' else '')
    width = min(420, int(font.getlength(text)) + 30)
    image = Image.new('RGB', (width, 36), '#172f30')
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, 5, 35), fill=label['swatch'])
    draw.text((15, 4), text, font=font, fill='#e6edf4')
    image.save(destination / (key + '.png'))

icon = Image.new('RGBA', (256, 256), '#101821')
draw = ImageDraw.Draw(icon)
draw.rounded_rectangle((8, 8, 248, 248), radius=48, fill='#1b3440')
draw.polygon([(48, 168), (72, 72), (156, 45), (211, 107), (195, 185), (112, 211)], fill='#5fbaa3', outline='#b0f0da', width=5)
draw.polygon([(72, 72), (156, 45), (139, 133)], fill='#91d4bb')
draw.polygon([(48, 168), (139, 133), (112, 211)], fill='#3a8a7a')
draw.polygon([(139, 133), (211, 107), (195, 185), (112, 211)], fill='#317b77')
icon.save(ROOT / 'src' / 'pc' / 'ore_app.ico', sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
print('Rendered', len(labels), 'badges and application icon.')
