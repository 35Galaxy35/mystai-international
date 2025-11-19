# chart_generator.py
# ===================
# MystAI - Profesyonel Astroloji Harita Üreticisi
#
# - Skyfield (NASA JPL DE421) ile gezegen hesapları
# - Natal & Solar Return haritaları için ortak çizici
# - Aspect çizgileri: kavuşum, kare, üçgen, karşıt, sekstil
# - PNG çıktı: /tmp klasörüne kaydedilir
#
# DIŞA AÇIK FONKSİYONLAR:
#   generate_natal_chart(...)
#   generate_solar_return_chart(...)
#
# main.py:
#   from chart_generator import generate_natal_chart, generate_solar_return_chart
#
# Not: Haritalar "profesyonel astroloji" standardında,
# Skyfield JPL efemerisi kullanıldığı için Swiss Ephemeris kadar hassas.

import os
import uuid
import math
from datetime import datetime, timedelta

from skyfield.api import load, wgs84
from PIL import Image, ImageDraw, ImageFont


# -------------------------
# Genel ayarlar
# -------------------------

IMAGE_SIZE = 1200                 # PNG boyutu
BG_COLOR   = (9, 11, 28)          # koyu gece mavisi
CIRCLE_COLOR = (240, 210, 120)
INNER_COLOR  = (190, 180, 150)
HOUSE_LINE_COLOR = (220, 220, 240)

ASPECT_COLORS = {
    "conj":    (255, 120, 120),
    "opp":     (255, 120, 120),
    "square":  (255, 120, 120),
    "trine":   (120, 190, 255),
    "sextile": (120, 230, 180),
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

SIGNS = [
    ("Aries", "♈"),
    ("Taurus", "♉"),
    ("Gemini", "♊"),
    ("Cancer", "♋"),
    ("Leo", "♌"),
    ("Virgo", "♍"),
    ("Libra", "♎"),
    ("Scorpio", "♏"),
    ("Sagittarius", "♐"),
    ("Capricorn", "♑"),
    ("Aquarius", "♒"),
    ("Pisces", "♓"),
]


# Skyfield ephemeris
_TS = load.timescale()
_EPH = load("de421.bsp")   # ücretsiz, küçük ephemeris


# -----------------------------------------------------
# Yardımcı: derece farkı (0–180 arası)
# -----------------------------------------------------
def _angle_diff(a, b):
    diff = abs(a - b) % 360.0
    if diff > 180.0:
        diff = 360.0 - diff
    return diff


# -----------------------------------------------------
# Yardımcı: datetime parse
# -----------------------------------------------------
def _parse_datetime(birth_date: str, birth_time: str) -> datetime:
    """
    birth_date: 'YYYY-MM-DD'
    birth_time: 'HH:MM' (24 saat format)
    """
    year, month, day = map(int, birth_date.split("-"))
    hh, mm = map(int, birth_time.split(":")[:2])
    return datetime(year, month, day, hh, mm)


# -----------------------------------------------------
# Güneş boylamı (profesyonel solar return için)
# -----------------------------------------------------
def _sun_longitude(dt: datetime) -> float:
    """
    Verilen datetime için Güneş'in ekliptik boylamı (0-360 derece)
    Burada ~UT varsayımı var (kullanıcı TZ bilinmiyor).
    """
    t = _TS.utc(dt.year, dt.month, dt.day, dt.hour, dt.minute)
    earth = _EPH["earth"]
    sun = _EPH["sun"]
    ecl_lat, ecl_lon, _ = earth.at(t).observe(sun).ecliptic_latlon()
    return float(ecl_lon.degrees % 360.0)


def compute_solar_return_datetime(birth_date: str, birth_time: str, year: int) -> datetime:
    """
    PROFESYONEL SOLAR RETURN:
    - Önce doğum anındaki Güneş boylamını bul
    - Seçilen yılda doğum günü civarında ±36 saatlik aralıkta
      Güneş boylamının en yakın olduğu zamanı tara
    """
    natal_dt = _parse_datetime(birth_date, birth_time)
    natal_sun_lon = _sun_longitude(natal_dt)

    # Aynı ay/gün + hedef yıl civarı
    approx = datetime(year, natal_dt.month, natal_dt.day, natal_dt.hour, natal_dt.minute)

    best_dt = approx
    best_diff = 999.0

    # -36 saatten +60 saate kadar, saat saat tara
    for h in range(-36, 61):
        cand = approx + timedelta(hours=h)
        lon = _sun_longitude(cand)
        diff = _angle_diff(lon, natal_sun_lon)
        if diff < best_diff:
            best_diff = diff
            best_dt = cand

    return best_dt


# -----------------------------------------------------
# Gezegen boylamlarını hesaplayan fonksiyon
# -----------------------------------------------------
def _compute_longitudes(birth_date: str, birth_time: str, lat: float, lon: float):
    """
    Verilen tarih/saat ve konum için temel gezegen boylamları.
    """
    year, month, day = map(int, birth_date.split("-"))
    hour, minute = map(int, birth_time.split(":")[:2])

    t = _TS.utc(year, month, day, hour, minute)

    earth = _EPH["earth"]
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
        longs[name] = float(ecl_lon.degrees % 360.0)

    return longs


# -----------------------------------------------------
# Polar koordinat hesaplayan yardımcı fonksiyon
# -----------------------------------------------------
def _polar(cx, cy, radius, angle_deg):
    rad = math.radians(angle_deg)
    return cx + radius * math.cos(rad), cy + radius * math.sin(rad)


# -----------------------------------------------------
# Haritayı çizen ana fonksiyon (Natal / Solar ortak)
# -----------------------------------------------------
def _draw_chart(longitudes: dict, title: str = "Astrology Chart", subtitle: str = "") -> Image.Image:
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

    # 12 burç & ev çizgisi (eşit ev sistemi – profesyonel sitelerin çoğunda seçenek)
    for i in range(12):
        angle = i * 30  # 30° aralıklarla
        # ev çizgisi
        x1, y1 = _polar(cx, cy, inner_r, angle)
        x2, y2 = _polar(cx, cy, outer_r, angle)
        draw.line([x1, y1, x2, y2], fill=HOUSE_LINE_COLOR, width=2)

    # Font
    try:
        font = ImageFont.truetype("DejaVuSans.ttf", 40)
        font_small = ImageFont.truetype("DejaVuSans.ttf", 26)
        font_title = ImageFont.truetype("DejaVuSans.ttf", 42)
    except Exception:
        font = ImageFont.load_default()
        font_small = font
        font_title = font

    # Üst başlık
    title_text = title or "Astrology Chart"
    tb = draw.textbbox((0, 0), title_text, font=font_title)
    tw = tb[2] - tb[0]
    draw.text((cx - tw/2, cy - outer_r - 70), title_text, font=font_title, fill=(245, 225, 160))

    if subtitle:
        sb = draw.textbbox((0, 0), subtitle, font=font_small)
        sw = sb[2] - sb[0]
        draw.text((cx - sw/2, cy - outer_r - 32), subtitle, font=font_small, fill=(210, 210, 230))

    # Burç sembolleri dış çember etrafında
    for i, (_, sign_glyph) in enumerate(SIGNS):
        mid_angle = i * 30 + 15  # her burcun orta noktası
        tx, ty = _polar(cx, cy, outer_r + 24, mid_angle - 90)
        sbbox = draw.textbbox((0, 0), sign_glyph, font=font_small)
        sw = sbbox[2] - sbbox[0]
        sh = sbbox[3] - sbbox[1]
        draw.text((tx - sw/2, ty - sh/2), sign_glyph, font=font_small, fill=(255, 233, 163))

    # Gezegenlerin noktaları + sembolleri
    planet_points = {}

    for name, glyph in PLANETS:
        lon_deg = longitudes.get(name)
        if lon_deg is None:
            continue

        # Astrolojik pozisyon: 0° Koç yukarı gelecek şekilde
        angle = (lon_deg - 90) % 360

        # Nokta
        px, py = _polar(cx, cy, aspect_r, angle)
        draw.ellipse([px - 6, py - 6, px + 6, py + 6], fill=(250, 250, 250))

        # Label
        tx, ty = _polar(cx, cy, text_r, angle)
        label = glyph or name[:2]

        bbox = draw.textbbox((0, 0), label, font=font)   # Pillow 10 uyumlu
        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]

        draw.text((tx - w/2, ty - h/2), label, font=font, fill=(240, 240, 250))

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
            elif abs(diff - 60) <= 4:
                aspect = "sextile"
            elif abs(diff - 90) <= 5:
                aspect = "square"
            elif abs(diff - 120) <= 5:
                aspect = "trine"
            elif abs(diff - 180) <= 6:
                aspect = "opp"

            if aspect:
                color = ASPECT_COLORS.get(aspect, (150,150,150))
                draw.line([x1, y1, x2, y2], fill=color, width=2)

    return img


