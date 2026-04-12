import gc
import asyncio
from machine import Pin

from leds.rgb_led import RGBLed
from leds.serial_leds import SerialLeds
from motors.engines import Engines
import sys
from music.song_titles import song_titles
from music.play import _async_sleep_ms, is_song_playing, playsong_async, set_volume, stop_song
from pins import MUSIC_STOP_BUTTON_PIN
from screen.oled import OLED
from webpage.microdot import Microdot, Response
from webpage.wifi import Wifi

USE_STATION_MODE: bool = False

SSID: str = "Brrrr-Robot"
PASSWORD: str = "12345678"
DEFAULT_MAX_SPEED: int = 220

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


def _speed_to_percent(speed_value: int) -> int:
    speed_percent: int = (speed_value * 100) // 400
    if speed_percent < 1:
        return 1
    if speed_percent > 100:
        return 100
    return speed_percent


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


set_mode(MODE_LOADING)
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


def _build_song_options(selected_title: str) -> str:
    options: list[str] = []
    for song_index, title in enumerate(song_titles):
        selected: str = " selected" if title == selected_title else ""
        options.append(
            "<option value=\"" + str(song_index) + "\"" + selected + ">" + title + "</option>"
        )
    return "".join(options)


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

    max_speed_percent: int = _speed_to_percent(int(state["max_speed"]))
    left_power: int = int(abs(left) * max_speed_percent)
    right_power: int = int(abs(right) * max_speed_percent)

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


