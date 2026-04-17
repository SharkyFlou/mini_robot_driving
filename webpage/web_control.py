import gc
import asyncio
import _thread
from machine import Pin

from leds.rgb_led import RGBLed
from leds.serial_leds import SerialLeds
from motors.engines import Engines
import sys
from music.song_titles import song_titles
from music.play import _async_sleep_ms, is_song_playing, playsong_async, set_volume, stop_song
from pins import MUSIC_STOP_BUTTON_PIN
from screen.oled import OLED
import os
import network
import machine as _machine
from webpage.microdot import Microdot, Response
from webpage.wifi_config import add_credential, load_all
import ujson

SETUP_AP_SSID: str = "Rob_Charly"
DEFAULT_MAX_SPEED: int = 220

# ThingSpeak — only active in station mode (robot connected to external WiFi).
# field1=distance_cm  field2=light_%  field3=accel_x  field4=accel_y  field5=accel_z  field6=temp_c
THINGSPEAK_WRITE_API_KEY: str = "J5D4CNVPH82HT6DM"
THINGSPEAK_READ_API_KEY: str = "KJ1WAN2QZ1VT9Q4L"
THINGSPEAK_CHANNEL_ID: str = "3334331"
THINGSPEAK_INTERVAL_S: int = 30  # free plan minimum: 15 s

MODE_LOADING = "loading"
MODE_WAITING = "waiting"
MODE_DEBUGGING = "debugging"
MODE_LEDS = "leds"
MODE_MOTORS = "motors"
MODE_SCREEN = "screen"
MODE_BUZZER = "buzzer"

hardware: dict[str, SerialLeds | Engines | None] = {
    "serial_leds": None,
    "motors": None,
}

drive_state: dict[str, int | str] = {
    "last_seq": -1,
    "session": "",
}

state: dict[str, str] = {
    "led": "off",
    "motor": "stopped",
    "screen": "ready",
    "mode": MODE_LOADING,
    "max_speed": str(DEFAULT_MAX_SPEED),
    "song": "none",
}

WIFI_MODE: str = "setup"
WIFI_AP_PASSWORD: str = ""
WIFI_STA_IP: str = ""

rgb_led = RGBLed()

music_stop_button: Pin | None = None
music_stop_button_task_started: bool = False

display: OLED | None = None
try:
    display = OLED()
except (OSError, RuntimeError) as exc:
    print("OLED init failed:", exc)


def screen_status(line_1: str, line_2: str = "", line_3: str = "") -> None:
    """Safely write status text on OLED if the display is available."""
    if display is None:
        return
    try:
        display.set_text(line_1, line_2, line_3)
    except (OSError, RuntimeError) as exc:
        print("OLED write failed:", exc)


def _flash_mode_indicator(mode: str) -> None:
    """Set single RGB LED by mode, then turn it off."""
    if mode == MODE_LOADING:
        rgb_led.set_blue()
    elif mode == MODE_WAITING:
        rgb_led.set_white()
    elif mode == MODE_DEBUGGING:
        rgb_led.set_purple()
    elif mode == MODE_LEDS:
        rgb_led.set_green()
    elif mode == MODE_MOTORS:
        rgb_led.set_red()
    elif mode == MODE_SCREEN:
        rgb_led.set_cyan()
    elif mode == MODE_BUZZER:
        rgb_led.set_yellow()
    else:
        rgb_led.set_off()


def _speed_to_permille(speed_value: int) -> int:
    permille: int = (speed_value * 1000) // 400
    if permille < 1:
        return 1
    if permille > 1000:
        return 1000
    return permille


def _clamp_speed(speed_value: int) -> int:
    if speed_value < 70:
        return 70
    if speed_value > 400:
        return 400
    return speed_value


def set_mode(mode: str) -> None:
    """Update current mode and flash the single RGB mode indicator."""
    if state["mode"] == mode:
        return
    state["mode"] = mode
    _flash_mode_indicator(mode)


def _gen_ap_password() -> str:
    """Generate a random 8-character lowercase alphanumeric password using hardware entropy."""
    chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
    try:
        raw = os.urandom(8)
        return ''.join(chars[b % len(chars)] for b in raw)
    except Exception:
        import random
        return ''.join(random.choice(chars) for _ in range(8))


