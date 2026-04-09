import swisseph as swe
from datetime import datetime
import logging
import pytz
from timezonefinder import TimezoneFinder
from app.models.domain import User, ChartData
from app.config.config_loader import get_astrology_config_loader
from app.utils.logger import log_calculation_step
from app.utils.runtime_paths import get_ephemeris_dir


logger = logging.getLogger(__name__)

class AstrologyEngine:
    AYANAMSA_MAP = {
        "lahiri": swe.SIDM_LAHIRI,
        "raman": getattr(swe, "SIDM_RAMAN", swe.SIDM_LAHIRI),
        "krishnamurti": getattr(swe, "SIDM_KRISHNAMURTI", swe.SIDM_LAHIRI),
    }

    HOUSE_SYSTEMS_MAP = {
        "whole_sign": b'W',
        "placidus": b'P',
        "koch": b'K',
        "equal": b'E',
        "porphyrius": b'O',
        "regiomontanus": b'R',
        "campanus": b'C',
        "shripati": b'S',
        "kp": b'P',  # KP often uses Placidus cusps
    }

    def __init__(self):
        # Set ephemeris path if data is external, but we use internal for now
        self.config_loader = get_astrology_config_loader()
        self.config = self.config_loader.load()
        self._configure_ephemeris_path()
        self._apply_ayanamsa_setting()
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

        self.house_system_key = str(self.config.get("house_system", "whole_sign")).strip().lower()
        self.house_system_code = self.HOUSE_SYSTEMS_MAP.get(self.house_system_key, b'W')
        
        if self.house_system_key not in self.HOUSE_SYSTEMS_MAP:
            logger.warning(
                "Configured house_system '%s' is not supported. Falling back to whole_sign.",
                self.house_system_key,
            )
            self.house_system_key = "whole_sign"
            self.house_system_code = b'W'

    def _configure_ephemeris_path(self) -> None:
        """Configures Swiss Ephemeris to use bundled offline ephemeris files when present."""
        ephemeris_dir = get_ephemeris_dir()
        if ephemeris_dir is None:
            logger.info("No external ephemeris directory found. Using Swiss Ephemeris defaults.")
            return

        swe.set_ephe_path(str(ephemeris_dir))
        log_calculation_step("ephemeris_path_configured", ephemeris_path=str(ephemeris_dir))

    def _apply_ayanamsa_setting(self) -> None:
        """Applies the configured ayanamsa while preserving Lahiri as the default."""
        configured_ayanamsa = str(self.config.get("ayanamsa", "Lahiri")).strip().lower()
        sid_mode = self.AYANAMSA_MAP.get(configured_ayanamsa, swe.SIDM_LAHIRI)
        if configured_ayanamsa not in self.AYANAMSA_MAP:
            logger.warning("Unsupported ayanamsa '%s'. Falling back to Lahiri.", configured_ayanamsa)
        swe.set_sid_mode(sid_mode)
        log_calculation_step("ayanamsa_applied", ayanamsa=configured_ayanamsa or "lahiri")

    def _get_utc_datetime(self, dob: str, tob: str, lat: float, lon: float) -> datetime:
        """
        Converts the local Date and Time of Birth to UTC using coordinates for timezone.
        """
        dt_str = f"{dob} {tob}"
        local_dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")

        timezone_mode = str(self.config.get("timezone_mode", "auto")).strip().lower() or "auto"
        if timezone_mode == "utc":
            tz_name = "UTC"
        elif timezone_mode not in {"auto", "utc"}:
            tz_name = self.config.get("timezone_mode")
        else:
            tz_name = self.tf.timezone_at(lng=lon, lat=lat)

        if not tz_name:
            tz_name = "UTC" # Fallback if timezone not found
            logger.warning("Timezone lookup failed for lat=%s lon=%s. Falling back to UTC.", lat, lon)
            
        local_tz = pytz.timezone(tz_name)
        log_calculation_step(
            "timezone_resolved",
            timezone=tz_name,
            timezone_mode=timezone_mode,
            latitude=lat,
            longitude=lon,
        )
        
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
        log_calculation_step(
            "chart_calculation_started",
            user_id=user.id or 0,
            name=user.name,
            dob=user.dob,
            latitude=user.latitude,
            longitude=user.longitude,
        )
        utc_dt = self._get_utc_datetime(user.dob, user.tob, user.latitude, user.longitude)
        
        # Convert to Julian Day
        # swe.utc_to_jd returns (jd_et, jd_ut)
        jd_et, jd_ut = swe.utc_to_jd(
            utc_dt.year, utc_dt.month, utc_dt.day,
            utc_dt.hour, utc_dt.minute, utc_dt.second,
            swe.GREG_CAL
        )
        log_calculation_step("julian_day_computed", jd_ut=jd_ut)
                                     
        # Calculate Ascendant (Lagna) and Houses
        # swe.houses_ex returns (cusps, ascmc)
        cusps, ascmc = swe.houses_ex(jd_ut, user.latitude, user.longitude, self.house_system_code, swe.FLG_SIDEREAL)
        asc_long = ascmc[0] # Ascendant is the 1st element of ascmc list
        
        asc_sign_idx, asc_sign_name, asc_deg = self._get_sign_and_degree(asc_long)
        log_calculation_step("ascendant_computed", sign=asc_sign_name, degree=round(asc_deg, 4), house_system=self.house_system_key)
        
        chart_data_list = []
        
        # Ascendant as the first ChartData record
        chart_data_list.append(ChartData(
            user_id=user.id or 0,
            planet_name="Ascendant",
            sign=asc_sign_name,
            house=1, # Whole sign system uses ascendant sign as 1st house
            degree=round(asc_deg, 4),
            absolute_longitude=round(asc_long, 6),
            is_retrograde=False
        ))
        
        # Calculate Planets
        calc_flags = swe.FLG_SWIEPH | swe.FLG_SIDEREAL
        
        for planet_name, planet_id in self.planets.items():
            # swe_calc_ut returns ([long, lat, dist, speed_l, speed_lat, speed_d], ret_flag)
            res, ret = swe.calc_ut(jd_ut, planet_id, calc_flags)
            p_long = res[0]
            
            p_sign_idx, p_sign_name, p_deg = self._get_sign_and_degree(p_long)
            
            # House logic
            if self.house_system_key == "whole_sign":
                # Whole Sign System: 1st house is the entire ascendant sign
                house_num = (p_sign_idx - asc_sign_idx) % 12 + 1
            else:
                # Cusp-based systems (Placidus, Koch, etc.)
                # swe.house_pos determines which house a longitude falls into
                house_num = int(swe.house_pos(asc_long, user.latitude, user.longitude, self.house_system_code, p_long))
            
            chart_data_list.append(ChartData(
                user_id=user.id or 0,
                planet_name=planet_name,
                sign=p_sign_name,
                house=house_num,
                degree=round(p_deg, 4),
                absolute_longitude=round(p_long, 6),
                is_retrograde=(planet_name == "Rahu") or (res[3] < 0)
            ))
            log_calculation_step(
                "planet_computed",
                planet=planet_name,
                sign=p_sign_name,
                house=house_num,
                degree=round(p_deg, 4),
            )
            
            # Compute Ketu (180 degrees from Rahu)
            if planet_name == "Rahu":
                ketu_long = (p_long + 180.0) % 360.0
                k_sign_idx, k_sign_name, k_deg = self._get_sign_and_degree(ketu_long)
                
                if self.house_system_key == "whole_sign":
                    k_house_num = (k_sign_idx - asc_sign_idx) % 12 + 1
                else:
                    k_house_num = int(swe.house_pos(asc_long, user.latitude, user.longitude, self.house_system_code, ketu_long))
                
                chart_data_list.append(ChartData(
                    user_id=user.id or 0,
                    planet_name="Ketu",
                    sign=k_sign_name,
                    house=k_house_num,
                    degree=round(k_deg, 4),
                    absolute_longitude=round(ketu_long, 6),
                    is_retrograde=True
                ))
                log_calculation_step(
                    "planet_computed",
                    planet="Ketu",
                    sign=k_sign_name,
                    house=k_house_num,
                    degree=round(k_deg, 4),
                )
                
        log_calculation_step("chart_calculation_completed", user_id=user.id or 0, points=len(chart_data_list))
        return chart_data_list
