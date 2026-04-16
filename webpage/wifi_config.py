import ujson
import os

_CREDS_FILE = 'wifi_creds.json'


def save_credentials(ssid: str, password: str) -> None:
    with open(_CREDS_FILE, 'w') as f:
        ujson.dump({'ssid': ssid, 'password': password}, f)


def load_credentials() -> tuple:
    """Returns (ssid, password) or (None, None) if no saved credentials."""
    try:
        with open(_CREDS_FILE, 'r') as f:
            data = ujson.load(f)
            ssid = data.get('ssid', '')
            pwd = data.get('password', '')
            if ssid:
                return ssid, pwd
    except (OSError, ValueError):
        pass
    return None, None


def delete_credentials() -> None:
    try:
        os.remove(_CREDS_FILE)
    except OSError:
        pass