def _start_ap(ssid: str, password: str) -> None:
    """Activate the WiFi Access Point."""
    ap = network.WLAN(network.AP_IF)
    ap.active(True)
    if password:
        ap.config(essid=ssid, authmode=network.AUTH_WPA_PSK, password=password)
    else:
        ap.config(essid=ssid, authmode=network.AUTH_OPEN)


def _try_sta_connect(ssid: str, password: str, timeout: int = 15) -> tuple:
    """Blocking STA connection attempt (for use before the event loop starts).

    Returns (True, ip_address) on success or (False, '') on failure.
    """
    import time
    sta = network.WLAN(network.STA_IF)
    was_active = sta.active()
    sta.active(True)
    if not was_active:
        time.sleep(0.3)  # let radio settle after first activation
    sta.connect(ssid, password)
    for i in range(timeout * 2):
        time.sleep(0.5)
        status = sta.status()
        if status == network.STAT_GOT_IP:
            return True, sta.ifconfig()[0]
        # Wait at least 2 s before treating failure as terminal — the radio
        # can report transient CONNECT_FAIL right after sta.connect().
        if i >= 4 and status in (network.STAT_WRONG_PASSWORD, network.STAT_NO_AP_FOUND, network.STAT_CONNECT_FAIL):
            sta.active(False)
            return False, ''
    sta.active(False)
    return False, ''


async def _try_sta_connect_async(ssid: str, password: str, timeout: int = 15) -> tuple:
    """Async STA connection attempt (for use inside the event loop).

    Returns (True, ip_address) on success or (False, '') on failure.
    """
    sta = network.WLAN(network.STA_IF)
    was_active = sta.active()
    sta.active(True)
    if not was_active:
        await asyncio.sleep_ms(300)  # let radio settle after activation
    try:
        sta.disconnect()  # clear stale state from previous boot attempt
    except Exception:
        pass
    sta.connect(ssid, password)
    for i in range(timeout * 5):
        await asyncio.sleep_ms(200)
        status = sta.status()
        if status == network.STAT_GOT_IP:
            return True, sta.ifconfig()[0]
        # Wait at least 2 s before treating failure as terminal — the radio
        # can report transient CONNECT_FAIL while AP is also active.
        if i >= 10 and status in (network.STAT_WRONG_PASSWORD, network.STAT_NO_AP_FOUND, network.STAT_CONNECT_FAIL):
            sta.active(False)
            return False, ''
    sta.active(False)
    return False, ''


async def _reset_after_delay_ms(ms: int) -> None:
    """Reboot the device after a delay to allow the HTTP response to flush."""
    await asyncio.sleep_ms(ms)
    _machine.reset()


def _scan_wifi() -> list:
    """Scan for WiFi networks. Returns list of (ssid, rssi) sorted by signal strength (strongest first)."""
    import time
    sta = network.WLAN(network.STA_IF)
    was_active = sta.active()
    sta.active(True)
    if not was_active:
        time.sleep(0.3)  # let radio settle after first activation
    results = []
    try:
        entries = sta.scan()
        seen = set()
        for entry in entries:
            ssid = entry[0]
            if isinstance(ssid, bytes):
                try:
                    ssid = ssid.decode('utf-8')
                except Exception:
                    ssid = ssid.decode('latin-1')
            ssid = ssid.strip()
            rssi = entry[3]
            if ssid and ssid not in seen:
                seen.add(ssid)
                results.append((ssid, rssi))
        results.sort(key=lambda x: -x[1])
    except Exception as exc:
        print("WiFi scan error:", exc)
    return results


set_mode(MODE_LOADING)

# Always start with AP disabled. This prevents any stale or default AP from
# being reachable before we have decided which mode to use. In station mode
# the AP will never be re-enabled, so the robot is only reachable via the
# external WiFi. In setup mode, _start_ap() will re-enable it deliberately.
network.WLAN(network.AP_IF).active(False)

_all_creds = load_all()
if _all_creds:
    # Scan to rank attempts by signal strength, but always try ALL saved
    # credentials — the scan can miss networks right after a reset (radio timing).
    screen_status("Scanning", "WiFi...", "")
    _nearby = _scan_wifi()
    _nearby_set = set(s for s, _ in _nearby)
    _nearby_order = [s for s, _ in _nearby if s in _all_creds]

    # Attempt order: scan-visible known networks first (full timeout),
    # then saved-but-not-visible as fallback (short probe timeout).
    _attempt_order = _nearby_order[:]
    for _s in _all_creds:
        if _s not in _nearby_set:
            _attempt_order.append(_s)

    for _ssid in _attempt_order:
        _timeout = 12 if _ssid in _nearby_set else 5
        screen_status("Connecting", _ssid[:16], "...")
        _sta_ok, _sta_ip = _try_sta_connect(_ssid, _all_creds[_ssid], _timeout)
        if _sta_ok:
            WIFI_MODE = "station"
            WIFI_STA_IP = _sta_ip
            screen_status("Connected!", _sta_ip, "Port 80")
            break

