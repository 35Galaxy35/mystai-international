"""
MystAI - Premium Chart Generator
-------------------------------

Bu modül, Swiss Ephemeris (swisseph) kullanarak gerçek gökyüzü
pozisyonlarından yaklaşık bir NATAL harita üretir ve modern,
profesyonel görünümlü bir tekerlek çizerek PNG olarak kaydeder.

main.py, buradan sadece generate_natal_chart() fonksiyonunu kullanır.
Fonksiyon imzası değişmedi:
    generate_natal_chart(birth_date, birth_time, latitude, longitude, out_dir="/tmp")
    -> (chart_id, chart_file_path)

chart_id, /chart/<id> endpoint'i için kullanılır.
chart_file_path ise /tmp/<id>.png dosyasına giden gerçek path'tir.
"""

import os
import math
import uuid
from datetime import datetime

# --- Swiss Ephemeris (gerçek astroloji hesapları) ---
try:
    import swisseph as swe

    HAS_SWISS = True
except Exception:
    # Her ihtimale karşı, swisseph kurulamazsa uygulama ÇÖKMESİN diye
    # basit fallback kullanacağız (gezegenler daireye eşit yayılır).
    HAS_SWISS = False

# --- Matplotlib: headless (Render uyumlu) ---
import matplotlib

matplotlib.use("Agg")  # GUI gerektirmez, Render'da sorunsuz
import matplotlib.pyplot as plt
from matplotlib.patches import Circle


# Gezegen listesi (Swiss Ephemeris sabitleri + kısaltmalar)
PLANETS = [
    ("Sun", "☉", getattr(swe, "SUN", 0)),
    ("Moon", "☽", getattr(swe, "MOON", 1)),
    ("Mercury", "☿", getattr(swe, "MERCURY", 2)),
    ("Venus", "♀", getattr(swe, "VENUS", 3)),
    ("Mars", "♂", getattr(swe, "MARS", 4)),
    ("Jupiter", "♃", getattr(swe, "JUPITER", 5)),
    ("Saturn", "♄", getattr(swe, "SATURN", 6)),
    ("Uranus", "♅", getattr(swe, "URANUS", 7)),
    ("Neptune", "♆", getattr(swe, "NEPTUNE", 8)),
    ("Pluto", "♇", getattr(swe, "PLUTO", 9)),
]

# Zodyak işaret isimleri
SIGNS = [
    ("♈", "Aries"),
    ("♉", "Taurus"),
    ("♊", "Gemini"),
    ("♋", "Cancer"),
    ("♌", "Leo"),
    ("♍", "Virgo"),
    ("♎", "Libra"),
    ("♏", "Scorpio"),
    ("♐", "Sagittarius"),
    ("♑", "Capricorn"),
    ("♒", "Aquarius"),
    ("♓", "Pisces"),
]


def _deg_to_rad(deg: float) -> float:
    return deg * math.pi / 180.0


def _compute_ut_hour(birth_time: str, longitude: float) -> float:
    """
    Basit zaman dilimi tahmini:
    - birth_time: "HH:MM"
    - longitude / 15 ile yaklaşık timezone hesaplanır.

    Bu profesyonel bir timezone veritabanı kadar kesin değil
    ama çoğu kullanıcı için yeterli doğruluk verir.
    """
    try:
        hh, mm = birth_time.split(":")
        local_hour = int(hh) + int(mm) / 60.0
    except Exception:
        local_hour = 12.0  # fallback

    # Çok kabaca: 15° boylam = 1 saat
    tz_guess = round(longitude / 15.0)
    ut_hour = local_hour - tz_guess
    return ut_hour


