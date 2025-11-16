import os
import math
from datetime import datetime
from flatlib.chart import Chart
from flatlib.datetime import Datetime
from flatlib.geopos import GeoPos
from flatlib import const

import matplotlib.pyplot as plt
from matplotlib.patches import Circle
from matplotlib.font_manager import FontProperties
from PIL import Image

# ============================
#    HARİTA AYARLARI
# ============================

IMAGE_SIZE = 2048           # Ultra HD
CENTER = IMAGE_SIZE // 2
RADIUS = IMAGE_SIZE // 2 - 120

PLANET_COLORS = "#FFD86B"   # Altın
CIRCLE_COLOR = "#DDC16F"
BACKGROUND_COLOR = "#0A0A0A"
TEXT_COLOR = "#FFFFFF"

PLANETS = [
    const.SUN, const.MOON, const.MERCURY, const.VENUS,
    const.MARS, const.JUPITER, const.SATURN,
    const.URANUS, const.NEPTUNE, const.PLUTO
]

HOUSES = list(range(1, 13))


# ============================
#  AÇI DÖNÜŞÜMÜ
# ============================

def to_radians(deg):
    return deg * math.pi / 180


def point_on_circle(angle_deg, radius):
    angle = to_radians(angle_deg - 90)
    x = CENTER + radius * math.cos(angle)
    y = CENTER + radius * math.sin(angle)
    return x, y


# ============================
#  HARİTA ÇİZİMİ
# ============================

def draw_chart(chart, output_path):
    fig, ax = plt.subplots(figsize=(12, 12), dpi=170)
    fig.patch.set_facecolor(BACKGROUND_COLOR)
    ax.set_facecolor(BACKGROUND_COLOR)

    ax.set_xlim(0, IMAGE_SIZE)
    ax.set_ylim(0, IMAGE_SIZE)
    plt.axis("off")

    # Ana daire
    main_circle = Circle((CENTER, CENTER), RADIUS, fill=False, linewidth=6, edgecolor=CIRCLE_COLOR)
    ax.add_patch(main_circle)

    # İç daire (ev bölümleri)
    inner_circle = Circle((CENTER, CENTER), RADIUS - 120, fill=False, linewidth=2, edgecolor=CIRCLE_COLOR)
    ax.add_patch(inner_circle)

    # Ev çizgileri
    for i, house in enumerate(HOUSES):
        cusp = chart.houses[house].lon
        x1, y1 = point_on_circle(cusp, RADIUS)
        x2, y2 = point_on_circle(cusp, RADIUS - 120)
        ax.plot([x1, x2], [y1, y2], color=CIRCLE_COLOR, linewidth=2)

    # Gezegen simgelerini yerleştir
    for planet in PLANETS:
        body = chart.get(planet)
        x, y = point_on_circle(body.lon, RADIUS - 60)
        ax.text(
            x, y,
            planet,
            fontsize=26,
            color=PLANET_COLORS,
            ha="center",
            va="center",
            fontweight="bold"
        )

    # Kaydet
    plt.savefig(output_path, dpi=170, facecolor=BACKGROUND_COLOR)
    plt.close()


# ============================
#  HARİTA ÜRETİM FONKSİYONU
# ============================

def generate_birth_chart(birth_date, birth_time, birth_place):
    """
    birth_date: "1978-11-06"
    birth_time: "13:40"
    birth_place: "Istanbul"
    """

    # --- Lokasyon çözümleme şimdilik default (İstanbul) ---
    # Daha sonra gerçek koordinat API'si ekleyeceğiz.
    city_coords = {
        "istanbul": (41.015137, 28.97953),
        "izmir": (38.4192, 27.1287),
        "ankara": (39.9208, 32.8541),
    }

    lat, lon = city_coords.get(birth_place.lower(), (41.015137, 28.97953))

    # Flatlib datetime
    date_obj = datetime.strptime(birth_date, "%Y-%m-%d")
    time_obj = datetime.strptime(birth_time, "%H:%M")

    dt = Datetime(
        date_obj.year, date_obj.month, date_obj.day,
        time_obj.hour, time_obj.minute,
        "+03:00"
    )

    pos = GeoPos(lat, lon)

    chart = Chart(dt, pos)

    # Dosya ID
    file_id = f"chart_{datetime.now().timestamp()}.png"
    output_path = f"/tmp/{file_id}"

    draw_chart(chart, output_path)

    return output_path, file_id
