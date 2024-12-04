import json
import requests
import time
import threading
import copy
from typing import Literal, List
from config import Config, MyLogger
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



class Controler():
    def __init__(self, config: Config, inital_rooms: List[int]):
        self.config = config
        self.rooms = []
        self.sensors = []
        self.catalog_address = self.config.CATALOG_URL
        self.logger = MyLogger.get_main_loggger()
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

        self.get_sensors()
        self.get_broker()
        self.get_topic_template()
        self.initiate_mqtt()
        self.subscribe_to_sensors()


    # TODO: procedure for unsubscribing the removed ones 
    def subscribe_to_sensors(self):
        for sensor in self.sensors:
            services_details = sensor.get("servicesDetails", [])

            for service_dict in services_details:
                topics = service_dict.get("topic", [])

                for topic in topics:
                    self.mqtt_client.subscribe(topic)



    def get_sensors(self):
        for room_id in self.rooms:
            sensors = self.get_devices(device_type="sensor", room_id=room_id)
            for sensor in sensors:
                if sensor not in self.sensors:
                    self.sensors.append(sensor)


    def get_devices(self,
                    measure_type: str=None,
                    device_type: str=None,
                    plant_id: int=None,
                    room_id: int=None):
        
        local = locals()
        local.pop(self)

        params = {k: v for k, v in local.items() if v is not None}
        endpoint = self._discover_service("devices", 'GET')
        try:
            if endpoint:    
                url = f"{self.catalog_address}{endpoint}"
            else:
                self.logger.error(f"Failed to get broker endpoint")
                return
            
            self.logger.info(f"Fetching sensors information from {url} with params: {params}")
            response = requests.get(url)
            response.raise_for_status()
            devices_response = response.json()

            if devices_response.get("success"):
                devices_list = devices_response["content"]

            if devices_list:
                return devices_list
                
            
            self.logger.error(f"Failed to fetch template information.")
            
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
        try:
            url = f"{self.catalog_address}/{self.config.SERVICES_ENDPOINT}/{self.config.SERVICE_REGISTRY_NAME}"
            response = requests.get(url)
            response.raise_for_status()

            service_response = response.json()

            if service_response.get("success"):
                # Extract the service registry from the response
                service_registry = service_response.get("content", [])
                service = service_registry[0]
                if service:
                    endpoints = service.get("endpoints", [])
                    for endpoint in endpoints:
                        path = endpoint.get("path", "")
                        service_method = endpoint.get("method", "")

                        if item in path and method == service_method:
                            if sub_path:
                                if sub_path in path:
                                    return path
                            else:
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





if __name__ == "__main__":
    controler = Controler(Config, [1, 2])
    controler.get_devices()