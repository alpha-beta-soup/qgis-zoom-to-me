"""Pure helpers for Zoom to Me. No QGIS imports here so this module is testable
with plain Python."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from enum import Enum


class Source(Enum):
    GPS = "gps"
    IP = "ip"


# Scale the canvas zooms to when the source gives no accuracy figure.
DEFAULT_SCALE = {
    Source.GPS: 5000,
    Source.IP: 100000,
}

IPINFO_URL = "https://ipinfo.io/json"


@dataclass(frozen=True)
class Location:
    lon: float
    lat: float
    source: Source
    label: str
    accuracy_m: float | None = None

    def scale(self) -> float:
        """Map scale denominator appropriate for how precise this fix is.

        A GPS fix with a known horizontal accuracy zooms so the error circle is
        a sensible fraction of the view. Everything else uses a fixed default.
        """
        if self.source is Source.GPS and self.accuracy_m is not None:
            return max(1000.0, self.accuracy_m * 200.0)
        return float(DEFAULT_SCALE[self.source])

    def describe(self) -> str:
        if self.source is Source.GPS:
            if self.accuracy_m is not None:
                return f"Zoomed to GPS fix, accuracy about {self.accuracy_m:.0f} m"
            return "Zoomed to GPS fix"
        return f"Zoomed to {self.label} from your IP address (city-level accuracy at best)"


def parse_ipinfo(body: bytes | str) -> Location:
    """Turn an ipinfo.io JSON response into a Location.

    Raises ValueError with a user-readable message when the response has no
    usable coordinates, for example on a private network ("bogon") or when the
    service returns an error document.
    """
    if isinstance(body, bytes):
        body = body.decode("utf-8", errors="replace")
    try:
        data = json.loads(body)
    except json.JSONDecodeError as exc:
        raise ValueError("ipinfo.io returned something that is not JSON") from exc
    if not isinstance(data, dict):
        raise ValueError("ipinfo.io returned an unexpected document")
    if data.get("bogon"):
        raise ValueError("ipinfo.io could not see a public IP address for this machine")
    if "error" in data:
        msg = data["error"]
        if isinstance(msg, dict):
            msg = msg.get("message") or msg.get("title") or str(msg)
        raise ValueError(f"ipinfo.io error: {msg}")
    loc = data.get("loc")
    if not isinstance(loc, str) or "," not in loc:
        raise ValueError("ipinfo.io response has no location for this IP address")
    try:
        lat_s, lon_s = loc.split(",", 1)
        lat, lon = float(lat_s), float(lon_s)
    except ValueError as exc:
        raise ValueError(f"ipinfo.io returned an unparseable location {loc!r}") from exc
    if not (math.isfinite(lat) and math.isfinite(lon)):
        raise ValueError(f"ipinfo.io returned a non-finite location {loc!r}")
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise ValueError(f"ipinfo.io returned an out-of-range location {loc!r}")

    parts = [data.get(k) for k in ("city", "region", "country")]
    label = ", ".join(p for p in parts if isinstance(p, str) and p) or "an unnamed place"
    return Location(lon=lon, lat=lat, source=Source.IP, label=label)
