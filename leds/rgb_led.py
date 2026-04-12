"""Class handling the RGB LED diode."""

from machine import Pin
from pins import RGB_LED_BLUE_PIN, RGB_LED_GREEN_PIN, RGB_LED_RED_PIN

class RGBLed:
    """RGB LED driver using three GPIO outputs."""

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
        self.__pin_red: Pin = Pin(pin_red, Pin.OUT, value=0)
        self.__pin_green: Pin = Pin(pin_green, Pin.OUT, value=0)
        self.__pin_blue: Pin = Pin(pin_blue, Pin.OUT, value=0)
        self.__max_intensity: int = 100

    @staticmethod
    def __calculate_intensity(intensity_percent: int) -> int:
        return 1 if intensity_percent > 0 else 0

    def __set_channel(self, channel: Pin, intensity_percent: int) -> None:
        channel.value(self.__calculate_intensity(intensity_percent))

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
        self.__set_channel(self.__pin_green, intensity_green)
        self.__set_channel(self.__pin_red, intensity_red)
        self.__set_channel(self.__pin_blue, intensity_blue)

    def set_red(self) -> None:
        """
        Set the RGB LED to Red.

        :return: None
        """
        self.__set_channel(self.__pin_red, self.__max_intensity)
        self.__set_channel(self.__pin_green, 0)
        self.__set_channel(self.__pin_blue, 0)

    def set_green(self) -> None:
        """
        Set the RGB LED to Green.

        :return: None
        """
        self.__set_channel(self.__pin_green, self.__max_intensity)
        self.__set_channel(self.__pin_red, 0)
        self.__set_channel(self.__pin_blue, 0)

    def set_blue(self) -> None:
        """
        Set the RGB LED to Blue.

        :return: None
        """
        self.__set_channel(self.__pin_green, 0)
        self.__set_channel(self.__pin_red, 0)
        self.__set_channel(self.__pin_blue, self.__max_intensity)

    def set_yellow(self) -> None:
        """
        Set the RGB LED to Yellow.

        :return: None
        """
        self.__set_channel(self.__pin_green, self.__max_intensity)
        self.__set_channel(self.__pin_red, self.__max_intensity)
        self.__set_channel(self.__pin_blue, 0)

    def set_purple(self) -> None:
        """
        Set the RGB LED to Purple.

        :return: None
        """
        self.__set_channel(self.__pin_green, 0)
        self.__set_channel(self.__pin_red, self.__max_intensity)
        self.__set_channel(self.__pin_blue, self.__max_intensity)

    def set_cyan(self) -> None:
        """
        Set the RGB LED to Cyan.

        :return: None
        """
        self.__set_channel(self.__pin_green, self.__max_intensity)
        self.__set_channel(self.__pin_red, 0)
        self.__set_channel(self.__pin_blue, self.__max_intensity)

    def set_white(self) -> None:
        """
        Set the RGB LED to White.

        :return: None
        """
        self.__set_channel(self.__pin_green, self.__max_intensity)
        self.__set_channel(self.__pin_red, self.__max_intensity)
        self.__set_channel(self.__pin_blue, self.__max_intensity)

    def set_off(self) -> None:
        """
        Turn off the RGB LED.

        :return: None
        """
        self.__set_channel(self.__pin_green, 0)
        self.__set_channel(self.__pin_red, 0)
        self.__set_channel(self.__pin_blue, 0)

    def release(self) -> None:
        """Turn the LED off."""
        self.set_off()

