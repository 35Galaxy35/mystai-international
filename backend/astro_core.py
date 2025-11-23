import swisseph as swe
from datetime import datetime
from zoneinfo import ZoneInfo

# Swiss Ephemeris dosyalarının yolu
# BURAYI DEĞİŞTİRECEĞİZ → şimdilik böyle kalsın
swe.set_ephe_path("./ephe")

PLANET_IDS = {
    "SUN": swe.SUN,
    "MOON": swe.MOON,
    "MERCURY": swe.MERCURY,
    "VENUS": swe.VENUS,
    "MARS": swe.MARS,
    "JUPITER": swe.JUPITER,
    "SATURN": swe.SATURN,
    "URANUS": swe.URANUS,
    "NEPTUNE": swe.NEPTUNE,
    "PLUTO": swe.PLUTO,
}

def local_to_utc(year, month, day, hour, minute, tz_name):
    local_dt = datetime(year, month, day, hour, minute, tzinfo=ZoneInfo(tz_name))
    utc_dt = local_dt.astimezone(ZoneInfo("UTC"))
    return utc_dt

def compute_birth_chart(date_str, time_str, lat, lon, tz_name):
    year, month, day = map(int, date_str.split("-"))
    hour, minute = map(int, time_str.split(":"))

    utc_dt = local_to_utc(year, month, day, hour, minute, tz_name)
    hour_decimal = utc_dt.hour + (utc_dt.minute / 60)

    jd_ut = swe.julday(utc_dt.year, utc_dt.month, utc_dt.day, hour_decimal, swe.GREG_CAL)

    planets = {}
    for name, pid in PLANET_IDS.items():
        lon_p, lat_p, dist, speed = swe.calc_ut(jd_ut, pid)
        planets[name] = lon_p

    houses, ascmc = swe.houses(jd_ut, lat, lon, b'P')

    asc = ascmc[0]
    mc  = ascmc[1]

    return {
        "utc": utc_dt.isoformat(),
        "julian_day": jd_ut,
        "planets": planets,
        "houses": houses,
        "asc": asc,
        "mc": mc
    }
