# backend/chart_generator.py
#
# Gerçek doğum haritası (natal wheel) üreten basit ama profesyonel bir çizici.
# - Gezegen konumları: skyfield (de421) ile hesaplanır
# - Harita çizimi: Pillow
#
# Kullanım:
#   from chart_generator import generate_natal_chart
#   chart_id, chart_path = generate_natal_chart("1978-11-06", "13:40", 38.4237, 27.1428)
#   -> /tmp/<chart_id>.png oluşturur

import os
import uuid
import math

from skyfield.api import load, wgs84
from PIL import Image, ImageDraw, ImageFont

# -------------------------
# Ayarlar
# -------------------------

IMAGE_SIZE = 1200              # Kare PNG boyutu
BG_COLOR = (248, 243, 230)     # Açık bej arkaplan
CIRCLE_COLOR = (140, 120, 80)
INNER_COLOR = (170, 160, 140)
HOUSE_LINE_COLOR = (180, 160, 120)

ASPECT_COLORS = {
    "conj": (200, 0, 0),
    "opp": (200, 0, 0),
    "square": (200, 0, 0),
    "trine": (0, 80, 160),
    "sextile": (0, 120, 60),
}

PLANETS = [
    ("Sun", "☉"),
    ("Moon", "☽"),
    ("Mercury", "☿"),
    ("Venus", "♀"),
    ("Mars", "♂"),
    ("Jupiter", "♃"),
    ("Saturn", "♄"),
    ("Uranus", "♅"),
    ("Neptune", "♆"),
    ("Pluto", "♇"),
]

# Skyfield ephemeris'i modül seviyesinde tek sefer yükleyelim
_TS = load.timescale()
_EPH = load("de421.bsp")  # ilk importta indirir, sonra cache'ler


def _compute_longitudes(birth_date: str, birth_time: str, lat: float, lon: float):
    """
    Gezegenlerin ekliptik boylamlarını (0–360°) hesaplar.
    birth_date: 'YYYY-MM-DD'
    birth_time: 'HH:MM'
    lat, lon: enlem / boylam (derece)
    """
    year, month, day = map(int, birth_date.split("-"))
    h_str, m_str = birth_time.split(":")[:2]
    hour, minute = int(h_str), int(m_str)

    t = _TS.utc(year, month, day, hour, minute)

    earth = _EPH["earth"]
    location = earth + wgs84.latlon(
        latitude_degrees=lat,
        longitude_degrees=lon
    )

    longs = {}

    planet_keys = {
        "Sun": "sun",
        "Moon": "moon",
        "Mercury": "mercury",
        "Venus": "venus",
        "Mars": "mars",
        "Jupiter": "jupiter barycenter",
        "Saturn": "saturn barycenter",
        "Uranus": "uranus barycenter",
        "Neptune": "neptune barycenter",
        "Pluto": "pluto barycenter",
    }

    for name, key in planet_keys.items():
        body = _EPH[key]
        ecl_lat, ecl_lon, _ = location.at(t).observe(body).ecliptic_latlon()
        lon_deg = ecl_lon.degrees % 360.0
        longs[name] = lon_deg

    return longs


def _polar(cx, cy, radius, angle_deg):
    """Merkez (cx,cy), yarıçap ve derece cinsinden açıdan x,y döndürür."""
    rad = math.radians(angle_deg)
    x = cx + radius * math.cos(rad)
    y = cy + radius * math.sin(rad)
    return x, y


def _draw_chart(longitudes: dict) -> Image.Image:
    """
    Verilen boylamlara göre profesyonel görünümlü natal wheel üretir.
    """
    size = IMAGE_SIZE
    img = Image.new("RGB", (size, size), BG_COLOR)
    draw = ImageDraw.Draw(img)

    cx = cy = size // 2
    outer_r = size * 0.45
    inner_r = size * 0.18
    text_r = size * 0.40
    aspect_r = size * 0.35

    # Dış daire
    draw.ellipse(
        [cx - outer_r, cy - outer_r, cx + outer_r, cy + outer_r],
        outline=CIRCLE_COLOR,
        width=8,
    )

    # İç daire
    draw.ellipse(
        [cx - inner_r, cy - inner_r, cx + inner_r, cy + inner_r],
        outline=INNER_COLOR,
        width=4,
    )

    # 12 ev çizgisi (şimdilik 0° Koç'tan başlayan eşit evler)
    for i in range(12):
        angle = i * 30.0  # her ev 30 derece
        x1, y1 = _polar(cx, cy, inner_r, angle)
        x2, y2 = _polar(cx, cy, outer_r, angle)
        draw.line([x1, y1, x2, y2], fill=HOUSE_LINE_COLOR, width=2)

    # Yazı tipi
    try:
        font = ImageFont.truetype("DejaVuSans.ttf", 32)
    except Exception:
        font = ImageFont.load_default()

    planet_points = {}

    # Gezegen noktaları + semboller
    for name, glyph in PLANETS:
        lon_deg = longitudes.get(name)
        if lon_deg is None:
            continue

        # Astrolojik wheel'de 0° Koç yukarıda olacak şekilde 90° kaydırıyoruz
        angle = (lon_deg - 90.0) % 360.0

        # Nokta
        px, py = _polar(cx, cy, aspect_r, angle)
        draw.ellipse(
            [px - 6, py - 6, px + 6, py + 6],
            fill=(0, 0, 0),
            outline=(0, 0, 0),
            width=1,
        )

        # Sembol
        tx, ty = _polar(cx, cy, text_r, angle)
        label = glyph if glyph else name[:2]
        w, h = draw.textsize(label, font=font)
        draw.text((tx - w / 2, ty - h / 2), label, font=font, fill=(10, 10, 10))

        planet_points[name] = (px, py, lon_deg)

    # Aspect çizgileri
    names = list(planet_points.keys())
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            n1 = names[i]
            n2 = names[j]
            x1, y1, lon1 = planet_points[n1]
            x2, y2, lon2 = planet_points[n2]

            diff = abs(lon1 - lon2)
            if diff > 180:
                diff = 360 - diff

            aspect_type = None
            # orb ±5°
            if abs(diff - 0) <= 5:
                aspect_type = "conj"
            elif abs(diff - 60) <= 5:
                aspect_type = "sextile"
            elif abs(diff - 90) <= 5:
                aspect_type = "square"
            elif abs(diff - 120) <= 5:
                aspect_type = "trine"
            elif abs(diff - 180) <= 5:
                aspect_type = "opp"

            if aspect_type:
                color = ASPECT_COLORS.get(aspect_type, (150, 150, 150))
                draw.line([x1, y1, x2, y2], fill=color, width=2)

    return img


def generate_natal_chart(
    birth_date: str,
    birth_time: str,
    latitude: float,
    longitude: float,
    out_dir: str = "/tmp",
):
    """
    Dışarıya açılan fonksiyon.
    Gerçek gezegen pozisyonlarına göre natal wheel çizer ve PNG kaydeder.

    Dönüş:
        chart_id (str), file_path (str)
    Frontend'te /chart/<chart_id> endpoint'i ile sunabilirsin.
    """
    os.makedirs(out_dir, exist_ok=True)

    longs = _compute_longitudes(birth_date, birth_time, latitude, longitude)
    img = _draw_chart(longs)

    chart_id = uuid.uuid4().hex
    file_path = os.path.join(out_dir, f"{chart_id}.png")
    img.save(file_path, format="PNG")

    return chart_id, file_path
