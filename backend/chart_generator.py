import os
import math
import uuid
from datetime import datetime

# Swiss Ephemeris (yüksek hassasiyetli astroloji hesapları)
try:
    import swisseph as swe
    HAS_SWISS = True
except Exception:
    HAS_SWISS = False

import matplotlib
matplotlib.use("Agg")  # Render / sunucu için GUI'siz backend
import matplotlib.pyplot as plt
import numpy as np

# ---------- Gezegen & burç listeleri ----------

if HAS_SWISS:
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
else:
    # Swiss yoksa sadece görsel amaçlı eşit aralıklı yerleşim
    PLANETS = [
        ("Sun",     "☉", 0),
        ("Moon",    "☽", 0),
        ("Mercury", "☿", 0),
        ("Venus",   "♀", 0),
        ("Mars",    "♂", 0),
        ("Jupiter", "♃", 0),
        ("Saturn",  "♄", 0),
        ("Uranus",  "♅", 0),
        ("Neptune", "♆", 0),
        ("Pluto",   "♇", 0),
    ]

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


# ---------- Yardımcı: tarih → Julian Day ----------

def _parse_datetime(birth_date: str, birth_time: str) -> float:
    """
    birth_date: 'YYYY-MM-DD'
    birth_time: 'HH:MM'
    """
    dt = datetime.strptime(f"{birth_date} {birth_time}", "%Y-%m-%d %H:%M")
    hour_decimal = dt.hour + dt.minute / 60.0

    if HAS_SWISS:
        jd = swe.julday(dt.year, dt.month, dt.day, hour_decimal, swe.GREG_CAL)
    else:
        # Basit Julian Day yaklaşık hesap (fallback)
        jd = (dt.toordinal() - 1721424.5) + hour_decimal / 24.0
    return jd


# ---------- Yardımcı: gezegen & ev pozisyonları ----------

def _compute_positions(
    birth_date: str,
    birth_time: str,
    latitude: float,
    longitude: float
):
    """
    Swiss varsa:
      - gezegen boylamları (0–360°)
      - 12 ev (Placidus) cusp dereceleri
    Swiss yoksa:
      - gezegenleri ve evleri eşit aralıklı yerleştirir (sadece görsel).
    """
    jd = _parse_datetime(birth_date, birth_time)

    planet_longitudes: list[float] = []
    house_cusps: list[float] = []

    if HAS_SWISS:
        # Gezegenler
        flags = swe.FLG_SWIEPH | swe.FLG_SPEED
        for name, glyph, pid in PLANETS:
            lon, lat, dist, speed = swe.calc_ut(jd, pid, flags)
            planet_longitudes.append(lon % 360.0)

        # Evler (Placidus)
        cusps, ascmc = swe.houses(jd, latitude, longitude)
        house_cusps = list(cusps)[:12]   # 12 ev
    else:
        # Fallback: hepsini eşit aralıklı dağıt
        n = len(PLANETS)
        for i in range(n):
            planet_longitudes.append((360.0 / n) * i)
        house_cusps = [(360.0 / 12) * i for i in range(12)]

    return planet_longitudes, house_cusps


# ---------- Çizim ----------

