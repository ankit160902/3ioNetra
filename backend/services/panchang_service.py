import logging
import math
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

try:
    from skyfield.api import load
    from jyotishganit.core.astronomical import get_timescale, get_ephemeris, calculate_ayanamsa
    from jyotishganit.components.panchanga import (
        calculate_tithi, calculate_nakshatra, calculate_yoga, 
        calculate_karana, calculate_vaara
    )
    JYOTISH_AVAILABLE = True
except ImportError:
    JYOTISH_AVAILABLE = False
    logging.warning("jyotishganit or skyfield not available. Panchang features will be disabled.")

logger = logging.getLogger(__name__)

class PanchangService:
    """
    Service for calculating Vedic Panchang (Tithi, Nakshatra, Yoga, Karana, Vaara).
    Uses the jyotishganit library based on Skyfield and JPL ephemeris.
    """

    def __init__(self):
        self.available = JYOTISH_AVAILABLE
        self._ts = None
        self._eph = None

    def _ensure_data(self):
        """Ensure astronomical data is loaded."""
        if not self.available:
            return False
        try:
            if self._ts is None:
                self._ts = get_timescale()
            if self._eph is None:
                self._eph = get_ephemeris()
            return True
        except Exception as e:
            logger.error(f"Failed to load astronomical data: {e}")
            self.available = False
            return False

    def get_panchang(self, dt: datetime, latitude: float = 28.6139, longitude: float = 77.2090, timezone_offset: float = 5.5) -> Dict[str, Any]:
        """
        Calculate Panchang for a given datetime and location.
        Defaults to New Delhi (28.6139, 77.2090) and IST (+5.5).
        """
        if not self._ensure_data():
            return {"error": "Panchang service unavailable"}

        try:
            # Convert to UTC Skyfield time for ayanamsa
            utc_dt = dt - timedelta(hours=timezone_offset)
            t = self._ts.utc(utc_dt.year, utc_dt.month, utc_dt.day, utc_dt.hour, utc_dt.minute, utc_dt.second)
            
            # Calculate Ayanamsa (True Chitra Paksha / Lahiri)
            ayanamsa = calculate_ayanamsa(t)

            # Calculate the five limbs
            tithi = calculate_tithi(dt, timezone_offset)
            nakshatra = calculate_nakshatra(dt, timezone_offset, ayanamsa)
            yoga = calculate_yoga(dt, timezone_offset, ayanamsa)
            karana = calculate_karana(dt, timezone_offset)
            vaara = calculate_vaara(dt)

            return {
                "date": dt.strftime("%Y-%m-%d"),
                "time": dt.strftime("%H:%M:%S"),
                "tithi": tithi,
                "nakshatra": nakshatra,
                "yoga": yoga,
                "karana": karana,
                "vaara": vaara,
                "ayanamsa": round(ayanamsa, 4),
                "location": {"lat": latitude, "lon": longitude}
            }
        except Exception as e:
            logger.exception(f"Error calculating panchang: {e}")
            return {"error": str(e)}

    def get_special_day_info(self, panchang: Dict[str, Any]) -> str:
        """
        Identify if today is a special spiritual day (Ekadashi, Amavasya, etc.)
        """
        tithi = panchang.get("tithi", "").lower()
        if "ekadashi" in tithi:
            return "Today is an auspicious Ekadashi. It is a day for fasting, prayer, and spiritual purification."
        elif "amavasya" in tithi:
            return "Today is Amavasya (New Moon). A powerful time for ancestral prayers and inner reflection."
        elif "purnima" in tithi:
            return "Today is Purnima (Full Moon). A time of fulfillment and spiritual abundance."
        return ""

_panchang_service = None

def get_panchang_service() -> PanchangService:
    global _panchang_service
    if _panchang_service is None:
        _panchang_service = PanchangService()
    return _panchang_service
