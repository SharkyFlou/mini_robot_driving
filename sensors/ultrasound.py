"""Author: Ing. Tomas Baca."""

from machine import Pin
from machine import Timer
import time
from pins import ULTRASOUND_ECHO_PIN, ULTRASOUND_TRIG_PIN


class HCSR04Nonblocking:
    """Class for non-blocking work with the HCSR-04."""

    def __init__(self,
                 trig_pin: int = ULTRASOUND_TRIG_PIN,
                 echo_pin: int = ULTRASOUND_ECHO_PIN,
                 timer_number: int = 0,
                 timeout_ms: int = 30) -> None:
        """
        Execute the constructor.

        :param trig_pin: pin to which is connected the TRIG pin of the HCSR-04.
        :param echo_pin: pin to which is connected the ECHO pin of the HCSR-04.
        :param timer_number: the number of the used timer.
        :param timeout_ms: the timeout expressed in milliseconds.
        """
        self.__trig_pin: Pin = Pin(trig_pin, Pin.OUT)
        self.__echo_pin: Pin = Pin(echo_pin, Pin.IN)
        self.__timer: Timer = Timer(timer_number)
        self.__timeout_ms: int = timeout_ms

        self.__ongoing_measurement: bool = False

        self.__initial_time_us: int = 0
        self.__final_time_us: int = 0

        self.__pulse_time: float = 0
        self.__distance_cm: float = 0
        self.__distance_mm: float = 0
        self.__echo_flag: bool = False

    @staticmethod
    def __empty(s) -> None:
        """
        Empty function.

        :param s: instance of the class that called the function.
        :return:
        """
        pass

    @staticmethod
    def __calculate_distance_cm(time_us: float) -> float:
        """
        Calculate the distance in cm from the measured time.

        :param time_us: measured time.
        :return: distance in cm.
        """
        return (time_us / 2) / 29.1

    @staticmethod
    def __calculate_distance_mm(time_us: float) -> float:
        """
        Calculate the distance in mm from the measured time.

        :param time_us: measured time.
        :return: distance in mm.
        """
        return time_us * 100 // 582

    def __echo_pin_interrupt_service_routine_stop(self, s) -> None:
        """
        ISR called when measurement of distance ends.

        :param s:  instance of the class that called the function.
        :return:
        """
        self.__echo_pin.irq(handler=self.__empty)  # disable IRQ completely
        self.__timer.deinit()
        self.__final_time_us = time.ticks_us()
        self.__pulse_time = time.ticks_diff(
            self.__final_time_us, self.__initial_time_us)
        self.__distance_cm = self.__calculate_distance_cm(self.__pulse_time)
        self.__distance_mm = self.__calculate_distance_mm(self.__pulse_time)
        self.__echo_flag = True
        self.__ongoing_measurement = False

    def __timer_interrupt_service_routine(self, s) -> None:
        """
        ISR called by the timer after the timeout will pass.

        :param s:  instance of the class that called the function.
        :return:
        """
        self.__echo_pin.irq(handler=self.__empty)  # disable IRQ completely
        self.__pulse_time = -1
        self.__distance_cm = -1
        self.__distance_mm = -1
        self.__echo_flag = True
        self.__ongoing_measurement = False

    def __echo_pin_interrupt_service_routine_start(self, s) -> None:
        """
        ISR called when measurement of distance start.

        :param s:  instance of the class that called the function.
        :return:
        """
        self.__echo_pin.irq(handler=self.__empty)  # disable IRQ completely
        self.__initial_time_us = time.ticks_us()
        self.__echo_pin.irq(
            trigger=Pin.IRQ_FALLING,
            handler=self.__echo_pin_interrupt_service_routine_stop)
        self.__timer.init(period=self.__timeout_ms,
                          mode=Timer.ONE_SHOT,
                          callback=self.__timer_interrupt_service_routine)

    def start_measurement(self) -> None:
        """
        Start the measurement by setting the trigger pin to logic one.

        :return:
        """
        if self.__ongoing_measurement is True:
            return
        self.__ongoing_measurement = True
        self.__trig_pin.value(0)
        time.sleep_us(5)
        self.__trig_pin.value(1)
        time.sleep_us(10)
        self.__trig_pin.value(0)
        self.__echo_pin.irq(
            trigger=Pin.IRQ_RISING,
            handler=self.__echo_pin_interrupt_service_routine_start)

    def get_flag(self) -> bool:
        """
        Echo flag gets set to True when the measurement ends.

        :return: flag signaling that the measurement has ended.
        """
        return self.__echo_flag

    def reset_flag(self) -> None:
        """
        Reset the echo flag back to False.

        :return:
        """
        self.__echo_flag = False

    def return_pulse_time(self) -> float:
        """:return: raw pulse time in micro seconds."""
        return self.__pulse_time

    def return_distance_cm(self) -> float:
        """:return: distance in cm."""
        return self.__distance_cm

    def return_distance_mm(self) -> float:
        """:return: distance in mm."""
        return self.__distance_mm


# hcsr04_nonblocking_instance: HCSR04Nonblocking = HCSR04Nonblocking()
#
# while True:
#     hcsr04_nonblocking_instance.start_measurement()
#
#     while hcsr04_nonblocking_instance.get_flag() is False:
#         pass
#
#     print()
#     print(f"Pulse time: {hcsr04_nonblocking_instance.return_pulse_time()} us")
#     print(f"Distance: {hcsr04_nonblocking_instance.return_distance_cm()} cm")
#     print(f"Distance: {hcsr04_nonblocking_instance.return_distance_mm()} mm")
#     print()
#     hcsr04_nonblocking_instance.reset_flag()
#     time.sleep(5)