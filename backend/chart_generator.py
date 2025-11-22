# chart_generator.py
# ===================
# MystAI - Profesyonel Astroloji Harita Üreticisi
#
# - Swiss Ephemeris (pyswisseph) varsa gerçek efemeris hesabı
# - Placidus ev sistemi
# - Natal & Solar return için ayrı haritalar
# - Aspect çizgileri (konj., kare, üçgen, karşıt, sekstil)
# - Render (headless) uyumlu matplotlib çıktısı (PNG)
#
# main.py bu modülden sadece:
#   from chart_generator import generate_natal_chart
#   chart_id, chart_file_path = generate_natal_chart(...)
# çağrısını yapıyor.

import os
import math
import uuid
from datetime import datetime, timezone

# ------------------------------
# Tarihsel timezone desteği
# ------------------------------
try:
    # Python 3.9+ standart kütüphane
    from zoneinfo import ZoneInfo

    HAS_TZINFO = True
except Exception:
    HAS_TZINFO = False

# -----------------------------------------
# Swiss Ephemeris (pyswisseph) opsiyonel
# -----------------------------------------
HAS_SWISS = False
try:
    import swisseph as swe  # pyswisseph paket adı

    HAS_SWISS = True
except Exception:
    HAS_SWISS = False

# -----------------------------------------
# Matplotlib - headless (Render uyumlu)
# -----------------------------------------
import matplotlib

matplotlib.use("Agg")  # GUI gerekmez
import matplotlib.pyplot as plt
from matplotlib.patches import Circle

# -----------------------------------------
# Gezegen & burç listeleri
# -----------------------------------------

if HAS_SWISS:
    # (İsim, Sembol, swe sabiti, çizim rengi)
    PLANETS = [
        ("Sun", "☉", swe.SUN, "#ffcc33"),
        ("Moon", "☽", swe.MOON, "#ffffff"),
        ("Mercury", "☿", swe.MERCURY, "#f5f5f5"),
        ("Venus", "♀", swe.VENUS, "#ff99cc"),
        ("Mars", "♂", swe.MARS, "#ff6666"),
        ("Jupiter", "♃", swe.JUPITER, "#ffd280"),
        ("Saturn", "♄", swe.SATURN, "#cccccc"),
        ("Uranus", "♅", swe.URANUS, "#66e0ff"),
        ("Neptune", "♆", swe.NEPTUNE, "#66b3ff"),
        ("Pluto", "♇", swe.PLUTO, "#ff99ff"),
    ]
