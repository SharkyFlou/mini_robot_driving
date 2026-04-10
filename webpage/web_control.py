import time

from leds.rgb_led import RGBLed
from leds.serial_leds import SeriallLeds
from motors.engines import Engines
from screen.oled import OLED
from webpage.microdot import Microdot, Response
from webpage.wifi import Wifi

USE_STATION_MODE: bool = False

SSID: str = "Zilena-Robot"
PASSWORD: str = "robot2026"
DEFAULT_MOTOR_SPEED_PERCENT: int = 150

MODE_LOADING = "loading"
MODE_WAITING = "waiting"
MODE_DEBUGGING = "debugging"
MODE_LEDS = "leds"
MODE_MOTORS = "motors"
MODE_SCREEN = "screen"
MODE_BUZZER = "buzzer"

hardware: dict[str, SeriallLeds | Engines | None] = {
    "serial_leds": None,
    "motors": None,
}

state: dict[str, str] = {
    "led": "off",
    "motor": "stopped",
    "screen": "ready",
    "mode": MODE_LOADING,
}

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
    """Set single RGB LED by mode, then release it to avoid PWM overflow."""
    indicator = RGBLed()
    print(f"Flashing mode: {mode}")

    if mode == MODE_LOADING:
        indicator.set_blue()
    elif mode == MODE_WAITING:
        indicator.set_white()
    elif mode == MODE_DEBUGGING:
        indicator.set_purple()
    elif mode == MODE_LEDS:
        indicator.set_green()
    elif mode == MODE_MOTORS:
        indicator.set_red()
    elif mode == MODE_SCREEN:
        indicator.set_cyan()
    elif mode == MODE_BUZZER:
        indicator.set_yellow()
    else:
        indicator.set_off()

    time.sleep(0.25)
    indicator.release()


def set_mode(mode: str) -> None:
    """Update current mode and flash the single RGB mode indicator."""
    if state["mode"] == mode:
        return
    state["mode"] = mode
    _flash_mode_indicator(mode)


set_mode(MODE_LOADING)
_flash_mode_indicator(MODE_LOADING)

screen_status("Boot", "Creating WiFi", SSID)
wifi: Wifi = Wifi(USE_STATION_MODE)
if USE_STATION_MODE:
    wifi.connect_to_wifi(SSID, PASSWORD)
    screen_status("WiFi ready", "STA mode", SSID)
else:
    wifi.create_wifi(SSID, PASSWORD)
    screen_status("WiFi ready", "AP mode", SSID)

app: Microdot = Microdot()
Response.default_content_type = "text/html"


def ensure_leds_mode() -> None:
    """Ensure serial LEDs are active and motors are released."""
    if hardware["motors"] is not None:
        hardware["motors"].release()
        hardware["motors"] = None
        state["motor"] = "stopped"

    if hardware["serial_leds"] is None:
        hardware["serial_leds"] = SeriallLeds()
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


def enter_debugging_mode() -> None:
    """Placeholder for debugging mode."""
    set_mode(MODE_DEBUGGING)


def enter_screen_mode() -> None:
    """Placeholder for screen mode."""
    set_mode(MODE_SCREEN)


def enter_buzzer_mode() -> None:
    """Placeholder for buzzer mode."""
    set_mode(MODE_BUZZER)


