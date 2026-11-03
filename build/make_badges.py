"""Run on Windows with Pillow; creates all Chinese image labels."""
import argparse
from pathlib import Path
import sys
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src/ps'))
from specimen_catalog import SPECIMENS

parser = argparse.ArgumentParser()
parser.add_argument('--font', default='C:/Windows/Fonts/msyh.ttc')
args = parser.parse_args()
font = ImageFont.truetype(args.font, 19)
destination = ROOT / 'src/ps/badges'
destination.mkdir(parents=True, exist_ok=True)
labels = [(item['id'], item['name'] + '（颜色示例）')
          for item in SPECIMENS]
labels.append(('unknown', '颜色未确定'))
for key, text in labels:
    width = min(420, int(font.getlength(text)) + 30)
    image = Image.new('RGB', (width, 36), '#172f30')
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, 5, 35), fill='#78cdb5')
    draw.text((15, 4), text, font=font, fill='#e6edf4')
    image.save(destination / (key + '.png'))
print('Created', len(labels), 'badges.')