else:
    # Eğer Swiss yoksa tamamen görsel amaçlı, yaklaşık yerleşim
    PLANETS = [
        ("Sun", "☉", 0.0, "#ffcc33"),
        ("Moon", "☽", 33.0, "#ffffff"),
        ("Mercury", "☿", 66.0, "#f5f5f5"),
        ("Venus", "♀", 99.0, "#ff99cc"),
        ("Mars", "♂", 132.0, "#ff6666"),
        ("Jupiter", "♃", 165.0, "#ffd280"),
        ("Saturn", "♄", 198.0, "#cccccc"),
        ("Uranus", "♅", 231.0, "#66e0ff"),
        ("Neptune", "♆", 264.0, "#66b3ff"),
        ("Pluto", "♇", 297.0, "#ff99ff"),
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

# Aspect tanımları: (açı, tolerans, renk, kalınlık)
ASPECTS = [
    (0, 6, "#ff6666", 1.2),   # conjunction
    (60, 4, "#66b3ff", 0.9),  # sextile
    (90, 5, "#ff6666", 1.1),  # square
    (120, 5, "#66b3ff", 1.1), # trine
    (180, 6, "#ff6666", 1.3), # opposition
]


# -----------------------------------------
# Yardımcı: tarih-saat (yerel) -> Julian Day (UT)
# -----------------------------------------
def _parse_datetime(
    birth_date: str,
    birth_time: str,
    timezone_str: str = "UTC",
) -> float:
    """
    birth_date: 'YYYY-MM-DD'
    birth_time: 'HH:MM'
    timezone_str: IANA timezone ismi (örn. 'Europe/Istanbul')

    Astro.com ile aynı mantık:
      - Girilen tarih/saat doğum yerinin YEREL saati kabul edilir
      - Bu saat, timezone_str kullanılarak UTC'ye çevrilir
      - Swiss Ephemeris'e her zaman UT verilir
    """
    # Temel parse
    try:
        dt_naive = datetime.strptime(
            f"{birth_date} {birth_time}",
            "%Y-%m-%d %H:%M",
        )
    except ValueError:
        # Saat verilmiyorsa öğlen varsayalım (astro yazılımlarının çoğu gibi)
        dt_naive = datetime.strptime(birth_date, "%Y-%m-%d")
        dt_naive = dt_naive.replace(hour=12, minute=0)

    # Yerel -> UTC
    if HAS_TZINFO:
        try:
            local_tz = ZoneInfo(timezone_str)
        except Exception:
            # bilinmeyen timezone ise UTC varsay
            local_tz = timezone.utc
        dt_local = dt_naive.replace(tzinfo=local_tz)
        dt_utc = dt_local.astimezone(timezone.utc)
    else:
        # zoneinfo yoksa, gelen saati zaten UTC kabul ediyoruz
        dt_utc = dt_naive.replace(tzinfo=timezone.utc)

    hour_decimal = (
        dt_utc.hour + dt_utc.minute / 60.0 + dt_utc.second / 3600.0
    )

    if HAS_SWISS:
        jd_ut = swe.julday(
            dt_utc.year,
            dt_utc.month,
            dt_utc.day,
            hour_decimal,
            swe.GREG_CAL,
        )
        return jd_ut
    else:
        # Swiss yoksa: basit Julian hesap (UTC'ye göre)
        a = (14 - dt_utc.month) // 12
        y = dt_utc.year + 4800 - a
        m = dt_utc.month + 12 * a - 3
        jdn = (
            dt_utc.day
            + ((153 * m + 2) // 5)
            + 365 * y
            + y // 4
            - y // 100
            + y // 400
            - 32045
        )
        jd = jdn + (hour_decimal - 12) / 24.0
        return jd


# -----------------------------------------
# Yardımcı: gezegen & ev pozisyonları
# -----------------------------------------
def _compute_positions(
    birth_date: str,
    birth_time: str,
    latitude: float,
    longitude: float,
    timezone_str: str = "UTC",
):
    """
    Swiss varsa:
      - gezegen boylamları (0-360°)
      - Placidus 12 ev cusp dereceleri
    Swiss yoksa:
      - gezegenler sabit örnek dereceler (PLANETS'ten)
      - evler 30° aralıklarla

    timezone_str ile yerel saat -> UT dönüşümü yapılır.
    """
    jd_ut = _parse_datetime(birth_date, birth_time, timezone_str=timezone_str)

    planets_longitudes = []
    houses = []

    if HAS_SWISS:
        # Evler (Placidus)
        try:
            # houses() -> (cusps[1..12], ascmc[0..9])
            cusps, ascmc = swe.houses(jd_ut, latitude, longitude, b"P")
            # `cusps` 13 elemanlı dizi: 1..12 ev başlangıçları
            houses = [float(cusps[i]) % 360.0 for i in range(1, 13)]
        except Exception:
            # Her ihtimale karşı fallback: 30° eşit evler
            houses = [(i * 30.0) % 360.0 for i in range(12)]

        # Gezegenler
        for name, symbol, code, color in PLANETS:
            if isinstance(code, (int, float)):
                try:
                    pos, _ = swe.calc_ut(jd_ut, code)
                    lon = float(pos[0]) % 360.0
                except Exception:
                    lon = 0.0
            else:
                lon = 0.0

            planets_longitudes.append(
                {
                    "name": name,
                    "symbol": symbol,
                    "lon": lon,
                    "color": color,
                }
            )

    else:
        # Swiss yoksa: eşit ev & sabit planet dereceleri
        houses = [(i * 30.0) % 360.0 for i in range(12)]
        for name, symbol, deg, color in PLANETS:
            planets_longitudes.append(
                {
                    "name": name,
                    "symbol": symbol,
                    "lon": float(deg) % 360.0,
                    "color": color,
                }
            )

    return planets_longitudes, houses


# -----------------------------------------
# Yardımcı: açı farkı (0-180)
# -----------------------------------------
def _angle_diff(a, b):
    """İki derece arasındaki en küçük fark (0-180)."""
    diff = abs(a - b) % 360.0
    if diff > 180.0:
        diff = 360.0 - diff
    return diff


# -----------------------------------------
# Aspect hesaplama
# -----------------------------------------
def _compute_aspects(planets):
    """
    Basit aspect kontrolü:
    Seçili gezegenler arasındaki açılar, ASPECTS listesine göre.
    """
    aspects = []
    n = len(planets)
    for i in range(n):
        for j in range(i + 1, n):
            p1 = planets[i]
            p2 = planets[j]
            diff = _angle_diff(p1["lon"], p2["lon"])
            for angle, orb, color, width in ASPECTS:
                if abs(diff - angle) <= orb:
                    aspects.append(
                        {
                            "p1": p1,
                            "p2": p2,
                            "angle": angle,
                            "diff": diff,
                            "color": color,
                            "width": width,
                        }
                    )
                    break
    return aspects


# -----------------------------------------
# Çizim fonksiyonu
# -----------------------------------------
def _draw_chart(
    planets, houses, out_path, title_text="Natal Chart", subtitle_text=""
):
    """
    planets: [{name, symbol, lon, color}, ...]
    houses: [deg1, deg2, ..., deg12] (0-360)
    out_path: kaydedilecek PNG yolu
    """

    # Tema: koyu mavi / altın – sitenle uyumlu
    fig = plt.figure(figsize=(6, 6), dpi=240)
    ax = plt.subplot(111)
    ax.set_aspect("equal")
    ax.set_xlim(-1.1, 1.1)
    ax.set_ylim(-1.1, 1.1)
    ax.axis("off")

    # Arka plan
    fig.patch.set_facecolor("#050816")
    ax.set_facecolor("#050816")

    # Dış çember
    outer = Circle((0, 0), 1.0, edgecolor="#f2d47f", facecolor="#101735", linewidth=2.0)
    ax.add_patch(outer)

    # İç çember (ev/planet alanı)
    inner = Circle(
        (0, 0), 0.7, edgecolor="#f2d47f", facecolor="#050816", linewidth=1.2
    )
    ax.add_patch(inner)

    # En iç çember (aspect çizgileri için sınır)
    core = Circle(
        (0, 0), 0.05, edgecolor="#30354f", facecolor="#050816", linewidth=0.8
    )
    ax.add_patch(core)

    # Burç dilimleri & semboller
    for i, (name, symbol) in enumerate(SIGNS):
        start_deg = i * 30.0
        mid_deg = start_deg + 15.0
        theta = math.radians(90.0 - mid_deg)

        x = 0.88 * math.cos(theta)
        y = 0.88 * math.sin(theta)

        # ince çizgi (burç sınırı)
        boundary_angle = math.radians(90.0 - start_deg)
        bx = [0.0, 1.0 * math.cos(boundary_angle)]
        by = [0.0, 1.0 * math.sin(boundary_angle)]
        ax.plot(bx, by, color="#283055", linewidth=0.4, alpha=0.8)

        ax.text(
            x,
            y,
            symbol,
            fontsize=10,
            ha="center",
            va="center",
            color="#ffe9a3",
        )

    # Ev çizgileri & numaralar
    for idx, cusp_deg in enumerate(houses):
        theta = math.radians(90.0 - cusp_deg)
        x1 = 0.0
        y1 = 0.0
        x2 = 0.7 * math.cos(theta)
        y2 = 0.7 * math.sin(theta)
        ax.plot([x1, x2], [y1, y2], color="#f8f8ff", linewidth=0.8, alpha=0.8)

        # Ev numarası
        mid_r = 0.78
        tx = mid_r * math.cos(theta)
        ty = mid_r * math.sin(theta)
        house_num = str(idx + 1)
        ax.text(
            tx,
            ty,
            house_num,
            fontsize=7,
            ha="center",
            va="center",
            color="#cfd2ff",
        )

    # Aspect çizgileri
    aspects = _compute_aspects(planets)
    for asp in aspects:
        p1 = asp["p1"]
        p2 = asp["p2"]
        color = asp["color"]
        width = asp["width"]

        r = 0.67  # aspect dairesi yarıçapı

        t1 = math.radians(90.0 - p1["lon"])
        t2 = math.radians(90.0 - p2["lon"])

        x1 = r * math.cos(t1)
        y1 = r * math.sin(t1)
        x2 = r * math.cos(t2)
        y2 = r * math.sin(t2)

        ax.plot(
            [x1, x2],
            [y1, y2],
            color=color,
            linewidth=width * 0.6,
            alpha=0.8,
        )

    # Gezegen sembolleri
    for pl in planets:
        theta = math.radians(90.0 - pl["lon"])
        r = 0.82

        x = r * math.cos(theta)
        y = r * math.sin(theta)

        # küçük nokta
        ax.scatter(
            [x],
            [y],
            s=8,
            color=pl["color"],
            zorder=5,
        )

        # sembol
        tx = (r + 0.04) * math.cos(theta)
        ty = (r + 0.04) * math.sin(theta)
        ax.text(
            tx,
            ty,
            pl["symbol"],
            fontsize=9,
            ha="center",
            va="center",
            color=pl["color"],
        )

    # Başlık
    ax.text(
        0,
        1.05,
        title_text,
        ha="center",
        va="bottom",
        color="#ffe9a3",
        fontsize=11,
        fontweight="bold",
    )
    if subtitle_text:
        ax.text(
            0,
            0.97,
            subtitle_text,
            ha="center",
            va="bottom",
            color="#cfd2ff",
            fontsize=7,
        )

    # Kayıt
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    fig.savefig(out_path, dpi=240, bbox_inches="tight", pad_inches=0.12)
    plt.close(fig)


# -----------------------------------------
# DIŞA AÇIK FONKSİYON
# -----------------------------------------
def generate_natal_chart(
    birth_date: str,
    birth_time: str,
    latitude: float,
    longitude: float,
    out_dir: str = "/tmp",
    timezone_str: str = "Europe/Istanbul",
):
    """
    main.py tarafından çağrılan fonksiyon.

    birth_date: 'YYYY-MM-DD'
    birth_time: 'HH:MM'
    latitude, longitude: float (derece, doğu +, batı -)
    out_dir: PNG'in yazılacağı klasör (Render'da /tmp)
    timezone_str: IANA timezone (örn. 'Europe/Istanbul', 'America/New_York')

    DÖNER:
      (chart_id, chart_file_path)

    Not: Solar return endpoint'i de bu fonksiyonu kullanıyor,
    sadece doğum tarihi yerine solar yılına göre tarih gönderiyor.
    """
    # Pozisyonları hesapla (Astro.com ile uyumlu zaman hesabı)
    planets, houses = _compute_positions(
        birth_date,
        birth_time,
        latitude,
        longitude,
        timezone_str=timezone_str,
    )

    # ID & dosya yolu
    chart_id = uuid.uuid4().hex
    chart_path = os.path.join(out_dir, f"{chart_id}.png")

    # Başlık metni (sadece görsel için, main.py mod’u belirliyor)
    title = "Astrology Chart"
    subtitle = f"{birth_date}  •  {birth_time}"

    _draw_chart(planets, houses, chart_path, title, subtitle)

    return chart_id, chart_path