def apply_led_state(led_state: str) -> None:
    """Apply one named serial LED strip color preset."""
    serial_leds = hardware["serial_leds"]
    if serial_leds is None:
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
    """Apply one cardinal motor command (up/down/left/right/stop)."""
    motors = hardware["motors"]
    if motors is None:
        return

    if direction == "up":
        motors.move_forward(DEFAULT_MOTOR_SPEED_PERCENT)
        state["motor"] = "forward"
        screen_status("Motors", "Forward", "")
        return

    if direction == "down":
        motors.move_backward(DEFAULT_MOTOR_SPEED_PERCENT)
        state["motor"] = "backward"
        screen_status("Motors", "Backward", "")
        return

    if direction == "left":
        motors.move_left_backward(DEFAULT_MOTOR_SPEED_PERCENT)
        motors.move_right_forward(DEFAULT_MOTOR_SPEED_PERCENT)
        state["motor"] = "left"
        screen_status("Motors", "Left", "")
        return

    if direction == "right":
        motors.move_left_forward(DEFAULT_MOTOR_SPEED_PERCENT)
        motors.move_right_backward(DEFAULT_MOTOR_SPEED_PERCENT)
        state["motor"] = "right"
        screen_status("Motors", "Right", "")
        return

    motors.coast()
    state["motor"] = "stopped"
    screen_status("Motors", "Stopped", "")


def render_webpage() -> str:
    return """<!DOCTYPE html>
<html lang=\"en\">
<head>
  <meta charset=\"UTF-8\">
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">
  <title>Zilena Robot Control</title>
  <style>
    body { font-family: Arial, sans-serif; background: #f4f7fb; margin: 0; padding: 20px; color: #1f2937; }
    .card { max-width: 520px; margin: 0 auto; background: #ffffff; padding: 20px; border-radius: 10px; box-shadow: 0 8px 20px rgba(0,0,0,0.08); }
    h1 { margin-top: 0; font-size: 24px; }
    .state { font-weight: bold; margin-bottom: 12px; }
    .section-title { margin: 18px 0 8px 0; font-weight: bold; }
    .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
    button { padding: 10px; border: none; border-radius: 8px; cursor: pointer; color: #ffffff; font-weight: bold; }
    .off { background: #111827; }
    .red { background: #dc2626; }
    .green { background: #16a34a; }
    .blue { background: #2563eb; }
    .yellow { background: #ca8a04; }
    .purple { background: #9333ea; }
    .cyan { background: #0891b2; }
    .white { background: #6b7280; }
    .danger { background: #b91c1c; width: 100%; margin-top: 10px; }
    .arrow-pad { margin-top: 10px; display: grid; gap: 8px; justify-content: center; }
    .arrow-row { display: flex; justify-content: center; gap: 8px; }
    .arrow-btn { min-width: 90px; background: #1d4ed8; }
    input[type=text] { width: 100%; box-sizing: border-box; padding: 8px; margin-top: 6px; border: 1px solid #cbd5e1; border-radius: 8px; }
    .send-screen { background: #0f766e; width: 100%; margin-top: 10px; }
  </style>
</head>
<body>
  <div class=\"card\">
    <h1>Zilena Robot Control</h1>
    <p class=\"state\">LEDs: """ + state["led"] + """</p>
    <p class=\"state\">Motors: """ + state["motor"] + """</p>
    <p class=\"state\">Screen: """ + state["screen"] + """</p>
    <p class=\"state\">Mode: """ + state["mode"] + """</p>

    <p class=\"section-title\">Serial LEDs control</p>
    <div class=\"grid\">
      <form action=\"/set_led\" method=\"post\"><input type=\"hidden\" name=\"state\" value=\"off\"><button class=\"off\" type=\"submit\">Off</button></form>
      <form action=\"/set_led\" method=\"post\"><input type=\"hidden\" name=\"state\" value=\"white\"><button class=\"white\" type=\"submit\">White</button></form>
      <form action=\"/set_led\" method=\"post\"><input type=\"hidden\" name=\"state\" value=\"red\"><button class=\"red\" type=\"submit\">Red</button></form>
      <form action=\"/set_led\" method=\"post\"><input type=\"hidden\" name=\"state\" value=\"green\"><button class=\"green\" type=\"submit\">Green</button></form>
      <form action=\"/set_led\" method=\"post\"><input type=\"hidden\" name=\"state\" value=\"blue\"><button class=\"blue\" type=\"submit\">Blue</button></form>
      <form action=\"/set_led\" method=\"post\"><input type=\"hidden\" name=\"state\" value=\"yellow\"><button class=\"yellow\" type=\"submit\">Yellow</button></form>
      <form action=\"/set_led\" method=\"post\"><input type=\"hidden\" name=\"state\" value=\"purple\"><button class=\"purple\" type=\"submit\">Purple</button></form>
      <form action=\"/set_led\" method=\"post\"><input type=\"hidden\" name=\"state\" value=\"cyan\"><button class=\"cyan\" type=\"submit\">Cyan</button></form>
    </div>

    <p class=\"section-title\">Motors control</p>
    <div class=\"arrow-pad\">
      <div class=\"arrow-row\">
        <form action=\"/move\" method=\"post\">
          <input type=\"hidden\" name=\"direction\" value=\"up\">
          <button class=\"arrow-btn\" type=\"submit\">Up</button>
        </form>
      </div>
      <div class=\"arrow-row\">
        <form action=\"/move\" method=\"post\">
          <input type=\"hidden\" name=\"direction\" value=\"left\">
          <button class=\"arrow-btn\" type=\"submit\">Left</button>
        </form>
        <form action=\"/move\" method=\"post\">
          <input type=\"hidden\" name=\"direction\" value=\"right\">
          <button class=\"arrow-btn\" type=\"submit\">Right</button>
        </form>
      </div>
      <div class=\"arrow-row\">
        <form action=\"/move\" method=\"post\">
          <input type=\"hidden\" name=\"direction\" value=\"down\">
          <button class=\"arrow-btn\" type=\"submit\">Back</button>
        </form>
      </div>
    </div>
    <form action=\"/stop_motors\" method=\"post\">
      <button class=\"danger\" type=\"submit\">Emergency stop</button>
    </form>

    <p class=\"section-title\">Screen control</p>
    <form action=\"/set_screen\" method=\"post\">
      <label>Line 1</label>
      <input type=\"text\" name=\"line1\" maxlength=\"16\" placeholder=\"Line 1\">
      <label>Line 2</label>
      <input type=\"text\" name=\"line2\" maxlength=\"16\" placeholder=\"Line 2\">
      <label>Line 3</label>
      <input type=\"text\" name=\"line3\" maxlength=\"16\" placeholder=\"Line 3\">
      <button class=\"send-screen\" type=\"submit\">Send to screen</button>
    </form>
  </div>
</body>
</html>
"""


