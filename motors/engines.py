from machine import Pin, PWM
from pins import (
    MOTOR_LEFT_BACKWARD_PIN,
    MOTOR_LEFT_FORWARD_PIN,
    MOTOR_RIGHT_BACKWARD_PIN,
    MOTOR_RIGHT_FORWARD_PIN,
)

# The right motor is physically stronger than the left one.
# This factor scales it down to match the left motor's output.
_RIGHT_MOTOR_CORRECTION: float = 1.1


class Engines:
    """Differential drive motor controller (left and right wheel).

    All power arguments are in per-thousand (0 = off, 1000 = full power).
    """

    def __init__(
        self,
        pin_right_forward: int = MOTOR_RIGHT_FORWARD_PIN,
        pin_right_backward: int = MOTOR_RIGHT_BACKWARD_PIN,
        pin_left_forward: int = MOTOR_LEFT_FORWARD_PIN,
        pin_left_backward: int = MOTOR_LEFT_BACKWARD_PIN,
    ):
        self.__pin_right_forward = pin_right_forward
        self.__pin_right_backward = pin_right_backward
        self.__pin_left_forward = pin_left_forward
        self.__pin_left_backward = pin_left_backward
        self.__engine_right_forward = PWM(Pin(pin_right_forward), freq=15000, duty_u16=0)
        self.__engine_right_backward = PWM(Pin(pin_right_backward), freq=15000, duty_u16=0)
        self.__engine_left_forward = PWM(Pin(pin_left_forward), freq=15000, duty_u16=0)
        self.__engine_left_backward = PWM(Pin(pin_left_backward), freq=15000, duty_u16=0)

    @staticmethod
    def __permille_to_duty(permille: int) -> int:
        """Convert a 0-1000 per-thousand value to a 16-bit PWM duty cycle."""
        value: int = permille * 65535 // 1000
        if value > 65535:
            return 65535
        if value < 0:
            return 0
        return value

    def move_right_forward(self, permille: int) -> None:
        self.__engine_right_forward.duty_u16(self.__permille_to_duty(round(permille / _RIGHT_MOTOR_CORRECTION)))
        self.__engine_right_backward.duty_u16(0)

    def move_right_backward(self, permille: int) -> None:
        self.__engine_right_backward.duty_u16(self.__permille_to_duty(round(permille / _RIGHT_MOTOR_CORRECTION)))
        self.__engine_right_forward.duty_u16(0)

    def move_left_forward(self, permille: int) -> None:
        self.__engine_left_forward.duty_u16(self.__permille_to_duty(permille))
        self.__engine_left_backward.duty_u16(0)

    def move_left_backward(self, permille: int) -> None:
        self.__engine_left_backward.duty_u16(self.__permille_to_duty(permille))
        self.__engine_left_forward.duty_u16(0)

    def move_forward(self, permille: int) -> None:
        self.move_right_forward(permille)
        self.move_left_forward(permille)

    def move_backward(self, permille: int) -> None:
        self.move_right_backward(permille)
        self.move_left_backward(permille)

    def coast_left(self) -> None:
        self.__engine_left_forward.duty_u16(0)
        self.__engine_left_backward.duty_u16(0)

    def coast_right(self) -> None:
        self.__engine_right_forward.duty_u16(0)
        self.__engine_right_backward.duty_u16(0)

    def coast(self) -> None:
        self.coast_left()
        self.coast_right()

    def brake_left(self) -> None:
        self.__engine_left_forward.duty_u16(self.__permille_to_duty(1000))
        self.__engine_left_backward.duty_u16(self.__permille_to_duty(1000))

    def brake_right(self) -> None:
        self.__engine_right_forward.duty_u16(self.__permille_to_duty(1000))
        self.__engine_right_backward.duty_u16(self.__permille_to_duty(1000))

    def brake(self) -> None:
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
