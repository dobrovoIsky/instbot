"""Statistics card image generator using Pillow with rich Instagram styling."""

import os
from datetime import datetime
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont


# Base colors
CANVAS_BG = (12, 14, 22)         # Deep modern dark
CARD_BG = (22, 26, 38)           # Dark card background
CARD_BORDER = (42, 48, 68)       # Subtle border
HEADER_BG = (18, 21, 32)

# Instagram Brand & Accent colors
INSTA_PURPLE = (131, 58, 180)    # #833ab4
INSTA_PINK = (225, 48, 108)      # #e1306c
INSTA_ORANGE = (245, 96, 64)     # #f56040
INSTA_YELLOW = (252, 175, 69)    # #fcaf45

# Status Metric Colors
COLOR_FOLLOWERS = (255, 140, 66)  # Warm orange
COLOR_FOLLOWING = (214, 41, 118)  # Instagram berry pink
COLOR_MUTUAL = (0, 230, 118)      # Neon emerald
COLOR_NOT_BACK = (255, 61, 0)     # Neon red/flame (unfollowers)
COLOR_YOU_NOT_BACK = (41, 121, 255) # Electric sky blue

# Typography colors
WHITE = (255, 255, 255)
LIGHT_GRAY = (200, 205, 220)
MUTED_GRAY = (130, 138, 160)


def _get_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    """Load font with guaranteed Cyrillic support."""
    # 1. Bundled assets fonts (guaranteed Cyrillic on all OS / Docker / Render)
    base_dir = os.path.dirname(os.path.abspath(__file__))
    bundled_names = [
        "arialbd.ttf" if bold else "arial.ttf",
        "arial.ttf",
    ]
    for b_name in bundled_names:
        p = os.path.join(base_dir, "assets", "fonts", b_name)
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                pass

    # 2. System fonts fallback
    system_names = [
        "C:\\Windows\\Fonts\\arialbd.ttf" if bold else "C:\\Windows\\Fonts\\arial.ttf",
        "C:\\Windows\\Fonts\\arial.ttf",
        "C:\\Windows\\Fonts\\segoeuib.ttf" if bold else "C:\\Windows\\Fonts\\segoeui.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf",
        "arial.ttf",
    ]
    for s_path in system_names:
        try:
            return ImageFont.truetype(s_path, size)
        except Exception:
            continue

    return ImageFont.load_default()


def _draw_gradient_line(draw: ImageDraw.Draw, x1: int, y: int, x2: int, height: int = 4):
    """Draw a smooth Instagram gradient accent line."""
    width = max(1, x2 - x1)
    colors = [INSTA_PURPLE, INSTA_PINK, INSTA_ORANGE, INSTA_YELLOW]
    n_segments = len(colors) - 1

    for px in range(width):
        t = px / width
        seg = int(t * n_segments)
        seg = min(seg, n_segments - 1)
        sub_t = (t * n_segments) - seg

        c1 = colors[seg]
        c2 = colors[seg + 1]
        r = int(c1[0] + (c2[0] - c1[0]) * sub_t)
        g = int(c1[1] + (c2[1] - c1[1]) * sub_t)
        b = int(c1[2] + (c2[2] - c1[2]) * sub_t)

        draw.line([(x1 + px, y), (x1 + px, y + height - 1)], fill=(r, g, b))