@app.route("/")
async def index(_request):
    ensure_leds_mode()
    set_mode(MODE_WAITING)
    screen_status("Web UI", "Connected", "")
    return Response(render_webpage())


@app.route("/set_led", methods=["POST"])
async def set_led(request):
    ensure_leds_mode()
    requested_state: str = request.form.get("state", "off")
    state["led"] = requested_state
    apply_led_state(requested_state)
    screen_status("LEDS", requested_state, "")
    return Response(render_webpage())


@app.route("/move", methods=["POST"])
async def move(request):
    ensure_motor_mode()
    direction: str = request.form.get("direction", "stop")
    apply_motor_direction(direction)
    return Response(render_webpage())


@app.route("/stop_motors", methods=["POST"])
async def stop_motors(_request):
    ensure_leds_mode()
    set_mode(MODE_WAITING)
    state["motor"] = "stopped"
    screen_status("Motors", "Emergency", "stop")
    return Response(render_webpage())


@app.route("/set_screen", methods=["POST"])
async def set_screen(request):
    enter_screen_mode()
    line_1: str = request.form.get("line1", "")
    line_2: str = request.form.get("line2", "")
    line_3: str = request.form.get("line3", "")

    screen_status(line_1, line_2, line_3)
    state["screen"] = (line_1[:5] + "...") if len(line_1) > 8 else line_1
    if state["screen"] == "":
        state["screen"] = "custom"
    set_mode(MODE_WAITING)
    return Response(render_webpage())


app.run(port=80)
