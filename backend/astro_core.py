import os
import swisseph as swe
from datetime import datetime
from zoneinfo import ZoneInfo

# ==========================
#  EPHE PATH  (Render için %100 doğru)
# ==========================
EPHE_PATH = os.path.join(os.path.dirname(__file__), "ephe")
swe.set_ephe_path(EPHE_PATH)

PLANET_IDS = {
    "Sun": swe.SUN,
    "Moon": swe.MOON,
    "Mercury": swe.MERCURY,
    "Venus": swe.VENUS,
    "Mars": swe.MARS,
    "Jupiter": swe.JUPITER,
    "Saturn": swe.SATURN,
    "Uranus": swe.URANUS,
    "Neptune": swe.NEPTUNE,
    "Pluto": swe.PLUTO,
}

SIGNS = [
    "Koç", "Boğa", "İkizler", "Yengeç", "Aslan", "Başak",
    "Terazi", "Akrep", "Yay", "Oğlak", "Kova", "Balık"
]


def degree_to_sign(deg: float):
    """0–360 dereceyi (burç adı, burç içi derece) olarak döndür."""
    deg = float(deg) % 360.0
    index = int(deg // 30)
    return SIGNS[index], deg % 30


# ==========================
#  LOCAL TIME → UTC
# ==========================
def local_to_utc(year, month, day, hour, minute, tz_name: str):
    dt_local = datetime(year, month, day, hour, minute, tzinfo=ZoneInfo(tz_name))
    return dt_local.astimezone(ZoneInfo("UTC"))


# ==========================
#   ANA HESAP FONKSİYONU
# ==========================
def compute_birth_chart(date_str, time_str, lat, lon, tz_name):
    """
    date_str  : 'YYYY-MM-DD'
    time_str  : 'HH:MM'
    lat, lon  : float
    tz_name   : 'Europe/Istanbul' gibi IANA timezone
    """
    year, month, day = map(int, date_str.split("-"))
    hour, minute = map(int, time_str.split(":"))

    # → UTC'ye çevir
    utc_dt = local_to_utc(year, month, day, hour, minute, tz_name)

    # → Julian Day için saat (UTC)
    hour_decimal = utc_dt.hour + utc_dt.minute / 60.0 + utc_dt.second / 3600.0

    jd_ut = swe.julday(
        utc_dt.year,
        utc_dt.month,
        utc_dt.day,
        hour_decimal,
        swe.GREG_CAL
    )

    # ============== PLANETS =================
    planet_data = []
    for name, pid in PLANET_IDS.items():
        # PY-Swisseph: calc_ut → (xx, retflag)
        xx, _ = swe.calc_ut(jd_ut, pid)
        lon_p = xx[0]  # sadece ekliptik boylamı kullanıyoruz

        sign_name, degree_in_sign = degree_to_sign(lon_p)

        planet_data.append({
            "name": name,
            "lon": float(lon_p),
            "sign": sign_name,
            "degree_in_sign": float(degree_in_sign),
        })

    # ============== HOUSES ==================
    lat = float(lat)
    lon = float(lon)

    # Placidus ev sistemi → 'P'
    houses, ascmc = swe.houses(jd_ut, lat, lon, b'P')

    asc = float(ascmc[0])
    mc = float(ascmc[1])

    asc_sign, asc_deg = degree_to_sign(asc)
    mc_sign, mc_deg = degree_to_sign(mc)

    return {
        "utc": utc_dt.isoformat(),
        "julian_day": jd_ut,
        "asc": {
            "lon": asc,
            "sign": asc_sign,
            "degree_in_sign": asc_deg,
        },
        "mc": {
            "lon": mc,
            "sign": mc_sign,
            "degree_in_sign": mc_deg,
        },
        "planets": planet_data,
        "houses": houses,
    }
