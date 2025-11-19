# backend/chart_generator.py
# --------------------------------------
# MystAI - Profesyonel astroloji harita üretici
# --------------------------------------
# - Swiss Ephemeris varsa: gerçek gezegen & ev pozisyonları
# - Yoksa: fallback hesaplama (tarih/saatten deterministik açı hesapları)
# - Matplotlib "Agg" backend ile Render / server uyumlu
# - Ana fonksiyon: generate_natal_chart(...)
# --------------------------------------

import os
import math
import uuid
from datetime import datetime

# -------------------------------
# Swiss Ephemeris (pyswisseph)
# -------------------------------
HAS_SWISS = False
try:
    import swisseph as swe  # pyswisseph paketi
    HAS_SWISS = True
except Exception:
    HAS_SWISS = False

# -------------------------------
# Matplotlib - headless
# -------------------------------
import matplotlib
matplotlib.use("Agg")  # GUI gerekmez
import matplotlib.pyplot as plt
from matplotlib.patches import Circle


# -------------------------------
# Sabitler: gezegenler & burçlar
# -------------------------------

if HAS_SWISS:
    # (isim, sembol, Swiss Ephemeris kodu)
    PLANETS_SWISS = [
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
else:
    PLANETS_SWISS = []  # kullanılmayacak

# Swiss yoksa kullanılacak basit, görsel amaçlı fallback listesi
PLANETS_FALLBACK = [
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

# 12 burç (sadece semboller, isimler görsel için)
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


# -------------------------------
# Yardımcı: tarih + saat → datetime
# -------------------------------

def _parse_datetime(birth_date: str, birth_time: str) -> datetime:
    """
    birth_date: 'YYYY-MM-DD'
    birth_time: 'HH:MM'
    """
    return datetime.strptime(f"{birth_date} {birth_time}", "%Y-%m-%d %H:%M")


# -------------------------------
# Gezegen & ev pozisyonları
# -------------------------------

def _compute_positions(birth_date: str,
                       birth_time: str,
                       latitude: float,
                       longitude: float):
    """
    Döndürür:
      planets: [(name, glyph, longitude_deg), ...]
      houses:  [deg1, deg2, ..., deg12]
    """
    dt = _parse_datetime(birth_date, birth_time)

    # --- Swiss Ephemeris ile gerçek hesap (mümkünse) ---
    if HAS_SWISS:
        try:
            # Julian Day
            hour_decimal = dt.hour + dt.minute / 60.0
            jd = swe.julday(dt.year, dt.month, dt.day, hour_decimal, swe.GREG_CAL)

            # Evler (Placidus)
            # swe.houses(jd, lat, lon, b"P") → (houses[1..12], ascmc)
            houses, ascmc = swe.houses(jd, latitude, longitude, b"P")
            house_cusps = list(houses[:12])

            # Gezegen boylamları
            planets = []
            for name, glyph, pid in PLANETS_SWISS:
                lon, lat_, dist, speed = swe.calc_ut(jd, pid)
                lon = lon % 360.0
                planets.append((name, glyph, lon))

            return planets, house_cusps

        except Exception as e:
            # Swiss kuruluyken bile ephemeris dosyası yoksa veya başka hata alırsak
            # fallback'e geçeceğiz.
            print("Swiss eph error, using fallback:", e)

    # --- Fallback: deterministik, basit hesap ---
    base = (dt.toordinal() * 17 + dt.hour * 13 + dt.minute * 7) % 360.0

    planets = []
    step = 360.0 / len(PLANETS_FALLBACK)  # 10 gezegen → 36° aralık
    for idx, (name, glyph) in enumerate(PLANETS_FALLBACK):
        lon = (base + idx * step) % 360.0
        planets.append((name, glyph, lon))

    # Evler: her 30 derece (12 eşit dilim)
    house_cusps = [(i * 30.0) % 360.0 for i in range(12)]

    return planets, house_cusps


# -------------------------------
# Çizim
# -------------------------------

def _draw_chart(planets, houses, out_path: str):
    """
    Basit ama modern, profesyonel görünümlü bir astroloji çemberi çizer.
    planets: [(name, glyph, lon_deg)]
    houses: [deg1..deg12]
    """
    fig, ax = plt.subplots(
        figsize=(6, 6),
        subplot_kw={"projection": "polar"},
    )

    # Arka plan
    fig.patch.set_facecolor("#050818")
    ax.set_facecolor("#050818")

    # Eksenleri kapat
    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_ylim(0, 1.05)

    # Dış çember
    outer = Circle((0, 0), 1.0,
                   transform=ax.transData._b,
                   fill=False,
                   edgecolor=(1, 1, 1, 0.8),
                   linewidth=1.4)
    ax.add_artist(outer)

    # İç çember (harita gövdesi)
    inner = Circle((0, 0), 0.25,
                   transform=ax.transData._b,
                   fill=False,
                   edgecolor=(1, 1, 1, 0.18),
                   linewidth=0.8)
    ax.add_artist(inner)

    # Ev çizgileri
    for deg in houses:
        rad = math.radians(deg)
        ax.plot([rad, rad], [0.25, 1.0],
                linewidth=0.6,
                color=(1, 1, 1, 0.16))

    # Burç sınırları (her 30°)
    for i, (sign_name, sign_glyph) in enumerate(SIGNS):
        start_deg = i * 30.0
        mid_deg = start_deg + 15.0

        # sınır çizgisi (daha silik)
        rad_border = math.radians(start_deg)
        ax.plot([rad_border, rad_border], [0.25, 1.0],
                linewidth=0.4,
                color=(1, 1, 1, 0.08))

        # burç sembolü
        rad_mid = math.radians(mid_deg)
        ax.text(
            rad_mid,
            1.02,
            sign_glyph,
            ha="center",
            va="center",
            fontsize=11,
            color=(1, 1, 1, 0.9),
        )

    # Gezegenler
    # Basit bir renk paleti (aynı uzunlukta dönüp dolaşacak)
    colors = [
        "#ffd54f", "#ff8a65", "#4dd0e1", "#ba68c8", "#81c784",
        "#ffb74d", "#9575cd", "#4db6ac", "#e57373", "#fff176",
    ]

    for idx, (name, glyph, lon) in enumerate(planets):
        rad = math.radians(lon)
        r = 0.62  # gezegenlerin yarıçapı

        c = colors[idx % len(colors)]

        # Nokta
        ax.scatter([rad], [r],
                   s=22,
                   color=c,
                   edgecolor=(0, 0, 0, 0.7),
                   linewidth=0.6,
                   zorder=5)

        # Sembol
        ax.text(
            rad,
            r + 0.06,
            glyph,
            ha="center",
            va="center",
            fontsize=13,
            color=c,
            zorder=6,
        )

    fig.tight_layout(pad=0.2)
    fig.savefig(out_path, dpi=160, facecolor="#050818")
    plt.close(fig)


# -------------------------------
# Dışarı açtığımız ana fonksiyon
# -------------------------------

def generate_natal_chart(
    birth_date: str,
    birth_time: str,
    latitude: float,
    longitude: float,
    out_dir: str = "/tmp",
):
    """
    main.py içinde kullanılan ana fonksiyon.

    Dönüş:
      chart_id (str), file_path (str)
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

    _draw_chart(planets, houses, file_path)

    return chart_id, file_path