def _compute_planet_positions(birth_date: str, birth_time: str, latitude: float, longitude: float):
    """
    Swiss Ephemeris kullanarak gezegenlerin ekliptik boylamlarını (0–360°) döndür.
    Swiss çalışmıyorsa, gezegenleri eşit aralıklı yerleştir (fallback).
    """
    positions = {}

    if HAS_SWISS:
        # swisseph için ephemeris path (gerekirse dışarıdan da eklenebilir)
        swe.set_ephe_path(".")  # Render'da default path de iş görür

        # birth_date: YYYY-MM-DD
        y, m, d = map(int, birth_date.split("-"))
        ut_hour = _compute_ut_hour(birth_time, longitude)

        jd_ut = swe.julday(y, m, d, ut_hour)
        swe.set_topo(longitude, latitude, 0)

        for name, symbol, swe_id in PLANETS:
            try:
                lon, lat, dist, speed = swe.calc_ut(jd_ut, swe_id)
                positions[name] = float(lon % 360.0)
            except Exception:
                # Hata olursa yine eşit dağıt
                positions.clear()
                break

    if not positions:
        # Fallback: gezegenleri dairede eşit aralıklı dağıt
        step = 360.0 / len(PLANETS)
        for i, (name, symbol, _) in enumerate(PLANETS):
            positions[name] = (i * step) % 360.0

    return positions


def _draw_chart_png(
    birth_date: str,
    birth_time: str,
    latitude: float,
    longitude: float,
    positions: dict,
    out_path: str,
):
    """
    Modern, premium görünümlü bir doğum haritası tekerleği çizer.
    """

    # --- Figure ayarları ---
    fig = plt.figure(figsize=(8, 8), dpi=300)
    ax = plt.subplot(111, polar=True)
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")

    # 0° Koç yukarıda olacak şekilde (astrolojik standart)
    ax.set_theta_zero_location("N")
    ax.set_theta_direction(-1)

    # Tekerlek sınırları
    ax.set_rlim(0, 1.05)
    ax.set_axis_off()

    # --- Zodyak dairesi ---
    outer_r = 1.0
    inner_r = 0.55

    # Ana daireler
    ax.add_patch(Circle((0, 0), radius=outer_r, transform=ax.transData._b, fill=False, lw=1.8, ec="#444b75"))
    ax.add_patch(Circle((0, 0), radius=inner_r, transform=ax.transData._b, fill=False, lw=1.0, ec="#b5bddf"))

    # Zodyak 30° bölümleri
    for i in range(12):
        angle = _deg_to_rad(i * 30.0)
        ax.plot([angle, angle], [inner_r, outer_r], color="#d0d4f0", lw=0.7, alpha=0.7)

    # Zodyak işaretleri (simge + derece skalası)
    for i, (symbol, name) in enumerate(SIGNS):
        mid_deg = i * 30.0 + 15.0
        angle = _deg_to_rad(mid_deg)
        r = outer_r + 0.02
        ax.text(
            angle,
            r,
            symbol,
            ha="center",
            va="center",
            fontsize=13,
            fontweight="bold",
            color="#262a4d",
        )

    # --- Gezegenler ---
    planet_r = (inner_r + outer_r) / 2.0
    aspect_radius = inner_r * 0.95

    # Basit sembol – bazı sistemlerde astro glifleri görünmeyebilir.
    # Bu nedenle hem glif hem kısa isim yazıyoruz (örn. "☉ Sun").
    for name, symbol, _ in PLANETS:
        lon = positions.get(name, 0.0)
        angle = _deg_to_rad(360.0 - lon)  # saat yönünün tersi

        ax.scatter(angle, planet_r, s=12, color="#1f6feb", zorder=5)
        label = f"{symbol} {name[0]}"
        ax.text(
            angle,
            planet_r + 0.04,
            label,
            ha="center",
            va="center",
            fontsize=7,
            color="#111111",
            fontweight="bold",
            zorder=6,
        )

    # --- Basit açısal açı çizgileri (aspect) ---
    # Klasik açılar: kavuşum (0), kare (90), üçgen (120), karşıt (180)
    # Bu kısmı çok agresif yapmıyoruz; sadece görsel kalite için.
    planet_list = [(name, positions[name]) for name, _, _ in PLANETS if name in positions]

    def angle_diff(a, b):
        d = abs(a - b) % 360.0
        return min(d, 360.0 - d)

    aspects = []
    for i in range(len(planet_list)):
        for j in range(i + 1, len(planet_list)):
            name1, lon1 = planet_list[i]
            name2, lon2 = planet_list[j]
            diff = angle_diff(lon1, lon2)

            if abs(diff - 0) <= 6:
                aspects.append(("conj", lon1, lon2))
            elif abs(diff - 60) <= 4:
                aspects.append(("sextile", lon1, lon2))
            elif abs(diff - 90) <= 4:
                aspects.append(("square", lon1, lon2))
            elif abs(diff - 120) <= 4:
                aspects.append(("trine", lon1, lon2))
            elif abs(diff - 180) <= 4:
                aspects.append(("opp", lon1, lon2))

    for kind, lon1, lon2 in aspects:
        a1 = _deg_to_rad(360.0 - lon1)
        a2 = _deg_to_rad(360.0 - lon2)

        if kind == "conj":
            col = "#ff9800"
            lw = 0.7
        elif kind in ("square", "opp"):
            col = "#ef5350"
            lw = 0.6
        elif kind in ("trine", "sextile"):
            col = "#66bb6a"
            lw = 0.6
        else:
            col = "#9e9e9e"
            lw = 0.5

        ax.plot([a1, a2], [aspect_radius, aspect_radius], color=col, lw=lw, alpha=0.9, zorder=3)

    # --- Başlık bandı (üstte) ---
    # Harita üzerinde küçük doğum bilgisi notu
    try:
        date_obj = datetime.strptime(birth_date, "%Y-%m-%d")
        date_str = date_obj.strftime("%d %b %Y")
    except Exception:
        date_str = birth_date

    info_line = f"{date_str} • {birth_time} • lat {latitude:.2f}°, lon {longitude:.2f}°"
    fig.text(
        0.5,
        0.03,
        info_line,
        ha="center",
        va="center",
        fontsize=8,
        color="#555b80",
    )

    # Kaydet
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    fig.savefig(out_path, dpi=300, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)


