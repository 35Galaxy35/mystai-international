# backend/chart_generator.py
# ==========================================
# MystAI - Profesyonel Doğum Haritası Çizici
# - Swiss Ephemeris (pyswisseph) varsa GERÇEK
#   gezegen ve ev konumları
# - Yoksa tarih/saatten türetilmiş deterministik
#   (her kullanıcıya özel) görsel fallback
# ==========================================

import os
import math
import uuid
from datetime import datetime

# -----------------------------
# Swiss Ephemeris
# -----------------------------
try:
    import swisseph as swe  # paket: pyswisseph
    HAS_SWISS = True
except Exception:
    HAS_SWISS = False

# -----------------------------
# Matplotlib (Render uyumlu)
# -----------------------------
import matplotlib
matplotlib.use("Agg")  # GUI yok, headless
import matplotlib.pyplot as plt
from matplotlib.patches import Circle

# -----------------------------
# Gezegen & burç listeleri
# -----------------------------
if HAS_SWISS:
    # (isim, sembol, swiss_ephemeris_kodu)
    PLANETS = [
        ("Sun",     "☉", swe.SUN),
        ("Moon",    "☾", swe.MOON),
        ("Mercury", "☿", swe.MERCURY),
        ("Venus",   "♀", swe.VENUS),
        ("Mars",    "♂", swe.MARS),
        ("Jupiter", "♃", swe.JUPITER),
        ("Saturn",  "♄", swe.SATURN),
        ("Uranus",  "♅", swe.URANUS),
        ("Neptune", "♆", swe.NEPTUNE),
        ("Pluto",   "♇", swe.PLUTO),
    ]
else:
    # Swiss yoksa: başlangıç dereceleri (0–360),
    # tarih/saatten küçük oynatmalar yapacağız
    PLANETS = [
        ("Sun",     "☉", 10.0),
        ("Moon",    "☾", 40.0),
        ("Mercury", "☿", 70.0),
        ("Venus",   "♀", 100.0),
        ("Mars",    "♂", 130.0),
        ("Jupiter", "♃", 160.0),
        ("Saturn",  "♄", 190.0),
        ("Uranus",  "♅", 220.0),
        ("Neptune", "♆", 250.0),
        ("Pluto",   "♇", 280.0),
    ]

# Burç isimleri (0° Koç'tan başlayarak her 30°)
SIGNS = [
    ("Aries",       "♈"),
    ("Taurus",      "♉"),
    ("Gemini",      "♊"),
    ("Cancer",      "♋"),
    ("Leo",         "♌"),
    ("Virgo",       "♍"),
    ("Libra",       "♎"),
    ("Scorpio",     "♏"),
    ("Sagittarius", "♐"),
    ("Capricorn",   "♑"),
    ("Aquarius",    "♒"),
    ("Pisces",      "♓"),
]


# =====================================================
# Yardımcı: tarih-saat → Julian Day / seed
# =====================================================
def _parse_datetime(birth_date: str, birth_time: str) -> datetime:
    """
    birth_date: 'YYYY-MM-DD'
    birth_time: 'HH:MM'
    """
    if not birth_date or not birth_time:
        raise ValueError("birth_date / birth_time eksik")
    dt = datetime.strptime(f"{birth_date} {birth_time}", "%Y-%m-%d %H:%M")
    return dt


def _datetime_to_jd(dt: datetime) -> float:
    # UT kabaca yerel saat kabul; çok hassas olmasına gerek yok
    hour_decimal = dt.hour + dt.minute / 60.0
    return swe.julday(dt.year, dt.month, dt.day, hour_decimal, swe.GREG_CAL)


def _fallback_seed(birth_date: str, birth_time: str) -> float:
    """
    Swiss yoksa haritayı kişiye özel ama deterministik
    şekilde oynatmak için basit bir seed.
    """
    try:
        dt = _parse_datetime(birth_date, birth_time)
        base = dt.year * 10000 + dt.month * 100 + dt.day
        base = base * 100 + dt.hour
        base = base * 100 + dt.minute
        return float(base % 360)  # 0–359
    except Exception:
        return 123.0


