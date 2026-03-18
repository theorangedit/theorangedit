# The contents of this file are subject to the Common Public Attribution
# License Version 1.0. (the "License"); you may not use this file except in
# compliance with the License. You may obtain a copy of the License at
# http://code.reddit.com/LICENSE. The License is based on the Mozilla Public
# License Version 1.1, but Sections 14 and 15 have been added to cover use of
# software over a computer network and provide for limited attribution for the
# Original Developer. In addition, Exhibit A has been modified to be consistent
# with Exhibit B.
#
# Software distributed under the License is distributed on an "AS IS" basis,
# WITHOUT WARRANTY OF ANY KIND, either express or implied. See the License for
# the specific language governing rights and limitations under the License.
#
# The Original Code is reddit.
#
# The Original Developer is the Initial Developer.  The Initial Developer of
# the Original Code is reddit Inc.
#
# All portions of the code written by reddit are Copyright (c) 2006-2015 reddit
# Inc. All Rights Reserved.
###############################################################################

"""
CAPTCHA generation using Pillow (replaces the PyCAPTCHA C extension).

Generates a simple distorted-text CAPTCHA image returned as JPEG bytes.
"""

import io
import math
import random
import string

from PIL import Image, ImageDraw, ImageFont, ImageFilter

from r2.lib.app_globals import g

IDEN_LENGTH = 32
SOL_LENGTH = 6

# Image dimensions matching the old PyCAPTCHA defaults
_WIDTH = 120
_HEIGHT = 50
_BG_COLOR = (0, 0, 0)
_TEXT_COLOR = (255, 255, 255)
_GRID_COLOR = (60, 60, 60)


def _draw_grid(draw, width, height, size=8):
    """Draw a subtle grid background."""
    for x in range(0, width, size):
        draw.line([(x, 0), (x, height)], fill=_GRID_COLOR)
    for y in range(0, height, size):
        draw.line([(0, y), (width, y)], fill=_GRID_COLOR)


def _sine_warp(image, amplitude=5):
    """Apply a horizontal sine-wave distortion to the image."""
    width, height = image.size
    pixels = image.load()
    warped = Image.new('RGB', (width, height), _BG_COLOR)
    warped_px = warped.load()
    freq = random.uniform(0.3, 0.7)
    phase = random.uniform(0, 2 * math.pi)
    for x in range(width):
        for y in range(height):
            offset = int(amplitude * math.sin(2 * math.pi * freq * x / width + phase))
            src_y = (y + offset) % height
            warped_px[x, y] = pixels[x, src_y]
    return warped


def _render_captcha(solution):
    """
    Render a CAPTCHA image for the given solution string.
    Returns JPEG bytes.
    """
    img = Image.new('RGB', (_WIDTH, _HEIGHT), _BG_COLOR)
    draw = ImageDraw.Draw(img)
    _draw_grid(draw, _WIDTH, _HEIGHT)

    # Try to load a bundled font; fall back to the default bitmap font
    try:
        import os
        font_path = os.path.join(
            os.path.dirname(__file__), '..', 'public', 'static', 'fonts', 'VeraBd.ttf'
        )
        font = ImageFont.truetype(font_path, 18)
    except (IOError, OSError):
        font = ImageFont.load_default()

    # Center the text
    try:
        bbox = draw.textbbox((0, 0), solution, font=font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
    except AttributeError:
        # Older Pillow without textbbox
        text_w, text_h = draw.textsize(solution, font=font)

    x = (_WIDTH - text_w) // 2
    y = (_HEIGHT - text_h) // 2
    draw.text((x, y), solution, fill=_TEXT_COLOR, font=font)

    # Apply sine warp distortion
    img = _sine_warp(img, amplitude=random.randint(5, 9))

    # Slight blur to make OCR harder
    img = img.filter(ImageFilter.GaussianBlur(radius=0.5))

    buf = io.BytesIO()
    img.save(buf, format='JPEG', quality=85)
    return buf.getvalue()


def get_iden():
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=IDEN_LENGTH))


def make_solution():
    return ''.join(random.choices(string.ascii_letters, k=SOL_LENGTH)).upper()


def get_image(iden):
    key = f"captcha:{iden}"
    solution = g.gencache.get(key)
    if not solution:
        solution = make_solution()
        g.gencache.set(key, solution, time=300)
    return _render_captcha(solution)


def valid_solution(iden, solution):
    key = f"captcha:{iden}"

    if (not iden or
            not solution or
            len(iden) != IDEN_LENGTH or
            len(solution) != SOL_LENGTH or
            solution.upper() != g.gencache.get(key)):
        # wrong guess — generate a new solution for the next attempt
        solution = make_solution()
        g.gencache.set(key, solution, time=300)
        return False
    else:
        g.gencache.delete(key)
        return True
