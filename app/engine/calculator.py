import swisseph as swe
from datetime import datetime
import pytz
from timezonefinder import TimezoneFinder
from app.models.domain import User, ChartData

class AstrologyEngine:
    def __init__(self):
        # Set ephemeris path if data is external, but we use internal for now
        # Set Sidereal mode for Vedic Astrology (Lahiri Ayanamsa)
        swe.set_sid_mode(swe.SIDM_LAHIRI)
        self.tf = TimezoneFinder()
        
        # Planets to calculate
        self.planets = {
            "Sun": swe.SUN,
            "Moon": swe.MOON,
            "Mars": swe.MARS,
            "Mercury": swe.MERCURY,
            "Jupiter": swe.JUPITER,
            "Venus": swe.VENUS,
            "Saturn": swe.SATURN,
            "Rahu": swe.MEAN_NODE
        }
        
        # Zodiac Signs
        self.zodiac_signs = [
            "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
            "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"
        ]

    def _get_utc_datetime(self, dob: str, tob: str, lat: float, lon: float) -> datetime:
        """
        Converts the local Date and Time of Birth to UTC using coordinates for timezone.
        """
        dt_str = f"{dob} {tob}"
        local_dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
        
        tz_name = self.tf.timezone_at(lng=lon, lat=lat)
        if tz_name is None:
            tz_name = "UTC" # Fallback if timezone not found
            
        local_tz = pytz.timezone(tz_name)
        
        # Localize naive datetime
        local_dt = local_tz.localize(local_dt)
        return local_dt.astimezone(pytz.utc)

    def _get_sign_and_degree(self, longitude: float):
        """
        Calculates zodiac sign and localized degree based on planetary longitude.
        """
        if longitude < 0:
            longitude += 360.0
        longitude = longitude % 360.0
        
        sign_index = int(longitude / 30)
        sign_name = self.zodiac_signs[sign_index]
        degree_in_sign = longitude % 30
        return sign_index, sign_name, degree_in_sign

    def calculate_chart(self, user: User) -> list[ChartData]:
        """
        Calculates Sidereal planetary positions and houses (Whole Sign) for the given user.
        """
        utc_dt = self._get_utc_datetime(user.dob, user.tob, user.latitude, user.longitude)
        
        # Convert to Julian Day
        # swe.utc_to_jd returns (jd_et, jd_ut)
        jd_et, jd_ut = swe.utc_to_jd(
            utc_dt.year, utc_dt.month, utc_dt.day,
            utc_dt.hour, utc_dt.minute, utc_dt.second,
            swe.GREG_CAL
        )
                                     
        # Calculate Ascendant (Lagna)
        # swe.houses returns (cusps, ascmc)
        cusps, ascmc = swe.houses_ex(jd_ut, user.latitude, user.longitude, b'P', swe.FLG_SIDEREAL)
        asc_long = ascmc[0] # Ascendant is the 1st element of ascmc list
        
        asc_sign_idx, asc_sign_name, asc_deg = self._get_sign_and_degree(asc_long)
        
        chart_data_list = []
        
        # Ascendant as the first ChartData record
        chart_data_list.append(ChartData(
            user_id=user.id or 0,
            planet_name="Ascendant",
            sign=asc_sign_name,
            house=1, # Whole sign system uses ascendant sign as 1st house
            degree=round(asc_deg, 4)
        ))
        
        # Calculate Planets
        calc_flags = swe.FLG_SWIEPH | swe.FLG_SIDEREAL
        
        for planet_name, planet_id in self.planets.items():
            # swe_calc_ut returns ([long, lat, dist, speed_l, speed_lat, speed_d], ret_flag)
            res, ret = swe.calc_ut(jd_ut, planet_id, calc_flags)
            p_long = res[0]
            
            p_sign_idx, p_sign_name, p_deg = self._get_sign_and_degree(p_long)
            
            # House logic (Whole Sign System: 1st house is ascendant sign)
            house_num = (p_sign_idx - asc_sign_idx) % 12 + 1
            
            chart_data_list.append(ChartData(
                user_id=user.id or 0,
                planet_name=planet_name,
                sign=p_sign_name,
                house=house_num,
                degree=round(p_deg, 4)
            ))
            
            # Compute Ketu (180 degrees from Rahu)
            if planet_name == "Rahu":
                ketu_long = (p_long + 180.0) % 360.0
                k_sign_idx, k_sign_name, k_deg = self._get_sign_and_degree(ketu_long)
                k_house_num = (k_sign_idx - asc_sign_idx) % 12 + 1
                
                chart_data_list.append(ChartData(
                    user_id=user.id or 0,
                    planet_name="Ketu",
                    sign=k_sign_name,
                    house=k_house_num,
                    degree=round(k_deg, 4)
                ))
                
        return chart_data_list
