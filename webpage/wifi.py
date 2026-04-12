import network
import time

class Wifi:
    def __init__(self,
                 station : bool) -> None:
        if station:
            self.__nic: network.WLAN = network.WLAN(network.STA_IF)
        else:
            self.__nic: network.WLAN = network.WLAN(network.AP_IF)
        self.__nic.active(False)
        time.sleep(0.5)
        self.__nic.active(True)
        self.__station : bool = station

    def create_wifi(self, name : str, pwd : str)-> None:
        if self.__station:
            print("You are operating like a station")
            return
        if pwd == "":
            self.__nic.config(essid=name,
                              authmode=network.AUTH_OPEN)
        else :
            self.__nic.config(essid=name,
                   authmode=network.AUTH_WPA_PSK,
                   password=pwd)

    def connect_to_wifi(self,name : str, pwd : str)-> None:
        if not self.__station:
            print("You are operating like a access point")
            return
        self.__nic.connect(name,pwd)
        while True:
            status: int = self.__nic.status()
            if status == network.STAT_GOT_IP:
                print("The ESP32 has connected")
                print(f"Network config : {self.__nic.ifconfig()}")
                break
            elif status in (network.STAT_WRONG_PASSWORD,
                            network.STAT_NO_AP_FOUND,
                            network.STAT_CONNECT_FAIL):
                print(f"Conection failed, status : {status}")
                break
            print(f"Connecting, status : {status}")
            time.sleep(1)