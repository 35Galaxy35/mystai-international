# chart_generator.py
# ===================
# MystAI - Profesyonel Astroloji Harita Üreticisi
#
# Bu sürümde:
# - Tüm astrolojik hesaplamalar astro_core.compute_birth_chart üzerinden gelir.
# - Swiss Ephemeris + doğru timezone + Placidus ev sistemi kullanılır.
# - generate_natal_chart:
#       (chart_id, chart_file_path, chart_meta) döndürür.
#   chart_meta, astro_core içindeki sözlüğü aynen iletir:
#       - planets: [{name, lon, sign, degree_in_sign}, ...]
#       - houses: 12 ev cusp derecesi (0–360)
#       - asc: {lon, sign, degree_in_sign}
#       - mc:  {lon, sign, degree_in_sign}

import os
import math
import uuid

# Tüm gerçek hesap astro_core'dan gelir
from astro_core import compute_birth_chart

# -----------------------------------------
# Matplotlib - headless (Render uyumlu)
# -----------------------------------------
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Circle

# -----------------------------------------
# Burç ve gezegen stilleri (sadece görsel)
# -----------------------------------------

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

# Çizim için gezegen sembolleri ve renkleri
PLANET_STYLE = {
    "Sun":     {"symbol": "☉", "color": "#ffcc33"},
    "Moon":    {"symbol": "☽", "color": "#ffffff"},
    "Mercury": {"symbol": "☿", "color": "#f5f5f5"},
    "Venus":   {"symbol": "♀", "color": "#ff99cc"},
    "Mars":    {"symbol": "♂", "color": "#ff6666"},
    "Jupiter": {"symbol": "♃", "color": "#ffd280"},
    "Saturn":  {"symbol": "♄", "color": "#cccccc"},
    "Uranus":  {"symbol": "♅", "color": "#66e0ff"},
    "Neptune": {"symbol": "♆", "color": "#66b3ff"},
    "Pluto":   {"symbol": "♇", "color": "#ff99ff"},
}

ASPECTS = [
    (0,   6, "#ff6666", 1.2),
    (60,  4, "#66b3ff", 0.9),
    (90,  5, "#ff6666", 1.1),
    (120, 5, "#66b3ff", 1.1),
    (180, 6, "#ff6666", 1.3),
]


def _deg_to_sign_index(deg: float) -> int:
    """0–360 dereceden burç index'i (0–11) üretir."""
    return int(float(deg) % 360.0 // 30.0)


# -----------------------------------------
# Açı farkı + aspect hesapları
# -----------------------------------------
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


# -----------------------------------------
# Harita çizimi
# -----------------------------------------
def _draw_chart(
    planets, houses, out_path, title_text="Natal Chart", subtitle_text=""
):
    fig = plt.figure(figsize=(6, 6), dpi=240)
    ax = plt.subplot(111)
    ax.set_aspect("equal")
    ax.set_xlim(-1.1, 1.1)
    ax.set_ylim(-1.1, 1.1)
    ax.axis("off")

    # Arkaplan
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

    # Merkez çekirdek
    core = Circle(
        (0, 0), 0.05, edgecolor="#30354f", facecolor="#050816", linewidth=0.8
    )
    ax.add_patch(core)

    # 12 burç bölümü + semboller
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

    # Ev çizgileri + numaralar
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

    # Aspect çizgileri
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

    # Gezegen sembolleri
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

    # Başlıklar
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
    main.py şunu çağırıyor:
        chart_id, chart_path, chart_meta = generate_natal_chart(...)

    Burada:
        - chart_meta = compute_birth_chart(...) çıktısını aynen döner.
        - chart_path = PNG haritanın dosya yolu
        - chart_id   = PNG ismi için kullanılan uuid (chart_id.png)
    """

    # 1) Gerçek astro veriyi astro_core'dan çek
    chart_meta = compute_birth_chart(
        date_str=birth_date,
        time_str=birth_time,
        lat=latitude,
        lon=longitude,
        tz_name=timezone_str,
    )

    houses = chart_meta.get("houses", [])
    planets_meta = chart_meta.get("planets", [])

    # 2) Çizim fonksiyonu için planet listesi hazırla
    planets_for_plot = []
    for pm in planets_meta:
        name = pm.get("name")
        lon = float(pm.get("lon", 0.0))

        style = PLANET_STYLE.get(name, {"symbol": name[0], "color": "#ffffff"})

        planets_for_plot.append(
            {
                "name": name,
                "symbol": style["symbol"],
                "lon": lon % 360.0,
                "color": style["color"],
            }
        )

    chart_id = uuid.uuid4().hex
    chart_path = os.path.join(out_dir, f"{chart_id}.png")

    title = "Astrology Chart"
    subtitle = f"{birth_date}  •  {birth_time}"

    _draw_chart(planets_for_plot, houses, chart_path, title, subtitle)

    return chart_id, chart_path, chart_meta