if WIFI_MODE == "setup":
    WIFI_AP_PASSWORD = _gen_ap_password()
    _start_ap(SETUP_AP_SSID, WIFI_AP_PASSWORD)
    screen_status(f"WiFi:{SETUP_AP_SSID}", WIFI_AP_PASSWORD, "192.168.4.1")

app: Microdot = Microdot()
Response.default_content_type = "text/html"

# Keep buzzer audible by default when triggering songs from the web UI.
set_volume(2000)

try:
    music_stop_button = Pin(MUSIC_STOP_BUTTON_PIN, Pin.IN, Pin.PULL_UP)
except (ValueError, TypeError):
    music_stop_button = None


def ensure_leds_mode() -> None:
    """Ensure serial LEDs are active and motors are released."""
    if hardware["motors"] is not None:
        hardware["motors"].release()
        hardware["motors"] = None
        state["motor"] = "stopped"

    if hardware["serial_leds"] is None:
        hardware["serial_leds"] = SerialLeds()
        hardware["serial_leds"].set_color_for_all(0, 0, 0)
        hardware["serial_leds"].send_setting()

    set_mode(MODE_LEDS)


def ensure_motor_mode() -> None:
    """Ensure motor PWM resources are active and serial LEDs are neutral."""
    if hardware["serial_leds"] is not None:
        hardware["serial_leds"].set_color_for_all(0, 0, 0)
        hardware["serial_leds"].send_setting()

    if hardware["motors"] is None:
        set_mode(MODE_MOTORS)
        hardware["motors"] = Engines()


def enter_screen_mode() -> None:
    """Placeholder for screen mode."""
    set_mode(MODE_SCREEN)



def _get_song_title(song_index: int) -> str:
    if 0 <= song_index < len(song_titles):
        return song_titles[song_index]
    return "none"


def _load_song(index: int) -> list:
    """Load a single song from its individual file, then evict it from the module cache."""
    mod_name = "music.songs.song_%02d" % index
    mod = __import__(mod_name, None, None, ("data",))
    song_data = mod.data
    sys.modules.pop(mod_name, None)
    gc.collect()
    return song_data


async def _monitor_music_stop_button() -> None:
    """Poll robot stop button and interrupt song playback when pressed."""
    if music_stop_button is None:
        return

    pressed_cycles: int = 0
    while True:
        if music_stop_button.value() == 0:
            pressed_cycles += 1
            if pressed_cycles >= 2:
                if is_song_playing():
                    stop_song()
                    state["song"] = "stopped"
                    set_mode(MODE_WAITING)
                    screen_status("Music", "Stopped", "button")

                while music_stop_button.value() == 0:
                    await _async_sleep_ms(30)
                pressed_cycles = 0
        else:
            pressed_cycles = 0

        await _async_sleep_ms(30)


def _ensure_music_stop_task() -> None:
    """Start the hardware stop-button monitor exactly once."""
    global music_stop_button_task_started
    if music_stop_button_task_started or music_stop_button is None:
        return
    asyncio.create_task(_monitor_music_stop_button())
    music_stop_button_task_started = True


_sensor_ultrasound = None
_sensor_photo = None
_sensor_mpu = None
_sensors_ready: bool = False

_thingspeak = None
_thingspeak_task_started: bool = False
_ts_sending: bool = False
_ts_enabled: bool = False  # off by default — user must enable from the UI


def _ensure_sensors() -> None:
    """Lazily initialise all sensors on first use."""
    global _sensor_ultrasound, _sensor_photo, _sensor_mpu, _sensors_ready
    if _sensors_ready:
        return
    _sensors_ready = True
    try:
        from sensors.ultrasound import HCSR04Nonblocking
        _sensor_ultrasound = HCSR04Nonblocking()
    except Exception as exc:
        print("Ultrasound init failed:", exc)
    try:
        from sensors.photo_resistor import PhotoResistor
        _sensor_photo = PhotoResistor()
    except Exception as exc:
        print("PhotoResistor init failed:", exc)
    try:
        from sensors.mpu6050 import MPU6050
        from machine import SoftI2C, Pin
        i2c = display.i2c if display is not None else SoftI2C(scl=Pin(7), sda=Pin(6))
        _sensor_mpu = MPU6050(i2c)
    except Exception as exc:
        print("MPU6050 init failed:", exc)
    gc.collect()


