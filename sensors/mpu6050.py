"""
Library for the 8 pin module with the MPU6050 sensor.
"""

from machine import Pin
from machine import SoftI2C
from machine import I2C
import time
import math

class MPU6050:

    def __init__(self, i2c_instance: SoftI2C | I2C, device_address_change: bool = False) -> None:
        self.__i2c: SoftI2C | I2C = i2c_instance
        self.__device_address: int = 0x68
        if device_address_change:
            self.__device_address: int = 0x69

        self.__gyroscope_sensitivity: float = 131
        self.__accelerometer_sensitivity: float = 16384
        self.__fifo_temperature_enable: bool = False
        self.__fifo_gyroscope_x_axis_enable: bool = False
        self.__fifo_gyroscope_y_axis_enable: bool = False
        self.__fifo_gyroscope_z_axis_enable: bool = False
        self.__fifo_accelerometer_enable: bool = False
        self.__fifo_number_of_data: int = 0
        self.__complementary_filter_period: float = 0
        self.__complementary_filter_pitch: float = 0
        self.__complementary_filter_roll: float = 0
        self.__complementary_filter_alpha: float = 0.98
        self.__complementary_filter_alpha_complement: float = 1 - self.__complementary_filter_alpha

        self.__self_test_outcome: bool = True
        self.__self_test_result: dict[str, float] = {"xa" : 0.0,
                                                     "ya" : 0.0,
                                                     "za" : 0.0,
                                                     "xg" : 0.0,
                                                     "yg" : 0.0,
                                                     "zg" : 0.0}


        # register addresses
        self.__reg_self_test_x: int = 0x0D
        self.__reg_self_test_y: int = 0x0E
        self.__reg_self_test_z: int = 0x0F
        self.__reg_self_test_a: int = 0x10

        self.__reg_sample_rate_divider: int = 0x19
        self.__reg_configuration: int = 0x1A
        self.__reg_gyroscope_configuration: int = 0x1B
        self.__reg_accelerometer_configuration: int = 0x1C
        self.__reg_fifo_enable: int = 0x23
        self.__reg_int_pin_cfg: int = 0x37
        self.__reg_int_enable: int = 0x38
        self.__reg_int_status: int = 0x3A

        self.__reg_accel_xout_h: int = 0x3B
        self.__reg_accel_xout_l:int = 0x3C
        self.__reg_accel_yout_h:int = 0x3D
        self.__reg_accel_yout_l:int = 0x3E
        self.__reg_accel_zout_h:int = 0x3F
        self.__reg_accel_zout_l:int = 0x40
        self.__reg_temp_h: int = 0x41
        self.__reg_temp_l:int = 0x42
        self.__reg_gyro_xout_h: int = 0x43
        self.__reg_gyro_xout_l:int = 0x44
        self.__reg_gyro_yout_h:int = 0x45
        self.__reg_gyro_yout_l:int = 0x46
        self.__reg_gyro_zout_h:int = 0x47
        self.__reg_gyro_zout_l:int = 0x48

        self.__reg_signal_path_reset: int = 0x68
        self.__reg_user_ctrl: int = 0x6A
        self.__reg_pwr_mgmt_1: int = 0x6B

        self.__reg_fifo_count_h: int = 0x72
        self.__reg_fifo_count_l: int = 0x73
        self.__reg_fifo_r_w: int = 0x74
        self.__reg_who_am_i: int = 0x75

        self.__reset_registers_content()
        if not self.__run_self_tests():
            print('The MPU6050 has not passed the self test')
            #raise RuntimeError('The MPU6050 has not passed the self test')

    def __read_memory(self, addr: int) -> int:
        """
        :param addr:
        Address in the sensor memory from which we want to read 1 byte (8 bits) of data.
        :return:
        The content of the memory location as int.
        """
        value: bytes = self.__i2c.readfrom_mem(
            self.__device_address,
            addr,
            1
        )
        return value[0]

    def __read_memory_burst(self, addr: int, length: int) -> list[int]:
        """
        :param addr:
        Address in the sensor memory from which we want to read 1 byte (8 bits) of data.
        :param length:
        Number of registers that we want to read
        :return:
        list containing the data that we read from registers
        """
        values: bytes = self.__i2c.readfrom_mem(
            self.__device_address,
            addr,
            length
        )
        return list(values)

    def __write_memory(self, addr: int, value: int = 0) -> None:
        """
        :param addr:
        Address in the sensor memory where we want to write 1 byte (8 bits) of data.
        :param value:
        Data stored as number in range 0 to 255.
        :return:
        """
        if value < 0 or value > 255:
            raise ValueError("Number must be between 0 and 255")
        self.__i2c.writeto_mem(
            self.__device_address,
            addr,
            bytes([value]),
            addrsize = 8
        )

    def __activate_software_reset(self):
        """
        Function performs a software reset of the signal paths of the gyroscope, accelerometer and temperature sensor.
        By calling the function the corresponding internal digital filter chains are reset, however the configuration registers
        remain unchanged, i.e. the device does not reboot and does not reinitialize itself.

        When we change the digital low pass filter settings, accelerometer full scale range or gyroscope full scale range the internal
        digital filters and scaling logic are reconfigured, however the internal filters state may contain old data that were measured under
        the old configuration.

        By the software reset we clear old filters history, prevents transient spikes or struck values, ensure the first samples after a
        configuration change are clear and avoid slow settling time of the internal filters.

        The software reset also needs to be called after enabling or disabling the FIFO and waking from the sleep mode.

        The software reset can be also called when the sensor output becomes too noisy or when the sensor is recovering from the
        I2C communication issues or FIFO overflow.
        """
        self.__write_memory(self.__reg_signal_path_reset, 0b0000_0111)
        for i in range(0,10):
            if (self.__read_memory(self.__reg_signal_path_reset) & 0b0000_0111) == 0:
                break
            time.sleep_ms(1)

    def __reset_registers_content(self) -> None:
        """
        Function resets all registers of the MPU6050 to their default state after the boot.
        Called in the constructor of the class to achieve unified behaviour independent of the previous sensor configuration.
        """
        self.sleep_mode_activation(False)
        self.__write_memory(self.__reg_pwr_mgmt_1, 0b1000_0000)
        for i in range(0,100):
            if (self.__read_memory(self.__reg_pwr_mgmt_1) & 0b1000_0000) == 0:
                break
            time.sleep_ms(1)

        # oscillator stabilization
        time.sleep_ms(50)

        self.sleep_mode_activation(False)

        # activating the accurate clok source
        self.__write_memory(self.__reg_pwr_mgmt_1, 0b0000_0001)

    def sleep_mode_activation(self, sleep_mode_state: bool = False) -> None:
        """
        :param sleep_mode_state:
        When set to true the MPU6050 is set into the sleep mode, in which the sensors don't measure any new samples and
        the power consumption is reduced from 500 uA in normal mode to 10 to 20 uA in sleep mode.

        The content of all registers can be also altered when in the sleep mode.

        The sleep mode is used primarily in the battery powered applications, where it allows us to save energy when the
        MPU6050 measurements are not necessary for the current state in which is the system.

        The recommended approach before altering the sample rate divider, digital low-pass filter settings, gyroscope full scale range
        or the accelerometer full scale range is to put the sensor into the sleep mode to prevent generation of signal noise which can
        corrupt the data in the registers and after this settings wake the device.
        :return:
        """
        if sleep_mode_state:
            self.__write_memory(self.__reg_pwr_mgmt_1, 0b0100_0001)
        else:
            self.__write_memory(self.__reg_pwr_mgmt_1, 0b0000_0001)
            # sensor power-up time
            time.sleep_ms(10)
            self.__activate_software_reset()


    def __read_self_test(self, gyro: bool) -> list[int]:
        """
        :param gyro:
        When set to True the data are read from the gyro registers.
        When set to False the data are read from the accelerometer registers.
        :return:
        List contains raw x, y and z axis values from the gyroscope/accelerometer registers.
        """
        time.sleep(0.2)
        if gyro:
            raw_data: list[int] = self.__read_memory_burst(self.__reg_gyro_xout_h, 6)
        else:
            raw_data: list[int] = self.__read_memory_burst(self.__reg_accel_xout_h, 6)
        data_self_test: list[int] = [0, 0, 0]
        data_self_test[0] = self.__to_signed(raw_data[0] << 8 | raw_data[1])
        data_self_test[1] = self.__to_signed(raw_data[2] << 8 | raw_data[3])
        data_self_test[2] = self.__to_signed(raw_data[4] << 8 | raw_data[5])
        return data_self_test

    def __gyro_self_test(self,self_test_response: int, g_test:int, y_axis: bool) -> float:
        """
        :param self_test_response:
        :param g_test:
        :param y_axis:
        :return:
        """
        if y_axis:
            ftg: float = -25 * 131 * (1.046 ** (g_test - 1))
        else:
            ftg: float = 25 * 131 * (1.046 ** (g_test - 1))
        change_gyro: float = (self_test_response - ftg) / ftg
        # +-14 per cent deviation from the factory trim value is okay, larger values means bad sensor.
        if change_gyro < -0.14 or change_gyro > 0.14:
            self.__self_test_outcome = False
        return change_gyro

    def __accel_self_test(self, self_test_response: int, a_test: int) -> float:
        pom: float = (0.92 / 0.34) ** ((a_test - 1) / 30)
        fta: float = 4096 * 0.34 * pom
        change_accel: float = (self_test_response - fta) / fta
        # +-14 per cent deviation from the factory trim value is okay, larger values means bad sensor.
        if change_accel < -0.14 or change_accel > 0.14:
            self.__self_test_outcome = False
        return change_accel

    def __run_self_tests(self) -> bool:
        """
        :return:
        True if the self test was successful, False otherwise.
        """
        self.__self_test_outcome = True

        gyroscope_full_scale_range: int = (self.__read_memory(self.__reg_gyroscope_configuration) & 0b0001_1000 ) >> 3
        accelerometer_full_scale_range: int = (self.__read_memory(self.__reg_accelerometer_configuration) & 0b0001_1000 ) >> 3

        self.change_gyroscope_full_scale_range(0)
        self.change_accelerometer_full_scale_range(2)

        # gyroscope self test
        time.sleep(0.2)
        gyro_original: list[int] = self.__read_self_test(True)
        current_state: int = self.__read_memory(self.__reg_gyroscope_configuration)
        new_state: int = (current_state & 0b00011000) | 0b11100000
        self.__write_memory(self.__reg_gyroscope_configuration, new_state)
        time.sleep(0.2)
        gyro_new: list[int] = self.__read_self_test(True)

        self_test_response_gyro_x: int = gyro_new[0] - gyro_original[0]
        self_test_response_gyro_y: int = gyro_new[1] - gyro_original[1]
        self_test_response_gyro_z: int = gyro_new[2] - gyro_original[2]

        xg_test: int = self.__read_memory(self.__reg_self_test_x) & 0b0001_1111
        yg_test: int = self.__read_memory(self.__reg_self_test_y) & 0b0001_1111
        zg_test: int = self.__read_memory(self.__reg_self_test_z) & 0b0001_1111

        if xg_test != 0:
            self.__self_test_result["xg"] = self.__gyro_self_test(self_test_response_gyro_x, xg_test, False)
        if yg_test != 0:
            self.__self_test_result["yg"] = self.__gyro_self_test(self_test_response_gyro_y, yg_test, True)
        if zg_test != 0:
            self.__self_test_result["zg"] = self.__gyro_self_test(self_test_response_gyro_z, zg_test, False)

        self.__write_memory(self.__reg_gyroscope_configuration, current_state)

        # accelerometer self test
        time.sleep(0.2)
        accelerometer_original: list[int] = self.__read_self_test(False)
        current_state = self.__read_memory(self.__reg_accelerometer_configuration)
        new_state = (current_state & 0b00011000) | 0b11100000
        self.__write_memory(self.__reg_accelerometer_configuration, new_state)
        time.sleep(0.2)
        accelerometer_new: list[int] = self.__read_self_test(False)

        self_test_response_accel_x: int = accelerometer_new[0] - accelerometer_original[0]
        self_test_response_accel_y: int = accelerometer_new[1] - accelerometer_original[1]
        self_test_response_accel_z: int = accelerometer_new[2] - accelerometer_original[2]

        xa_test_h: int = (self.__read_memory(self.__reg_self_test_x) & 0b1110_0000) >> 3
        ya_test_h: int = (self.__read_memory(self.__reg_self_test_y) & 0b1110_0000) >> 3
        za_test_h: int = (self.__read_memory(self.__reg_self_test_z) & 0b1110_0000) >> 3
        xa_test_l: int = (self.__read_memory(self.__reg_self_test_a) & 0b0011_0000) >> 4
        ya_test_l: int = (self.__read_memory(self.__reg_self_test_a) & 0b0000_1100) >> 2
        za_test_l: int = (self.__read_memory(self.__reg_self_test_a) & 0b0000_0011)
        xa_test: int = xa_test_h | xa_test_l
        ya_test: int = ya_test_h | ya_test_l
        za_test: int = za_test_h | za_test_l

        if xa_test != 0:
            self.__self_test_result["xa"] = self.__accel_self_test(self_test_response_accel_x, xa_test)
        if ya_test != 0:
            self.__self_test_result["ya"] = self.__accel_self_test(self_test_response_accel_y, ya_test)
        if za_test != 0:
            self.__self_test_result["za"] = self.__accel_self_test(self_test_response_accel_z, za_test)

        self.__write_memory(self.__reg_accelerometer_configuration, current_state)

        # setting back the original full scale ranges
        self.change_gyroscope_full_scale_range(gyroscope_full_scale_range)
        self.change_accelerometer_full_scale_range(accelerometer_full_scale_range)
        return self.__self_test_outcome


    def who_am_i(self):
        """
        :return:
        The identification of the sensor should be value 104 (represents the sensor default I2C address 0x68).
        """
        address: int = self.__read_memory(self.__reg_who_am_i)
        if address != 104:
            raise RuntimeError('The MPU6050 was not detected')
        return address

    def change_sample_rate_divider(self, sample_rate_setting: int) -> list[float]:
        """
        :param sample_rate_setting:
        Sets the sample rate of the gyroscope and accelerometer.
        The accelerometer internal measurement rate is fixed at 1 kHz, i.e. the accelerometer produces a new internal measurement every 1 ms.
        The gyroscope internal measurement rate is:
            8 kHz when the Digital Low‑Pass Filter (DLPF) is disabled, i.e. the gyroscope produces a new internal measurement every 0.125 ms.
            1 kHz when the DLPF is enabled, i.e. the gyroscope produces a new internal measurement every 1 ms.
        Using the sample rate divider (SMPLRT_DIV), we control how often these internally measured values are written into the output registers and made available to the MCU.
        The divider can be any value from 0 to 255, and the resulting output sample rate is:
            sample_rate=internal_rate / (1 + divider)
        Changing the divider affects both the accelerometer and gyroscope output sample rates.
        For stable readings, the DLPF should be enabled and the sample rate reduced below 250 Hz.
        For fast‑motion tracking, the DLPF may be disabled to allow higher output rates up to 8 kHz, at the cost of increased noise.
        :return:
        list containing two elements, first element is the sample rate of the gyroscope, second element is the sample rate of the accelerometer.
        """
        self.__write_memory(self.__reg_sample_rate_divider, sample_rate_setting)
        data_sample_rate = [0.0,0.0]
        if self.__read_memory(self.__reg_configuration) & 0b0000_0111 == 0:
            data_sample_rate[0] = 8000/(1 + sample_rate_setting)
        else:
            data_sample_rate[0] = 1000/(1 + sample_rate_setting)
        data_sample_rate[1] = 1000/(1 + sample_rate_setting)
        if data_sample_rate[0] == data_sample_rate[1]:
            self.__complementary_filter_period = 1/data_sample_rate[0]
        return data_sample_rate

    def change_digital_low_pass_filter_setting(self, setting: int) -> bool:
        """
        :param setting:
        The digital low‑pass filter (DLPF) affects the noise, latency, and bandwidth of the accelerometer and gyroscope.
        The DLPF removes high‑frequency noise from the accelerometer and gyroscope signals.
        When the DLPF is set to low values (0 or 1), the sensor responds quickly to changes in motion; however, the data contains a significant amount of high‑frequency noise. These settings are used primarily in drones, robots, or any system requiring fast control.
        When the DLPF is set to high values (4, 5, or 6), the sensor responds very slowly to changes in motion; however, the data contains only a minimal amount of high‑frequency noise. These settings are used mainly for tilt sensing, slow‑motion tracking, or smoothing noisy data.
        When the DLPF is set to middle values (2 or 3), it provides a balanced choice suitable for most applications.

        The following table summarizes the DLPF values for the accelerometer.
        The first column shows the setting number.

        The second column shows the accelerometer bandwidth (the cutoff frequency above which signals are heavily attenuated).
        For example, if the bandwidth is set to 44 Hz, motions faster than 44 Hz are heavily filtered out, and noise above that frequency is removed. The output becomes smoother but slower.

        The third column shows the accelerometer delay (the response time indicating how long it takes before sensor motion affects the readings).
        For example, if the delay is set to 4.9 ms, the reading from the sensor is approximately 4.9 ms behind the real motion. This small delay matters for fast control loops.

        The fourth column shows the accelerometer’s internal measurement rate.
        Setting     Bandwidth(Hz)   Delay(ms)   Measurement rate (kHz)      Notes
        0           260             0           1                           Fastest response, most noise
        1           184             2.0         1                           Good for fast motions
        2           94              3.0         1                           Balanced (recommended for most applications)
        3           44              4.9         1                           Smooth output, moderate delay
        4           21              8.5         1                           Very smooth output, and slow response
        5           10              13.8        1                           Very slow response
        6           5               19.0        1                           Ultra smooth output, high delay

        The following table summarizes the DLPF values for the gyroscope.
        The columns have the same meaning as in the accelerometer table.
        Setting     Bandwidth(Hz)   Delay(ms)   Measurement rate (kHz)      Notes
        0           256             0.98        8                           Fastest response, most noise
        1           188             1.9         1                           Good for fast motions
        2           98              2.8         1                           Balanced (recommended for most applications)
        3           42              4.8         1                           Smooth output, moderate delay
        4           20              8.3         1                           Very smooth output, and slow response
        5           10              13.4        1                           Very slow response
        6           5               18.6        1                           Ultra smooth output, high delay

        Setting the DLPF value affects both the accelerometer and the gyroscope simultaneously.

        Return:
        False if the parameter value is outside the allowed range (0 to 6).
        True if the settings were applied successfully.
        """
        if setting < 0 or setting > 6:
            print('change_digital_low_pass_filter_setting wrong argument value')
            return False
        current_state: int = self.__read_memory(self.__reg_configuration)
        current_state = current_state & 0b11111000
        new_state: int = current_state | setting
        self.__write_memory(self.__reg_configuration, new_state)
        self.__activate_software_reset()
        return True

    def change_gyroscope_full_scale_range(self, setting: int) -> bool:
        """
        :param setting:
        Gyroscope full‑scale range (FSR) directly affects the maximum measurable angular velocity on its three axes (x, y, z).
        Angular velocity expresses how fast the object is rotating around a given axis. It is expressed in degrees per second (°/s) or radians per second (rad/s). Angular velocity therefore represents the rotation speed; by integrating it over time we can calculate the change in orientation, and we can determine how the object moves in 3D space.

        With a small FSR (±250 °/s), we can measure only slow rotations of the object. This setting is used for slow stabilization tasks or robotic joints.
        With a high FSR (±2000 °/s), we can measure fast rotations of the object. This setting is used for drones, RC cars, or gimbals.

        When the rotation speed exceeds the selected FSR, saturation (also called clipping) occurs, and the measured values no longer represent the actual rotational speed of the object. Therefore, by increasing the FSR, we affect the angular velocity at which the sensor saturates.

        With the MPU6050 we can choose from four settings described in the following table:
        Setting     Full Scale Range    Sensitivity    Application             Notes
        0           +- 250 °/s          131            Stabilization systems   Maximum sensitivity
        1           +- 500 °/s          65.5           Human motion            Less sensitive, slower motion
        2           +- 1000 °/s         32.8           General robotics        Fast motions
        3           +- 2000 °/s         16.4           Racing drones           Extreme motions

        The sensitivity is used when converting the raw data from registers into the degrees per second.

        With a low FSR, each ADC step represents a smaller change in angular velocity; therefore, the sensor becomes more sensitive to small changes in motion. In other words, even small motions produce large changes in the digital value stored in the registers. The disadvantage is that even small noise in the analogue output signal will strongly affect the digital value.
        With a high FSR, each ADC step represents a larger change in angular velocity; therefore, the sensor becomes less sensitive to small changes in motion. Small motions produce only small changes in the digital value stored in the registers. The advantage is that small noise in the analogue output signal will affect the digital value only slightly.
        Therefore, increasing the FSR provides better noise immunity (even though the physical noise does not change), at the cost of reduced angular‑velocity measurement precision.
        :return:
        False if the parameter value is outside the allowed range (0 to 3).
        True if the settings were applied successfully.
        """
        if setting < 0 or setting > 3:
            print('change_gyroscope_full_scale_range wrong argument value')
            return False

        current_state: int = self.__read_memory(self.__reg_gyroscope_configuration) & 0b11100111
        setting_shifted: int = setting << 3
        new_state: int = current_state | setting_shifted
        self.__write_memory(self.__reg_gyroscope_configuration, new_state)
        self.__activate_software_reset()
        self.__determine_gyroscope_sensitivity()
        return True

    def __determine_gyroscope_sensitivity(self) -> None:
        """
        :return:
        """
        current_setting: int = (self.__read_memory(self.__reg_gyroscope_configuration) & 0b0001_1000) >> 3
        if current_setting == 0:
            self.__gyroscope_sensitivity = 131
        elif current_setting == 1:
            self.__gyroscope_sensitivity =  65.5
        elif current_setting == 2:
            self.__gyroscope_sensitivity =  32.8
        elif current_setting == 3:
            self.__gyroscope_sensitivity =  16.4

    def change_accelerometer_full_scale_range(self, setting: int) -> bool:
        """
        :param setting:
        Accelerometer full-scale range (FSR) directly affects the maximum measurable acceleration on its three axes (x, y, z).
        Acceleration describes how quickly the object's velocity changes in a given axis. It is usually expressed in the units of gravitational force (g) or m/s² and 1 g ≈ 9.81 m/s².
        Acceleration is therefore the rate of change of velocity in a given axis, but not the speed itself. Therefore, if the objects move at constant velocity in straight line,
        the accelerometer reads in x and y-axis 0g and if the object speeds up, slows down, or changes direction, the accelerometer detects the acceleration.
        When the object is stationary or moving just in the x and y-axis the acceleration in the z axis is 1, however if the object is tilted to side during movement the acceleration in the z axis changes.

        With a small FSR (± 2 g), we can measure only slow accelerations of the object. This setting is used for slow stabilization tasks or robotic joints.
        With a high FSR (± 16 g), we can measure fast accelerations of the object. This setting is used for drones, RC cars, or gimbals.

        When the acceleration exceeds the selected FSR, saturation (also called clipping) occurs, and the measured values no longer represent the actual acceleration of the object. Therefore, by increasing the FSR, we affect the acceleration at which the sensor saturates.

        With the MPU6050 we can choose from four settings described in the following table:
        Setting     Full Scale Range    Sensitivity   Application                 Notes
        0           +- 2 g              16384         Tilt sensing, slow motion   Highest precision
        1           +- 4 g              8192          Walking, human motion       Moderate motion
        2           +- 8 g              4096          Robotics, drones            Fast motion, impacts
        3           +- 16 g             2048          High-impact systems         Extreme motion

        The sensitivity is used when converting the raw data from registers into the gravitational force.

        With a low FSR, each ADC step represents a smaller change in acceleration; therefore, the sensor becomes more sensitive to small changes in motion. In other words, even small changes in motion produce large changes in the digital value stored in the registers. The disadvantage is that even small noise in the analogue output signal will strongly affect the digital value.
        With a high FSR, each ADC step represents a larger change in acceleration; therefore, the sensor becomes less sensitive to small changes in motion. Small changes in motion produce only small changes in the digital value stored in the registers. The advantage is that small noise in the analogue output signal will affect the digital value only slightly.
        Therefore, increasing the FSR provides better noise immunity (even though the physical noise does not change), at the cost of reduced acceleration measurement precision.
        :return:
        False if the parameter value is outside the allowed range (0 to 3).
        True if the settings were applied successfully.
        """
        if setting < 0 or setting > 3:
            print('change_accelerometer_full_scale_range wrong argument value')
            return False

        current_state: int = self.__read_memory(self.__reg_accelerometer_configuration) & 0b11100111
        setting_shifted: int = setting << 3
        new_state: int = current_state | setting_shifted
        self.__write_memory(self.__reg_accelerometer_configuration, new_state)
        self.__activate_software_reset()
        self.__determine_accelerometer_sensitivity()
        return True

    def __determine_accelerometer_sensitivity(self) -> None:
        """

        :return:
        """
        current_setting: int = (self.__read_memory(self.__reg_accelerometer_configuration) & 0b0001_1000) >> 3
        if current_setting == 0:
            self.__accelerometer_sensitivity = 16384
        elif current_setting == 1:
            self.__accelerometer_sensitivity = 8192
        elif current_setting == 2:
            self.__accelerometer_sensitivity = 4096
        elif current_setting == 3:
            self.__accelerometer_sensitivity = 2048

    def change_fifo_enable_settings(self,
                                    temp: bool = False,
                                    gyroscope_x_axis: bool = False,
                                    gyroscope_y_axis: bool = False,
                                    gyroscope_z_axis: bool = False,
                                    accelerometer: bool = False):

        """
        The MPU6050 contains FIFO buffer into which can be stored the measured data from the sensors.
        The FIFO buffer is used when the sample rate of the microcontroller is smaller than the sample rate of the sensors.
        I.e. The sensor takes measurements faster than the microcontroller can read them, and we want to prevent the loss of samples.
        FIFO buffer have size of 1024 bytes (1 KB) when the FIFO overflows the oldest data are lost and new data are stored into the buffer.
        When multiple FIFO sources are enabled the order and size of the stored data are fixed, and the data type stored in the FIFO is determined
        by the enabled FIFO sources, the known byte length of each enabled data block and the fixed order in the MPU6050 writes data into the FIFO.

        1.  Accelerometer data (6 bytes)
        2.  Gyroscope X axis data (2 bytes)
        3.  Gyroscope Y axis data (2 bytes)
        4.  Gyroscope Z axis data (2 bytes)
        5.  Temperature (2 bytes)
        Only the data from the enabled sources are stored into the FIFO however they are always stored in this order, i.e. the data from
        not enabled sources are skipped.

        The data from the FIFO always needs to be read as group, i.e. when we enable just the gyroscope X axis data (2 bytes) and temperature data (2 bytes)
        we always need to read 4 bytes of data from the FIFO as group.

        The FIFO needs to be globally enabled via the USER_CTRL register.

        :param temp:
        When set to true the temperature measurements will be stored into the FIFO buffer.
        Each temperature measurements require 2 bytes of memory
        :param gyroscope_x_axis:
        When set to true the gyroscope x-axis measurements will be stored in FIFO buffer.
        :param gyroscope_y_axis:
        When set to true the gyroscope y-axis measurements will be stored in FIFO buffer.
        :param gyroscope_z_axis:
        When set to true the gyroscope z-axis measurements will be stored in FIFO buffer.
        :param accelerometer:
        When set to true the accelerometer measurements will be stored in FIFO buffer.
        :return:
        """
        settings: int = 0
        if temp:
            settings = settings | 0b1000_0000
        if gyroscope_x_axis:
            settings = settings | 0b0100_0000
        if gyroscope_y_axis:
            settings = settings | 0b0010_0000
        if gyroscope_z_axis:
            settings = settings | 0b0001_0000
        if accelerometer:
            settings = settings | 0b0000_1000

        if settings != 0:
            self.__write_memory(self.__reg_user_ctrl, 0b0000_0000)
            self.__write_memory(self.__reg_user_ctrl, 0b0000_0100)
            self.__write_memory(self.__reg_fifo_enable, settings)
            self.__write_memory(self.__reg_user_ctrl, 0b0100_0000)
            self.__activate_software_reset()
            self.__determine_fifo_enable_settings()
        else:
            self.__write_memory(self.__reg_user_ctrl, 0b0000_0000)
            self.__activate_software_reset()


    def __determine_fifo_enable_settings(self) -> None:
        """

        :return:
        """
        current_settings: int = self.__read_memory(self.__reg_fifo_enable)
        self.__fifo_number_of_data = 0
        if (current_settings & 0b1000_0000) != 0:
            self.__fifo_temperature_enable = True
            self.__fifo_number_of_data = self.__fifo_number_of_data + 2
        else:
            self.__fifo_temperature_enable = False

        if current_settings & 0b0100_0000 != 0:
            self.__fifo_gyroscope_x_axis_enable = True
            self.__fifo_number_of_data = self.__fifo_number_of_data + 2
        else:
            self.__fifo_gyroscope_x_axis_enable = False

        if current_settings & 0b0010_0000 != 0:
            self.__fifo_gyroscope_y_axis_enable = True
            self.__fifo_number_of_data = self.__fifo_number_of_data + 2
        else:
            self.__fifo_gyroscope_y_axis_enable = False

        if current_settings & 0b0001_0000 != 0:
            self.__fifo_gyroscope_z_axis_enable = True
            self.__fifo_number_of_data = self.__fifo_number_of_data + 2
        else:
            self.__fifo_gyroscope_z_axis_enable = False

        if current_settings & 0b0000_1000 != 0:
            self.__fifo_accelerometer_enable = True
            self.__fifo_number_of_data = self.__fifo_number_of_data + 6
        else:
            self.__fifo_accelerometer_enable = False


    def change_interrupt_settings(self,
                                  int_level: bool = False,
                                  int_open: bool = False,
                                  latch_int_enable: bool = True,
                                  int_rd_clear: bool = False,
                                  fifo_oflow_enable: bool = False,
                                  data_rdy_enable: bool = False,):
        """
        :param int_level:
        When set to false, the interrupt pin will output a logic one during an interrupt.
        When set to true, the interrupt pin will output a logic zero during an interrupt.

        :param int_open:
        When set to false, the interrupt pin is configured as push‑pull (no external pull‑up or pull‑down resistors required).
        When set to true, the interrupt pin is configured as open‑drain (the pin can actively drive only to GND, and an external pull‑up resistor is required).

        :param latch_int_enable:
        When set to false, the interrupt pin generates a pulse lasting at least 50 µs; the polarity of the pulse depends on the int_level bit.
        When set to true, the interrupt pin is held in the state determined by the int_level bit until the interrupt status bit is cleared.

        :param int_rd_clear:
        When set to false, the interrupt status bit in register INT_ENABLE which caused the interrupt is cleared only by reading the INT_STATUS register.
        When set to true, the interrupt status bit in register INT_ENABLE which caused the interrupt is cleared by any read operation.

        :param fifo_oflow_enable:
        When set to true, an interrupt will be generated each time the FIFO buffer overflows (when there is no more space
        to store new data, and old data needs to be erased to make space for the new one).

        :param data_rdy_enable:
        When set to true, an interrupt will be generated each time the full set of measurements (gyroscope, accelerometer, and temperature)
        is written into the registers, replacing the previous results. This can be used to synchronize register reads by the
        microcontroller with register updates by the MPU6050.


        :return:
        """
        settings: int = 0
        if int_level:
            settings = settings | 0b1000_0000
        if int_open:
            settings = settings | 0b0100_0000
        if latch_int_enable:
            settings = settings | 0b0010_0000
        if int_rd_clear:
            settings = settings | 0b0001_0000
        self.__write_memory(self.__reg_int_pin_cfg, settings)

        settings = 0
        if fifo_oflow_enable:
            settings = settings | 0b0001_0000
        if data_rdy_enable:
            settings = settings | 0b0000_0001
        self.__write_memory(self.__reg_int_enable, settings)

    def read_the_interrupt_status_register(self) -> list[int]:
        """
        :return:
        List containing two integers.
        When the first integer is set to 1, the interrupt was caused by the fifo_oflow_enable event.
        When the second integer is set to 1, the interrupt was caused by the data_rdy_enable event.

        When int_rd_clear is set to false and latch_int_enable is set to true, the interrupt state will be cleared
        by calling this function.
        """
        data_interrupt_status: int = self.__read_memory(self.__reg_int_status)
        output: list[int] = [0,0]
        if data_interrupt_status & 0b0001_0000 == 16:
            output[0] = 1
        if data_interrupt_status & 0b0000_0001 == 1:
            output[1] = 1
        return output

    @staticmethod
    def __to_signed(value) -> int:
        """
        :param value:
        Function is checking if the raw data (value) are negative or positive and converting then to signed integer
        :return:
        signed integer
        """
        return value - 0x10000 if value & 0x8000 else value

    def read_all_sensors(self) -> dict[str,float]:
        """
        Function reads the data from all sensors registers in the burst mode
        :return:
        List containing seven floats.
        First element of list is the acceleration in the x-axis in the gravitational force (g).
        Second element of list is the acceleration in the y-axis in the gravitational force (g).
        Third element of list is the acceleration in the z-axis in the gravitational force (g).
        Fourth element of list is the angular velocity in the x-axis in the degrees per second (°/s).
        Fifth element of list is the angular velocity in the y-axis in the degrees per second (°/s).
        Sixth element of list is the angular velocity in the z-axis in the degrees per second (°/s).
        Seventh element is the temperature in degrees of Celsius.
        """
        raw_bytes: list[int] = self.__read_memory_burst(self.__reg_accel_xout_h, 14)

        ax = (raw_bytes[0] << 8) | raw_bytes[1]
        ay = (raw_bytes[2] << 8) | raw_bytes[3]
        az = (raw_bytes[4] << 8) | raw_bytes[5]

        temp = (raw_bytes[6] << 8) | raw_bytes[7]

        gx = (raw_bytes[8] << 8) | raw_bytes[9]
        gy = (raw_bytes[10] << 8) | raw_bytes[11]
        gz = (raw_bytes[12] << 8) | raw_bytes[13]

        data_sensors_readings: dict[str,float] = {"ax": self.__to_signed(ax) / self.__accelerometer_sensitivity,
                                                  "ay": self.__to_signed(ay) / self.__accelerometer_sensitivity,
                                                  "az": self.__to_signed(az) / self.__accelerometer_sensitivity,
                                                  "gx": self.__to_signed(gx) / self.__gyroscope_sensitivity,
                                                  "gy": self.__to_signed(gy) / self.__gyroscope_sensitivity,
                                                  "gz": self.__to_signed(gz) / self.__gyroscope_sensitivity,
                                                  "temp": self.__to_signed(temp) / 340.0 + 36.53}

        return data_sensors_readings

    def __number_of_bytes_in_fifo_register(self) -> int:
        """
        :return:
        The current number of bytes stored in the FIFO registers.
        """
        number_h = self.__read_memory(self.__reg_fifo_count_h)
        number_h = number_h << 8
        number_l = self.__read_memory(self.__reg_fifo_count_l)
        return number_h | number_l

    def __read_fifo_word(self) -> int:
        """
        :return:
        16 bits read from the FIFO register.
        """
        data_fifo_buffer = self.__read_memory_burst(self.__reg_fifo_r_w,2)
        return (data_fifo_buffer[0] << 8) | data_fifo_buffer[1]

    def read_data_from_fifo_register(self) -> dict[str,float] | None:
        """
        Reads the data from the FIFO register.

        :return:
        None when the FIFO register is empty.
        List containing seven floats when the FIFO register contains data.
        First element of list is the acceleration in the x-axis in the gravitational force (g).
        Second element of list is the acceleration in the y-axis in the gravitational force (g).
        Third element of list is the acceleration in the z-axis in the gravitational force (g).
        Fourth element of list is the angular velocity in the x-axis in the degrees per second (°/s).
        Fifth element of list is the angular velocity in the y-axis in the degrees per second (°/s).
        Sixth element of list is the angular velocity in the z-axis in the degrees per second (°/s).
        Seventh element is the temperature in degrees of Celsius.
        The data are stored just from the sensors enabled by the function change_fifo_enable_settings
        """
        if self.__number_of_bytes_in_fifo_register() < self.__fifo_number_of_data:
            return None

        data_sensors_readings: dict[str, float | None] = {"ax": None, "ay": None, "az": None, "gx": None, "gy": None,
                                                          "gz": None, "temp": None}
        if self.__fifo_accelerometer_enable:
            data_sensors_readings["ax"] = self.__to_signed(self.__read_fifo_word()) / self.__accelerometer_sensitivity
            data_sensors_readings["ay"] = self.__to_signed(self.__read_fifo_word()) / self.__accelerometer_sensitivity
            data_sensors_readings["az"] = self.__to_signed(self.__read_fifo_word()) / self.__accelerometer_sensitivity
        if self.__fifo_temperature_enable:
            data_sensors_readings["temp"] = self.__to_signed(self.__read_fifo_word()) / 340.0 + 36.53
        if self.__fifo_gyroscope_x_axis_enable:
            data_sensors_readings["gx"] = self.__to_signed(self.__read_fifo_word()) / self.__gyroscope_sensitivity
        if self.__fifo_gyroscope_y_axis_enable:
            data_sensors_readings["gy"] = self.__to_signed(self.__read_fifo_word()) / self.__gyroscope_sensitivity
        if self.__fifo_gyroscope_z_axis_enable:
            data_sensors_readings["gz"] = self.__to_signed(self.__read_fifo_word()) / self.__gyroscope_sensitivity

        return data_sensors_readings

    def set_frequency_of_complementary_filter(self, frequency):
        """
        :param frequency:
        The frequency at which the MPU6050 takes the samples from the input.
        :return:
        """
        self.__complementary_filter_period = 1/frequency

    def complementary_filter(self, measured_values: dict[str,float]) -> list[float]:
        """
        :param measured_values:
        Measured values from the MPU6050 accelerometer and gyroscope
        :return:
        list contains two elements, the first one is the pitch and the second is the roll
        """
        # Calculating angles in radians from the accelerometer data
        accel_pitch: float = math.atan2(measured_values["ax"],
                                        math.sqrt(measured_values["ay"] ** 2 + measured_values["az"] ** 2))
        accel_roll: float = math.atan2(measured_values["ay"],measured_values["az"])

        # formulas for our board
        #accel_pitch: float = math.atan2(measured_values["ay"], measured_values["az"])
        #accel_roll: float = math.atan2(-measured_values["ax"],
        #                        math.sqrt(measured_values["ay"] ** 2 + measured_values["az"] ** 2))

        # Converting gyroscope angles to radians
        gx: float = math.radians(measured_values["gx"])
        gy: float = math.radians(measured_values["gy"])

        # Calculating angles in radians from the gyroscope data
        gyro_pitch: float = self.__complementary_filter_pitch + gx * self.__complementary_filter_period
        gyro_roll: float = self.__complementary_filter_roll + gy * self.__complementary_filter_period

        # Complementary filter
        self.__complementary_filter_pitch = (
                self.__complementary_filter_alpha * gyro_pitch +
                (1 - self.__complementary_filter_alpha) * accel_pitch
        )

        self.__complementary_filter_roll = (
                self.__complementary_filter_alpha * gyro_roll +
                (1 - self.__complementary_filter_alpha) * accel_roll
        )

        # Complementary filter returns the angles in radians
        return [self.__complementary_filter_pitch, self.__complementary_filter_roll]





