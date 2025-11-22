# chart_generator.py
# ===================
# MystAI - Profesyonel Astroloji Harita Üreticisi (Swiss Ephemeris)
#
# - Swiss Ephemeris (pyswisseph) ile gezegen konumları
# - Natal & Solar Return haritaları için ortak çizici
# - Aspect çizgileri: kavuşum, kare, üçgen, karşıt, sekstil
# - PNG çıktı: /tmp klasörüne kaydedilir
#
# DIŞA AÇIK FONKSİYONLAR:
#   generate_natal_chart(...)
#   generate_solar_return_chart(...)
#
# Not:
# - Zaman hesabı: doğum saati ve doğum yeri -> TimezoneFinder + pytz ile UTC'ye çevrilir
# - Ev sistemi: şu an çizimde eşit ev çemberi kullanıyoruz; gezegen dereceleri
#   ve burç yerleşimleri Swiss Ephemeris ile astro.com ile uyumlu hale getirildi.

import os
import uuid
import math
from datetime import datetime, timedelta

from PIL import Image, ImageDraw, ImageFont
from timezonefinder import TimezoneFinder
import pytz
import swisseph as swe

# -------------------------------------------------
# Swiss Ephemeris ayarı (ephemeris dosya yolu)
# -------------------------------------------------
EPHE_PATH = os.path.join(os.path.dirname(swe.__file__), "ephe")
if os.path.isdir(EPHE_PATH):
    swe.set_ephe_path(EPHE_PATH)

# -------------------------------------------------
# Görsel ayarları
# -------------------------------------------------
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
    ("Sun",     "☉", swe.SUN),
    ("Moon",    "☽", swe.MOON),
    ("Mercury", "☿", swe.MERCURY),
    ("Venus",   "♀", swe.VENUS),
    ("Mars",    "♂", swe.MARS),
    ("Jupiter", "♃", swe.JUPITER),
    ("Saturn",  "♄", swe.SATURN),
    ("Uranus",  "♅", swe.URANUS),
    ("Neptune", "♆", swe.NEPTUNE),
    ("Pluto",   "♇", swe.PLUTO),
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

_tf = TimezoneFinder()


# -------------------------------------------------
# Yardımcı fonksiyonlar
# -------------------------------------------------
def _angle_diff(a, b):
    """0–180 arası derece farkı."""
    diff = abs(a - b) % 360.0
    if diff > 180.0:
        diff = 360.0 - diff
    return diff


def _parse_local_to_utc(birth_date: str, birth_time: str, lat: float, lon: float) -> datetime:
    """
    Doğum tarihi & yerel saat -> UTC datetime
    birth_date: 'YYYY-MM-DD'
    birth_time: 'HH:MM'
    """
    year, month, day = map(int, birth_date.split("-"))
    hh, mm = map(int, birth_time.split(":")[:2])

    # Tahmini timezone (şehir koordinatına göre)
    try:
        tzname = _tf.timezone_at(lat=lat, lng=lon) or "UTC"
    except Exception:
        tzname = "UTC"

    try:
        tz = pytz.timezone(tzname)
    except Exception:
        tz = pytz.UTC

    local_dt = tz.localize(datetime(year, month, day, hh, mm))
    utc_dt = local_dt.astimezone(pytz.UTC)
    return utc_dt


def _utc_to_julday(dt_utc: datetime) -> float:
    """UTC datetime -> Swiss Ephemeris Julian Day (UT)."""
    return swe.julday(dt_utc.year, dt_utc.month, dt_utc.day,
                      dt_utc.hour + dt_utc.minute / 60.0 + dt_utc.second / 3600.0)


# -------------------------------------------------
# Güneş boylamı (solar return için)
# -------------------------------------------------
def _sun_longitude_utc(dt_utc: datetime) -> float:
    jd_ut = _utc_to_julday(dt_utc)
    lon, lat, dist, speed = swe.calc_ut(jd_ut, swe.SUN)
    return lon % 360.0


def compute_solar_return_datetime(birth_date: str, birth_time: str, lat: float, lon: float, year: int) -> datetime:
    """
    Profesyonel solar return:
    - Doğumdaki Güneş boylamını bul
    - İstenen yılda doğum günü civarında Güneş aynı boylama dönene kadar ara
    """
    # Doğum anını UTC'ye çevir
    natal_local = datetime.strptime(birth_date + " " + birth_time, "%Y-%m-%d %H:%M")
    natal_utc = _parse_local_to_utc(birth_date, birth_time, lat, lon)
    natal_sun_lon = _sun_longitude_utc(natal_utc)

    # Aynı ay/gün + hedef yıl civarı başlangıç (lokal saat yaklaşık)
    approx_local = natal_local.replace(year=year)
    approx_utc = _parse_local_to_utc(approx_local.strftime("%Y-%m-%d"),
                                     approx_local.strftime("%H:%M"),
                                     lat, lon)

    best_dt = approx_utc
    best_diff = 999.0

    # -36 saatten +60 saate kadar 1 saat aralıkla tara
    for h in range(-36, 61):
        cand = approx_utc + timedelta(hours=h)
        lon_sun = _sun_longitude_utc(cand)
        diff = _angle_diff(lon_sun, natal_sun_lon)
        if diff < best_diff:
            best_diff = diff
            best_dt = cand

    return best_dt