def render_webpage():
    selected_song: str = state["song"]
    song_options: str = _build_song_options(selected_song)
    gc.collect()
    yield """<!DOCTYPE html>
<html lang=\"en\">
<head>
  <meta charset=\"UTF-8\">
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">
  <title>Zilena Robot Control</title>
  <style>
    body { font-family: Arial, sans-serif; background: #f4f7fb; margin: 0; padding: 20px; color: #1f2937; }
    .card { max-width: 560px; margin: 0 auto; background: #ffffff; padding: 20px; border-radius: 10px; box-shadow: 0 8px 20px rgba(0,0,0,0.08); }
    h1 { margin-top: 0; font-size: 24px; }
    .state { font-weight: bold; margin-bottom: 10px; }
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
        .motor-wrap { display: flex; gap: 20px; align-items: center; justify-content: center; flex-wrap: wrap; }
        .joystick-wrap { display: flex; flex-direction: column; align-items: center; gap: 8px; }
        .joystick-label { font-size: 13px; color: #334155; }
        .joystick-base {
            position: relative;
            width: 170px;
            height: 170px;
            border-radius: 50%;
            border: 2px solid #1d4ed8;
            background: radial-gradient(circle at center, #dbeafe 0%, #bfdbfe 55%, #93c5fd 100%);
            touch-action: none;
            user-select: none;
        }
        .joystick-knob {
            position: absolute;
            left: 50%;
            top: 50%;
            width: 62px;
            height: 62px;
            border-radius: 50%;
            transform: translate(-50%, -50%);
            background: linear-gradient(180deg, #2563eb 0%, #1e40af 100%);
            box-shadow: 0 5px 12px rgba(30, 64, 175, 0.35);
        }
        .joystick-state { min-height: 18px; font-weight: bold; color: #1e3a8a; }
    .speed-wrap { display: flex; gap: 14px; align-items: flex-end; }
    .speed-panel { display: flex; flex-direction: column; align-items: center; min-width: 90px; }
    .speed-value { font-weight: bold; margin-bottom: 8px; }
    .v-slider {
      writing-mode: vertical-lr;
      direction: rtl;
      appearance: slider-vertical;
      width: 16px;
      vertical-align: bottom;
    }
    .speed-btn { margin-top: 10px; background: #334155; width: 100%; }
    .song-btn { margin-top: 10px; background: #6d28d9; width: 100%; }
    .song-stop-btn { margin-top: 10px; background: #7f1d1d; width: 100%; }
    select { width: 100%; box-sizing: border-box; padding: 8px; margin-top: 6px; border: 1px solid #cbd5e1; border-radius: 8px; }
    input[type=text] { width: 100%; box-sizing: border-box; padding: 8px; margin-top: 6px; border: 1px solid #cbd5e1; border-radius: 8px; }
    .send-screen { background: #0f766e; width: 100%; margin-top: 10px; }
  </style>
</head>
<body>
  <div class=\"card\">
    <h1>Zilena Robot Control</h1>
    <p class=\"state\">LEDs: """
    yield state["led"]
    yield """</p>
    <p class=\"state\">Motors: """
    yield state["motor"]
    yield """</p>
    <p class=\"state\">Max speed: """
    yield state["max_speed"]
    yield """</p>
    <p class=\"state\">Song: """
    yield state["song"]
    yield """</p>
    <p class=\"state\">Screen: """
    yield state["screen"]
    yield """</p>
    <p class=\"state\">Mode: """
    yield state["mode"]
    yield """</p>

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
        <div class=\"motor-wrap\">
            <div class=\"joystick-wrap\">
                <div class=\"joystick-label\">Drag the joystick to move</div>
                <div class=\"joystick-base\" id=\"joystick_base\">
                    <div class=\"joystick-knob\" id=\"joystick_knob\"></div>
                </div>
                <div class=\"joystick-state\" id=\"joystick_state\">x=0 y=0</div>
            </div>

      <form action=\"/set_max_speed\" method=\"post\">
        <div class=\"speed-wrap\">
                    <div class=\"speed-panel\">
                        <label for=\"max_speed\">Max speed</label>
                        <div class=\"speed-value\" id=\"speed_value\">"""
    yield state["max_speed"]
    yield """</div>
                        <input class=\"v-slider\" type=\"range\" id=\"max_speed\" name=\"max_speed\" orient=\"vertical\" min=\"70\" max=\"400\" value=\""""
    yield state["max_speed"]
    yield """\" oninput=\"document.getElementById('speed_value').textContent = this.value\">
                    </div>
        </div>
        <button class=\"speed-btn\" type=\"submit\">Apply</button>
      </form>
    </div>
    <p style=\"margin: 8px 0 0 0; font-size: 12px; color: #475569;\">Slider range: 70 to 400</p>

    <form action=\"/stop_motors\" method=\"post\">
      <button class=\"danger\" type=\"submit\">Emergency stop</button>
    </form>

        <p class=\"section-title\">Music control</p>
        <form action=\"/play_song\" method=\"post\">
            <label for=\"song_index\">Choose a song</label>
            <select id=\"song_index\" name=\"song_index\">"""
    yield song_options
    yield """</select>
            <button class=\"song-btn\" type=\"submit\">Play selected song</button>
        </form>
        <form action=\"/stop_song\" method=\"post\">
            <button class=\"song-stop-btn\" type=\"submit\">Stop song</button>
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
<script>
    (function() {
        const base = document.getElementById('joystick_base');
        const knob = document.getElementById('joystick_knob');
        const joystickState = document.getElementById('joystick_state');
        const maxDistance = 52;
        const sessionId = String(Date.now()) + '-' + String(Math.floor(Math.random() * 1000000));
        let dragging = false;
        let lastEnqueueMs = 0;
        let queuedX = 999;
        let queuedY = 999;
        let latestCommand = null;
        let inFlight = false;
        let commandSeq = 0;

        function flushLatestCommand() {
            if (inFlight || latestCommand === null) {
                return;
            }

            const commandToSend = latestCommand;
            latestCommand = null;
            inFlight = true;

            fetch('/api/drive', {
                method: 'POST',
                headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                body: 'x=' + encodeURIComponent(commandToSend.x)
                    + '&y=' + encodeURIComponent(commandToSend.y)
                    + '&sid=' + encodeURIComponent(sessionId)
                    + '&seq=' + encodeURIComponent(commandToSend.seq)
            }).catch(function(_err) {
            }).finally(function() {
                inFlight = false;
                flushLatestCommand();
            });
        }

        function enqueueVector(xPercent, yPercent, force) {
            const now = Date.now();
            const tooSoon = (now - lastEnqueueMs) < 50;
            const tinyChange = Math.abs(xPercent - queuedX) < 2 && Math.abs(yPercent - queuedY) < 2;
            if (!force && tooSoon && tinyChange) {
                return;
            }

            lastEnqueueMs = now;
            queuedX = xPercent;
            queuedY = yPercent;
            latestCommand = {
                x: xPercent,
                y: yPercent,
                seq: commandSeq,
            };
            commandSeq += 1;
            flushLatestCommand();
        }

        function resetKnob() {
            knob.style.transform = 'translate(-50%, -50%)';
            joystickState.textContent = 'x=0 y=0';
            enqueueVector(0, 0, true);

            // Ensure stop survives transient network loss when finger is released.
            setTimeout(function() {
                enqueueVector(0, 0, true);
            }, 60);
        }

        function updateJoystick(clientX, clientY) {
            const rect = base.getBoundingClientRect();
            const centerX = rect.left + (rect.width / 2);
            const centerY = rect.top + (rect.height / 2);
            let dx = clientX - centerX;
            let dy = clientY - centerY;
            const distance = Math.sqrt((dx * dx) + (dy * dy));

            if (distance > maxDistance) {
                const scale = maxDistance / distance;
                dx *= scale;
                dy *= scale;
            }

            knob.style.transform = 'translate(calc(-50% + ' + dx + 'px), calc(-50% + ' + dy + 'px))';

            const xPercent = Math.round((dx / maxDistance) * 100);
            const yPercent = Math.round((-dy / maxDistance) * 100);
            joystickState.textContent = 'x=' + xPercent + ' y=' + yPercent;
            enqueueVector(xPercent, yPercent, false);
        }

        base.addEventListener('pointerdown', function(event) {
            dragging = true;
            base.setPointerCapture(event.pointerId);
            updateJoystick(event.clientX, event.clientY);
        });

        base.addEventListener('pointermove', function(event) {
            if (!dragging) {
                return;
            }
            updateJoystick(event.clientX, event.clientY);
        });

        function stopDragging() {
            if (!dragging) {
                return;
            }
            dragging = false;
            resetKnob();
        }

        base.addEventListener('pointerup', stopDragging);
        base.addEventListener('pointercancel', stopDragging);
        base.addEventListener('lostpointercapture', stopDragging);
    })();
</script>
</body>
</html>
"""