def _init_thingspeak() -> None:
    """Initialise the ThingSpeak client. Called only when in station mode."""
    global _thingspeak
    if WIFI_MODE != "station" or not THINGSPEAK_WRITE_API_KEY:
        return
    try:
        from thingspeak.u_thing_speak import ThingSpeak
        _thingspeak = ThingSpeak()
        _thingspeak.set_write_api_key(THINGSPEAK_WRITE_API_KEY)
        print("ThingSpeak ready")
    except Exception as exc:
        print("ThingSpeak init failed:", exc)


def _thingspeak_send_bg(data: dict) -> None:
    """Blocking HTTP POST to ThingSpeak — runs in a separate thread so the
    asyncio event loop is never stalled."""
    global _ts_sending
    try:
        _thingspeak.send_data(data)
    except Exception as exc:
        print("ThingSpeak send error:", exc)
    finally:
        _ts_sending = False
        gc.collect()


async def _thingspeak_loop() -> None:
    """Collect sensor readings every interval, then fire a background thread
    for the blocking HTTP send.  The event loop stays free at all times."""
    global _ts_sending
    while True:
        await asyncio.sleep(THINGSPEAK_INTERVAL_S)
        if _thingspeak is None or _ts_sending or not _ts_enabled:
            continue
        _ensure_sensors()
        data = {}
        try:
            if _sensor_ultrasound is not None:
                _sensor_ultrasound.reset_flag()
                _sensor_ultrasound.start_measurement()

            if _sensor_photo is not None:
                result = _sensor_photo.measure()
                data["field2"] = round(result[2], 0)  # light_percent

            if _sensor_mpu is not None:
                d = _sensor_mpu.read_all_sensors()
                data["field3"] = round(d["ax"], 3)  # accel_x_g
                data["field4"] = round(d["ay"], 3)  # accel_y_g
                data["field5"] = round(d["az"], 3)  # accel_z_g
                data["field6"] = round(d["temp"], 1)  # temp_c

            if _sensor_ultrasound is not None:
                for _ in range(4):
                    await asyncio.sleep_ms(10)
                    if _sensor_ultrasound.get_flag():
                        break
                if _sensor_ultrasound.get_flag():
                    raw_dist = _sensor_ultrasound.return_distance_cm()
                    if raw_dist >= 0:
                        data["field1"] = round(raw_dist, 1)  # distance_cm

            if data:
                _ts_sending = True
                _thread.start_new_thread(_thingspeak_send_bg, (data,))
        except Exception as exc:
            print("ThingSpeak prepare error:", exc)
        gc.collect()


def _ensure_thingspeak_task() -> None:
    """Start the ThingSpeak background task exactly once."""
    global _thingspeak_task_started
    if _thingspeak_task_started or _thingspeak is None:
        return
    asyncio.create_task(_thingspeak_loop())
    _thingspeak_task_started = True


def _hsv_to_rgb(h: int, s: float, v: float) -> tuple:
    """Convert HSV (h: 0-359, s/v: 0.0-1.0) to an (r, g, b) tuple of 0-255 ints."""
    h = h % 360
    i = h // 60
    f = (h / 60.0) - i
    p = int(v * (1.0 - s) * 255)
    q = int(v * (1.0 - s * f) * 255)
    t = int(v * (1.0 - s * (1.0 - f)) * 255)
    vi = int(v * 255)
    if i == 0: return vi, t, p
    if i == 1: return q, vi, p
    if i == 2: return p, vi, t
    if i == 3: return p, q, vi
    if i == 4: return t, p, vi
    return vi, p, q


async def _rainbow_loop() -> None:
    """Slowly cycle serial LEDs through all hues until the LED state changes."""
    hue = 0
    while state["led"] == "rainbow":
        serial_leds = hardware["serial_leds"]
        if serial_leds is not None:
            r, g, b = _hsv_to_rgb(hue, 1.0, 0.5)
            serial_leds.set_color_for_all(r, g, b)
            serial_leds.send_setting()
        hue = (hue + 1) % 360
        await asyncio.sleep_ms(15)


