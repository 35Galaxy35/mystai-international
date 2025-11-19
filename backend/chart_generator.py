import os
import math
import uuid
from datetime import datetime

# -----------------------------------------
# Swiss Ephemeris (profesyonel astroloji)
# -----------------------------------------
try:
    import swisseph as swe
    HAS_SWISS = True
except Exception as e:
    print("Swiss Ephemeris bulunamadı, fallback mod:", e)
    HAS_SWISS = False

# -----------------------------------------
# Matplotlib (Render için headless)
# -----------------------------------------
import matplotlib
matplotlib.use("Agg")  # GUI istemez, Render için uygun
import matplotlib.pyplot as plt
from matplotlib.patches import Circle

# -----------------------------------------
# Gezegen & burç listeleri
# -----------------------------------------

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
    # Swiss yoksa, tamamen basit, görsel amaçlı bir fallback.
    # (Her biri farklı dereceye yerleşsin diye)
    PLANETS = [
        ("Sun",     "☉",   10),
        ("Moon",    "☽",   40),
        ("Mercury", "☿",   70),
        ("Venus",   "♀",  100),
        ("Mars",    "♂",  130),
        ("Jupiter", "♃",  160),
        ("Saturn",  "♄",  190),
        ("Uranus",  "♅",  220),
        ("Neptune", "♆",  250),
        ("Pluto",   "♇",  280),
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


# -----------------------------------------
# Yardımcı: tarih-saat → Julian Day
# -----------------------------------------
def _parse_datetime(birth_date: str, birth_time: str) -> float:
    """
    birth_date: 'YYYY-MM-DD'
    birth_time: 'HH:MM'
    Swiss varsa gerçek Julian Day, yoksa sadece saat hesaplanır.
    """
    dt = datetime.strptime(f"{birth_date} {birth_time}", "%Y-%m-%d %H:%M")
    # Not: Zaman dilimi bilgisini bilmiyoruz, yaklaşık olarak UT gibi alıyoruz.
    hour_decimal = dt.hour + dt.minute / 60.0

    if HAS_SWISS:
        jd = swe.julday(dt.year, dt.month, dt.day, hour_decimal, swe.GREG_CAL)
        return jd
    else:
        # fallback için sadece derece hesaplamakta kullanacağız
        # (gerçek JD gerekmez)
        return hour_decimal


# -----------------------------------------
# Yardımcı: gezegen & ev pozisyonları
# -----------------------------------------
def _compute_positions(birth_date: str, birth_time: str,
                       latitude: float, longitude: float):
    """
    Swiss varsa:
      - gezegen boylamları (0–360°)
      - 12 ev (Placidus) cusp dereceleri
    Swiss yoksa:
      - gezegenler sabit örnek dereceler
      - evler 30° aralıklarla
    """
    jd = _parse_datetime(birth_date, birth_time)

    planets_longitudes = []
    houses = []

    if HAS_SWISS:
        flags = swe.FLG_SWIEPH | swe.FLG_SPEED
        # Gezegenler
        for name, glyph, pid in PLANETS:
            lon, lat, dist, speed_lon = swe.calc_ut(jd, pid, flags)[:4]
            planets_longitudes.append((name, glyph, lon % 360.0))

        # Evler (Placidus varsayılan)
        cusps, ascmc = swe.houses(jd, latitude, longitude)
        # cusps: 1..12 indeksli gelir
        houses = [(i, cusps[i - 1] % 360.0) for i in range(1, 13)]

    else:
        # Fallback: evler 30° aralıkla, gezegenler PLANETS listesindeki derece ile
        for name, glyph, deg in PLANETS:
            planets_longitudes.append((name, glyph, float(deg) % 360.0))
        for i in range(12):
            houses.append((i + 1, (i * 30.0) % 360.0))

    return planets_longitudes, houses


# -----------------------------------------
# Çizim yardımcıları
# -----------------------------------------
def _deg_to_xy(angle_deg: float, radius: float):
    """
    0°'yi tepe noktası kabul ediyoruz; saat yönünün tersine.
    Matplotlib için x,y (kartesyen) koordinat döner.
    """
    # astrolojide genelde çember soldan (AC) başlar ama burada
    # görsel için 0° tepeyi kullanıyoruz.
    rad = math.radians(90.0 - angle_deg)
    x = radius * math.cos(rad)
    y = radius * math.sin(rad)
    return x, y


# -----------------------------------------
# ANA FONKSİYON:
#   gerçek harita PNG üretir ve yolunu döner
# -----------------------------------------
def generate_natal_chart(
    birth_date: str,
    birth_time: str,
    latitude: float,
    longitude: float,
    out_dir: str = "/tmp",
):
    """
    birth_date: 'YYYY-MM-DD'
    birth_time: 'HH:MM'
    latitude, longitude: ondalık derece
    out_dir: PNG'nin kaydedileceği klasör

    Dönüş:
      (chart_id, chart_file_path)
    """
    os.makedirs(out_dir, exist_ok=True)

    planets, houses = _compute_positions(birth_date, birth_time, latitude, longitude)

    chart_id = uuid.uuid4().hex
    chart_file = os.path.join(out_dir, f"{chart_id}.png")

    # ---- FIGURE / AX ----
    fig, ax = plt.subplots(figsize=(6, 6), dpi=220)
    ax.set_aspect("equal")
    ax.axis("off")

    # Arka plan
    fig.patch.set_facecolor("#050818")
    ax.set_facecolor("#050818")

    # Çember yarıçapları
    outer_r = 1.0
    inner_r = 0.6
    center_r = 0.25

    # Dış çember (zodyak)
    outer_circle = Circle((0, 0), outer_r, fill=False, linewidth=2.0, edgecolor="#d9e2ff")
    ax.add_patch(outer_circle)

    # Ev çemberi
    inner_circle = Circle((0, 0), inner_r, fill=False, linewidth=1.3, edgecolor="#8fa2ff")
    ax.add_patch(inner_circle)

    # Merkez (gölge)
    core = Circle((0, 0), center_r, fill=True, linewidth=0, facecolor="#040615")
    ax.add_patch(core)

    # ---- Ev çizgileri ----
    for house_num, cusp_deg in houses:
        x1, y1 = _deg_to_xy(cusp_deg, center_r)
        x2, y2 = _deg_to_xy(cusp_deg, outer_r)
        ax.plot([x1, x2], [y1, y2], color="#505a86", linewidth=0.7)

    # ---- Burç sınırları ve semboller ----
    for i, (sign_name, sign_glyph) in enumerate(SIGNS):
        start_deg = i * 30.0
        # Burç çizgisi
        x1, y1 = _deg_to_xy(start_deg, inner_r)
        x2, y2 = _deg_to_xy(start_deg, outer_r)
        ax.plot([x1, x2], [y1, y2], color="#313b70", linewidth=0.8)

        # Burç sembolü
        mid_deg = start_deg + 15.0
        sx, sy = _deg_to_xy(mid_deg, (outer_r + 1.05) / 2)
        ax.text(
            sx, sy, sign_glyph,
            ha="center", va="center",
            fontsize=14, color="#f0f2ff",
        )

    # ---- Gezegenler ----
    planet_r = (inner_r + outer_r) / 2.0
    for name, glyph, lon in planets:
        px, py = _deg_to_xy(lon, planet_r)
        ax.scatter([px], [py], s=12, color="#ffd54f", zorder=5)
        # sembolü hafif dışa yaz
        tx, ty = _deg_to_xy(lon, planet_r + 0.06)
        ax.text(
            tx, ty, glyph,
            ha="center", va="center",
            fontsize=13, color="#ffeaa0",
            zorder=6,
        )

    # Küçük not: Swiss yoksa uyarı yaz
    if not HAS_SWISS:
        ax.text(
            0, -1.15,
            "Approximate demo chart (Swiss Ephemeris not installed)",
            ha="center", va="center",
            fontsize=6,
            color="#ff9a9a",
        )

    # Kaydet
    plt.tight_layout(pad=0.3)
    fig.savefig(chart_file, dpi=220, facecolor=fig.get_facecolor(), transparent=False)
    plt.close(fig)

    return chart_id, chart_file
