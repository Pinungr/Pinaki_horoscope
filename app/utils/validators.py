from __future__ import annotations

from datetime import datetime
from typing import Any, Dict


def _normalize_scalar(value: Any) -> str:
    """Returns a stripped string while preserving valid zero-like numeric inputs."""
    if value is None:
        return ""
    return str(value).strip()


def validate_date(dob: Any) -> str:
    """
    Validates and normalizes a date string in YYYY-MM-DD format.

    Returns the normalized date string or raises ValueError with a meaningful message.
    """
    value = _normalize_scalar(dob)
    if not value:
        raise ValueError("Date of birth is required.")

    try:
        parsed = datetime.strptime(value, "%Y-%m-%d")
    except ValueError as exc:
        raise ValueError("Date of birth must be in YYYY-MM-DD format.") from exc

    return parsed.strftime("%Y-%m-%d")


def validate_time(tob: Any) -> str:
    """
    Validates and normalizes a time string.

    Accepts HH:MM or HH:MM:SS and always returns HH:MM:SS.
    """
    value = _normalize_scalar(tob)
    if not value:
        raise ValueError("Time of birth is required.")

    for fmt in ("%H:%M:%S", "%H:%M"):
        try:
            parsed = datetime.strptime(value, fmt)
            return parsed.strftime("%H:%M:%S")
        except ValueError:
            continue

    raise ValueError("Time of birth must be in HH:MM or HH:MM:SS format.")


def validate_lat_long(lat: Any, lon: Any) -> tuple[float, float]:
    """
    Validates latitude and longitude values and returns normalized floats.

    Latitude must be between -90 and 90.
    Longitude must be between -180 and 180.
    """
    try:
        latitude = float(_normalize_scalar(lat))
    except ValueError as exc:
        raise ValueError("Latitude must be a valid number.") from exc

    try:
        longitude = float(_normalize_scalar(lon))
    except ValueError as exc:
        raise ValueError("Longitude must be a valid number.") from exc

    if not -90.0 <= latitude <= 90.0:
        raise ValueError("Latitude must be between -90 and 90.")
    if not -180.0 <= longitude <= 180.0:
        raise ValueError("Longitude must be between -180 and 180.")

    return latitude, longitude


def validate_user_input(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validates and normalizes user input before calculation or persistence.

    Required fields:
    - name
    - dob
    - tob
    - place
    - latitude
    - longitude
    """
    if not isinstance(data, dict):
        raise ValueError("User input must be provided as a dictionary.")

    name = str(data.get("name", "")).strip()
    if not name:
        raise ValueError("Name is required.")

    place = str(data.get("place", "")).strip()
    if not place:
        raise ValueError("Place is required.")

    dob = validate_date(data.get("dob"))
    tob = validate_time(data.get("tob"))
    latitude, longitude = validate_lat_long(data.get("latitude"), data.get("longitude"))

    validated = dict(data)
    validated.update(
        {
            "name": name,
            "dob": dob,
            "tob": tob,
            "place": place,
            "latitude": latitude,
            "longitude": longitude,
            "state": str(data.get("state", "")).strip() or None,
            "city": str(data.get("city", "")).strip() or None,
        }
    )
    return validated
