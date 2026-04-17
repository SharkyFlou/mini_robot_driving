# Zilena Robot — ESP32-C6

A MicroPython-based robot controlled from a web browser over WiFi.  
The robot hosts its own access point and serves a responsive web interface on port 80.

---

## Hardware

| Component | Description |
|-----------|-------------|
| **MCU** | ESP32-C6 |
| **Motors** | 2× DC motors via H-bridge (differential drive) |
| **LEDs** | 1× RGB LED (status indicator) + 3× NeoPixel strip |
| **Display** | SSD1306 OLED 128×32 (I2C) |
| **Sensors** | HC-SR04 ultrasonic, photoresistor, MPU6050 IMU |
| **Buzzer** | Passive buzzer (PWM music playback) |
| **Button** | Physical stop button for music |

### Pin mapping

| Pin | Function |
|-----|----------|
| 21 / 11 / 10 | RGB LED (R / G / B) |
| 8 | NeoPixel data |
| 19 / 18 | Right motor (forward / backward) |
| 20 / 22 | Left motor (forward / backward) |
| 7 / 6 | OLED SCL / SDA (I2C) |
| 15 / 23 | Ultrasonic TRIG / ECHO |
| 3 | Photoresistor (ADC) |
| 5 | Buzzer |
| 2 | Music stop button |

---

## Getting Started

### 1. Flash MicroPython

Download the latest ESP32-C6 MicroPython firmware from [micropython.org](https://micropython.org/download/ESP32_GENERIC_C6/) and flash it:

```bash
esptool.py --chip esp32c6 --port /dev/ttyUSB0 erase_flash
esptool.py --chip esp32c6 --port /dev/ttyUSB0 write_flash -z 0x0 firmware.bin
```

### 2. Upload the project

Copy all project files to the board using [mpremote](https://docs.micropython.org/en/latest/reference/mpremote.html) or [Thonny](https://thonny.org/):

```bash
mpremote connect /dev/ttyUSB0 cp -r . :
```

### 3. Power on

Connect the robot to power (USB or battery). The OLED display will show boot status.  
`main.py` is the entry point — it imports `webpage.web_control` which initialises all hardware and starts the web server.

---

## Connecting to WiFi

The robot operates in two modes depending on whether it has saved WiFi credentials.

### Setup mode (first boot or no saved network)

If no known WiFi network is found, the robot creates its own access point:

| Setting | Value |
|---------|-------|
| **SSID** | `Rob_Charly` |
| **Password** | Random 8-character code shown on the OLED display |
| **IP address** | `192.168.4.1` |

1. Connect your phone or computer to the `Rob_Charly` WiFi network using the password shown on the OLED.
2. Open a browser and go to `http://192.168.4.1`.
3. The WiFi setup page will appear. It automatically scans for nearby networks.
4. Select your network from the list (or type the SSID manually), enter the password, and click **Connect**.
5. The robot will attempt the connection. On success it restarts automatically and connects to your network on the next boot.

### Station mode (saved credentials found)

On boot, the robot scans nearby networks and tries all saved credentials, prioritising the strongest signal. The OLED shows the connection progress. Once connected, the IP address is displayed — open `http://<ip>` in your browser to access the control interface.

---

## WiFi Credential Storage

Credentials are saved in a JSON file (`wifi_creds.json`) on the robot's flash storage.

- **Multiple networks** are supported. Every successfully connected network is saved.
- **On each boot**, the robot scans nearby networks and ranks them by signal strength (RSSI). It tries scan-visible known networks first (full timeout), then saved-but-invisible networks as a fallback (short timeout).
- **No limit** on the number of saved networks.
- Credentials persist across reboots and power cycles.
- There is currently no UI to remove a saved network — delete `wifi_creds.json` via the REPL to reset:
  ```python
  import os; os.remove('wifi_creds.json')
  ```

---

## Web Interface

The interface is divided into four tabs.

### Motors tab

Control the robot's movement using an **analog joystick** (drag with mouse or touch):

- Dragging the joystick applies a differential drive vector: `x` = turn, `y` = forward/backward.
- Commands are sent as AJAX requests with sequence numbers — stale packets are discarded automatically.
- A **Max speed slider** (range 70–400) sets the maximum motor power. Click **Apply** to send.
- The **Emergency stop** button immediately cuts motor power and switches to LED mode.

### Misc tab

**Serial LEDs** — Set all 3 NeoPixels to one of 8 preset colors: Off, White, Red, Green, Blue, Yellow, Purple, Cyan. The **Rainbow** button slowly cycles through the full RGB spectrum (one complete cycle ≈ 6 s) until another color is selected.

**Music** — Select a song from the list and click **Play selected song**. The buzzer plays the melody asynchronously (the robot remains controllable during playback). A physical button on the robot also stops the music. Available songs (42 total):

> Star Trek intro, Silent Night, Pacman, Ode an die Freude, Star Wars theme, Wiegenlied, Tetris Theme A, Happy Birthday, Darth Vader theme, Nokia Ringtone, Mii Channel, Minuet in G, Badinerie (Bach), Für Elise, Cantina Band, Song of Storms, The Lion Sleeps Tonight, The Lick, Canon in D, At Doom's Gate, Pink Panther, Hedwig's Theme, Jigglypuff's Song, We Wish You a Merry Christmas, Keyboard Cat, Game of Thrones, Greensleeves, Green Hill Zone, Zelda Theme, Baby Elephant Walk, Bloody Tears, O Pulo da Gaita, Vampire Killer, Never Gonna Give You Up, Take On Me, Prince Igor, Zelda's Lullaby, Super Mario Bros, Asa Branca, The Godfather, Professor Layton's Theme, Coalescence.

**Screen** — Send up to 3 lines of custom text to the OLED display (16 characters max per line).

### Sensors tab

Displays live sensor readings, refreshed every 800 ms:

| Sensor | Measurements |
|--------|-------------|
| **HC-SR04** | Distance (cm) |
| **Photoresistor** | Light intensity (%, V, raw ADC) |
| **MPU6050** | Acceleration X/Y/Z (g), Gyroscope X/Y/Z (°/s), Temperature (°C) |

Sensors are initialised lazily on first access to save memory at boot.

### Telemetry tab

Integrates with **ThingSpeak** for cloud data logging (station mode only).

- Toggle the **Send to ThingSpeak** switch to enable periodic uploads every 30 seconds.
- The following fields are uploaded: distance (cm), light (%), accel X/Y/Z (g), temperature (°C).
- The table displays the last 20 readings fetched directly from the ThingSpeak API.
- ThingSpeak is disabled by default and must be enabled from this tab each session.

---

## RGB LED Status Indicator

The single RGB LED reflects the current robot mode:

| Color | Mode |
|-------|------|
| Blue | Loading / booting |
| White | Waiting (idle) |
| Green | LED mode active |
| Red | Motor mode active |
| Cyan | Screen mode active |
| Yellow | Music playing |
| Purple | Debugging |

---

## Motor Calibration

The right motor is physically stronger than the left. A correction factor of `1.1` is applied automatically to the right motor's PWM duty cycle to keep the robot driving straight.  
To adjust, edit `_RIGHT_MOTOR_CORRECTION` in [motors/engines.py](motors/engines.py).