def generate_stats_card(
    stats: dict,
    username: str = "Instagram",
    bot_username: str = "@InstagramAnalyzerBot"
) -> BytesIO:
    """Generate a high-resolution, viral Instagram stats card with bot promotion."""
    width, height = 980, 680
    img = Image.new("RGB", (width, height), CANVAS_BG)
    draw = ImageDraw.Draw(img)

    # 1. Outer Glow / Accent Border
    draw.rounded_rectangle(
        [(14, 14), (width - 14, height - 14)],
        radius=24,
        fill=HEADER_BG,
        outline=(35, 40, 60),
        width=2,
    )

    # Top Instagram gradient bar across the header
    _draw_gradient_line(draw, 16, 16, width - 16, height=5)

    # 2. Header Section
    title_font = _get_font(28, bold=True)
    sub_font = _get_font(15, bold=False)
    badge_font = _get_font(13, bold=True)

    # Header Tag / Pill: "📊 INSTAGRAM АНАЛИТИКА"
    tag_text = "📊 INSTAGRAM АНАЛИТИКА"
    draw.rounded_rectangle([(42, 38), (250, 64)], radius=8, fill=(35, 30, 55), outline=INSTA_PINK, width=1)
    draw.text((54, 43), tag_text, fill=INSTA_YELLOW, font=badge_font)

    # User title
    display_user = username if username.startswith("@") else f"@{username}"
    draw.text((42, 74), f"Профиль: {display_user}", fill=WHITE, font=title_font)

    # Subtitle with date
    today_str = datetime.now().strftime("%d.%m.%Y")
    draw.text((42, 114), f"Сформировано: {today_str} • 100% точный анализ по архиву Meta", fill=MUTED_GRAY, font=sub_font)

    # Divider line
    draw.line([(42, 142), (width - 42, 142)], fill=(40, 45, 65), width=1)

    # 3. Metrics Section
    stat_font = _get_font(42, bold=True)
    label_font = _get_font(14, bold=True)
    sublabel_font = _get_font(12, bold=False)

    # Row 1: 3 cards
    row1_items = [
        (str(stats.get("followers", 0)), "ПОДПИСЧИКИ", "следят за тобой", COLOR_FOLLOWERS),
        (str(stats.get("following", 0)), "ПОДПИСКИ", "ты следишь", COLOR_FOLLOWING),
        (str(stats.get("mutual", 0)), "ВЗАИМНЫЕ", "двусторонняя связь", COLOR_MUTUAL),
    ]

    gap = 18
    start_x = 42
    total_w = width - 84
    col_w_r1 = (total_w - gap * 2) // 3
    y_r1 = 158
    card_h_r1 = 145

    for i, (val, title, subtitle, color) in enumerate(row1_items):
        cx1 = start_x + i * (col_w_r1 + gap)
        cy1 = y_r1
        cx2 = cx1 + col_w_r1
        cy2 = cy1 + card_h_r1

        # Card base
        draw.rounded_rectangle([(cx1, cy1), (cx2, cy2)], radius=16, fill=CARD_BG, outline=CARD_BORDER, width=1)
        # Top color accent strip
        draw.rounded_rectangle([(cx1 + 12, cy1 + 2), (cx2 - 12, cy1 + 5)], radius=2, fill=color)

        # Number
        draw.text((cx1 + 20, cy1 + 20), val, fill=WHITE, font=stat_font)
        # Title
        draw.text((cx1 + 20, cy1 + 84), title, fill=color, font=label_font)
        # Subtitle
        draw.text((cx1 + 20, cy1 + 106), subtitle, fill=MUTED_GRAY, font=sublabel_font)

    # Row 2: 2 highlighted cards (unfollowers & not followed back)
    row2_items = [
        (
            str(stats.get("not_following_back", 0)),
            "НЕ ПОДПИСАНЫ В ОТВЕТ",
            "Ты подписан, а они отписались / не подписаны",
            COLOR_NOT_BACK,
            "😤 ОТПИСЧИКИ",
        ),
        (
            str(stats.get("not_followed_back", 0)),
            "ТЫ НЕ ПОДПИСАН В ОТВЕТ",
            "Они подписаны на тебя, а ты взаимно нет",
            COLOR_YOU_NOT_BACK,
            "👤 ФАНАТЫ",
        ),
    ]

    col_w_r2 = (total_w - gap) // 2
    y_r2 = 320
    card_h_r2 = 150

    for i, (val, title, subtitle, color, badge) in enumerate(row2_items):
        cx1 = start_x + i * (col_w_r2 + gap)
        cy1 = y_r2
        cx2 = cx1 + col_w_r2
        cy2 = cy1 + card_h_r2

        # Card base
        draw.rounded_rectangle([(cx1, cy1), (cx2, cy2)], radius=16, fill=CARD_BG, outline=color, width=1)
        # Top color accent
        draw.rounded_rectangle([(cx1 + 12, cy1 + 2), (cx2 - 12, cy1 + 6)], radius=2, fill=color)

        # Badge pill
        draw.rounded_rectangle([(cx2 - 130, cy1 + 16), (cx2 - 16, cy1 + 40)], radius=6, fill=(35, 30, 45))
        draw.text((cx2 - 122, cy1 + 20), badge, fill=color, font=_get_font(11, bold=True))

        # Number
        draw.text((cx1 + 22, cy1 + 20), val, fill=WHITE, font=stat_font)
        # Title
        draw.text((cx1 + 22, cy1 + 86), title, fill=color, font=label_font)
        # Subtitle
        draw.text((cx1 + 22, cy1 + 110), subtitle, fill=LIGHT_GRAY, font=sublabel_font)

    # 4. Promo / Bot Advertising Banner (Bottom)
    promo_y1 = 490
    promo_y2 = 648
    draw.rounded_rectangle(
        [(start_x, promo_y1), (width - start_x, promo_y2)],
        radius=18,
        fill=(20, 24, 38),
        outline=INSTA_PINK,
        width=2,
    )

    # Subtle top gradient bar for promo banner
    _draw_gradient_line(draw, start_x + 2, promo_y1 + 2, width - start_x - 2, height=3)

    promo_title_font = _get_font(18, bold=True)
    promo_sub_font = _get_font(14, bold=False)
    cta_font = _get_font(14, bold=True)

    # Promo texts
    clean_bot_name = bot_username if bot_username.startswith("@") else f"@{bot_username}"
    draw.text((start_x + 24, promo_y1 + 22), "🔥 Хочешь узнать, кто отписался от тебя в Instagram?", fill=WHITE, font=promo_title_font)
    draw.text(
        (start_x + 24, promo_y1 + 54),
        f"Заходи в бесплатный Telegram-бот: {clean_bot_name}",
        fill=INSTA_YELLOW,
        font=_get_font(15, bold=True),
    )
    draw.text((start_x + 24, promo_y1 + 86), "🔒 Без ввода логина и пароля • Быстро • 100% безопасно", fill=MUTED_GRAY, font=promo_sub_font)

    # CTA Button / Badge on the right
    btn_x1 = width - start_x - 220
    btn_y1 = promo_y1 + 38
    btn_x2 = width - start_x - 24
    btn_y2 = promo_y1 + 88
    draw.rounded_rectangle([(btn_x1, btn_y1), (btn_x2, btn_y2)], radius=12, fill=INSTA_PINK)
    draw.text((btn_x1 + 24, btn_y1 + 16), "ПРОВЕРИТЬ ➔", fill=WHITE, font=cta_font)

    # Save to buffer
    buf = BytesIO()
    img.save(buf, format="PNG", quality=95)
    buf.seek(0)
    return buf