def apply_led_state(led_state: str) -> None:
    """Apply one named serial LED strip color preset."""
    serial_leds = hardware["serial_leds"]
    if serial_leds is None:
        return

    if led_state == "rainbow":
        asyncio.create_task(_rainbow_loop())
        return

    if led_state == "red":
        serial_leds.set_color_for_all(255, 0, 0)
    elif led_state == "green":
        serial_leds.set_color_for_all(0, 255, 0)
    elif led_state == "blue":
        serial_leds.set_color_for_all(0, 0, 255)
    elif led_state == "yellow":
        serial_leds.set_color_for_all(255, 255, 0)
    elif led_state == "purple":
        serial_leds.set_color_for_all(255, 0, 255)
    elif led_state == "cyan":
        serial_leds.set_color_for_all(0, 255, 255)
    elif led_state == "white":
        serial_leds.set_color_for_all(255, 255, 255)
    else:
        serial_leds.set_color_for_all(0, 0, 0)

    serial_leds.send_setting()


def apply_motor_direction(direction: str) -> None:
    """Compatibility mapping from cardinal commands to analog vector drive."""
    if direction == "up":
        apply_motor_vector(0, 100)
        return
    if direction == "down":
        apply_motor_vector(0, -100)
        return
    if direction == "left":
        apply_motor_vector(-100, 0)
        return
    if direction == "right":
        apply_motor_vector(100, 0)
        return
    apply_motor_vector(0, 0)


def apply_motor_vector(x_percent: int, y_percent: int) -> None:
    """Apply analog drive vector where x is turn and y is forward power."""
    motors = hardware["motors"]
    if motors is None:
        return

    if x_percent > 100:
        x_percent = 100
    elif x_percent < -100:
        x_percent = -100

    if y_percent > 100:
        y_percent = 100
    elif y_percent < -100:
        y_percent = -100

    x: float = x_percent / 100.0
    y: float = y_percent / 100.0
    deadzone: float = 0.08

    if (-deadzone < x < deadzone) and (-deadzone < y < deadzone):
        motors.coast()
        state["motor"] = "stopped"
        return

    # Differential drive mix: forward/backward from y and turning from x.
    left: float = y + x
    right: float = y - x

    scale: float = max(abs(left), abs(right), 1.0)
    left = left / scale
    right = right / scale

    max_speed_permille: int = _speed_to_permille(int(state["max_speed"]))
    left_power: int = int(abs(left) * max_speed_permille)
    right_power: int = int(abs(right) * max_speed_permille)

    if left_power < 1 and abs(left) > deadzone:
        left_power = 1
    if right_power < 1 and abs(right) > deadzone:
        right_power = 1

    if left > deadzone:
        motors.move_left_forward(left_power)
    elif left < -deadzone:
        motors.move_left_backward(left_power)
    else:
        motors.coast_left()

    if right > deadzone:
        motors.move_right_forward(right_power)
    elif right < -deadzone:
        motors.move_right_backward(right_power)
    else:
        motors.coast_right()

    state["motor"] = "x=" + str(x_percent) + " y=" + str(y_percent)


