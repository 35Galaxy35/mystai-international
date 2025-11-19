import os
import math
import uuid
from datetime import datetime

# Swiss Ephemeris (profesyonel astroloji hesapları)
# -------------------------------------------------
HAS_SWISS = False
try:
    import swisseph as swe  # pyswisseph paketi böyle import edilir
    HAS_SWISS = True
except Exception:
    HAS_SWISS = False

import matplotlib
matplotlib.use("Agg")  # GUI istemez, Render ile uyumlu
import matplotlib.pyplot as plt
from matplotlib.patches import Circle

# Yer koordinatları için (şehir, ülke -> enlem / boylam)
try:
    from geopy.geocoders import Nominatim
    GEOLOCATOR = Nominatim(user_agent="mystai-astrology")
except Exception:
    GEOLOCATOR = None

# =======================
#  Genel sabitler
# =======================

# Gezegen listesi (Swiss Ephemeris sabitleri + semboller + isim)
if HAS_SWISS:
    PLANETS = [
        (swe.SUN,     "☉", "Sun"),
        (swe.MOON,    "☽", "Moon"),
        (swe.MERCURY, "☿", "Mercury"),
        (swe.VENUS,   "♀", "Venus"),
        (swe.MARS,    "♂", "Mars"),
        (swe.JUPITER, "♃", "Jupiter"),
        (swe.SATURN,  "♄", "Saturn"),
        (swe.URANUS,  "♅", "Uranus"),
        (swe.NEPTUNE, "♆", "Neptune"),
        (swe.PLUTO,   "♇", "Pluto"),
    ]
