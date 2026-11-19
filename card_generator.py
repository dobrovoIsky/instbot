"""Statistics card image generator using Pillow."""

import os
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont


# Colors
BG_COLOR = (18, 18, 18)
CARD_BG = (30, 30, 30)
ACCENT = (225, 48, 108)  # Instagram gradient pink
ACCENT2 = (131, 58, 180)  # Instagram purple
WHITE = (255, 255, 255)
GRAY = (170, 170, 170)
LIGHT_GRAY = (120, 120, 120)


def _get_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    """Try to load a good font, fall back to default."""
    font_names = [
        "arial.ttf", "arialbd.ttf" if bold else "arial.ttf",
        "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf",
        "segoeui.ttf", "segoeuib.ttf" if bold else "segoeui.ttf",
    ]
    for name in font_names:
        try:
            return ImageFont.truetype(name, size)
        except (OSError, IOError):
            pass
    return ImageFont.load_default()


def _draw_rounded_rect(draw: ImageDraw.Draw, xy, radius, fill):
    """Draw a rounded rectangle."""
    x1, y1, x2, y2 = xy
    draw.rounded_rectangle(xy, radius=radius, fill=fill)


def generate_stats_card(stats: dict, username: str = "Instagram") -> BytesIO:
    """Generate a beautiful statistics card image."""
    width, height = 800, 520
    img = Image.new("RGB", (width, height), BG_COLOR)
    draw = ImageDraw.Draw(img)

    # Main card background
    _draw_rounded_rect(draw, (20, 20, width - 20, height - 20), radius=20, fill=CARD_BG)

    # Title
    title_font = _get_font(32, bold=True)
    draw.text((40, 40), f"📊 {username}", fill=WHITE, font=title_font)

    # Subtitle
    sub_font = _get_font(16)
    draw.text((40, 82), "Instagram Analyzer", fill=LIGHT_GRAY, font=sub_font)

    # Divider line
    draw.line([(40, 115), (width - 40, 115)], fill=(60, 60, 60), width=1)

    # Stats grid - 2 rows, 3 columns
    stat_font = _get_font(42, bold=True)
    label_font = _get_font(15)

    items = [
        (str(stats["followers"]), "Подписчики", ACCENT),
        (str(stats["following"]), "Подписки", ACCENT2),
        (str(stats["mutual"]), "Взаимные", (0, 200, 100)),
        (str(stats["not_following_back"]), "Не подписаны\nв ответ", (255, 165, 0)),
        (str(stats["not_followed_back"]), "Ты не подписан\nв ответ", (100, 149, 237)),
    ]

    # First row: 3 items
    col_width = (width - 80) // 3
    for i, (value, label, color) in enumerate(items[:3]):
        x = 40 + i * col_width
        y = 140

        # Card for each stat
        card_x1 = x + 5
        card_y1 = y
        card_x2 = x + col_width - 5
        card_y2 = y + 140
        _draw_rounded_rect(draw, (card_x1, card_y1, card_x2, card_y2), radius=12, fill=(45, 45, 45))

        # Accent bar on top
        _draw_rounded_rect(draw, (card_x1, card_y1, card_x2, card_y1 + 4), radius=2, fill=color)

        # Number
        bbox = draw.textbbox((0, 0), value, font=stat_font)
        tw = bbox[2] - bbox[0]
        cx = card_x1 + (card_x2 - card_x1 - tw) // 2
        draw.text((cx, card_y1 + 25), value, fill=WHITE, font=stat_font)

        # Label
        lines = label.split("\n")
        for li, line in enumerate(lines):
            bbox = draw.textbbox((0, 0), line, font=label_font)
            tw = bbox[2] - bbox[0]
            cx = card_x1 + (card_x2 - card_x1 - tw) // 2
            draw.text((cx, card_y1 + 85 + li * 20), line, fill=GRAY, font=label_font)

    # Second row: 2 items
    col_width_2 = (width - 80) // 2
    for i, (value, label, color) in enumerate(items[3:]):
        x = 40 + i * col_width_2
        y = 300

        card_x1 = x + 5
        card_y1 = y
        card_x2 = x + col_width_2 - 5
        card_y2 = y + 140
        _draw_rounded_rect(draw, (card_x1, card_y1, card_x2, card_y2), radius=12, fill=(45, 45, 45))
        _draw_rounded_rect(draw, (card_x1, card_y1, card_x2, card_y1 + 4), radius=2, fill=color)

        bbox = draw.textbbox((0, 0), value, font=stat_font)
        tw = bbox[2] - bbox[0]
        cx = card_x1 + (card_x2 - card_x1 - tw) // 2
        draw.text((cx, card_y1 + 25), value, fill=WHITE, font=stat_font)

        lines = label.split("\n")
        for li, line in enumerate(lines):
            bbox = draw.textbbox((0, 0), line, font=label_font)
            tw = bbox[2] - bbox[0]
            cx = card_x1 + (card_x2 - card_x1 - tw) // 2
            draw.text((cx, card_y1 + 85 + li * 20), line, fill=GRAY, font=label_font)

    # Footer
    footer_font = _get_font(12)
    draw.text((40, height - 42), "🤖 @InstagramAnalyzerBot", fill=LIGHT_GRAY, font=footer_font)

    # Save to BytesIO
    buf = BytesIO()
    img.save(buf, format="PNG", quality=95)
    buf.seek(0)
    return buf