def render_setup_page(error: str = ""):
    yield """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Robot Charly - WiFi Setup</title>
  <style>
    body { font-family: Arial, sans-serif; background: #f4f7fb; margin: 0; padding: 40px 20px; color: #1f2937; }
    .card { max-width: 420px; margin: 0 auto; background: #fff; padding: 24px; border-radius: 12px; box-shadow: 0 8px 20px rgba(0,0,0,0.08); }
    h1 { margin-top: 0; font-size: 22px; color: #1e3a8a; }
    p { color: #475569; font-size: 14px; }
    .section-label { display: block; margin: 16px 0 6px; font-weight: bold; font-size: 12px; color: #374151; text-transform: uppercase; letter-spacing: .05em; }
    .scan-row { display: flex; gap: 8px; }
    select { flex: 1; padding: 10px; border: 1px solid #cbd5e1; border-radius: 8px; font-size: 14px; background: #fff; min-width: 0; }
    .btn-refresh { padding: 10px 14px; background: #475569; color: #fff; border: none; border-radius: 8px; font-size: 13px; font-weight: bold; cursor: pointer; white-space: nowrap; flex-shrink: 0; }
    .btn-refresh:disabled { opacity: .5; cursor: default; }
    .divider { border: none; border-top: 1px solid #e2e8f0; margin: 18px 0 4px; }
    label { display: block; margin: 14px 0 4px; font-size: 14px; font-weight: bold; }
    input[type=text], input[type=password] { width: 100%; box-sizing: border-box; padding: 10px; border: 1px solid #cbd5e1; border-radius: 8px; font-size: 15px; }
    .btn-connect { margin-top: 20px; width: 100%; padding: 12px; background: #2563eb; color: #fff; border: none; border-radius: 8px; font-size: 16px; font-weight: bold; cursor: pointer; }
    .error { color: #dc2626; background: #fef2f2; border: 1px solid #fca5a5; border-radius: 8px; padding: 10px; margin-bottom: 14px; font-size: 14px; }
    .hint { font-size: 12px; color: #94a3b8; margin-top: 20px; text-align: center; }
  </style>
</head>
<body>
  <div class="card">
    <h1>WiFi Setup</h1>
    <p>Connect the robot to your WiFi network to access the internet.</p>"""
    if error:
        yield '\n    <div class="error">'
        yield error
        yield '</div>'
    yield """
    <span class="section-label">Available Networks</span>
    <div class="scan-row">
      <select id="net-list" onchange="pickNetwork(this.value)">
        <option value="">-- Scanning... --</option>
      </select>
      <button class="btn-refresh" id="btn-refresh" type="button" onclick="doScan()">Refresh</button>
    </div>
    <hr class="divider">
    <form action="/wifi_setup" method="post">
      <label for="ssid">Network Name (SSID)</label>
      <input type="text" id="ssid" name="ssid" placeholder="Enter network name" required autocomplete="off">
      <label for="password">Password</label>
      <input type="password" id="password" name="password" placeholder="Password" autocomplete="off">
      <button class="btn-connect" type="submit">Connect</button>
    </form>
    <p class="hint">Robot_Charly &bull; 192.168.4.1</p>
  </div>
<script>
  function pickNetwork(ssid) {
    if (ssid) { document.getElementById('ssid').value = ssid; }
  }
  function doScan() {
    var sel = document.getElementById('net-list');
    var btn = document.getElementById('btn-refresh');
    sel.innerHTML = '<option value="">-- Scanning... --</option>';
    btn.disabled = true;
    fetch('/api/scan_wifi')
      .then(function(r) { return r.json(); })
      .then(function(nets) {
        if (nets.length === 0) {
          sel.innerHTML = '<option value="">-- No networks found --</option>';
        } else {
          var html = '<option value="">-- Select a network --</option>';
          nets.forEach(function(n) {
            html += '<option value="' + n.ssid.replace(/&/g,'&amp;').replace(/"/g,'&quot;') + '">'
                  + n.ssid.replace(/&/g,'&amp;').replace(/</g,'&lt;')
                  + ' (' + n.rssi + ' dBm)</option>';
          });
          sel.innerHTML = html;
        }
      })
      .catch(function() {
        sel.innerHTML = '<option value="">-- Scan failed --</option>';
      })
      .finally(function() { btn.disabled = false; });
  }
  doScan();
</script>
</body>
</html>"""


def render_connecting_page(ip: str):
    yield """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta http-equiv="refresh" content="8;url=http://"""
    yield ip
    yield """/">
  <title>Connected!</title>
  <style>
    body { font-family: Arial, sans-serif; background: #f0fdf4; margin: 0; padding: 40px 20px; text-align: center; color: #14532d; }
    .card { max-width: 400px; margin: 0 auto; background: #fff; padding: 28px; border-radius: 12px; box-shadow: 0 8px 20px rgba(0,0,0,0.08); }
    h1 { color: #16a34a; margin-top: 0; }
    .ip { font-size: 22px; font-weight: bold; color: #1e40af; margin: 16px 0; }
    p { color: #475569; font-size: 14px; }
  </style>
</head>
<body>
  <div class="card">
    <h1>Connected!</h1>
    <p>The robot is connected to WiFi and is restarting...</p>
    <div class="ip">"""
    yield ip
    yield """</div>
    <p>New address available in a few seconds.</p>
    <p>Redirecting to <strong>http://"""
    yield ip
    yield """/</strong></p>
  </div>
</body>
</html>"""