else:
    # Swiss çalışmazsa: sadece görsel amaçlı, eşit aralıklı yerleşim
    PLANETS = [
        ("SUN",     "☉", "Sun"),
        ("MOON",    "☽", "Moon"),
        ("MERCURY", "☿", "Mercury"),
        ("VENUS",   "♀", "Venus"),
        ("MARS",    "♂", "Mars"),
        ("JUPITER", "♃", "Jupiter"),
        ("SATURN",  "♄", "Saturn"),
        ("URANUS",  "♅", "Uranus"),
        ("NEPTUNE", "♆", "Neptune"),
        ("PLUTO",   "♇", "Pluto"),
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

# Aspect tipi: (derece, orb, isim)
ASPECTS = [
    (0,   6, "conjunction"),
    (60,  4, "sextile"),
    (90,  5, "square"),
    (120, 5, "trine"),
    (180, 6, "opposition"),
]


# =======================
#  Yardımcı fonksiyonlar
# =======================

def _parse_datetime(birth_date: str, birth_time: str) -> float:
    """
    Doğum tarih-saatini alır, UT saatine yaklaşık çevirir ve Julian Day döner.
    birth_date: 'YYYY-MM-DD'
    birth_time: 'HH:MM'
    """
    dt = datetime.strptime(f"{birth_date} {birth_time}", "%Y-%m-%d %H:%M")
    # Basit yaklaşım: bulunduğu saati UT kabul ediyoruz (kullanıcı zaten yerel yazıyor).
    hour_decimal = dt.hour + dt.minute / 60.0

    if HAS_SWISS:
        jd = swe.julday(dt.year, dt.month, dt.day, hour_decimal, swe.GREG_CAL)
        return jd
    else:
        # Fallback: sadece saat bazlı basit bir değer, gerçek astrolojik değil
        # ama çizim için yeterli (gezegenler eşit aralıkta dağıtılıyor).
        return hour_decimal


def _geocode_place(place: str):
    """
    Şehir, ülke bilgisini enlem / boylama çevirir.
    Geopy çalışmazsa varsayılan (0,0) döner.
    """
    if not place:
        return 0.0, 0.0

    if GEOLOCATOR is None:
        return 0.0, 0.0

    try:
        loc = GEOLOCATOR.geocode(place, timeout=5)
        if loc:
            return float(loc.latitude), float(loc.longitude)
    except Exception:
        pass
    return 0.0, 0.0


def _compute_positions_natal(birth_date: str, birth_time: str, place: str):
    """
    NATAL için gezegen ve ev pozisyonlarını hesaplar.
    Swiss varsa gerçek hesap, yoksa görsel amaçlı eşit aralıklı dağıtım.
    Dönen:
      planets -> list[dict{name, symbol, lon}]
      houses  -> list[float] 12 ev cuspu (0–360)
    """
    lat, lon = _geocode_place(place)

    if HAS_SWISS:
        jd = _parse_datetime(birth_date, birth_time)

        # Gezegen boylamları
        planets = []
        for p_const, symbol, name in PLANETS:
            lonlat, _ = swe.calc_ut(jd, p_const)  # lon, lat
            pl_long = float(lonlat[0]) % 360.0
            planets.append({
                "name": name,
                "symbol": symbol,
                "lon": pl_long,
            })

        # Evler (Placidus varsayılan)
        cusps, ascmc = swe.houses(jd, lat, lon)
        houses = [float(c) % 360.0 for c in cusps]  # 12 eleman

        return planets, houses

    # ------------ Fallback (Swiss yoksa) ------------
    planets = []
    step = 360.0 / len(PLANETS)
    for idx, (_, symbol, name) in enumerate(PLANETS):
        pl_long = (idx * step) % 360.0
        planets.append({
            "name": name,
            "symbol": symbol,
            "lon": pl_long,
        })

    houses = [(i * 30.0) % 360.0 for i in range(12)]
    return planets, houses


def _compute_positions_solar(birth_date: str, birth_time: str, place: str, year: int):
    """
    SOLAR RETURN için pozisyonlar.
    Basit yaklaşım: aynı gün/ay + verilen yıl, aynı saat.
    Swiss varsa yine gerçek gezegen/ev hesapları.
    """
    # Doğum tarihinden gün/ay al
    dt_birth = datetime.strptime(birth_date, "%Y-%m-%d")
    pseudo_date = f"{year:04d}-{dt_birth.month:02d}-{dt_birth.day:02d}"

    return _compute_positions_natal(pseudo_date, birth_time, place)


def _compute_aspects(planets):
    """
    Gezegenler arası basic aspect hesaplaması.
    Dönen liste: dict{p1, p2, type, angle, diff}
    """
    aspects_found = []
    n = len(planets)
    for i in range(n):
        for j in range(i + 1, n):
            lon1 = planets[i]["lon"]
            lon2 = planets[j]["lon"]
            diff = abs(lon1 - lon2) % 360.0
            if diff > 180.0:
                diff = 360.0 - diff

            for aspect_deg, orb, name in ASPECTS:
                if abs(diff - aspect_deg) <= orb:
                    aspects_found.append({
                        "p1": planets[i],
                        "p2": planets[j],
                        "type": name,
                        "angle": aspect_deg,
                        "diff": diff,
                    })
                    break
    return aspects_found


# =======================
#  ÇİZİM
# =======================

def _draw_chart(planets, houses, aspects, mode: str, chart_id: str) -> str:
    """
    Profesyonel görünümlü haritayı PNG olarak çizer.
    mode: "natal" veya "solar"
    charts/<chart_id>.png dosyasının yolunu döndürür.
    """
    base_dir = os.path.dirname(__file__)
    charts_dir = os.path.join(base_dir, "charts")
    os.makedirs(charts_dir, exist_ok=True)

    fig = plt.figure(figsize=(8, 8), dpi=150)
    ax = fig.add_subplot(111, polar=True)
    ax.set_axis_off()

    # 0 derece Koç'u sol tarafta başlatmak yerine üstte başlatmak için:
    ax.set_theta_zero_location("E")  # 0° sağda
    ax.set_theta_direction(-1)       # saat yönünde artış

    # Ana daireler
    outer_r = 1.0
    inner_r = 0.35
    house_r = 0.9

    # Dış çember
    theta = [math.radians(i) for i in range(0, 361)]
    ax.plot(theta, [outer_r] * len(theta), linewidth=1.2)

    # İç çember (ev iç sınırı)
    ax.plot(theta, [inner_r] * len(theta), linewidth=0.8)

    # 12 burç dilimi çizgileri (her 30°)
    for i in range(12):
        ang = math.radians(i * 30.0)
        ax.plot([ang, ang], [inner_r, outer_r], linewidth=0.8)

    # Burç sembolleri
    for i, (_, sign_symbol) in enumerate(SIGNS):
        angle_deg = i * 30.0 + 15.0  # dilimin ortası
        ang = math.radians(angle_deg)
        r = outer_r + 0.05
        ax.text(ang, r, sign_symbol, fontsize=12, ha="center", va="center")

    # Ev çizgileri
    for cusp in houses:
        ang = math.radians(cusp)
        ax.plot([ang, ang], [inner_r - 0.02, house_r], linewidth=1.0)

    # Ev numaraları
    for i, cusp in enumerate(houses):
        ang = math.radians((cusp + 15.0) % 360.0)
        r = inner_r + 0.02
        ax.text(ang, r, str(i + 1), fontsize=8, ha="center", va="center")

    # Gezegenler
    planet_radius = (inner_r + house_r) / 2.0
    for p in planets:
        ang = math.radians(p["lon"])
        ax.text(ang, planet_radius, p["symbol"], fontsize=13, ha="center", va="center")

    # Aspect çizgileri (iç çemberin içinde)
    aspect_inner_r = inner_r - 0.05
    for asp in aspects:
        lon1 = asp["p1"]["lon"]
        lon2 = asp["p2"]["lon"]
        a1 = math.radians(lon1)
        a2 = math.radians(lon2)

        # Aspect tipine göre renk
        t = asp["type"]
        if t in ("conjunction", "opposition"):
            color = "#ff5555"  # kırmızı ton
        elif t in ("square",):
            color = "#ff8800"  # turuncu
        elif t in ("trine", "sextile"):
            color = "#4a9cff"  # mavi ton
        else:
            color = "#888888"

        ax.plot([a1, a2], [aspect_inner_r, aspect_inner_r], linewidth=0.8, color=color)

    # Başlık
    if mode == "solar":
        title = "Solar Return Chart"
    else:
        title = "Natal Chart"
    fig.suptitle(title, fontsize=14)

    # Kayıt
    file_path = os.path.join(charts_dir, f"{chart_id}.png")
    fig.tight_layout()
    fig.savefig(file_path, bbox_inches="tight", facecolor="white")
    plt.close(fig)

    return file_path


# =======================
#  DIŞA AÇIK FONKSİYONLAR
# =======================

def generate_natal_chart(birth_date: str, birth_time: str, birth_place: str):
    """
    main.py tarafından çağrılır.
    DÖNEN:
      chart_path (str), chart_id (str), planets (list[dict]), houses (list[float])
    """
    planets, houses = _compute_positions_natal(birth_date, birth_time, birth_place)
    aspects = _compute_aspects(planets)

    chart_id = str(uuid.uuid4())
    chart_path = _draw_chart(planets, houses, aspects, mode="natal", chart_id=chart_id)

    return chart_path, chart_id, planets, houses


def generate_solar_return_chart(birth_date: str, birth_time: str, birth_place: str, year: int):
    """
    Solar return için aynı imza:
      chart_path, chart_id, planets, houses
    """
    planets, houses = _compute_positions_solar(birth_date, birth_time, birth_place, year)
    aspects = _compute_aspects(planets)

    chart_id = str(uuid.uuid4())
    chart_path = _draw_chart(planets, houses, aspects, mode="solar", chart_id=chart_id)

    return chart_path, chart_id, planets, houses


def get_chart_path(chart_id: str) -> str | None:
    """
    /chart/<chart_id> endpoint'i için dosya yolunu verir.
    Dosya yoksa None.
    """
    base_dir = os.path.dirname(__file__)
    charts_dir = os.path.join(base_dir, "charts")
    path = os.path.join(charts_dir, f"{chart_id}.png")
    if os.path.exists(path):
        return path
    return None
