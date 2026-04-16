import urequests
import gc

class ThingSpeak:
    """Class used for work with ThingSpeak."""
    
    def __init__(self) -> None:
        """
        Constructor of the class.

        :param: None
        :return: None
        """
        self.__thingspeak_write_api_key = ''
        self.__thingspeak_read_api_key = ''
        self.__thingspeak_channel_id = ''
        
    def set_write_api_key(self, write_api_key: str) -> None:
        """
        With this function we can set the write API key for ThingSpeak

        :param write_api_key: str
        :return: None

        Parameters:
        - First parameter is the write api key used for communication
        with ThingSpeak
        """
        self.__thingspeak_write_api_key = str(write_api_key)
        del write_api_key
        gc.collect()
        
    def set_read_api_key(self, read_api_key: str) -> None:
        """
        With this function we can set the read API key for ThingSpeak

        :param read_api_key: str
        :return: None

        Parameters:
        - First parameter is the read api key used for communication
        with ThingSpeak
        """
        self.__thingspeak_read_api_key = str(read_api_key)
        del read_api_key
        gc.collect()
        
    def set_channel_id(self, channel_id: str) -> None:
        """
        With this function we can set the channel id for ThingSpeak

        :param channel_id: str
        :return: None

        Parameters:
        - First parameter is the channel id used for communication
        with ThingSpeak
        """
        self.__thingspeak_channel_id = str(channel_id)
        del channel_id
        gc.collect()
        
    def send_data(self, data: dict) -> int:
        """
        This function can send data to the ThingSpeak.

        :param data: dict
        :return: int

        Parameters:
        - the first parameter are the data that we want to send
        to the ThingSpeak.

        Return:
        - 0 if data was succesfully sent.
        - 1 if the write api key was not set.
        - 2 if the data is not or cannot be transformed to dictionary.
        - 3 if the curent WiFi network dont support ThingSpeak
        communication.
        """
        if self.__thingspeak_write_api_key == '':
            print('at first you must set write api key')
            print('ThingSpeak - send_data')
            del data
            gc.collect()
            return 1
        
        if type(data) != dict:
            try:
                data = eval(data)
            except NameError:
                print('the parameter to this function must be dictionary')
                print('ThingSpeak - send_data')
                del data
                gc.collect()
                return 2                
        
        try:
            request = urequests.post('http://api.thingspeak.com/update?api_key=' +
                                    self.__thingspeak_write_api_key,
                                    json = data,
                                    headers = {'Content-Type': 'application/json'})
        except ValueError:
            print('the current network dont support ThingSpeak communication')
            del data
            return 3
        request.close()
        
        del request
        del data
        gc.collect()
        
        return 0

    def gather_data(self, number_of_previous_samples: str = 0) -> list:
        """
        This function is used for gathering data from the ThingSpeak.

        :param number_of_previous_samples: str, default = 0
        :return: list

        Parameters:
        - the first parameter is maximal number of previouse samples
        that we want to gather from the ThingSpeak.

        Return:
        - This function return list.
            * first element
            - If the first element of the list is 0 we have succesfully
            gathered the data from the ThingSpeak.
            - If it is 1 the first parameter cant be converted to int.
            - If it is 2 the read api key was not set.
            - If it is 3 the channel id was not set
            - If it is 4 the curent WiFi network dont support ThingSpeak
            communication.
            - If it is 5 the set ThingSpeak read api key is invallid.
            
            * second element
            - if we have gathered some data the second parameter are
            general information about ThingSpeak account. The second
            element is dictionary
            
            * third element
            - if we have gathered some data the third parameter is list
            containing previously measured data. If we set the first
            parameter to 0 it is an empty list. The elements of this list
            are dictionaries. If we set the first parameter to number higher
            then the amount of data in the ThingSpeak the function will
            return all the data that was so far uploaded to the ThingSpeak.
        """
        try:
            number_of_previous_samples = int(number_of_previous_samples)
            number_of_previous_samples = str(number_of_previous_samples)
        except ValueError:
            print('first parameter cant be converted to int')
            print('ThingSpeak - gather_data')
            del number_of_previous_samples
            gc.collect()
            return [1]
        
        if self.__thingspeak_read_api_key == '':
            print('at first you must set read api key')
            print('ThingSpeak - gather_data')
            del number_of_previous_samples
            gc.collect()
            return [2]
        
        if self.__thingspeak_channel_id == '':
            print('at first you must set channel id')
            print('ThingSpeak - gather_data')
            del number_of_previous_samples
            gc.collect()
            return [3]

        request = urequests.get('http://api.thingspeak.com/channels/' +
                         self.__thingspeak_channel_id +
                         '/feeds.json?api_key=' +
                         self.__thingspeak_read_api_key +
                         '&results=' +
                         number_of_previous_samples
                         )
        message = request.text
        request.close()
        
        beginning = message.find('"feeds":[')
        beginning2 = message.find('{"channel":') + 1
        if beginning2 != 1:
            if message == '-1':
                print('the enterred thingspeak read api key or channel id is invallid')
                return [5]
            else:
                print('the current network dont support ThingSpeak communication')
                return [4]
        general_information = None
        try:
            general_information = eval(message[(beginning2 + len('"channel":')):beginning-1])
        except NameError:
            beginning3 = message.find('"last_entry_id"')
            general_information = eval(message[(beginning2 + len('"channel":')):beginning3-1] + '}')
            del beginning3
            gc.collect()
        previous_data = message[beginning + len('"feeds":['):-2]
        if int(number_of_previous_samples) == 0:
            del number_of_previous_samples
            del request
            del message
            del beginning
            del beginning2
            del previous_data
            gc.collect()
            return [0, general_information, []]
            
        previous_data_array = [''] * int(number_of_previous_samples)
        
        for i in range(0,int(number_of_previous_samples)):
            if i == (int(number_of_previous_samples)-1):
                previous_data_array[i] = eval(previous_data[0:])
                break
            
            find_character = previous_data.find('},{') + 1
            if find_character == 0:
                previous_data_array[i] = eval(previous_data[0:])
                previous_data_array_pom = [''] * (i+1)
                for x in range(0,(i+1)):
                    previous_data_array_pom[x] = previous_data_array[x]
                    
                previous_data_array = None
                gc.collect()
                    
                previous_data_array = previous_data_array_pom
                
                del previous_data_array_pom
                del find_character
                gc.collect()               
                break
            
            previous_data_array[i] = eval(previous_data[0:find_character])
            previous_data = previous_data[(find_character+1):]
            del find_character
            gc.collect()
            
        del number_of_previous_samples
        del request
        del message
        del beginning
        del beginning2
        del previous_data
        gc.collect()

        return [0, general_information, previous_data_array]
