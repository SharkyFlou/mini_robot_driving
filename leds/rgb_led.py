"""Class handling the RGB LED diode."""

from machine import Pin
from machine import PWM
from pins import RGB_LED_BLUE_PIN, RGB_LED_GREEN_PIN, RGB_LED_RED_PIN

class RGBLed:
    """RGB LED driver using three PWM channels."""

    def __init__(self,
                 pin_red: int = RGB_LED_RED_PIN,
                 pin_green: int = RGB_LED_GREEN_PIN,
                 pin_blue: int = RGB_LED_BLUE_PIN) -> None:
        """
        Execute the constructor for the RGB LED diode.

        :param pin_red: Pin connected to the Red LED
        :param pin_green: Pin connected to the Green LED
        :param pin_blue: Pin connected to the Blue LED

        :return: None
        """
        self.__pin_red_number: int = pin_red
        self.__pin_green_number: int = pin_green
        self.__pin_blue_number: int = pin_blue
        self.__pin_red: PWM = PWM(Pin(pin_red), freq=100, duty_u16=0)
        self.__pin_green: PWM = PWM(Pin(pin_green), freq=100, duty_u16=0)
        self.__pin_blue: PWM = PWM(Pin(pin_blue), freq=100, duty_u16=0)
        self.__max_intensity: int = 40

    @staticmethod
    def __calculate_intensity(intensity_percent: int) -> int:
        one_percent: float = 65535 / 100
        intensity: int = int(intensity_percent * one_percent)
        if intensity > 65535:
            intensity = 65535
        elif intensity < 0:
            intensity = 0
        return intensity

    def set_specific_colour(self,
                            intensity_red: int,
                            intensity_green: int,
                            intensity_blue: int) -> None:
        """
        Set the RGB LED to specific color.

        :param intensity_red: intensity of the red LED int percentage
        :param intensity_green: intensity of the green LED int percentage
        :param intensity_blue: intensity of the blue LED int percentage
        :return:
        """
        self.__pin_green.duty_u16(self.__calculate_intensity(intensity_green))
        self.__pin_red.duty_u16(self.__calculate_intensity(intensity_red))
        self.__pin_blue.duty_u16(self.__calculate_intensity(intensity_blue))

    def set_red(self) -> None:
        """
        Set the RGB LED to Red.

        :return: None
        """
        self.__pin_red.duty_u16(self.__calculate_intensity(self.__max_intensity))
        self.__pin_green.duty_u16(self.__calculate_intensity(0))
        self.__pin_blue.duty_u16(self.__calculate_intensity(0))

    def set_green(self) -> None:
        """
        Set the RGB LED to Green.

        :return: None
        """
        self.__pin_green.duty_u16(self.__calculate_intensity(self.__max_intensity))
        self.__pin_red.duty_u16(self.__calculate_intensity(0))
        self.__pin_blue.duty_u16(self.__calculate_intensity(0))

    def set_blue(self) -> None:
        """
        Set the RGB LED to Blue.

        :return: None
        """
        self.__pin_green.duty_u16(self.__calculate_intensity(0))
        self.__pin_red.duty_u16(self.__calculate_intensity(0))
        self.__pin_blue.duty_u16(self.__calculate_intensity(self.__max_intensity))

    def set_yellow(self) -> None:
        """
        Set the RGB LED to Yellow.

        :return: None
        """
        self.__pin_green.duty_u16(self.__calculate_intensity(self.__max_intensity))
        self.__pin_red.duty_u16(self.__calculate_intensity(self.__max_intensity))
        self.__pin_blue.duty_u16(self.__calculate_intensity(0))

    def set_purple(self) -> None:
        """
        Set the RGB LED to Purple.

        :return: None
        """
        self.__pin_green.duty_u16(self.__calculate_intensity(0))
        self.__pin_red.duty_u16(self.__calculate_intensity(self.__max_intensity))
        self.__pin_blue.duty_u16(self.__calculate_intensity(self.__max_intensity))

    def set_cyan(self) -> None:
        """
        Set the RGB LED to Cyan.

        :return: None
        """
        self.__pin_green.duty_u16(self.__calculate_intensity(self.__max_intensity))
        self.__pin_red.duty_u16(self.__calculate_intensity(0))
        self.__pin_blue.duty_u16(self.__calculate_intensity(self.__max_intensity))

    def set_white(self) -> None:
        """
        Set the RGB LED to White.

        :return: None
        """
        self.__pin_green.duty_u16(self.__calculate_intensity(self.__max_intensity))
        self.__pin_red.duty_u16(self.__calculate_intensity(self.__max_intensity))
        self.__pin_blue.duty_u16(self.__calculate_intensity(self.__max_intensity))

    def set_off(self) -> None:
        """
        Turn off the RGB LED.

        :return: None
        """
        self.__pin_green.duty_u16(self.__calculate_intensity(0))
        self.__pin_red.duty_u16(self.__calculate_intensity(0))
        self.__pin_blue.duty_u16(self.__calculate_intensity(0))

    def release(self) -> None:
        """Turn the LED off and free PWM channels."""
        self.set_off()
        self.__pin_red.deinit()
        self.__pin_green.deinit()
        self.__pin_blue.deinit()

        # Force LED pins low after PWM deinit to prevent noise coupling.
        Pin(self.__pin_red_number, Pin.OUT, value=0)
        Pin(self.__pin_green_number, Pin.OUT, value=0)
        Pin(self.__pin_blue_number, Pin.OUT, value=0)

