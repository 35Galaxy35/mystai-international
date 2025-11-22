# chart_generator.py
# ===================
# MystAI - Profesyonel Astroloji Harita Üreticisi
#
# - Swiss Ephemeris (pyswisseph) varsa gerçek efemeris hesabı
# - Placidus ev sistemi
# - Natal & Solar return için harita
# - Aspect çizgileri
# - Render (headless) uyumlu matplotlib çıktısı (PNG)
#
# generate_natal_chart:
#   (chart_id, chart_file_path, chart_meta)
# döndürür.
# chart_meta:
#   - planets: gezegen listesi (burç, derece vb.)
#   - houses: 12 ev cusp derecesi
#   - asc: yükselen bilgisi
#   - mc: MC bilgisi

import os
import math
import uuid
from datetime import datetime, timezone

# ------------------------------
# Tarihsel timezone desteği (ZoneInfo)
# ------------------------------
try:
    from zoneinfo import ZoneInfo  # Python 3.9+
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

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Circle

# -----------------------------------------
# Gezegen & burç listeleri
# -----------------------------------------

if HAS_SWISS:
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
    # Swiss yoksa görsel amaçlı sabit dereceler
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

ASPECTS = [
    (0, 6, "#ff6666", 1.2),
    (60, 4, "#66b3ff", 0.9),
    (90, 5, "#ff6666", 1.1),
    (120, 5, "#66b3ff", 1.1),
    (180, 6, "#ff6666", 1.3),
]


