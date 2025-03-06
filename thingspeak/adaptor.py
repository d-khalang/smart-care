import requests
import threading
import json
from typing import Literal
from MyMQTT2 import MyMQTT
from config import Config, MyLogger

class MyClientMQTT():
    def __init__(self, clientID, broker, port, host, child_logger):
        self.host = host
        self.client = MyMQTT(clientID, broker, port, host, child_logger)


    ## Connecting to the broker
    def start(self):
        self.client.start()

    ## Disconnecting from the broker
    def stop(self):
        self.client.stop()

    def publish(self, topic, msg):
        self.client.myPublish(topic, msg)

    # Add the topic to the subscribed topics not substitude
    def subscribe(self, topic):
        self.client.mySubscribe(topic)

    def unsubscribe(self, topic):
        self.client.unsubscribe(topic)



class Adaptor():
    def __init__(self, config: Config):
        self.config = config
        self.catalog_address = self.config.CATALOG_URL
        self.logger = MyLogger.get_main_loggger()
        self.endpoint_cache = {}
        self.broker = ""
        self.port = None
        self.rooms = []
        self.topic = ""
        self.main_topic = ""
        self.sensors_by_room = {}
        self.channels_detail = {}
        self.user_API_key = self.config.USER_API_KEY
        self.available_measure_types = self.config.AVAILABLE_MEASURE_TYPES

        self.logger.info("Initiating the adaptor...")
        self.get_broker()
        self.initiate_mqtt()
        self.post_service()
        self.get_topic_template()
        self.prepare_main_topic()
        self.subscribe_to_topic()
        self.update_and_sort_devices_by_room()
        self.check_and_create_channel()
        # self.start_update_timer()
        print()


    def start_update_timer(self):
        # Ensure the timer starts only once
        self.update_timer = threading.Timer(self.config.UPDATE_INTERVAL, self.update_and_sort_devices_by_room)
        self.update_timer.daemon = True
        self.update_timer.start()


    def check_and_create_channel(self):
        # Step 1: Send request to retrieve list of channels
        url = self.config.THINGSPEAK_URL + self.config.THINGSPEAK_CHANNELS_ENDPOINT + self.config.USER_API_KEY
        # url = self.config.CHANNELS_API.replace("{API_key}", self.user_API_key)
        response = requests.get(url)
        channels = response.json()

        for room_id in self.rooms:
            channel_name = str(room_id)

            # Dictionary mapping field numbers to their names according to data sensing devices
            field_names_dict = {}
            fieldNum = 1
            for device in self.sensors_by_room[room_id]:
                for measure_type in device["measureTypes"]:
                    if measure_type in self.available_measure_types:
                        plant_id = device["deviceLocation"].get("plantId")
                        if plant_id:
                            field_names_dict[f"field{fieldNum}"] = f"{measure_type}-{plant_id}"
                        else:
                            field_names_dict[f"field{fieldNum}"] = measure_type
                        fieldNum += 1
                    

            # Adding the information of channels' fields to the channel detail dict
            self.channels_detail[channel_name] = {"fields" : field_names_dict}

            # Step 2: Check if the channel exists
            channel_exists = any(channel['name'] == channel_name for channel in channels)

            if channel_exists:
                self.logger.info(f"Channel '{channel_name}' already exists.")
                channel_id, write_api_key = next((channel['id'], channel["api_keys"][0]["api_key"]) for channel in channels if channel['name'] == channel_name)
                self.channels_detail[channel_name]["writeApiKey"] = write_api_key
                self.channels_detail[channel_name]["channelId"] = channel_id

            else:
                # Step 3: Create the channel
                create_channel_url = self.config.THINGSPEAK_URL + self.config.THINGSPEAK_CHANNELS_ENDPOINT.rstrip("?")
                create_channel_payload = {"api_key": self.user_API_key.split("=")[1], "name": channel_name, "public_flag":"true"}

                # Creating the fields of the channel
                for fieldID, fieldName in field_names_dict.items():
                    create_channel_payload[fieldID] = fieldName

                # ADD TRY AND except
                try:
                    create_channel_response = requests.post(create_channel_url, params=create_channel_payload)
                    created_channel = create_channel_response.json()
                    channel_id, write_api_key = created_channel['id'], created_channel["api_keys"][0]["api_key"]
                    self.logger.info(f"Channel '{channel_name}' created with ID {channel_id}")
                    self.channels_detail[channel_name]["writeApiKey"] = write_api_key
                    self.channels_detail[channel_name]["channelId"] = channel_id
                except requests.exceptions.RequestException as e:
                    self.logger.info(f"Failed to create channel {channel_name}: {e}")


    # To get the channels and fields information for user interface
    def get_channel_detail(self, room_id: str=None):
        return self.channels_detail.get(room_id, self.channels_detail)


    def get_sensing_data(self, room_id: str, results: int = 4, plant_id: str = None, start_date: str = None, end_date: str = None):
        channel_detail = self.channels_detail.get(room_id)
        if not room_id:
            self.logger.error(f"No channel detail found for room ID: {room_id}")
            return False

        fields, the_channel_id = channel_detail["fields"], channel_detail['channelId']
        params = {'results': results}
        if start_date:
            params['start'] = start_date
        if end_date:
            params['end'] = end_date

        # requests thingSpeak for the last 5 data point to get the last value of each sensor
        try:
            # https://api.thingspeak.com/channels/<2425367>/feeds.json?results=4
            url = f"{self.config.THINGSPEAK_URL}/channels/{str(the_channel_id)}/feeds.json"
            req_g = requests.get(url, params=params)
            # req_g = requests.get(f"{self.thingSpeak_channels_url}{str(the_channel_id)}/feeds.json?results=4")
            self.logger.info(f"Get request of sensing data for room {room_id} with params {params}")

            data_list = req_g.json().get("feeds", [])
            current_data_dict = {field: [] for field in fields.values()}

            for datumDict in data_list:
                timestamp = datumDict.get("created_at")
                for field, value in datumDict.items():
                    if field.startswith("field") and value:
                        if not plant_id:
                            current_data_dict[fields[field]].append((value, timestamp))
                        elif fields[field] not in ['temperature', 'light']:
                            if fields[field].endswith(plant_id):
                                current_data_dict[fields[field]].append((value, timestamp))
                        else:
                            current_data_dict[fields[field]].append((value, timestamp))
            

            # Remove empty lists from the dictionary
            current_data_dict = {k: v for k, v in current_data_dict.items() if v}

            return current_data_dict

        except requests.exceptions.RequestException as e:
            self.logger.error(f"Failed to get sensing data from ThingSpeak. Error: {e}")
            return 
        except KeyError as e:
            self.logger.error(f"Key error: {e}")
            return 


    def update_and_sort_devices_by_room(self):
        self._update_rooms()
        sensors_by_room = {}

        for room_id in self.rooms:
            sensors = self._get_devices(device_type="sensor", room_id=room_id) or []
            sensors_by_room[room_id] = sensors
        self.sensors_by_room = sensors_by_room

         # Schedule the next update if the method is not triggered by external requests
        self.start_update_timer()
        

    def _update_rooms(self):
        rooms = self._get_rooms()
        if not rooms:
            self.logger.error("No rooms detected!")
            return
        
        rooms_list = []
        for room in rooms:
            rooms_list.append(room["roomId"])
        self.rooms = rooms_list

    
    def _get_rooms(self):
        endpoint = self._discover_service("rooms", 'GET')
        try:
            if endpoint:    
                url = f"{self.catalog_address}{endpoint}"
            else:
                self.logger.error(f"Failed to get rooms endpoint")
                return
            
            self.logger.info(f"Fetching sensors information from {url}")
            req = requests.get(url)
            req.raise_for_status()
            response = req.json()

            if response.get("success"):
                rooms_list = response["content"]

            if rooms_list:
                return rooms_list
                
            return []
            
        except requests.RequestException as e:
            self.logger.error(f"Failed to fetch rooms information: {e}")


    def get_broker(self):
        endpoint = self._discover_service("general", 'GET')
        try:
            if endpoint:    
                url = f"{self.catalog_address}{endpoint}/broker"
            else:
                self.logger.error(f"Failed to get broker endpoint")
                return
            
            self.logger.info(f"Fetching broker information from {url} ...")
            response = requests.get(url)
            response.raise_for_status()
            broker_response = response.json()

            if broker_response.get("success"):
                broker_info = broker_response["content"].get("broker")

            self.broker = broker_info.get("IP")
            self.port = broker_info.get("port")

            if not self.broker or not self.port:
                raise ValueError("Broker information is incomplete.")

            self.logger.info(f"Broker set to {self.broker} and port set to {self.port}.")
        except requests.RequestException as e:
            self.logger.error(f"Failed to fetch broker information: {e}")
        except ValueError as e:
            self.logger.error(f"Invalid broker information received: {e}")


    def _discover_service(self, item: str, method: Literal['GET', 'POST', 'PUT', 'DELETE'], sub_path: str=None):
        # Return the endpoint from the cache
        if item in self.endpoint_cache and method in self.endpoint_cache[item]:
            return self.endpoint_cache[item][method]

        try:
            url = f"{self.catalog_address}/{self.config.SERVICES_ENDPOINT}/{self.config.SERVICE_REGISTRY_NAME}"
            response = requests.get(url)
            response.raise_for_status()

            service_response = response.json()

            if service_response.get("success"):
                # Extract the service registry from the response
                service_registry = service_response.get("content", [[]])
                service = service_registry[0]
                if service:
                    endpoints = service.get("endpoints", [])
                    for endpoint in endpoints:
                        path = endpoint.get("path", "")
                        service_method = endpoint.get("method", "")

                        if item in path and method == service_method:
                            if sub_path:
                                if sub_path in path:
                                    self.endpoint_cache.setdefault(item, {})[method] = path
                                    return path
                            else:
                                self.endpoint_cache.setdefault(item, {})[method] = path
                                return path
                            
            self.logger.error(f"Failed to discover service endpoint")

        except requests.RequestException as e:
            self.logger.error(f"Failed to fetch services endpoint: {e}")


    def initiate_mqtt(self):
        self.mqtt_client = MyClientMQTT(clientID = self.config.MQTT_CLIENT_ID,
                                        broker=self.broker,
                                        port=self.port,
                                        host=self,
                                        child_logger=MyLogger.set_logger(logger_name=self.config.MQTT_LOGGER))
        self.mqtt_client.start()


    def _get_devices(self,
                    measure_type: str=None,
                    device_type: str=None,
                    plant_id: int=None,
                    room_id: int=None):
        
        local_vars = {
        'measure_type': measure_type,
        'device_type': device_type,
        'plant_id': plant_id,
        'room_id': room_id
    }
        
        params = {k: v for k, v in local_vars.items() if v is not None}
        endpoint = self._discover_service(self.config.DEVICES_ENDPOINT, 'GET')
        try:
            if endpoint:    
                url = f"{self.catalog_address}{endpoint}"
            else:
                self.logger.error(f"Failed to get devices endpoint")
                return
            
            self.logger.info(f"Fetching sensors information from {url} with params: {params}")
            response = requests.get(url, params)
            response.raise_for_status()
            devices_response = response.json()

            if devices_response.get("success"):
                devices_list = devices_response["content"]

            if devices_list:
                return devices_list
                
            return []
            
        except requests.RequestException as e:
            self.logger.error(f"Failed to fetch devices information: {e}")


    def get_plants(self, plant_id: int=None):
        endpoint = self._discover_service("plants", 'GET')
        try:
            if endpoint:    
                url = f"{self.catalog_address}{endpoint}"
                if plant_id:
                    url += f"/{plant_id}"
            else:
                self.logger.error(f"Failed to get plant endpoint")
                return
            
            self.logger.info(f"Fetching plants information from {url}.")
            response = requests.get(url)
            response.raise_for_status()
            plants_response = response.json()

            if plants_response.get("success"):
                plants_list = plants_response["content"]

            if plants_list:
                return plants_list
                
            return []
            
        except requests.RequestException as e:
            self.logger.error(f"Failed to fetch plants information: {e}")

    

    def get_topic_template(self):
        endpoint = self._discover_service("general", 'GET')
        try:
            if endpoint:    
                url = f"{self.catalog_address}{endpoint}/template"
            else:
                self.logger.error(f"Failed to get template endpoint")
                return
            
            self.logger.info(f"Fetching template information from {url} ...")
            response = requests.get(url)
            response.raise_for_status()
            template_response = response.json()

            if template_response.get("success"):
                template = template_response["content"].get("template")
                topic = template_response["content"].get("example")

            if template:
                self.template = template
                self.topic = topic
                self.logger.info(f"Topic template received: {self.template}.")
                return
            
            self.logger.error(f"Failed to fetch template information.")
            
        except requests.RequestException as e:
            self.logger.error(f"Failed to fetch template information: {e}")


    def prepare_main_topic(self):
        try:
            splitted_topic = self.topic.split("/")
            main_topic = f"{splitted_topic[int(self.template['project_name'])]}/{splitted_topic[int(self.template['device_type'])]}/#"
            self.main_topic = main_topic

        except Exception as e:
            self.logger.error(f"Failed to shape main topic: {str(e)}")
            self.main_topic = ""
        
    
    def stop_mqtt(self):
        self.mqtt_client.stop()


    def subscribe_to_topic(self):
        self.mqtt_client.subscribe(topic=self.main_topic)


    def post_service(self):
        # Read the JSON file
        try:
            with open(self.config.SERVICE_REGISTRY_FILE, 'r') as file:
                data = json.load(file)
        except FileNotFoundError:
            self.logger.error(f"Service registry file not found: {self.config.SERVICE_REGISTRY_FILE}")
            return
        except json.JSONDecodeError:
            self.logger.error(f"Error decoding JSON from file: {self.config.SERVICE_REGISTRY_FILE}")
            return

        # Post the data to the registry system
        url = f"{self.catalog_address}/{self.config.SERVICES_ENDPOINT}"
        try:
            response = requests.post(url, json=data)
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Error posting service data: {str(e)}")
        if response.json().get("success"): 
            self.logger.info("Service registered successfully.")
        else:
            self.logger.error("Error registring the service.")


    # Triggered when a message recieved
    def notify(self, topic, payload):
        msg = json.loads(payload)
        event = msg["e"][0]
        print(f"{topic} measured a {event['n']} of {event['v']} {event['u']} at time {event['t']}")

        # Identifing the room, plant, and kind of sensor from which the data is received 
        try:
            msg_info = {}
            seperatedTopic = topic.strip().split("/")
            for info_key, index in self.template.items():
                msg_info[info_key] = seperatedTopic[index]
            room_id, plant_id, measure_type = msg_info["room_id"], msg_info["plant_id"], msg_info["measure_type"]
        except Exception as e:
            self.logger.error(f"Topic {topic }and topic template {self.template} not operable.")
            return

        field_available = False
        for channel_name, channel_detail in self.channels_detail.items():
            if channel_name == room_id:
                channel_API = channel_detail["writeApiKey"]
                for field, sensor_name in channel_detail["fields"].items():   # sensor_name: 'PH_101', 'light
                    target_field_name = measure_type
                    if int(plant_id):
                        target_field_name += f"-{plant_id}"
                    if sensor_name == target_field_name:
                        channedlField = field
                        field_available = True
                        break
            if field_available:
                break
                
        # Writing on Thingspeak channel
        if field_available:
            try:
                self.logger.debug(f"{self.config.THINGSPEAK_URL}\n{self.config.THINGSPEAK_UPDATE_ENDPOINT}\n&{channedlField}={str(event['v'])}")
                url = self.config.THINGSPEAK_URL+self.config.THINGSPEAK_UPDATE_ENDPOINT+f"api_key={channel_API}"+f"&{channedlField}={str(event['v'])}"
                response = requests.get(url)     
                self.logger.info(f"{measure_type} on channel {channel_name} and {field} is writen on thinkspeak with code {response.text}\n")
            
            except (requests.exceptions.RequestException, UnboundLocalError) as e:
                self.logger.error(f"Error during writing {sensor_name} on thinkspeak channel: {e}")


# if __name__ == "__main__":
#     adaptor = Adaptor(Config)
#     adaptor.get_sensing_data('1', 20, '101')
#     print()