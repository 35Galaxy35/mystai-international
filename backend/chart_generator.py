import os
import math
import uuid
from datetime import datetime

# --------------------------------------------------
#  Swiss Ephemeris (gerçek astroloji hesapları)
# --------------------------------------------------
HAS_SWISS = False
try:
    import swisseph as swe  # pyswisseph
    HAS_SWISS = True
    # Ephemeris dosya yolunu otomatik ayarla (varsa)
    swe.set_ephe_path(".")
except Exception:
    # Swiss yoksa, tamamen görsel – yaklaşık fallback kullanacağız
    HAS_SWISS = False

# --------------------------------------------------
#  Matplotlib – headless (Render uyumlu)
# --------------------------------------------------
import matplotlib
matplotlib.use("Agg")  # GUI istemez, server’da çalışır
import matplotlib.pyplot as plt
from matplotlib.patches import Circle

# --------------------------------------------------
#  Gezegen & burç tanımları
# --------------------------------------------------

if HAS_SWISS:
    PLANETS = [
        ("Sun", "☉", swe.SUN),
        ("Moon", "☽", swe.MOON),
        ("Mercury", "☿", swe.MERCURY),
        ("Venus", "♀", swe.VENUS),
        ("Mars", "♂", swe.MARS),
        ("Jupiter", "♃", swe.JUPITER),
        ("Saturn", "♄", swe.SATURN),
        ("Uranus", "♅", swe.URANUS),
        ("Neptune", "♆", swe.NEPTUNE),
        ("Pluto", "♇", swe.PLUTO),
    ]
