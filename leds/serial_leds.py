from machine import Pin
import neopixel
from pins import SERIAL_LED_DATA_PIN

class SeriallLeds:
    """Simple NeoPixel strip wrapper with range validation."""

    def __init__(self,
                 pin : int = SERIAL_LED_DATA_PIN,
                 number_of_led : int = 3):
        self.__np : neopixel.NeoPixel = neopixel.NeoPixel(Pin(pin), number_of_led)
        self.__number_of_led :int = number_of_led

    def check_led_index_range(self, index :int) -> bool:
        if index < 0 or self.__number_of_led <= index :
            return False
        return True

    @staticmethod
    def check_color_range(color :int) -> bool:
        if color < 0 or color > 255 :
            return False
        return True
    def set_color(self,
                  led_index: int,
                  color_red : int,
                  color_green: int,
                  color_blue : int):
        if not self.check_led_index_range(led_index):
            print("Led index out of range")
            return
        if not self.check_color_range(color_red):
            print("Red intensity out of range")
            return
        if not self.check_color_range(color_green):
            print("Green intensity out of range")
            return
        if not self.check_color_range(color_blue):
            print("Blue intensity out of range")
            return
        self.__np[led_index] = (color_red, color_green, color_blue)
    def set_color_for_all(self,
                  color_red : int,
                  color_green: int,
                  color_blue : int):
        if not self.check_color_range(color_red):
            print("Red intensity out of range")
            return
        if not self.check_color_range(color_green):
            print("Green intensity out of range")
            return
        if not self.check_color_range(color_blue):
            print("Blue intensity out of range")
            return
        self.__np.fill((color_red, color_green, color_blue))

    def send_setting(self):
        self.__np.write()

    def return_number_of_led(self):
        return self.__number_of_led
