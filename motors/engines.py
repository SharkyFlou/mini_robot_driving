from machine import Pin,PWM
from pins import (
    MOTOR_LEFT_BACKWARD_PIN,
    MOTOR_LEFT_FORWARD_PIN,
    MOTOR_RIGHT_BACKWARD_PIN,
    MOTOR_RIGHT_FORWARD_PIN,
)


class Engines:
    """Differential drive motor controller (left and right wheel)."""

    def __init__(self,
                 pin_right_forward:int=MOTOR_RIGHT_FORWARD_PIN,
                 pin_right_backward:int=MOTOR_RIGHT_BACKWARD_PIN,
                 pin_left_forward:int=MOTOR_LEFT_FORWARD_PIN,
                 pin_left_backward:int=MOTOR_LEFT_BACKWARD_PIN):
        self.__pin_right_forward = pin_right_forward
        self.__pin_right_backward = pin_right_backward
        self.__pin_left_forward = pin_left_forward
        self.__pin_left_backward = pin_left_backward
        self.__engine_right_forward = PWM(Pin(pin_right_forward),freq=15000, duty_u16=0)
        self.__engine_right_backward = PWM(Pin(pin_right_backward),freq=15000, duty_u16=0)
        self.__engine_left_forward = PWM(Pin(pin_left_forward),freq=15000, duty_u16=0)
        self.__engine_left_backward = PWM(Pin(pin_left_backward),freq=15000, duty_u16=0)

    @staticmethod
    def __percent_to_duty(percent: int) -> int:
        value: int = int(percent * (65535 / 100))

        if value > 65535:
            value = 65535
        elif value < 0:
            value = 0
        return value

    def move_right_forward(self, percent:int) -> None:
        self.__engine_right_forward.duty_u16(self.__percent_to_duty(percent))
        self.__engine_right_backward.duty_u16(self.__percent_to_duty(0))

    def move_right_backward(self, percent:int) -> None:
        self.__engine_right_backward.duty_u16(self.__percent_to_duty(percent))
        self.__engine_right_forward.duty_u16(self.__percent_to_duty(0))

    def move_left_forward(self, percent:int) -> None:
        self.__engine_left_forward.duty_u16(self.__percent_to_duty(percent))
        self.__engine_left_backward.duty_u16(self.__percent_to_duty(0))


    def move_left_backward(self, percent:int) -> None:
        self.__engine_left_backward.duty_u16(self.__percent_to_duty(percent))
        self.__engine_left_forward.duty_u16(self.__percent_to_duty(0))


    def brake_right(self) -> None:
        self.__engine_right_forward.duty_u16(self.__percent_to_duty(100))
        self.__engine_right_backward.duty_u16(self.__percent_to_duty(100))

    def brake_left(self) -> None:
        self.__engine_left_forward.duty_u16(self.__percent_to_duty(100))
        self.__engine_left_backward.duty_u16(self.__percent_to_duty(100))

    def move_forward(self, percent:int) -> None:
        self.move_right_forward(percent)
        self.move_left_forward(percent)

    def move_backward(self, percent:int) -> None:
        self.move_right_backward(percent)
        self.move_left_backward(percent)

    def coast_left(self) -> None:
        self.__engine_left_forward.duty_u16(0)
        self.__engine_left_backward.duty_u16(0)

    def coast_right(self) -> None:
        self.__engine_right_forward.duty_u16(0)
        self.__engine_right_backward.duty_u16(0)

    def coast(self):
        self.coast_left()
        self.coast_right()

    def brake(self)->None:
        self.brake_right()
        self.brake_left()

    def release(self) -> None:
        """Stop motors and free PWM channels."""
        self.coast()
        self.__engine_right_forward.deinit()
        self.__engine_right_backward.deinit()
        self.__engine_left_forward.deinit()
        self.__engine_left_backward.deinit()

        # Force all H-bridge control pins low after PWM deinit.
        Pin(self.__pin_right_forward, Pin.OUT, value=0)
        Pin(self.__pin_right_backward, Pin.OUT, value=0)
        Pin(self.__pin_left_forward, Pin.OUT, value=0)
        Pin(self.__pin_left_backward, Pin.OUT, value=0)

