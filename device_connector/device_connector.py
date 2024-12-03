import os
import json
import requests
import time
import threading
import copy
from typing import Literal
from models import Device, Plant
from config import Config, MyLogger
from sensors import TempSen, LightSen, PHSen, SoilMoistureSen, create_sensor
from utility import case_insensitive
from MyMQTT2 import MyMQTT


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
    
    # Will be triggered when a message is received
    def notify(self, topic, payload):
        self.host.notify(topic, payload)



class DeviceConnector:
    def __init__(self, config: Config):
        self.config = config
        self.devices = []
        self.plants = []
        self.available_sensors = {}
        self.catalog_address = self.config.CATALOG_URL
        self.logger = MyLogger.get_main_loggger()
        self.broker = None
        self.port = None
        self.msg = {
            "bn": "",
            "e": [
                {
                    "n": 'senKind',
                    "u": 'unit',
                    "t": None,
                    "v": None
                }
            ]
        }

        self.initiate(config_file=self.config.CONFIG_FILE)
        # Register plants and devices on catalog
        self.register(initial=True)
        self.get_broker()
        self.initiate_mqtt()
        self.subscribe_to_actuators()
        self.initialize_sensors() # Initialize sensors after loading devices
        self.start_data_collection_thread()  # Start data collection in a separate thread

        

    # TODO: serivice registry    


    def initiate(self, config_file: str):
        # Check if the file exists
        if not os.path.exists(config_file):
            raise FileNotFoundError(f"Configuration file {config_file} not found.")
        
        with open(config_file, 'r') as file:
            try:
                config_data = json.load(file)
            except json.JSONDecodeError as e:
                raise ValueError(f"Error decoding JSON from file {config_file}: {e}")

        # Validate the file structure
        if 'plants' not in config_data:
            raise ValueError("Configuration file must contain 'plants' field.")
        if 'devices' not in config_data or not config_data['devices']:
            raise ValueError("Configuration file must contain 'devices' field with at least one device.")
        
        # Populate plants
        for plant_data in config_data['plants']:
            plant = Plant(**plant_data)
            self.add_plant(plant)

        # Populate devices
        for device_data in config_data['devices']:
            device = Device(**device_data)
            self.add_device(device)


    def initiate_mqtt(self):
        self.mqtt_client = MyClientMQTT(clientID = self.config.MQTT_CLIENT_ID,
                                        broker=self.broker,
                                        port=self.port,
                                        host=self,
                                        child_logger=MyLogger.set_logger(logger_name=Config.MQTT_LOGGER))
    

    def stop_mqtt(self):
        self.mqtt_client.stop()

    def subscribe_to_actuators(self):
        self.logger.info("Subscribing to actuators' topics...")
        for device in self.devices:
            if device.device_type == "actuator":
                for service_detail in device.services_details:
                            if service_detail.service_type == "MQTT":
                                for topic in service_detail.topic:
                                    self.mqtt_client.subscribe(topic)


    def initialize_sensors(self):
        self.logger.info("Initializing sensors...")
        for device in self.devices:
            if device.device_type == "sensor":
                for measure_type in device.measure_types:
                    try:
                        sensor_instance = create_sensor(measure_type)
                        sensor_key = f"{measure_type}_{device.device_id}"
                        self.available_sensors[sensor_key] = {"obj": sensor_instance, "topics": []}
                        self.logger.info(f"Sensor {sensor_key} created and added.")

                        for service_detail in device.services_details:
                            if service_detail.service_type == "MQTT":
                                for topic in service_detail.topic:
                                    if measure_type in topic:
                                        self.available_sensors[sensor_key]["topics"].append(topic)

                    except ValueError as e:
                        self.logger.error(f"Error creating sensor for device {device.device_id} with type {measure_type}: {e}")
                
                
        self.logger.debug(f"Created sensors: {self.available_sensors}")


    def add_device(self, device: Device):
        self.devices.append(device)
        self.logger.info(f"Device {device.device_id} added.")
    
    def add_plant(self, plant: Plant):
        self.plants.append(plant)
        self.logger.info(f"Plant {plant.plant_id} added.")


    def register(self, initial: bool=False):
        self._register_plants(initial)
        self._register_devices(initial)
        print()


    def _register_plants(self, initial: bool=False):
        url = f"{self.catalog_address}/{self.config.PLANTS_ENDPOINT}"
        method = "POST" if initial else "PUT"
        for plant in self.plants:
            self.logger.info(f"Registring plant {plant.plant_id} ...")
            self._send_request(method, url, plant.model_dump(), 
                               plant.plant_id, item_type="plant")


    def _register_devices(self, initial: bool=False):
        url = f"{self.catalog_address}/{self.config.DEVICES_ENDPOINT}"
        method = 'POST' if initial else 'PUT'
        for device in self.devices:
            self.logger.info(f"Registring device {device.device_id} ...")
            self._send_request(method, url, device.model_dump(), 
                               device.device_id, item_type="device")

    
    def _send_request(self, method: str, url: str, data: dict, 
                      item_id: int, item_type: Literal["plant", "device"]):
        try:
            response = requests.request(method, url, json=data)
            self.logger.info(f"{method} Request with response: {response.text}")
            if response.json().get("status") == 409 and method == 'POST':
                # Conflict, item already exists, retry with PUT
                self.logger.warning(f"Conflict detected for {item_type} {item_id}, retrying with PUT request.")
                response = requests.put(url, json=data)

            response.raise_for_status()
            if not response.json().get("success"):
                self.logger.info(f"Registration unsuccessful for {item_type} {item_id} with message {str(response.text)}.")
            else:
                self.logger.info(f"Successfully registered {item_type} {item_id}.")

        except requests.RequestException as e:
            self.logger.error(f"Failed to register {item_type} {item_id}: {e}")


    def collect_and_average_sensor_data(self):
        while True:
            collected_data = {device_id: [] for device_id in self.available_sensors.keys()}
            
            try:
                for _ in range(self.config.DATA_POINTS_FOR_AVERAGE):
                    for device_id, sensor_dict in self.available_sensors.items():
                        sensor = sensor_dict.get("obj")
                        if sensor:
                            try:
                                data = sensor.generate_data()
                                collected_data[device_id].append(data)
                            except Exception as e:
                                self.logger.error(f"Error generating data for sensor {device_id}: {e}")
                        else:
                            self.logger.error(f"Sensor object not found for device {device_id}")
                    time.sleep(self.config.DATA_COLLECTION_INTERVAL)

                averaged_data = {}
                for device_id, data_list in collected_data.items():
                    if data_list:
                        averaged_data[device_id] = sum(data_list) / len(data_list)
                    else:
                        self.logger.warning(f"No data collected for device {device_id}")

                self.logger.info(f"Averaged sensor data: {averaged_data}")
                self.prepare_data_to_publish(averaged_data)

            except Exception as e:
                self.logger.error(f"Error in data collection loop: {e}")


    def start_data_collection_thread(self):
        # Start the data collection in a separate thread so it doesn't block the main thread
        try:
            data_collection_thread = threading.Thread(target=self.collect_and_average_sensor_data)
            data_collection_thread.daemon = True  # Ensures the thread is killed when the main program exits
            data_collection_thread.start()    
        except Exception as e:
            self.logger.error(f"Error starting data collection thread: {e}")


    def prepare_data_to_publish(self, averaged_data: dict):
        for sensor_key, datum in averaged_data.items():
            sensor_dict = self.available_sensors.get(sensor_key)
            if sensor_dict:
                sensor = sensor_dict.get("obj")
                if sensor:
                    try:
                        msg = copy.deepcopy(self.msg)
                        msg['e'][0]['n'], msg['e'][0]['u'] = sensor.get_info()
                        msg['e'][0]['t'] = str(time.time())
                        msg['e'][0]['v'] = datum

                        for topic in sensor_dict.get("topics"):
                            msg['bn'] = topic
                            try:
                                self.mqtt_client.publish(topic=topic, msg=msg)
                                self.logger.info(f"Message {datum} published on topic: {topic}")
                            except Exception as e:
                                self.logger.error(f"Error publishing message to topic {topic}: {e}")

                    except Exception as e:
                        self.logger.error(f"Error preparing message for sensor {sensor_key}: {e}")
                else:
                    self.logger.error(f"Sensor object not found for sensor {sensor_key}")
            else:
                self.logger.error(f"Sensor dictionary not found for sensor {sensor_key}")
            

    def get_broker(self):
        try:
            url = f"{self.catalog_address}/general/broker"
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



    def notify(self, topic, payload):
        msg = json.loads(payload)
        
        # Part of the message related to the event happened
        event = msg["e"][0]
        print(f"{topic} measured a {event['n']} of {event['v']} {event['u']} at time {event['t']}")

        #TODO:change the status of device in catalog





if __name__ == "__main__":
    dc = DeviceConnector(config=Config)
    
    while True:
        time.sleep(10)
        print(".........")
    else:
        dc.stop_mqtt()
        
        # dc.collect_and_average_sensor_data()

    # t = 1
    # while t < 600:
    #     if t % Config.REGISTERATION_INTERVAL == 0:
    #         dc.register()
    #     if t % Config.DATA_GENERATION_INTERVAL ==

    #     time.sleep(1)
    #     t+=1
