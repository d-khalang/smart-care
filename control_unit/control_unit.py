import json
import requests
import time
import threading
import copy
from typing import Literal, List
from config import Config, MyLogger
from MyMQTT2 import MyMQTT

from utility import create_response


class MyClientMQTT():
    def __init__(self, clientID, broker, port, host, child_logger):
        self.host = host
        self.client = MyMQTT(clientID, broker, port, self, child_logger)
        self.start()  

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
    
    # Will be triggered when a message is received
    def notify(self, topic, payload):
        return self.host.notify(topic, payload)



class Controler():
    def __init__(self, config: Config, inital_rooms: List[int]):
        self.config = config
        self.rooms = inital_rooms
        self.rooms_location = {}
        self.sensors = []
        self.device_topics = {}
        self.catalog_address = self.config.CATALOG_URL
        self.logger = MyLogger.get_main_loggger()
        self.endpoint_cache = {}
        self.broker = None
        self.port = None
        self.forecast_url = self.config.WEATHER_FORECAST_URL
        self.forecast_api_key = self.config.WEATHER_FORECAST_API_KEY
        self.msg = {
            "bn": "",
            "e": [
                {
                    "n": 'controler',
                    "u": 'command',
                    "t": None,
                    "v": None
                }
            ]
        }
        
        self.logger.info("Initiating the controler...")
        self.lock = threading.RLock()
        self.get_broker()
        self.initiate_mqtt()
        self.get_topic_template()
        self.update_sensors_location_and_subscriptions(from_main=True)
        
        # self.start_sensors_update_thread(self)


    def update_sensors_location_and_subscriptions(self, from_main: bool=False):
        with self.lock:
            self.logger.info("Updating sensors and subscriptions...")
            self._set_rooms_location()
            self._outside_weather_update()
            self._get_sensors()
            self._subscribe_to_sensors()

        if from_main:
            # Schedule the next update if the method is not triggered by external requests
            threading.Timer(self.config.TOPICS_UPDATE_INTERVAL, lambda: self.update_sensors_location_and_subscriptions(from_main=True)).start()
    

    def _set_rooms_location(self):
        self.logger.info("Updating the room locations...")

        for room in self.rooms:
            room_location = self._get_room_location(room_id = room)
            if self.rooms_location.get(room):
                self.rooms_location[room]["location"] = room_location
            else:
                self.rooms_location[room] = {"location": room_location}

        self.logger.info("Room locations updated.")


    def _get_room_location(self, room_id: int):
        endpoint = self._discover_service("rooms", 'GET')
        try:
            if endpoint:    
                url = f"{self.catalog_address}{endpoint}/{room_id}"
            else:
                self.logger.error(f"Failed to get rooms endpoint")
                return
            
            self.logger.info(f"Fetching rooms information from {url}.")
            response = requests.get(url)
            response.raise_for_status()
            rooms_response = response.json()

            if rooms_response.get("success"):
                rooms_list = rooms_response["content"]
                if rooms_list:
                    room = rooms_list[0]
                    location = room.get("location", {})
                    return location
            return {}
            
        except requests.RequestException as e:
            self.logger.error(f"Failed to fetch rooms information: {e}")



    def _subscribe_to_sensors(self):
        with self.lock:
            self.logger.info("Updating the subscriptions...")

            # Track device IDs that are currently present
            current_device_ids = {sensor["deviceId"] for sensor in self.sensors}

            # Identify old devices to remove
            old_device_ids = set(self.device_topics.keys()) - current_device_ids
            for old_device_id in old_device_ids:
                old_topics = self.device_topics[old_device_id]["topics"]
                for topic in old_topics:
                    self.mqtt_client.unsubscribe(topic)
                del self.device_topics[old_device_id]
                self.logger.info(f"Unsubscribed and removed old device: {old_device_id}")


            for sensor in self.sensors:
                device_id = sensor["deviceId"]
                new_topics = []

                services_details = sensor.get("servicesDetails", [])

                for service_dict in services_details:
                    topics = service_dict.get("topic", [])

                    for topic in topics:
                        new_topics.append(topic)

                # When device is new for controler
                if not self.device_topics.get(device_id):
                    self.device_topics[device_id] = {"topics":[]}
                    for topic in new_topics:
                        self.mqtt_client.subscribe(topic)
                        self.device_topics[device_id]["topics"].append(topic)
                    
                else:
                    old_topics = copy.deepcopy(self.device_topics[device_id]["topics"])

                    # Unsubscribe from topics that are in old_topics but not in new_topics
                    topics_to_unsubscribe = [topic for topic in old_topics if topic not in new_topics]
                    for topic in topics_to_unsubscribe:
                        self.mqtt_client.unsubscribe(topic)

                    # Subscribe to topics that are in new_topics but not in old_topics
                    topics_to_subscribe = [topic for topic in new_topics if topic not in old_topics]
                    for topic in topics_to_subscribe:
                        self.mqtt_client.subscribe(topic)

                    # Update the device topics
                    self.device_topics[device_id]["topics"] = new_topics
            self.logger.info("Subscriptions updated.")
        


    def _get_sensors(self):
        with self.lock:
            # Remove sensors whose roomId is not in self.rooms
            self.sensors = [sensor for sensor in self.sensors if sensor["deviceLocation"]["roomId"] in self.rooms]

            for room_id in self.rooms:
                sensors = self._get_devices(device_type="sensor", room_id=room_id)
                for sensor in sensors:
                    if sensor not in self.sensors:
                        self.sensors.append(sensor)
                        self.logger.info(f"Sensor with ID {sensor.get("deviceId")} added.")
            
            self.logger.info("Sensors updated.")


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
        endpoint = self._discover_service("devices", 'GET')
        try:
            if endpoint:    
                url = f"{self.catalog_address}{endpoint}"
            else:
                self.logger.error(f"Failed to get broker endpoint")
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

            if template:
                self.template = template
                self.logger.info(f"Topic template received: {self.template}.")
                return
            
            self.logger.error(f"Failed to fetch template information.")
            
        except requests.RequestException as e:
            self.logger.error(f"Failed to fetch template information: {e}")



    def initiate_mqtt(self):
        self.mqtt_client = MyClientMQTT(clientID = self.config.MQTT_CLIENT_ID,
                                        broker=self.broker,
                                        port=self.port,
                                        host=self,
                                        child_logger=MyLogger.set_logger(logger_name=Config.MQTT_LOGGER))
        

    def stop_mqtt(self):
        self.mqtt_client.stop()



    def expose_rooms(self):
        return self.rooms

    def add_rooms(self, new_rooms: List[int]):
        try:
            # Convert current rooms and new rooms to sets
            current_rooms_set = set(self.rooms)
            new_rooms_set = set(new_rooms)

            # Find the rooms that are not already in the current rooms list
            rooms_to_add = new_rooms_set - current_rooms_set

            # Add new rooms to self.rooms
            self.rooms.extend(rooms_to_add)
            
            # Log the rooms that were added
            for room in rooms_to_add:
                self.logger.info(f"Room {room} added.")

            response = create_response(True, message=f"Added rooms: {list(rooms_to_add)}.", status=200)

        except Exception as e:
            return create_response(False, message=str(e), status=500)
        
        if rooms_to_add:
            self.update_sensors_location_and_subscriptions()
        return response


    def remove_rooms(self, removed_rooms: List[int]):
        try:
            current_rooms_set = set(self.rooms)
            removable_rooms_set = set(removed_rooms)
            
            # Find the intersection of the two sets (common items)
            intersection = current_rooms_set & removable_rooms_set
            for room in intersection:
                self.rooms.remove(room)
                self.logger.info(f"Room {room} eliminated.")

            response = create_response(True, message=f"Eliminated rooms: {list(intersection)}.", status=200)

        except Exception as e:
            return create_response(False, message=str(e), status=500)
        if intersection:
            self.update_sensors_location_and_subscriptions()
        return response


    def notify(self, topic, payload):
        try:
            msg = json.loads(payload)
            # Part of the message related to the event happened
            event = msg["e"][0]
        except Exception as e:
            self.logger.warning(f"Unrecognized payload received over mqtt: {str(e)}.")
            return
        
        self.logger.info(f"{topic} measured a {event['n']} of {event['v']} {event['u']} at time {event['t']}")
        msg_info = {}
        splitted_topic = topic.split("/")

        try:
            for key, index in self.template.items():
                msg_info[key] = splitted_topic[index]
        except Exception as e:
            self.logger.warning(f"Unrecognized topic detected: {str(e)}.")
            return

        msg_info["measure_type"] = event['n']
        msg_info["value"] = event['v']

        # Classifing and analysing the data according to the type of measurements
        if msg_info["measure_type"] == "temperature":
            self.send_temp_command(msg_info)

        elif msg_info["measure_type"] == "light":
            self.send_light_command(msg_info)
        
        elif msg_info["measure_type"] == "ph":
            self.send_PH_command(msg_info)
        
        elif msg_info["measure_type"] == "soilMoisture":
            self.send_soilMoisture_command(msg_info)


    


















    
    # Gets and adds the outter temperature to the plant dict
    def _outside_weather_update(self):
        pre_location = {"lat": "","lon": ""}
        default_temp = 0
        for room_id, outside_dict in self.rooms_location.items():
            location = outside_dict.get("location")
            if not location:
                continue

            if location.get("lat") == pre_location.get("lat"):
                current_temp = default_temp
                self.rooms_location[room_id]["outsideTemperature"] = current_temp

            # to avoid api call many times for the same location at the same time
            else:    
                # call forecast api
                try:
                    req = requests.get(url=self.forecast_url, params={
                        "lat": location["lat"],
                        "lon": location["lon"],
                        "sections": "current",
                        "key": self.forecast_api_key
                    })
                    forecast_dict = req.json()
                except requests.exceptions as e:
                    self.logger.debug(f"Error fetching weatherforcast from api: {str(e)}")
                    forecast_dict = {}
                # clean it and attach to plant dictionary 
                current_temp = forecast_dict["current"].get("temperature", 0)
                self.rooms_location[room_id]["outsideTemperature"] = current_temp
                self.logger.info(f"Outside temperature of {current_temp} degree recieved for the room {room_id}")

                pre_location = location
                default_temp = current_temp




    def fetch_actuators(self, room_id):
        return self._get_devices(room_id=room_id, device_type="actuator")

