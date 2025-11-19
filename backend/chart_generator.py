import os
import math
import uuid
from datetime import datetime

# ----------------------------------------
# Swiss Ephemeris (gerçek astroloji hesapları)
# ----------------------------------------
HAS_SWISS = True
try:
    import swisseph as swe
except Exception:
    HAS_SWISS = False

# ----------------------------------------
# Matplotlib (Render için headless)
# ----------------------------------------
import matplotlib
matplotlib.use("Agg")  # GUI istemez, sunucu için güvenli
import matplotlib.pyplot as plt
from matplotlib.patches import Circle

# ----------------------------------------
# Gezegen, burç ve açı tanımları
# ----------------------------------------

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
    # Swiss yoksa sadece görsel için sabit daireye diz
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

# Açı türleri: (isim, derece, orb, renk)
ASPECTS = [
    ("Conjunction", 0,   8, "#ffffff"),
    ("Opposition",  180, 8, "#ff5555"),
    ("Square",      90,  7, "#ff5555"),
    ("Trine",       120, 7, "#4ea5ff"),
    ("Sextile",     60,  5, "#4ea5ff"),
    ("Quincunx",    150, 3, "#b17bff"),
    ("Semisquare",  45,  3, "#b17bff"),
    ("Sesquisq",    135, 3, "#b17bff"),
]


# =========================================================
# Yardımcı fonksiyonlar
# =========================================================

def _parse_datetime(birth_date: str, birth_time: str) -> float:
    """
    'YYYY-MM-DD' + 'HH:MM' formatından Julian Day (UT) üretir.
    Zaman dilimini bilmediğimiz için kabaca yerel zamanı UT kabul ediyoruz.
    Ticari / eğlence amaçlı yorum için fazlasıyla yeterli.
    """
    dt = datetime.strptime(f"{birth_date} {birth_time}", "%Y-%m-%d %H:%M")
    hour_decimal = dt.hour + dt.minute / 60.0
    if HAS_SWISS:
        jd = swe.julday(dt.year, dt.month, dt.day, hour_decimal, swe.GREG_CAL)
    else:
        # fallback – gerçek astronomi yok, sadece derece dağıtmak için
        jd = dt.toordinal() + hour_decimal / 24.0
    return jd


def _normalize_deg(x: float) -> float:
    return x % 360.0


def _angular_distance(a: float, b: float) -> float:
    """İki derece arasındaki en küçük fark (0–180)."""
    diff = abs(a - b) % 360.0
    return diff if diff <= 180.0 else 360.0 - diff


def _compute_positions(birth_date: str, birth_time: str,
                       latitude: float, longitude: float):
    """
    Gezegen boylamları (0–360) ve 12 ev cusp derecesi döner.
    """
    jd = _parse_datetime(birth_date, birth_time)

    planet_longitudes = []
    houses = []

    if HAS_SWISS:
        # Toposentrik hesap (yaklaşık) – doğum yeri bilgisi kullanılıyor
        swe.set_topo(longitude, latitude, 0)

        # Gezegenler
        for name, symbol, pid in PLANETS:
            lon, lat, dist, speed_lon = swe.calc_ut(jd, pid)
            planet_longitudes.append(_normalize_deg(lon))

        # Evler (Placidus)
        cusps, ascmc = swe.houses(jd, latitude, longitude, b"P")  # Placidus
        # cusps: 1–12 arasını al
        houses = [_normalize_deg(c) for c in cusps[1:13]]

    else:
        # Swiss yoksa: sadece görsel için daireye diz
        n = len(PLANETS)
        for i in range(n):
            planet_longitudes.append((360.0 / n) * i)
        houses = [(360.0 / 12) * i for i in range(12)]

    return planet_longitudes, houses


def _detect_aspects(planet_longitudes):
    """
    Gezegen çiftleri arasındaki açıları bulur.
    Dönen liste: (idx1, idx2, aspect_def)
    """
    aspects_found = []
    n = len(planet_longitudes)

    for i in range(n):
        for j in range(i + 1, n):
            a1 = planet_longitudes[i]
            a2 = planet_longitudes[j]
            diff = _angular_distance(a1, a2)

            for asp in ASPECTS:
                name, exact, orb, color = asp
                if abs(diff - exact) <= orb:
                    aspects_found.append((i, j, asp))
                    break

    return aspects_found


# =========================================================
# ÇİZİM
# =========================================================

def _angle_to_xy(angle_deg: float, radius: float):
    """
    0° = Koç başlangıcı = sol yatay, saat yönünün tersine artan derece.
    (astro.com benzeri yönelim)
    """
    # 0° Aries = 9 o'clock -> 180°
    theta = math.radians(180.0 - angle_deg)
    x = radius * math.cos(theta)
    y = radius * math.sin(theta)
    return x, y


