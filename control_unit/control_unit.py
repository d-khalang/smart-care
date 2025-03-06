import json
import requests
import time
import threading
import copy
from datetime import date, datetime
from typing import Literal, List
from config import Config, MyLogger
from MyMQTT2 import MyMQTT

from utility import create_response


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



class Controler():
    def __init__(self, config: Config, inital_rooms: List[int]=Config.ROOM_IDS):
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
        self.template = {}
        weather_forecast = self.get_weather_forecast() 
        self.forecast_url = weather_forecast.get("address", "")
        self.forecast_api_key = weather_forecast.get("key", "")
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
        endpoint = self._discover_service(self.config.ROOMS_ENDPOINT, 'GET')
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
            
        except requests.RequestException as e:
            self.logger.error(f"Failed to fetch rooms information: {e}")
        return {}


    def get_weather_forecast(self):
        endpoint = self._discover_service(self.config.GENERAL_ENDPOINT, 'GET')
        output = {}
        try:
            if endpoint:    
                url = f"{self.catalog_address}{endpoint}/weather_forecast"
            else:
                self.logger.error(f"Failed to get weather forecast's endpoint")
                
            self.logger.info(f"Fetching weather forecast information from {url}")
            response = requests.get(url)
            response.raise_for_status()
            json_data = response.json()

            if json_data.get("success"):
                data = json_data.get("content", [[]])
                output = data.get("weatherForecast",{})
                if output:
                    self.logger.info("weather forecast info received.")
        
        except requests.RequestException as e:
            self.logger.error(f"Failed to fetch weather forecast's information: {e}")
        return output


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
                        self.logger.info(f"Sensor with ID {sensor.get('deviceId')} added.")
            
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


    def get_broker(self):
        endpoint = self._discover_service(self.config.GENERAL_ENDPOINT, 'GET')
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
        endpoint = self._discover_service(self.config.GENERAL_ENDPOINT, 'GET')
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
                                        child_logger=MyLogger.set_logger(logger_name=self.config.MQTT_LOGGER))
        self.mqtt_client.start()
        

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
        
        elif msg_info["measure_type"] in ["ph", "PH"]:
            self.send_PH_command(msg_info)
        
        elif msg_info["measure_type"] == "soil_moisture":
            self.send_soilMoisture_command(msg_info)

    def _prepare_topic(self, msg_info: dict):
        msg_info["device_type"] = 'actuator'
        reversed_template = {v: k for k, v in self.template.items()}
        topic_prep_list = sorted(reversed_template.keys())

        topic = ""
        for index in topic_prep_list:
            topic += msg_info.get(reversed_template[index]) + "/"
        return topic.rstrip("/")
    
    def _get_plant_kind_for_room(self, msg_info: dict):
        endpoint = self._discover_service("rooms", 'GET')
        try:
            if endpoint:    
                url = f"{self.catalog_address}{endpoint}/{msg_info.get('room_id')}"
            else:
                self.logger.error(f"Failed to get rooms endpoint")
                return
            
            response = requests.get(url)
            response.raise_for_status()
            rooms_response = response.json()

            if rooms_response.get("success"):
                rooms_list = rooms_response["content"]
                if rooms_list:
                    room = rooms_list[0]
                    plant_kind = room.get("plantKind", "")
                    return plant_kind
            return ""
            
        except requests.RequestException as e:
            self.logger.error(f"Failed to fetch rooms information: {e}")
    
    def _get_plant_date_for_room(self, msg_info: dict):
        endpoint = self._discover_service("rooms", 'GET')
        try:
            if endpoint:    
                url = f"{self.catalog_address}{endpoint}/{msg_info.get('room_id')}"
            else:
                self.logger.error(f"Failed to get rooms endpoint")
                return
            
            response = requests.get(url)
            response.raise_for_status()
            rooms_response = response.json()

            if rooms_response.get("success"):
                rooms_list = rooms_response["content"]
                if rooms_list:
                    room = rooms_list[0]
                    plant_date = room.get("plantDate", "")
                    return plant_date
            return "2001-01-01"
            
        except requests.RequestException as e:
            self.logger.error(f"Failed to fetch rooms information: {e}")

    def _get_plant_kind_info(self, plant_kind: str):
        endpoint = self._discover_service("plant_kinds", 'GET')
        try:
            if endpoint:    
                url = f"{self.catalog_address}{endpoint}/{plant_kind}"
            else:
                self.logger.error(f"Failed to get plant_kinds endpoint")
                return
            
            response = requests.get(url)
            response.raise_for_status()
            plant_kinds_response = response.json()

            if plant_kinds_response.get("success"):
                plant_kinds_list = plant_kinds_response["content"]
                if plant_kinds_list:
                    return plant_kinds_list[0]
            return {}
            
        except requests.RequestException as e:
            self.logger.error(f"Failed to fetch rooms information: {e}")

    def _find_topic_for_actuator(self, actuators: list, actuator_name: str):
        topic = ""
        for actuator in actuators:
            if actuator["deviceName"] == actuator_name:
                for services_detail in actuator["servicesDetails"]:
                    if services_detail.get("serviceType") == "MQTT":
                        topic = services_detail["topic"][0]
        return topic

    # Processing the temperature data
    def send_temp_command(self, msg_info: dict):
        # # Topic preparation according to the universal template
        # topic = self._prepare_topic(msg_info)

        # Get corressponding plant kind
        plant_kind = self._get_plant_kind_for_room(msg_info)
        if not plant_kind:
            self.logger.error(f"Faild to figure out plant kind for room {msg_info['room_id']}")
        
        # Getting the suitable temperature of the corresponding plant kind
        plant_kind_dict = self._get_plant_kind_info(plant_kind)
        if not plant_kind_dict:
                self.logger.error(f"Faild to get plant kind information for plant kind {plant_kind}")
            
        minTemp, maxTemp, bestTempRange = plant_kind_dict.get("coldestTemperature"), plant_kind_dict.get("hottestTemperature"), plant_kind_dict.get("bestTemperatureRange")
        outTemp = self.rooms_location.get(int(msg_info["room_id"])).get("outsideTemperature", 0)
        
        # Status of the temp actuators of the plant     
        fan_status, heater_status, window_status = None, None, 'DISABLE'
        # Fetch temperature actuators of the room
        actuators = self._get_devices(measure_type="temperature", device_type="actuator", room_id=int(msg_info["room_id"]))
        for actuator in actuators:
            if actuator["deviceName"] == "fan_switch":
                fan_status = actuator.get("deviceStatus")
            
            elif actuator["deviceName"] == "heater_switch":
                heater_status = actuator.get("deviceStatus")

            elif actuator["deviceName"] == "window_switch":
                window_status = actuator.get("deviceStatus", "DISABLE")

        if not (fan_status and heater_status):
            self.logger.error('Failed to get the status of the fan and heater')
            return

        # Checking if actuator is operating
        if (fan_status and heater_status) != "DISABLE":
            # Structure the SenML message
            msg = copy.deepcopy(self.msg)
            msg["e"][0]["t"] = str(time.time())
            

            ### Check the temperature regarding the plant suitable temperature
            # Check if temperature is less than minimum threshold
            value = msg_info["value"]
            corresponding_actuator = ""
            if value < minTemp:
                if window_status != "DISABLE":
                    if value > outTemp and outTemp > minTemp and window_status == "CLOSE":
                        self.logger.info("Temperature less than threshold, OPEN the window")
                        corresponding_actuator = "window_switch"
                        msg["e"][0]["v"] = "OPEN"
                        self.publish_command(actuators, corresponding_actuator, msg)
                    elif heater_status == "OFF":
                        self.logger.info("Temperature less than threshold, Turn ON the heater")
                        corresponding_actuator = "heater_switch"
                        msg["e"][0]["v"] = "ON"
                        self.publish_command(actuators, corresponding_actuator, msg)
                else:
                    if heater_status == "OFF":
                        self.logger.info("Temperature less than threshold, Turn ON the heater")
                        corresponding_actuator = "heater_switch"
                        msg["e"][0]["v"] = "ON"
                        self.publish_command(actuators, corresponding_actuator, msg)
                    if fan_status == "ON":
                        self.logger.info("Temperature less than threshold, Turn OFF the fan")
                        corresponding_actuator = "fan_switch"
                        msg["e"][0]["v"] = "OFF"
                        self.publish_command(actuators, corresponding_actuator, msg)

            # Check if temperature is more than maximum threshold
            elif value > maxTemp:
                if window_status != "DISABLE":
                    if value < outTemp and outTemp < maxTemp and window_status == "OPEN":
                        self.logger.info("Temperature more than threshold, CLOSE the window")
                        corresponding_actuator = "window_switch"
                        msg["e"][0]["v"] = "CLOSE"
                        self.publish_command(actuators, corresponding_actuator, msg)
                    elif fan_status == "OFF":
                        self.logger.info("Temperature more than threshold, Turn ON the fan")
                        corresponding_actuator = "fan_switch"
                        msg["e"][0]["v"] = "ON"
                        self.publish_command(actuators, corresponding_actuator, msg)
                else:
                    if fan_status == "OFF":
                        self.logger.info("Temperature more than threshold, Turn ON the fan")
                        corresponding_actuator = "fan_switch"
                        msg["e"][0]["v"] = "ON"
                        self.publish_command(actuators, corresponding_actuator, msg)
                    if heater_status == "ON":
                        self.logger.info("Temperature more than threshold, Turn OFF the heater")
                        corresponding_actuator = "heater_switch"
                        msg["e"][0]["v"] = "OFF"
                        self.publish_command(actuators, corresponding_actuator, msg)
            
            # Check if temperature is in the optimal range
            elif bestTempRange[0] <= value <= bestTempRange[1]:
                if window_status != "DISABLE":
                    if outTemp not in range(bestTempRange[0], bestTempRange[1]) and window_status == "OPEN":
                        self.logger.info("Temperature in optimal range, but outside temperature is not optimal, CLOSE the window")
                        corresponding_actuator = "window_switch"
                        msg["e"][0]["v"] = "CLOSE"
                        self.publish_command(actuators, corresponding_actuator, msg)
                if heater_status == "ON":
                    self.logger.info("Temperature in optimal range, turn OFF the heater")
                    corresponding_actuator = "heater_switch"
                    msg["e"][0]["v"] = "OFF"
                    self.publish_command(actuators, corresponding_actuator, msg)
                if fan_status == "ON":
                    self.logger.info("Temperature in optimal range, turn OFF the fan")
                    corresponding_actuator = "fan_switch"
                    msg["e"][0]["v"] = "OFF"
                    self.publish_command(actuators, corresponding_actuator, msg)
        else:
            self.logger.warning("The heating actuators are DISABLE!")


    # Processing the brightness data and send command if intervention is needed
    def send_light_command(self, msg_info: dict):
        # Get corressponding plant kind
        plant_kind = self._get_plant_kind_for_room(msg_info)
        if not plant_kind:
            self.logger.error(f"Faild to figure out plant kind for room {msg_info['room_id']}")
        
        plant_kind_dict = self._get_plant_kind_info(plant_kind)
        if not plant_kind_dict:
            self.logger.error(f"Faild to get plant kind information for plant kind {plant_kind}")
                
        vegetative_light_range, flowering_light_rang = plant_kind_dict["vegetativeLightRange"], plant_kind_dict["floweringLightRang"]

        # Status of the light switch actuators of the plant
        light_switch_status = None
        # Fetch light actuators of the room
        actuators = self._get_devices(measure_type="light", device_type="actuator", room_id=int(msg_info["room_id"]))
        actuator = actuators[0]
        light_switch_status = actuator.get("deviceStatus")
        
        if not light_switch_status:
            self.logger.error('Failed to get the status of the light switch')

        # Checking if actuator is operating
        if light_switch_status != "DISABLE":
            plant_date = self._get_plant_date_for_room(msg_info)
            plant_age = self.days_difference_from_today(plant_date)

            # Structure the SenML message
            msg = copy.deepcopy(self.msg)
            msg["e"][0]["t"] = str(time.time())
            command_value = None
            value = msg_info["value"]

            ## availableStatuses: ["OFF","LOW","MID","HIGH"]
            # Vegetative stage
            if plant_age <= 15:
                # If brightness is less that what is expected in vegetetive stage
                # Ligh switch will be put on one level stronger
                if value < vegetative_light_range[0]:
                    if light_switch_status == "OFF":
                        command_value = "LOW"
                    elif light_switch_status == "LOW":
                        command_value = "MID"
                    elif light_switch_status == "MID":
                        command_value = "HIGH"

                # If brightness is in the range of flowering stage
                # Ligh switch will be put on one level weaker
                elif value in range(flowering_light_rang[0], flowering_light_rang[1]):
                    if light_switch_status == "HIGH":
                        command_value = "MID"
                    elif light_switch_status == "MID":
                        command_value = "LOW"
                    elif light_switch_status == "LOW":
                        command_value = "OFF"

                # If brightness is way more than what is expected 
                # Ligh switch will be shut down
                elif value > flowering_light_rang[1]:
                    if light_switch_status != "OFF":
                        command_value = "OFF"
                    

            # Flowering stage
            elif plant_age > 15:
                ## Set the switch to full power
                if value < vegetative_light_range[0]:
                    if light_switch_status != "HIGH":
                        command_value = "HIGH"

                # One level forward
                elif value in range(vegetative_light_range[0], vegetative_light_range[1]):
                    if light_switch_status == "OFF":
                        command_value = "LOW"
                    elif light_switch_status == "LOW":
                        command_value = "MID"
                    elif light_switch_status == "MID":
                        command_value = "HIGH"

                # One level backward
                elif value > flowering_light_rang[1]:
                    if light_switch_status == "HIGH":
                        command_value = "MID"
                    elif light_switch_status == "MID":
                        command_value = "LOW"
                    elif light_switch_status == "LOW":
                        command_value = "OFF"

            if command_value:
                msg["e"][0]["v"] = command_value
                self.publish_command(actuators, "light_switch", msg)
        else:
            self.logger.warning("Light actuator is DISABLE!")


    # Processing the PH data and send command if intervention is needed
    def send_PH_command(self, msg_info: dict):
        # Get corressponding plant kind
        plant_kind = self._get_plant_kind_for_room(msg_info)
        if not plant_kind:
            self.logger.error(f"Faild to figure out plant kind for room {msg_info['room_id']}")
        
        plant_kind_dict = self._get_plant_kind_info(plant_kind)
        if not plant_kind_dict:
            self.logger.error(f"Faild to get plant kind information for plant kind {plant_kind}")
                
        PH_range = plant_kind_dict["PHRange"]

        # Status of the PH switch actuators of the plant
        PH_actuator_status = None
        # Fetch PH actuator of the plant
        actuators = self._get_devices(measure_type="PH", device_type="actuator", 
                                      room_id=int(msg_info["room_id"]), plant_id=int(msg_info["plant_id"]))
        if not actuators:
            return
        actuator = actuators[0]
        PH_actuator_status = actuator["deviceStatus"]
        
        if not PH_actuator_status:
            self.logger.error('Failed to get the status of the PH actuator')

        # Checking if actuator is operating
        if PH_actuator_status != "DISABLE":
            # Structure the SenML message
            msg = copy.deepcopy(self.msg)
            msg["e"][0]["t"] = str(time.time())
            command_value = None
            value = msg_info["value"]

            # Setting the command
            if value < PH_range[0]:
                command_value = "release_PH_high"
            elif value > PH_range[1]:
                command_value = "release_PH_low"

            if command_value:
                msg["e"][0]["v"] = command_value
                self.publish_command(actuators, "PH_actuator", msg)
        else:
            self.logger.warning("PH actuator is DISABLE!")


    # Processing the water level data and send command if intervention is needed
    def send_soilMoisture_command(self, msg_info: dict):
        # Get corressponding plant kind
        plant_kind = self._get_plant_kind_for_room(msg_info)
        if not plant_kind:
            self.logger.error(f"Faild to figure out plant kind for room {msg_info['room_id']}")
        
        plant_kind_dict = self._get_plant_kind_info(plant_kind)
        if not plant_kind_dict:
            self.logger.error(f"Faild to get plant kind information for plant kind {plant_kind}")
                
        minMoisture = plant_kind_dict["volumetricWaterContent"][0]

        # Status of the light switch actuators of the plant
        irrigator_status = None
        # Fetch irrigator of the plant
        actuators = self._get_devices(measure_type="soil_moisture", device_type="actuator", 
                                      room_id=int(msg_info["room_id"]), plant_id=int(msg_info["plant_id"]))
        if not actuators:
            return
        actuator = actuators[0]
        irrigator_status = actuator["deviceStatus"]
        
        if not irrigator_status:
            self.logger.error('Failed to get the status of the irrigator')

        # Checking if actuator is operating
        if irrigator_status != "DISABLE":
            # Structure the SenML message
            msg = copy.deepcopy(self.msg)
            msg["e"][0]["t"] = str(time.time())
            command_value = None
            value = msg_info["value"]

            # Setting the command
            if value < minMoisture:
                command_value = "pour_water"

            if command_value:
                msg["e"][0]["v"] = command_value
                self.publish_command(actuators, "irrigator", msg)
        else:
            self.logger.warning("Irrigator is DISABLE!")



    def publish_command(self, actuators, corresponding_actuator, msg):
        # Sending command to the actuators 
            topic = self._find_topic_for_actuator(actuators, corresponding_actuator)
            msg['bn'] = topic   
            self.mqtt_client.publish(topic, msg)
            self.logger.info(f"{msg['e'][0]['v']} is published on topic: {topic}")


    def days_difference_from_today(self, plantingDate):
        today = date.today()

        # Convert the format from string to date obj
        theDate = datetime.strptime(plantingDate, "%Y-%m-%d").date()

        # Calculate the difference in days
        difference = (today - theDate).days

        return difference


    
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