else:
    # Swiss yoksa sadece isim/simge, dereceyi biz uyduracağız
    PLANETS = [
        ("Sun", "☉", 0),
        ("Moon", "☽", 0),
        ("Mercury", "☿", 0),
        ("Venus", "♀", 0),
        ("Mars", "♂", 0),
        ("Jupiter", "♃", 0),
        ("Saturn", "♄", 0),
        ("Uranus", "♅", 0),
        ("Neptune", "♆", 0),
        ("Pluto", "♇", 0),
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

# Sert/yumuşak açılar
ASPECTS = [
    ("conjunction", 0, 6, "#bbbbbb"),
    ("opposition", 180, 6, "#ff5555"),
    ("square", 90, 6, "#ff7777"),
    ("trine", 120, 6, "#5c8cff"),
    ("sextile", 60, 4, "#4bbf7f"),
]


# --------------------------------------------------
#  Yardımcı: derece → kartesyen
# --------------------------------------------------
def _pol_to_cart(radius: float, degree: float):
    """
    0° Koç = sol tarafta, saat yönünün tersine artıyor.
    Matematiksel açı 0° üst tarafta olduğu için 90° kaydırıyoruz.
    """
    rad = math.radians(90 - degree)
    x = radius * math.cos(rad)
    y = radius * math.sin(rad)
    return x, y


# --------------------------------------------------
#  Yardımcı: tarih-saat → Julian Day (veya saat)
# --------------------------------------------------
def _parse_datetime(birth_date: str, birth_time: str):
    """
    birth_date: 'YYYY-MM-DD'
    birth_time: 'HH:MM'
    Swiss varsa gerçek Julian day, yoksa sadece saat (float) döner.
    """
    dt = datetime.strptime(f"{birth_date} {birth_time}", "%Y-%m-%d %H:%M")
    hour_decimal = dt.hour + dt.minute / 60.0

    if HAS_SWISS:
        jd = swe.julday(dt.year, dt.month, dt.day, hour_decimal, swe.GREG_CAL)
        return jd
    else:
        return hour_decimal


# --------------------------------------------------
#  Yardımcı: gezegen & ev pozisyonları
# --------------------------------------------------
def _compute_positions(
    birth_date: str,
    birth_time: str,
    latitude: float,
    longitude: float,
):
    """
    Swiss varsa:
      - gezegen boylamları (0-360°)
      - Placidus 12 ev cusp dereceleri
      - ASC ve MC
    Swiss yoksa:
      - gezegenler & evler eşit aralıklı, sadece görsel.
    """
    jd_or_hour = _parse_datetime(birth_date, birth_time)

    planets_longitudes = []
    houses = []
    asc = 0.0
    mc = 0.0

    if HAS_SWISS:
        jd = jd_or_hour

        # Gezegenler
        for idx, (name, symbol, swiss_id) in enumerate(PLANETS):
            try:
                # pyswisseph: (xx, retflag) döner.
                pos = swe.calc_ut(jd, swiss_id)
                if isinstance(pos, tuple) and len(pos) >= 1:
                    first = pos[0]
                    if isinstance(first, (list, tuple)):
                        lon = float(first[0])
                    else:
                        lon = float(first)
                else:
                    lon = float(pos)
            except Exception:
                # Tek bir gezegende hata olursa bile diğerleri çizilsin
                step = 360.0 / len(PLANETS)
                lon = (idx * step) % 360.0

            lon = lon % 360.0
            planets_longitudes.append(lon)

        try:
            cusps, ascmc = swe.houses(jd, latitude, longitude, b"P")
            # cusps 1..12 kullanılıyor.
            houses = [float(cusps[i]) % 360.0 for i in range(1, 13)]
            asc = float(ascmc[0]) % 360.0
            mc = float(ascmc[1]) % 360.0
        except Exception:
            # Ev hesaplama başarısızsa eşit ev fallback
            houses = [(i * 30.0) % 360.0 for i in range(12)]
            asc = houses[0]
            mc = houses[9]

    else:
        # Tamamen görsel, ama yine de farklı dereceler
        base = jd_or_hour  # saat
        step = 360.0 / len(PLANETS)
        for idx, _pl in enumerate(PLANETS):
            lon = (base * 15.0 + idx * step) % 360.0
            planets_longitudes.append(lon)

        houses = [(i * 30.0) % 360.0 for i in range(12)]
        asc = houses[0]
        mc = houses[9]

    return planets_longitudes, houses, asc, mc


# --------------------------------------------------
#  Haritayı çiz
# --------------------------------------------------
def _draw_chart_png(
    planets_longitudes,
    houses,
    asc,
    mc,
    out_path: str,
    title: str = "",
):
    """
    Verilen gezegen & ev derecelerine göre profesyonel görünümlü
    bir çark + aspect çizgileri çizer.
    """
    # Tema 1: koyu mavi altın detaylı
    fig, ax = plt.subplots(figsize=(6, 6), dpi=220)
    ax.set_xlim(-1.1, 1.1)
    ax.set_ylim(-1.1, 1.1)
    ax.set_aspect("equal")
    ax.axis("off")
    fig.patch.set_facecolor("#050816")
    ax.set_facecolor("#050816")

    # Dış altın halka
    outer = Circle((0, 0), 1.0, edgecolor="#f2d27a", facecolor="#181b3a", linewidth=2.2)
    ax.add_patch(outer)

    # İç halkalar
    ring2 = Circle((0, 0), 0.82, edgecolor="#f2d27a", facecolor="#101532", linewidth=1.5)
    ring3 = Circle((0, 0), 0.60, edgecolor="#444a7a", facecolor="#050816", linewidth=1.0)
    ax.add_patch(ring2)
    ax.add_patch(ring3)

    # Burç çizgileri & isimleri
    for i, (sign_name, sign_sym) in enumerate(SIGNS):
        start_deg = i * 30.0
        # Sınır çizgisi
        x1, y1 = _pol_to_cart(0.60, start_deg)
        x2, y2 = _pol_to_cart(1.0, start_deg)
        ax.plot([x1, x2], [y1, y2], color="#3c4270", linewidth=0.8)

        # Burç simgesi (segment ortası)
        mid_deg = start_deg + 15.0
        tx, ty = _pol_to_cart(1.04, mid_deg)
        ax.text(
            tx,
            ty,
            sign_sym,
            ha="center",
            va="center",
            fontsize=13,
            color="#f7e5a0",
            fontweight="bold",
        )

    # Ev çizgileri & numaralar
    for i, house_deg in enumerate(houses):
        x1, y1 = _pol_to_cart(0.60, house_deg)
        x2, y2 = _pol_to_cart(0.98, house_deg)
        ax.plot([x1, x2], [y1, y2], color="#7075a5", linewidth=0.9)

        # Ev numarası, biraz içerde
        mid_deg = (house_deg + 15.0) % 360.0
        tx, ty = _pol_to_cart(0.70, mid_deg)
        ax.text(
            tx,
            ty,
            str((i + 1)),
            ha="center",
            va="center",
            fontsize=9,
            color="#d6ddff",
        )

    # ASC ve MC işaretleri (isteğe bağlı)
    # ASC
    ax.text(
        *_pol_to_cart(1.06, asc),
        "ASC",
        ha="center",
        va="center",
        fontsize=8,
        color="#ffffff",
    )
    # MC
    ax.text(
        *_pol_to_cart(1.06, mc),
        "MC",
        ha="center",
        va="center",
        fontsize=8,
        color="#ffffff",
    )

    # Gezegenler (dış halkaya yakın)
    planet_positions_xy = []
    planet_radius = 0.76
    for idx, (lon, (name, symbol, _)) in enumerate(zip(planets_longitudes, PLANETS)):
        x, y = _pol_to_cart(planet_radius, lon)
        planet_positions_xy.append((x, y, lon))

        ax.scatter([x], [y], s=22, color="#faf3d0", edgecolors="#22263c", zorder=5)
        ax.text(
            x,
            y,
            symbol,
            ha="center",
            va="center",
            fontsize=10,
            color="#15193a",
            zorder=6,
            fontweight="bold",
        )

    # Aspect çizgileri (merkezdeki iç dairenin içinde)
    aspect_radius = 0.58
    for i in range(len(planet_positions_xy)):
        name_i, symbol_i, code_i = PLANETS[i]
        _, _, lon_i = planet_positions_xy[i]
        x_i, y_i = _pol_to_cart(aspect_radius, lon_i)

        for j in range(i + 1, len(planet_positions_xy)):
            name_j, symbol_j, code_j = PLANETS[j]
            _, _, lon_j = planet_positions_xy[j]
            x_j, y_j = _pol_to_cart(aspect_radius, lon_j)

            diff = abs(lon_i - lon_j)
            diff = min(diff, 360.0 - diff)

            for asp_name, asp_angle, orb, color in ASPECTS:
                if abs(diff - asp_angle) <= orb:
                    ax.plot(
                        [x_i, x_j],
                        [y_i, y_j],
                        color=color,
                        linewidth=0.7,
                        alpha=0.9,
                        zorder=3,
                    )
                    break

    # Başlık
    if title:
        ax.text(
            0,
            1.14,
            title,
            ha="center",
            va="center",
            fontsize=10,
            color="#f7e5a0",
            fontweight="bold",
        )

    # Kayıt
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    fig.savefig(out_path, dpi=220, transparent=False, bbox_inches="tight", pad_inches=0.12)
    plt.close(fig)


# --------------------------------------------------
#  Dışa açık fonksiyon – main.py bundan çağırıyor
# --------------------------------------------------
def generate_natal_chart(
    birth_date: str,
    birth_time: str,
    latitude: float,
    longitude: float,
    out_dir: str = "/tmp",
    chart_title: str = "",
):
    """
    main.py şu şekilde kullanıyor:
        chart_id, chart_path = generate_natal_chart(
            birth_date=birth_date,
            birth_time=birth_time,
            latitude=lat,
            longitude=lon,
            out_dir="/tmp",
        )

    Burada hem natal hem solar için aynı fonksiyon kullanılıyor;
    solar return'de sadece tarih farklı.
    """
    # 1) Hesaplamalar
    planets_longitudes, houses, asc, mc = _compute_positions(
        birth_date=birth_date,
        birth_time=birth_time,
        latitude=latitude,
        longitude=longitude,
    )

    # 2) Benzersiz id + dosya yolu
    chart_id = str(uuid.uuid4())
    os.makedirs(out_dir, exist_ok=True)
    file_path = os.path.join(out_dir, f"{chart_id}.png")

    # 3) Çizim
    title = chart_title or "MystAI Astrology Chart"
    _draw_chart_png(planets_longitudes, houses, asc, mc, file_path, title=title)

    # 4) main.py'nin beklediği şekilde geriye dön
    return chart_id, file_path