# Filters implementation:
# Complementary Filter
# Mahony filter
# Madgwick filter



# i2c_object: I2C = I2C(0, sda=Pin(6), scl=Pin(7))
#
# mpu6050:MPU6050 = MPU6050(i2c_object)
# # print(mpu6050.who_am_i())
#
# # waking up the chip from sleep mode
# mpu6050.sleep_mode_activation(False)
#
#
# mpu6050.change_digital_low_pass_filter_setting(3)
# print(mpu6050.change_sample_rate_divider(10))
# mpu6050.change_gyroscope_full_scale_range(3)
# mpu6050.change_accelerometer_full_scale_range(3)
#
# mpu6050.change_fifo_enable_settings(temp=False,
#                                     gyroscope_x_axis=True,
#                                     gyroscope_y_axis=True,
#                                     gyroscope_z_axis=True,
#                                     accelerometer=True)
#
# mpu6050.change_interrupt_settings(int_level=True,
#                                   int_open=False,
#                                   latch_int_enable=False,
#                                   int_rd_clear=False,
#                                   fifo_oflow_enable= False,
#                                   data_rdy_enable=False)
#
# mpu6050.read_the_interrupt_status_register()
#
# counter = 0
#
# while True:
#     data = mpu6050.read_data_from_fifo_register()
#     if data is not None:
#         #print(data)
#         #print(mpu6050.read_all_sensors())
#         print(mpu6050.complementary_filter(data))
#         print()
#         #counter = counter + 1
#         #if counter > 30:
#         #    break