def _draw_wheel(planet_longitudes, house_cusps, out_path: str):
    """
    Astro.com tarzında:
      - dış burç halkası
      - iç ev halkası
      - iç dairede aspect çizgileri
    """
    fig, ax = plt.subplots(figsize=(6, 6), subplot_kw={"projection": "polar"})
    fig.patch.set_facecolor("#f9f4e5")      # açık bej arka plan (Tema 1)
    ax.set_facecolor("#f9f4e5")
    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_ylim(0, 1)

    def deg_to_rad(lon: float) -> float:
        # 0° Koç'ı solda değil, üstte başlatmak için 90 - lon
        return math.radians(90 - lon)

    # Yarıçaplar
    outer_zodiac = 0.98
    inner_zodiac = 0.78
    outer_houses = 0.76
    inner_houses = 0.56
    aspect_r = 0.40

    # Daire çizmek için tam açı
    theta_full = np.linspace(0, 2 * math.pi, 720)

    # Ana halkalar
    for r, lw in [
        (outer_zodiac, 1.6),
        (inner_zodiac, 1.0),
        (outer_houses, 1.2),
        (inner_houses, 1.0),
        (aspect_r, 0.8),
    ]:
        ax.plot(theta_full, [r] * len(theta_full),
                color="#555555", linewidth=lw, alpha=0.85)

    # ---------- Burç çizgileri & semboller ----------
    for i, (_, glyph) in enumerate(SIGNS):
        start_lon = i * 30.0
        mid_lon = start_lon + 15.0

        theta_mid = deg_to_rad(mid_lon)
        ax.text(
            theta_mid,
            outer_zodiac - 0.03,
            glyph,
            fontsize=13,
            ha="center",
            va="center",
            color="#333333",
        )

        # Burç sınırı çizgisi
        theta_bound = deg_to_rad(start_lon)
        ax.plot(
            [theta_bound, theta_bound],
            [inner_zodiac, outer_zodiac],
            color="#aaaaaa",
            linewidth=0.6,
        )

    # ---------- Ev çizgileri ----------
    for cusp in house_cusps:
        theta = deg_to_rad(cusp)
        ax.plot(
            [theta, theta],
            [inner_houses, outer_houses],
            color="#444444",
            linewidth=0.9,
        )

    # ---------- Gezegen sembolleri ----------
    planet_positions = []
    planet_ring_r = (inner_houses + aspect_r) / 2.0

    for (name, glyph, _), lon in zip(PLANETS, planet_longitudes):
        theta = deg_to_rad(lon)

        # Nokta
        ax.scatter(theta, planet_ring_r, s=22, color="#000000", zorder=5)

        # Sembol
        ax.text(
            theta,
            planet_ring_r + 0.035,
            glyph,
            fontsize=11,
            ha="center",
            va="center",
            color="#111111",
        )

        planet_positions.append((name, lon, theta))

    # ---------- Aspect çizgileri ----------
    major_aspects = [0, 60, 90, 120, 150, 180]
    colors = {
        0:   "#333333",  # kavuşum
        60:  "#008000",  # sextile
        90:  "#cc0000",  # kare
        120: "#0055cc",  # üçgen
        150: "#800080",  # quincunx
        180: "#cc0000",  # karşıt
    }
    orb = 6.0  # ±6° tolerans

    for i in range(len(planet_positions)):
        name1, lon1, theta1 = planet_positions[i]
        for j in range(i + 1, len(planet_positions)):
            name2, lon2, theta2 = planet_positions[j]

            diff = abs(lon1 - lon2)
            diff = min(diff, 360 - diff)

            matched = None
            for asp in major_aspects:
                if abs(diff - asp) <= orb:
                    matched = asp
                    break
            if matched is None:
                continue

            color = colors.get(matched, "#999999")

            ax.plot(
                [theta1, theta2],
                [aspect_r, aspect_r],
                color=color,
                linewidth=0.7,
                alpha=0.85,
            )

    fig.savefig(out_path, dpi=170, bbox_inches="tight")
    plt.close(fig)


# ---------- Dışa açılan fonksiyon (main.py bunu kullanıyor) ----------

def generate_natal_chart(
    birth_date: str,
    birth_time: str,
    latitude: float,
    longitude: float,
    out_dir: str,
):
    """
    main.py hem natal hem de solar return için
    bu fonksiyonu çağırıyor. Solar endpoint sadece
    farklı bir tarih gönderiyor.
    """
    os.makedirs(out_dir, exist_ok=True)

    planet_longitudes, house_cusps = _compute_positions(
        birth_date=birth_date,
        birth_time=birth_time,
        latitude=latitude,
        longitude=longitude,
    )

    chart_id = uuid.uuid4().hex
    out_path = os.path.join(out_dir, f"{chart_id}.png")

    _draw_wheel(planet_longitudes, house_cusps, out_path)

    return chart_id, out_path
