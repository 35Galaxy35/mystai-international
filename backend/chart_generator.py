# backend/chart_generator.py
#
# Gerçek doğum haritası (natal wheel) üreten profesyonel bir çizer.
# - Gezegen konumları: Skyfield
# - Harita çizimi: Pillow (Pillow 10 uyumlu)
# - Export: PNG /tmp dizinine kaydedilir

import os
import uuid
import math
from datetime import datetime

from skyfield.api import load, wgs84
from PIL import Image, ImageDraw, ImageFont

# -------------------------
# Ayarlar
# -------------------------

IMAGE_SIZE = 1200                 # Çıktı PNG boyutu
BG_COLOR   = (248, 243, 230)      # Arkaplan (açık bej)
CIRCLE_COLOR = (140, 120, 80)
INNER_COLOR  = (170, 160, 140)
HOUSE_LINE_COLOR = (180, 160, 120)

ASPECT_COLORS = {
    "conj":    (200, 0, 0),
    "opp":     (200, 0, 0),
    "square":  (200, 0, 0),
    "trine":   (0, 80, 160),
    "sextile": (0, 120, 60),
}

PLANETS = [
    ("Sun",     "☉"),
    ("Moon",    "☽"),
    ("Mercury", "☿"),
    ("Venus",   "♀"),
    ("Mars",    "♂"),
    ("Jupiter", "♃"),
    ("Saturn",  "♄"),
    ("Uranus",  "♅"),
    ("Neptune", "♆"),
    ("Pluto",   "♇"),
]

# Skyfield ephemeris
_TS = load.timescale()
_EPH = load("de421.bsp")   # ücretsiz, küçük ephemeris


# -----------------------------------------------------
# Gezegen boylamlarını hesaplayan fonksiyon
# -----------------------------------------------------
def _compute_longitudes(birth_date: str, birth_time: str, lat: float, lon: float):
    year, month, day = map(int, birth_date.split("-"))
    hour, minute = map(int, birth_time.split(":")[:2])

    t = _TS.utc(year, month, day, hour, minute)

    earth = _EPH["earth"]
    # Önemli: skyfield için doğru parametre isimleri
    location = earth + wgs84.latlon(latitude_degrees=lat, longitude_degrees=lon)

    planet_keys = {
        "Sun":      "sun",
        "Moon":     "moon",
        "Mercury":  "mercury",
        "Venus":    "venus",
        "Mars":     "mars",
        "Jupiter":  "jupiter barycenter",
        "Saturn":   "saturn barycenter",
        "Uranus":   "uranus barycenter",
        "Neptune":  "neptune barycenter",
        "Pluto":    "pluto barycenter",
    }

    longs = {}
    for name, key in planet_keys.items():
        body = _EPH[key]
        ecl_lat, ecl_lon, _ = location.at(t).observe(body).ecliptic_latlon()
        longs[name] = float(ecl_lon.degrees % 360)

    return longs


# -----------------------------------------------------
# Polar koordinat hesaplayan yardımcı fonksiyon
# -----------------------------------------------------
def _polar(cx, cy, radius, angle_deg):
    rad = math.radians(angle_deg)
    return cx + radius * math.cos(rad), cy + radius * math.sin(rad)


# -----------------------------------------------------
# Haritayı çizen ana fonksiyon
# -----------------------------------------------------
def _draw_chart(longitudes: dict) -> Image.Image:
    size = IMAGE_SIZE
    img = Image.new("RGB", (size, size), BG_COLOR)
    draw = ImageDraw.Draw(img)

    cx = cy = size // 2
    outer_r = size * 0.46
    inner_r = size * 0.18
    text_r  = size * 0.41
    aspect_r = size * 0.34

    # Ana dış çember
    draw.ellipse(
        [cx - outer_r, cy - outer_r, cx + outer_r, cy + outer_r],
        outline=CIRCLE_COLOR, width=8
    )

    # İç çember
    draw.ellipse(
        [cx - inner_r, cy - inner_r, cx + inner_r, cy + inner_r],
        outline=INNER_COLOR, width=4
    )

    # 12 ev çizgisi
    for i in range(12):
        angle = i * 30
        x1, y1 = _polar(cx, cy, inner_r, angle)
        x2, y2 = _polar(cx, cy, outer_r, angle)
        draw.line([x1, y1, x2, y2], fill=HOUSE_LINE_COLOR, width=2)

    # Font
    try:
        font = ImageFont.truetype("DejaVuSans.ttf", 40)
    except Exception:
        font = ImageFont.load_default()

    # Gezegenlerin noktaları + sembolleri
    planet_points = {}

    for name, glyph in PLANETS:
        lon_deg = longitudes.get(name)
        if lon_deg is None:
            continue

        # Astrolojik pozisyon: 0° Koç yukarı
        angle = (lon_deg - 90) % 360

        # Nokta
        px, py = _polar(cx, cy, aspect_r, angle)
        draw.ellipse([px - 6, py - 6, px + 6, py + 6], fill=(0, 0, 0))

        # Label (Pillow 10 uyumlu textbbox)
        tx, ty = _polar(cx, cy, text_r, angle)
        label = glyph or name[:2]

        bbox = draw.textbbox((0, 0), label, font=font)
        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]

        draw.text((tx - w/2, ty - h/2), label, font=font, fill=(20, 20, 20))

        planet_points[name] = (px, py, lon_deg)

    # Aspect çizimleri
    names = list(planet_points.keys())
    for i in range(len(names)):
        for j in range(i+1, len(names)):
            n1, n2 = names[i], names[j]
            x1, y1, lon1 = planet_points[n1]
            x2, y2, lon2 = planet_points[n2]

            diff = abs(lon1 - lon2)
            if diff > 180:
                diff = 360 - diff

            aspect = None
            if abs(diff - 0) <= 6:
                aspect = "conj"
            elif abs(diff - 60) <= 6:
                aspect = "sextile"
            elif abs(diff - 90) <= 6:
                aspect = "square"
            elif abs(diff - 120) <= 6:
                aspect = "trine"
            elif abs(diff - 180) <= 6:
                aspect = "opp"

            if aspect:
                color = ASPECT_COLORS.get(aspect, (150,150,150))
                draw.line([x1, y1, x2, y2], fill=color, width=2)

    return img


# -----------------------------------------------------
# DIŞA AÇILAN ANA FONKSİYON
# -----------------------------------------------------
def generate_natal_chart(birth_date: str, birth_time: str,
                         latitude: float, longitude: float,
                         out_dir: str = "/tmp"):

    os.makedirs(out_dir, exist_ok=True)

    longs = _compute_longitudes(birth_date, birth_time, latitude, longitude)
    img = _draw_chart(longs)

    chart_id = uuid.uuid4().hex
    file_path = os.path.join(out_dir, f"{chart_id}.png")
    img.save(file_path, format="PNG")

    return chart_id, file_path