@app.route("/")
async def index(_request):
    _ensure_music_stop_task()
    ensure_leds_mode()
    set_mode(MODE_WAITING)
    screen_status("Web UI", "Connected", "")
    return Response(render_webpage())


@app.route("/set_led", methods=["POST"])
async def set_led(request):
    _ensure_music_stop_task()
    ensure_leds_mode()
    requested_state: str = request.form.get("state", "off")
    state["led"] = requested_state
    apply_led_state(requested_state)
    screen_status("LEDS", requested_state, "")
    return Response(render_webpage())


@app.route("/move", methods=["POST"])
async def move(request):
    _ensure_music_stop_task()
    ensure_motor_mode()
    direction: str = request.form.get("direction", "stop")
    apply_motor_direction(direction)
    return Response(render_webpage())


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
    return Response(render_webpage())


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
    return Response(render_webpage())


@app.route("/stop_song", methods=["POST"])
async def stop_song_route(_request):
    _ensure_music_stop_task()
    stop_song()
    state["song"] = "stopped"
    set_mode(MODE_WAITING)
    screen_status("Music", "Stopped", "web")
    return Response(render_webpage())


@app.route("/stop_motors", methods=["POST"])
async def stop_motors(_request):
    _ensure_music_stop_task()
    ensure_leds_mode()
    set_mode(MODE_WAITING)
    state["motor"] = "stopped"
    screen_status("Motors", "Emergency", "stop")
    return Response(render_webpage())


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
    return Response(render_webpage())


app.run(port=80)