def _stream_html(path: str):
    """Stream an HTML file from the filesystem in 1024-byte chunks.
    Only one chunk is in RAM at a time — the file itself stays on flash."""
    try:
        with open(path) as f:
            while True:
                chunk = f.read(1024)
                if not chunk:
                    break
                yield chunk
    except OSError as exc:
        yield "<p>Page load error: " + str(exc) + "</p>"


@app.route("/")
async def index(_request):
    if WIFI_MODE == "setup":
        return Response(render_setup_page())
    _ensure_music_stop_task()
    _ensure_thingspeak_task()
    ensure_leds_mode()
    set_mode(MODE_WAITING)
    screen_status("Web UI", "Connected", "")
    return Response(_stream_html("webpage/templates/main.html"))


@app.route("/wifi_setup", methods=["POST"])
async def wifi_setup_route(request):
    ssid: str = (request.form.get("ssid") or "").strip()
    password: str = (request.form.get("password") or "").strip()

    if not ssid:
        return Response(render_setup_page("Network name is required."))

    screen_status("Connecting...", ssid[:16], "")
    success, ip = await _try_sta_connect_async(ssid, password)

    if success:
        add_credential(ssid, password)
        screen_status("Connected!", ip, "Restarting...")
        asyncio.create_task(_reset_after_delay_ms(1500))
        return Response(render_connecting_page(ip))

    screen_status(SETUP_AP_SSID, WIFI_AP_PASSWORD, "192.168.4.1")
    return Response(render_setup_page("Connection failed. Check the SSID and password."))


@app.route("/api/scan_wifi")
async def api_scan_wifi(_request):
    """Scan for available WiFi networks and return them as JSON."""
    if WIFI_MODE != "setup":
        return Response('[]', headers={"Content-Type": "application/json"})
    networks = _scan_wifi()
    payload = ujson.dumps([{"ssid": s, "rssi": r} for s, r in networks])
    return Response(payload, headers={"Content-Type": "application/json"})


@app.route("/set_led", methods=["POST"])
async def set_led(request):
    _ensure_music_stop_task()
    ensure_leds_mode()
    requested_state: str = request.form.get("state", "off")
    state["led"] = requested_state
    apply_led_state(requested_state)
    screen_status("LEDS", requested_state, "")
    return "ok"


@app.route("/move", methods=["POST"])
async def move(request):
    _ensure_music_stop_task()
    ensure_motor_mode()
    direction: str = request.form.get("direction", "stop")
    apply_motor_direction(direction)
    return "ok"


@app.route("/api/move", methods=["POST"])
async def api_move(request):
    """Handle low-latency motor commands from joystick JS."""
    _ensure_music_stop_task()
    ensure_motor_mode()
    direction: str = request.form.get("direction", "stop")
    apply_motor_direction(direction)
    return "ok"


@app.route("/api/drive", methods=["POST"])
async def api_drive(request):
    """Handle analog joystick vector commands from web UI."""
    _ensure_music_stop_task()
    ensure_motor_mode()

    session_id: str = request.form.get("sid", "")
    if session_id != drive_state["session"]:
        drive_state["session"] = session_id
        drive_state["last_seq"] = -1

    try:
        sequence_number: int = int(request.form.get("seq", -1))
    except ValueError:
        sequence_number = -1

    # Ignore stale commands that were delayed in transport or processing.
    if sequence_number >= 0:
        if sequence_number <= drive_state["last_seq"]:
            return "stale"
        drive_state["last_seq"] = sequence_number

    try:
        x_percent: int = int(request.form.get("x", 0))
    except ValueError:
        x_percent = 0

    try:
        y_percent: int = int(request.form.get("y", 0))
    except ValueError:
        y_percent = 0

    apply_motor_vector(x_percent, y_percent)
    return "ok"


@app.route("/api/state")
async def api_state(_request):
    """Return all robot state needed by the static HTML page on first load."""
    payload = ujson.dumps({
        "motor": state["motor"],
        "max_speed": state["max_speed"],
        "mode": state["mode"],
        "led": state["led"],
        "song": state["song"],
        "screen": state["screen"],
        "songs": song_titles,
        "ts_read_key": THINGSPEAK_READ_API_KEY,
        "ts_channel_id": THINGSPEAK_CHANNEL_ID,
        "ts_enabled": _ts_enabled,
    })
    return Response(payload, headers={"Content-Type": "application/json"})


@app.route("/api/thingspeak", methods=["POST"])
async def api_thingspeak_toggle(request):
    global _ts_enabled
    _ts_enabled = request.form.get("enabled", "0") == "1"
    return Response(ujson.dumps({"enabled": _ts_enabled}),
                    headers={"Content-Type": "application/json"})