def _deg_to_sign_info(deg: float):
    """0–360° dereceden burç ve burç içi derece bilgisi üret."""
    idx = int(deg // 30) % 12
    sign_name, sign_symbol = SIGNS[idx]
    deg_in_sign = deg % 30.0
    return {
        "sign": sign_name,
        "symbol": sign_symbol,
        "degree": deg,
        "degree_in_sign": deg_in_sign,
        "sign_index": idx,
    }


# -----------------------------------------
# Yerel tarih-saat -> Julian Day (UT)
# -----------------------------------------
def _parse_datetime(
    birth_date: str,
    birth_time: str,
    timezone_str: str = "UTC",
) -> float:
    """
    Astro.com mantığı:
      - Girilen tarih/saat doğum yerinin yerel zamanı
      - timezone_str ile UTC'ye çevrilir
      - Swiss Ephemeris'e UT verilir
    """
    try:
        dt_naive = datetime.strptime(
            f"{birth_date} {birth_time}",
            "%Y-%m-%d %H:%M",
        )
    except ValueError:
        dt_naive = datetime.strptime(birth_date, "%Y-%m-%d")
        dt_naive = dt_naive.replace(hour=12, minute=0)

    if HAS_TZINFO:
        try:
            local_tz = ZoneInfo(timezone_str)
        except Exception:
            local_tz = timezone.utc
        dt_local = dt_naive.replace(tzinfo=local_tz)
        dt_utc = dt_local.astimezone(timezone.utc)
    else:
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
# Pozisyon hesaplama (planetler + evler)
# -----------------------------------------
def _compute_positions(
    birth_date: str,
    birth_time: str,
    latitude: float,
    longitude: float,
    timezone_str: str = "UTC",
):
    jd_ut = _parse_datetime(birth_date, birth_time, timezone_str=timezone_str)

    planets_longitudes = []
    houses = []
    asc_info = None
    mc_info = None

    if HAS_SWISS:
        try:
            cusps, ascmc = swe.houses(jd_ut, latitude, longitude, b"P")
            houses = [float(cusps[i]) % 360.0 for i in range(1, 13)]

            asc_deg = float(ascmc[0]) % 360.0
            mc_deg = float(ascmc[1]) % 360.0
            asc_info = _deg_to_sign_info(asc_deg)
            mc_info = _deg_to_sign_info(mc_deg)
        except Exception:
            houses = [(i * 30.0) % 360.0 for i in range(12)]
            asc_info = _deg_to_sign_info(houses[0])
            mc_info = _deg_to_sign_info(houses[9])

        for name, symbol, code, color in PLANETS:
            if isinstance(code, (int, float)):
                try:
                    pos, _ = swe.calc_ut(jd_ut, code)
                    lon = float(pos[0]) % 360.0
                except Exception:
                    lon = 0.0
            else:
                lon = 0.0

            sign_info = _deg_to_sign_info(lon)
            planets_longitudes.append(
                {
                    "name": name,
                    "symbol": symbol,
                    "lon": lon,
                    "color": color,
                    "sign": sign_info["sign"],
                    "sign_symbol": sign_info["symbol"],
                    "degree_in_sign": sign_info["degree_in_sign"],
                }
            )

    else:
        # Swiss yoksa: görsel amaçlı, sabit örnek dereceler
        houses = [(i * 30.0) % 360.0 for i in range(12)]
        asc_info = _deg_to_sign_info(houses[0])
        mc_info = _deg_to_sign_info(houses[9])
        for name, symbol, deg, color in PLANETS:
            sign_info = _deg_to_sign_info(deg)
            planets_longitudes.append(
                {
                    "name": name,
                    "symbol": symbol,
                    "lon": float(deg) % 360.0,
                    "color": color,
                    "sign": sign_info["sign"],
                    "sign_symbol": sign_info["symbol"],
                    "degree_in_sign": sign_info["degree_in_sign"],
                }
            )

    chart_meta = {
        "planets": planets_longitudes,
        "houses": houses,
        "asc": asc_info,
        "mc": mc_info,
    }

    return planets_longitudes, houses, chart_meta


def _angle_diff(a, b):
    diff = abs(a - b) % 360.0
    if diff > 180.0:
        diff = 360.0 - diff
    return diff


def _compute_aspects(planets):
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


def _draw_chart(
    planets, houses, out_path, title_text="Natal Chart", subtitle_text=""
):
    fig = plt.figure(figsize=(6, 6), dpi=240)
    ax = plt.subplot(111)
    ax.set_aspect("equal")
    ax.set_xlim(-1.1, 1.1)
    ax.set_ylim(-1.1, 1.1)
    ax.axis("off")

    fig.patch.set_facecolor("#050816")
    ax.set_facecolor("#050816")

    outer = Circle((0, 0), 1.0, edgecolor="#f2d47f", facecolor="#101735", linewidth=2.0)
    ax.add_patch(outer)

    inner = Circle(
        (0, 0), 0.7, edgecolor="#f2d47f", facecolor="#050816", linewidth=1.2
    )
    ax.add_patch(inner)

    core = Circle(
        (0, 0), 0.05, edgecolor="#30354f", facecolor="#050816", linewidth=0.8
    )
    ax.add_patch(core)

    for i, (name, symbol) in enumerate(SIGNS):
        start_deg = i * 30.0
        mid_deg = start_deg + 15.0
        theta = math.radians(90.0 - mid_deg)

        x = 0.88 * math.cos(theta)
        y = 0.88 * math.sin(theta)

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

    for idx, cusp_deg in enumerate(houses):
        theta = math.radians(90.0 - cusp_deg)
        x1 = 0.0
        y1 = 0.0
        x2 = 0.7 * math.cos(theta)
        y2 = 0.7 * math.sin(theta)
        ax.plot([x1, x2], [y1, y2], color="#f8f8ff", linewidth=0.8, alpha=0.8)

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

    aspects = _compute_aspects(planets)
    for asp in aspects:
        p1 = asp["p1"]
        p2 = asp["p2"]
        color = asp["color"]
        width = asp["width"]

        r = 0.67

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

    for pl in planets:
        theta = math.radians(90.0 - pl["lon"])
        r = 0.82

        x = r * math.cos(theta)
        y = r * math.sin(theta)

        ax.scatter(
            [x],
            [y],
            s=8,
            color=pl["color"],
            zorder=5,
        )

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

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    fig.savefig(out_path, dpi=240, bbox_inches="tight", pad_inches=0.12)
    plt.close(fig)


def generate_natal_chart(
    birth_date: str,
    birth_time: str,
    latitude: float,
    longitude: float,
    out_dir: str = "/tmp",
    timezone_str: str = "Europe/Istanbul",
):
    planets, houses, chart_meta = _compute_positions(
        birth_date,
        birth_time,
        latitude,
        longitude,
        timezone_str=timezone_str,
    )

    chart_id = uuid.uuid4().hex
    chart_path = os.path.join(out_dir, f"{chart_id}.png")

    title = "Astrology Chart"
    subtitle = f"{birth_date}  •  {birth_time}"

    _draw_chart(planets, houses, chart_path, title, subtitle)

    return chart_id, chart_path, chart_meta
