import ujson
import os

_CREDS_FILE = 'wifi_creds.json'


def load_all() -> dict:
    """Return the full credentials database as {ssid: password}."""
    try:
        with open(_CREDS_FILE, 'r') as f:
            data = ujson.load(f)
            if isinstance(data, dict):
                return data
    except (OSError, ValueError):
        pass
    return {}


def add_credential(ssid: str, password: str) -> None:
    """Add or update a WiFi credential in the database."""
    creds = load_all()
    creds[ssid] = password
    with open(_CREDS_FILE, 'w') as f:
        ujson.dump(creds, f)


def find_known_network(nearby_ssids: list) -> tuple:
    """Given an ordered list of nearby SSIDs (strongest signal first), return (ssid, password)
    for the first one that has saved credentials. Returns (None, None) if no match."""
    creds = load_all()
    for ssid in nearby_ssids:
        if ssid in creds:
            return ssid, creds[ssid]
    return None, None
