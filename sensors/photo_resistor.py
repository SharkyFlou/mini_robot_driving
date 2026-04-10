from machine import ADC
from machine import Pin
from pins import PHOTORESISTOR_ADC_PIN


class PhotoResistor:
    """Photoresistor reader that returns raw, voltage and percent."""

    def __init__(self, pin : int = PHOTORESISTOR_ADC_PIN) -> None:
        self.__adc: ADC = ADC(Pin(pin), atten=ADC.ATTN_11DB)

    @staticmethod
    def get_voltage(raw_value: int) -> float:
        one_percent: float = 3.3 / 100
        voltage: int = int(raw_value * one_percent)
        return voltage

    @staticmethod
    def get_percent(raw_value: int) -> int:
        one_percent: float = 65535 / 100
        intensity: int = int(raw_value / one_percent)
        if intensity > 100:
            intensity = 100
        elif intensity < 0:
            intensity = 0
        return intensity

    def measure(self) -> list[float]:
        raw_value : int = self.__adc.read_u16()
        voltage_value : float = self.get_voltage(raw_value)
        percent_value : float = self.get_percent(raw_value)
        return [raw_value,voltage_value, percent_value]