# -------------------------------------------------
# Gezegen boylamlarını hesaplayan fonksiyon
# -------------------------------------------------
def _compute_longitudes_utc(jd_ut: float):
    """
    Julian Day (UT) için temel gezegen boylamları (ecliptic, geocentric).
    """
    longs = {}
    for name, glyph, swe_id in PLANETS:
        lon, lat, dist, speed = swe.calc_ut(jd_ut, swe_id)
        longs[name] = lon % 360.0
    return longs


# -------------------------------------------------
# Polar koordinat hesaplayan fonksiyon
# -------------------------------------------------
def _polar(cx, cy, radius, angle_deg):
    rad = math.radians(angle_deg)
    return cx + radius * math.cos(rad), cy + radius * math.sin(rad)


# -------------------------------------------------
# Haritayı çizen ana fonksiyon (Natal / Solar ortak)
# -------------------------------------------------
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

    # 12 eşit ev çizgisi (şimdilik görsel amaçlı)
    for i in range(12):
        angle = i * 30  # 30° aralıklarla
        x1, y1 = _polar(cx, cy, inner_r, angle)
        x2, y2 = _polar(cx, cy, outer_r, angle)
        draw.line([x1, y1, x2, y2], fill=HOUSE_LINE_COLOR, width=2)

    # Fontlar
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
    draw.text((cx - tw / 2, cy - outer_r - 70), title_text, font=font_title, fill=(245, 225, 160))

    if subtitle:
        sb = draw.textbbox((0, 0), subtitle, font=font_small)
        sw = sb[2] - sb[0]
        draw.text((cx - sw / 2, cy - outer_r - 32), subtitle, font=font_small, fill=(210, 210, 230))

    # Burç sembolleri dış çember etrafında (0° Koç yukarıda olacak şekilde)
    for i, (_, sign_glyph) in enumerate(SIGNS):
        mid_angle = i * 30 + 15  # her burcun orta noktası
        # 0° Koç yukarı gelsin diye -90 kaydırıyoruz
        tx, ty = _polar(cx, cy, outer_r + 24, mid_angle - 90)
        sbbox = draw.textbbox((0, 0), sign_glyph, font=font_small)
        sw = sbbox[2] - sbbox[0]
        sh = sbbox[3] - sbbox[1]
        draw.text((tx - sw / 2, ty - sh / 2), sign_glyph, font=font_small, fill=(255, 233, 163))

    # Gezegenlerin noktaları + sembolleri
    planet_points = {}

    for name, glyph, _ in PLANETS:
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

        bbox = draw.textbbox((0, 0), label, font=font)
        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]

        draw.text((tx - w / 2, ty - h / 2), label, font=font, fill=(240, 240, 250))

        planet_points[name] = (px, py, lon_deg)

    # Aspect çizimleri
    names = list(planet_points.keys())
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
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
                color = ASPECT_COLORS.get(aspect, (150, 150, 150))
                draw.line([x1, y1, x2, y2], fill=color, width=2)

    return img


# -------------------------------------------------
# NATAL HARİTA ÜRETİCİ (DIŞA AÇIK)
# -------------------------------------------------
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

    # Lokal doğum zamanı -> UTC -> JD
    dt_utc = _parse_local_to_utc(birth_date, birth_time, latitude, longitude)
    jd_ut = _utc_to_julday(dt_utc)

    longs = _compute_longitudes_utc(jd_ut)

    subtitle = f"{birth_date} • {birth_time}"
    img = _draw_chart(longs, title="Natal Chart", subtitle=subtitle)

    chart_id = uuid.uuid4().hex
    file_path = os.path.join(out_dir, f"{chart_id}.png")
    img.save(file_path, format="PNG")

    return chart_id, file_path


# -------------------------------------------------
# SOLAR RETURN HARİTA ÜRETİCİ (DIŞA AÇIK)
# -------------------------------------------------
def generate_solar_return_chart(
    birth_date: str,
    birth_time: str,
    latitude: float,
    longitude: float,
    year: int,
    out_dir: str = "/tmp",
):
    """
    Profesyonel Solar Return haritası üretir.

    - Güneşin, doğum anındaki boylamına döndüğü UTC zamanı bulur
    - O anki gökyüzüne göre harita çizer.

    DÖNEN:
      chart_id, chart_file_path, sr_date_str, sr_time_str
    """
    os.makedirs(out_dir, exist_ok=True)

    # Solar return anını UTC olarak bul
    sr_dt_utc = compute_solar_return_datetime(birth_date, birth_time, latitude, longitude, year)
    sr_date_str = sr_dt_utc.strftime("%Y-%m-%d")
    sr_time_str = sr_dt_utc.strftime("%H:%M")

    jd_ut = _utc_to_julday(sr_dt_utc)
    longs = _compute_longitudes_utc(jd_ut)

    subtitle = f"Solar Return: {sr_date_str} • {sr_time_str} (UTC)"
    img = _draw_chart(longs, title="Solar Return Chart", subtitle=subtitle)

    chart_id = uuid.uuid4().hex
    file_path = os.path.join(out_dir, f"{chart_id}.png")
    img.save(file_path, format="PNG")

    return chart_id, file_path, sr_date_str, sr_time_str