@app.route("/api/sensors")
async def api_sensors(_request):
    """Return a JSON snapshot of all available sensors."""
    _ensure_sensors()

    dist_cm = None
    if _sensor_ultrasound is not None:
        try:
            _sensor_ultrasound.reset_flag()
            _sensor_ultrasound.start_measurement()
        except Exception:
            pass

    light_raw = light_v = light_pct = None
    if _sensor_photo is not None:
        try:
            result = _sensor_photo.measure()
            light_raw = result[0]
            light_v = result[1]
            light_pct = result[2]
        except Exception:
            pass

    ax = ay = az = gx = gy = gz = temp_c = None
    if _sensor_mpu is not None:
        try:
            d = _sensor_mpu.read_all_sensors()
            ax = d["ax"]; ay = d["ay"]; az = d["az"]
            gx = d["gx"]; gy = d["gy"]; gz = d["gz"]
            temp_c = d["temp"]
        except Exception:
            pass

    if _sensor_ultrasound is not None:
        for _ in range(4):
            await _async_sleep_ms(10)
            if _sensor_ultrasound.get_flag():
                break
        if _sensor_ultrasound.get_flag():
            raw_dist = _sensor_ultrasound.return_distance_cm()
            if raw_dist >= 0:
                dist_cm = raw_dist

    def _r(v, n):
        return round(v, n) if v is not None else None

    payload = ujson.dumps({
        "distance_cm": _r(dist_cm, 1),
        "light_percent": _r(light_pct, 0),
        "light_voltage": _r(light_v, 2),
        "light_raw": light_raw,
        "accel_x_g": _r(ax, 3),
        "accel_y_g": _r(ay, 3),
        "accel_z_g": _r(az, 3),
        "gyro_x_dps": _r(gx, 1),
        "gyro_y_dps": _r(gy, 1),
        "gyro_z_dps": _r(gz, 1),
        "temp_c": _r(temp_c, 1),
    })
    return Response(payload, headers={"Content-Type": "application/json"})


@app.route("/set_max_speed", methods=["POST"])
async def set_max_speed(request):
    _ensure_music_stop_task()
    try:
        max_speed: int = int(request.form.get("max_speed", state["max_speed"]))
    except ValueError:
        max_speed = DEFAULT_MAX_SPEED

    max_speed = _clamp_speed(max_speed)

    state["max_speed"] = str(max_speed)
    screen_status("Motors", "Max speed", str(max_speed))
    return "ok"


@app.route("/play_song", methods=["POST"])
async def play_song(request):
    _ensure_music_stop_task()
    selected_index_str: str = request.form.get("song_index", "0")
    try:
        selected_index: int = int(selected_index_str)
    except ValueError:
        selected_index = 0

    if selected_index < 0 or selected_index >= len(song_titles):
        selected_index = 0

    selected_song = _load_song(selected_index)
    state["song"] = _get_song_title(selected_index)
    if is_song_playing():
        stop_song()
        await _async_sleep_ms(40)
    set_mode(MODE_BUZZER)
    screen_status("Music", "Playing", state["song"][:16])
    asyncio.create_task(playsong_async(selected_song))
    return "ok"


@app.route("/stop_song", methods=["POST"])
async def stop_song_route(_request):
    _ensure_music_stop_task()
    stop_song()
    state["song"] = "stopped"
    set_mode(MODE_WAITING)
    screen_status("Music", "Stopped", "web")
    return "ok"


@app.route("/stop_motors", methods=["POST"])
async def stop_motors(_request):
    _ensure_music_stop_task()
    ensure_leds_mode()
    set_mode(MODE_WAITING)
    state["motor"] = "stopped"
    screen_status("Motors", "Emergency", "stop")
    return "ok"


@app.route("/set_screen", methods=["POST"])
async def set_screen(request):
    _ensure_music_stop_task()
    enter_screen_mode()
    line_1: str = request.form.get("line1", "")
    line_2: str = request.form.get("line2", "")
    line_3: str = request.form.get("line3", "")

    screen_status(line_1, line_2, line_3)
    state["screen"] = (line_1[:5] + "...") if len(line_1) > 8 else line_1
    if state["screen"] == "":
        state["screen"] = "custom"
    set_mode(MODE_WAITING)
    return "ok"


_init_thingspeak()
app.run(port=80)