def _draw_chart(planet_longitudes, houses, chart_id, out_dir):
    """
    Profesyonel görünümde dairesel harita çizer ve PNG kaydeder.
    """
    fig = plt.figure(figsize=(8, 8), facecolor="#f7f0dc")
    ax = plt.axes([0.04, 0.04, 0.92, 0.92])
    ax.set_facecolor("#f7f0dc")
    ax.set_aspect("equal")
    ax.axis("off")

    # Yarıçaplar
    R_OUTER = 1.0
    R_SIGNS = 0.95
    R_HOUSES = 0.78
    R_PLANETS = 0.83
    R_ASPECT_INNER = 0.15
    R_ASPECT_OUTER = 0.70

    # Dış daire
    outer_circle = Circle((0, 0), R_OUTER, transform=ax.transData,
                          fill=False, lw=2.0, edgecolor="#c9bfa4")
    ax.add_patch(outer_circle)

    # İç daire (ev alanı)
    inner_circle = Circle((0, 0), R_HOUSES, transform=ax.transData,
                          fill=False, lw=1.2, edgecolor="#c9bfa4")
    ax.add_patch(inner_circle)

    # En iç daire (aspect alanı)
    core_circle = Circle((0, 0), R_ASPECT_INNER, transform=ax.transData,
                         fill=False, lw=0.8, edgecolor="#d9cfb4")
    ax.add_patch(core_circle)

    # --- Burç dilimleri (her 30°) ---
    for i in range(12):
        start_deg = i * 30.0
        # sınır çizgisi
        x0, y0 = _angle_to_xy(start_deg, R_OUTER)
        x1, y1 = _angle_to_xy(start_deg, R_HOUSES)
        ax.plot([x0, x1], [y0, y1], color="#d0c6aa", lw=1.0)

        # burç sembolü
        sign_name, sign_sym = SIGNS[i]
        mid_deg = start_deg + 15.0
        sx, sy = _angle_to_xy(mid_deg, (R_OUTER + R_HOUSES) / 2.0 + 0.02)
        ax.text(
            sx,
            sy,
            sign_sym,
            ha="center",
            va="center",
            fontsize=18,
            color="#6b5b33",
            fontweight="bold",
        )

    # --- Ev çizgileri (Placidus cusps) ---
    if houses:
        for h_deg in houses:
            x0, y0 = _angle_to_xy(h_deg, R_HOUSES)
            x1, y1 = _angle_to_xy(h_deg, R_ASPECT_INNER)
            ax.plot([x0, x1], [y0, y1], color="#998f78", lw=1.3)

    # --- Gezegenler ---
    planet_positions_xy = []
    for idx, (lon, (name, symbol, pid)) in enumerate(zip(planet_longitudes, PLANETS)):
        angle = lon
        px, py = _angle_to_xy(angle, R_PLANETS)

        planet_positions_xy.append((px, py))

        ax.text(
            px,
            py,
            symbol,
            ha="center",
            va="center",
            fontsize=16,
            color="#222222",
            fontweight="bold",
        )

    # --- Açılar (çizgiler) ---
    aspects = _detect_aspects(planet_longitudes)
    for i, j, asp in aspects:
        name, exact, orb, color = asp
        (x1, y1) = _angle_to_xy(planet_longitudes[i], R_ASPECT_OUTER)
        (x2, y2) = _angle_to_xy(planet_longitudes[j], R_ASPECT_OUTER)

        # çizgiyi biraz içerden başlat
        k1 = R_ASPECT_INNER / R_ASPECT_OUTER
        k2 = 1.0
        ax.plot(
            [x1 * k1, x2 * k2],
            [y1 * k1, y2 * k2],
            color=color,
            lw=1.0,
            alpha=0.8,
        )

    # Hafif gölge efekti
    shadow_circle = Circle(
        (0, 0),
        R_OUTER,
        transform=ax.transData,
        fill=False,
        lw=12,
        edgecolor="black",
        alpha=0.05,
    )
    ax.add_patch(shadow_circle)

    # -------------------------
    # KAYDET
    # -------------------------
    os.makedirs(out_dir, exist_ok=True)
    file_path = os.path.join(out_dir, f"{chart_id}.png")
    fig.savefig(
        file_path,
        dpi=220,
        facecolor=fig.get_facecolor(),
        edgecolor="none",
        bbox_inches="tight",
        pad_inches=0.25,
    )
    plt.close(fig)
    return file_path


# =========================================================
# DIŞA AÇIK FONKSİYON
# =========================================================

def generate_natal_chart(
    birth_date: str,
    birth_time: str,
    latitude: float,
    longitude: float,
    out_dir: str = "/tmp",
):
    """
    main.py içinden çağrılan tek fonksiyon.

    Dönüş:
        (chart_id, chart_file_path)

    - chart_id: UUID (frontend /chart/<id> şeklinde kullanıyor)
    - chart_file_path: /tmp/.../png
    """
    chart_id = uuid.uuid4().hex

    try:
        planet_longitudes, houses = _compute_positions(
            birth_date, birth_time, latitude, longitude
        )
        file_path = _draw_chart(planet_longitudes, houses, chart_id, out_dir)
        return chart_id, file_path
    except Exception as e:
        # Hata olursa log için yaz, ama uygulama çökmesin
        print("Natal chart generation error:", repr(e))
        # Boş bir PNG üret (uygulama bozulmasın)
        os.makedirs(out_dir, exist_ok=True)
        file_path = os.path.join(out_dir, f"{chart_id}.png")
        fig = plt.figure(figsize=(6, 6), facecolor="#111111")
        plt.text(
            0.5,
            0.5,
            "Chart error",
            ha="center",
            va="center",
            color="white",
        )
        plt.axis("off")
        fig.savefig(file_path, dpi=150, bbox_inches="tight", pad_inches=0.1)
        plt.close(fig)
        return chart_id, file_path