# -----------------------------------------------------
# NATAL HARİTA ÜRETİCİ (DIŞA AÇIK)
# -----------------------------------------------------
def generate_natal_chart(
    birth_date: str,
    birth_time: str,
    latitude: float,
    longitude: float,
    out_dir: str = "/tmp",
):
    """
    Natal (doğum) haritası üretir.
    DÖNEN:
      chart_id, chart_file_path
    """
    os.makedirs(out_dir, exist_ok=True)

    longs = _compute_longitudes(birth_date, birth_time, latitude, longitude)

    subtitle = f"{birth_date} • {birth_time}"
    img = _draw_chart(longs, title="Natal Chart", subtitle=subtitle)

    chart_id = uuid.uuid4().hex
    file_path = os.path.join(out_dir, f"{chart_id}.png")
    img.save(file_path, format="PNG")

    return chart_id, file_path


# -----------------------------------------------------
# SOLAR RETURN HARİTA ÜRETİCİ (DIŞA AÇIK)
# -----------------------------------------------------
def generate_solar_return_chart(
    birth_date: str,
    birth_time: str,
    latitude: float,
    longitude: float,
    year: int,
    out_dir: str = "/tmp",
):
    """
    PROFESYONEL Solar Return haritası üretir.

    - Güneşin, doğum anındaki boylamına döndüğü anı bulur (yaklaşık ±1 saat hassasiyet)
    - O anki gökyüzüne göre harita çizer.

    DÖNEN:
      chart_id, chart_file_path, sr_date_str, sr_time_str
    """
    os.makedirs(out_dir, exist_ok=True)

    sr_dt = compute_solar_return_datetime(birth_date, birth_time, year)
    sr_date_str = sr_dt.strftime("%Y-%m-%d")
    sr_time_str = sr_dt.strftime("%H:%M")

    longs = _compute_longitudes(sr_date_str, sr_time_str, latitude, longitude)

    subtitle = f"Solar Return: {sr_date_str} • {sr_time_str} (UT approx)"
    img = _draw_chart(longs, title="Solar Return Chart", subtitle=subtitle)

    chart_id = uuid.uuid4().hex
    file_path = os.path.join(out_dir, f"{chart_id}.png")
    img.save(file_path, format="PNG")

    return chart_id, file_path, sr_date_str, sr_time_str