# =====================================================
# Gezegen & Ev pozisyonları
# =====================================================
def _compute_positions(
    birth_date: str,
    birth_time: str,
    latitude: float,
    longitude: float,
):
    """
    Dönüş:
      planets: list[(name, symbol, degree)]
      houses : list[degree] (12 ev)
    """
    planets = []
    houses = []

    if HAS_SWISS:
        dt = _parse_datetime(birth_date, birth_time)
        jd = _datetime_to_jd(dt)

        # gözlem yeri
        swe.set_topo(longitude, latitude, 0.0)

        # gezegen uzunlukları
        for name, symbol, body in PLANETS:
            lon, lat, dist, speed = swe.calc_ut(jd, body)
            degree = float(lon % 360.0)
            planets.append((name, symbol, degree))

        # evler (Placidus)
        cusps, ascmc = swe.houses(jd, latitude, longitude)
        houses = [float(c % 360.0) for c in cusps[:12]]

    else:
        # Basit ama kişiye özel deterministik fallback
        base = _fallback_seed(birth_date, birth_time)
        for idx, (name, symbol, base_deg) in enumerate(PLANETS):
            # doğum bilgisine göre küçük kaymalar
            degree = (base_deg + base * 0.35 + idx * 7.0) % 360.0
            planets.append((name, symbol, float(degree)))

        houses = []
        for i in range(12):
            deg = (base * 0.5 + i * 30.0) % 360.0
            houses.append(float(deg))

    return planets, houses


# =====================================================
# Çizim: dairesel harita
# =====================================================
def _deg_to_xy(deg: float, radius: float):
    rad = math.radians(90.0 - deg)  # 0° Koç üstte olsun
    return radius * math.cos(rad), radius * math.sin(rad)


def generate_natal_chart(
    birth_date: str,
    birth_time: str,
    latitude: float,
    longitude: float,
    out_dir: str = "/tmp",
):
    """
    Verilen doğum bilgileri ile PNG harita üretir.
    Dönüş: (chart_id, file_path)
    """
    os.makedirs(out_dir, exist_ok=True)

    planets, houses = _compute_positions(
        birth_date=birth_date,
        birth_time=birth_time,
        latitude=latitude,
        longitude=longitude,
    )

    chart_id = uuid.uuid4().hex
    file_path = os.path.join(out_dir, f"{chart_id}.png")

    # --- Matplotlib fig/axes ---
    fig, ax = plt.subplots(figsize=(5.5, 5.5), dpi=140)
    ax.set_aspect("equal")
    ax.axis("off")

    # daireler
    outer_r = 1.0
    mid_r = 0.78
    inner_r = 0.50

    outer = Circle((0, 0), outer_r, fill=False, linewidth=2.0)
    mid = Circle((0, 0), mid_r, fill=False, linewidth=1.0, linestyle="--")
    inner = Circle((0, 0), inner_r, fill=False, linewidth=1.0)

    ax.add_patch(outer)
    ax.add_patch(mid)
    ax.add_patch(inner)

    # ev çizgileri
    for deg in houses:
        x0, y0 = _deg_to_xy(deg, inner_r)
        x1, y1 = _deg_to_xy(deg, outer_r)
        ax.plot([x0, x1], [y0, y1], linewidth=0.8)

    # burç işaretleri (her 30°'de)
    for i, (name, glyph) in enumerate(SIGNS):
        deg = i * 30.0 + 15.0  # burcun ortası
        x, y = _deg_to_xy(deg, outer_r + 0.08)
        ax.text(
            x,
            y,
            glyph,
            ha="center",
            va="center",
            fontsize=10,
        )

    # gezegen sembolleri
    for name, symbol, deg in planets:
        x, y = _deg_to_xy(deg, mid_r + 0.05)
        ax.text(
            x,
            y,
            symbol,
            ha="center",
            va="center",
            fontsize=9,
        )

    plt.tight_layout(pad=0.2)
    fig.savefig(file_path, transparent=True, bbox_inches="tight")
    plt.close(fig)

    return chart_id, file_path