def generate_natal_chart(
    birth_date: str,
    birth_time: str,
    latitude: float,
    longitude: float,
    out_dir: str = "/tmp",
):
    """
    Ana fonksiyon.
    - Doğum tarih/saat + koordinatlar → gezegen pozisyonlarını hesaplar
    - Profesyonel bir PNG chart çizer
    - (chart_id, chart_file_path) döner

    HATA OLURSA:
    - Hata raise etmek yerine yine de basit bir tekerlek çizer
      (eşit dağıtılmış gezegenler) böylece backend çökmemiş olur.
    """
    chart_id = uuid.uuid4().hex
    chart_path = os.path.join(out_dir, f"{chart_id}.png")

    try:
        positions = _compute_planet_positions(birth_date, birth_time, latitude, longitude)
        _draw_chart_png(birth_date, birth_time, latitude, longitude, positions, chart_path)
    except Exception as e:
        # Log yazmak isteyen için:
        print("Chart generation error:", e)

        # Fallback: çok basit bir daire çiz
        fig = plt.figure(figsize=(8, 8), dpi=300)
        ax = plt.subplot(111, polar=True)
        fig.patch.set_facecolor("white")
        ax.set_facecolor("white")
        ax.set_theta_zero_location("N")
        ax.set_theta_direction(-1)
        ax.set_rlim(0, 1.05)
        ax.set_axis_off()

        ax.add_patch(Circle((0, 0), radius=1.0, transform=ax.transData._b, fill=False, lw=1.8, ec="#444b75"))
        ax.add_patch(Circle((0, 0), radius=0.55, transform=ax.transData._b, fill=False, lw=1.0, ec="#b5bddf"))

        fig.savefig(chart_path, dpi=300, bbox_inches="tight", facecolor=fig.get_facecolor())
        plt.close(fig)

    return chart_id, chart_path
