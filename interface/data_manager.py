import requests
import time
from typing import Literal
from MyMQTT2 import MyMQTT
from config import Config, MyLogger


class MyClientMQTT():
    def __init__(self, clientID, broker, port, host, child_logger):
        self.host = host
        self.client = MyMQTT(clientID, broker, port, host, child_logger)
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




class DataManager():
    def __init__(self):
        self.config = Config
        self.logger = MyLogger.set_logger(self.config.MANAGER_LOGGER)
        self.catalog_address = self.config.CATALOG_URL
        self.plants = []
        self.endpoint_cache = {}
        self.broker = None
        self.port = None

       
        self.logger.info("Initiating the data manager...")
        self.get_broker()
        



    # Add getting info of adaptor address from the catalog and then request
    def get_channel_detail(self, channel_name):
        endpoint, host = self._discover_service_plus(item=self.config.ADAPTOR_CHANNEL_ENDPOINT, 
                                                    method='GET',
                                                    microservice=self.config.THINGSPEAK_ADAPTOR_REGISTRY_NAME)
        try:
            if endpoint and host:    
                url = f"{host}{endpoint}/{channel_name}"
                req_p = requests.get(url=url)
                req_p.raise_for_status()
                self.logger.info(f"Thingspeak channel {channel_name }'s detail is updated.")
                channel_detail = req_p.json()
                if not channel_detail.get("success"):
                    self.logger.error(f"Failed to get channel detail for {channel_name}.")
                    return {}
                return channel_detail.get("content")
                
            else:
                self.logger.error(f"Failed to get plant endpoint")
                return {}
        except requests.RequestException as e:
            self.logger.error(f"Failed to fetch adaptor channel information: {e}")
            return {}
        
        
    # Post the satatus of the device to the operator control
    def post_device_status(self, device_detail: dict):
        self.initiate_mqtt()
        time.sleep(1)
        devices = self._get_devices(device_id=device_detail.get("deviceId"))
        if not devices:
            self.logger.error(f"No device detected for device status request with detail: {str(device_detail)}")
        device = devices[0]
        for services_detail in device["servicesDetails"]:
            topics = services_detail.get("topic")
            if topics:
                topic = topics[0]
        msg = {
            "bn": topic,
            "e": [
                {
                    "n": 'interface',
                    "u": 'command',
                    "t": str(time.time()),
                    "v": device_detail.get("status")
                }
            ]
        }
        self.logger.debug(f"topic: {topic}, msg: {msg}")
        self.mqtt_client.publish(topic, msg)
        time.sleep(1)



    def update_plant_list(self, plant_id: int=None):
        endpoint, host = self._discover_service_plus(self.config.PLANTS_ENDPOINT, 'GET')
        try:
            if endpoint:    
                url = f"{self.catalog_address}{endpoint}"
                if plant_id:
                    url += f"/{plant_id}"
            else:
                self.logger.error(f"Failed to get plant endpoint")
                return
            
            self.logger.info(f"Fetching sensors information from {url}")
            response = requests.get(url)
            response.raise_for_status()
            plants_response = response.json()

            if plants_response.get("success"):
                plants_list = plants_response["content"]
                if plants_list:
                    self.plants = plants_list
            
        except requests.RequestException as e:
            self.logger.error(f"Failed to fetch devices information: {e}")


    def get_plants(self):
        return self.plants
    
    def get_room_for_plant(self, plant_id: int):
        for plant in self.plants:
            if plant["plantId"] == plant_id:
                return plant["roomId"]
        return 1    


    def _get_devices(self,
                    measure_type: str=None,
                    device_type: str=None,
                    plant_id: int=None,
                    room_id: int=None,
                    device_id: str=""):
        
        local_vars = {
        'measure_type': measure_type,
        'device_type': device_type,
        'plant_id': plant_id,
        'room_id': room_id
    }
        
        params = {k: v for k, v in local_vars.items() if v is not None}
        endpoint, host = self._discover_service_plus(self.config.DEVICES_ENDPOINT, 'GET')
        try:
            if endpoint:    
                url = f"{self.catalog_address}{endpoint}"
                if device_id:
                    url += f"/{device_id}"
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


    def get_devices_for_plant(self, room_id: int, plant_id: int): 
        plant_devices = self._get_devices(room_id=room_id, plant_id=plant_id) 
        temp_device = self._get_devices(measure_type="temperature", room_id=room_id)
        ligh_device = self._get_devices(measure_type="light", room_id=room_id)

        return plant_devices + temp_device + ligh_device


    def initiate_mqtt(self):
        self.mqtt_client = MyClientMQTT(clientID = self.config.MQTT_CLIENT_ID,
                                        broker=self.broker,
                                        port=self.port,
                                        host=None,
                                        child_logger=MyLogger.set_logger(logger_name=Config.MQTT_LOGGER))


    def stop_mqtt(self):
        self.mqtt_client.stop()


    def _discover_service_plus(self, item: str, method: Literal['GET', 'POST', 'PUT', 'DELETE'], sub_path: str=None, microservice: str=Config.SERVICE_REGISTRY_NAME):
        # Return the endpoint from the cache
        if item in self.endpoint_cache and method in self.endpoint_cache[item]:
            return self.endpoint_cache[item][method], self.endpoint_cache[item]['host']

        try:
            url = f"{self.catalog_address}/{self.config.SERVICES_ENDPOINT}/{microservice}"
            response = requests.get(url)
            response.raise_for_status()

            service_response = response.json()

            if service_response.get("success"):
                # Extract the service registry from the response
                service_registry = service_response.get("content", [[]])
                service = service_registry[0]
                if service:
                    endpoints = service.get("endpoints", [])
                    host = service.get("host", "")
                    for endpoint in endpoints:
                        path = endpoint.get("path", "")
                        service_method = endpoint.get("method", "")

                        if item in path and method == service_method:
                            if sub_path:
                                if sub_path in path:
                                    self.endpoint_cache.setdefault(item, {})[method] = path
                                    self.endpoint_cache[item]["host"] = host
                                    return path, host
                            else:
                                self.endpoint_cache.setdefault(item, {})[method] = path
                                self.endpoint_cache[item]["host"] = host
                                return path, host
                            
            self.logger.error(f"Failed to discover service endpoint")

        except requests.RequestException as e:
            self.logger.error(f"Failed to fetch services endpoint: {e}")


    def get_broker(self):
        endpoint, host = self._discover_service_plus(self.config.GENERAL_ENDPOINT, 'GET')
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



# if __name__ == "__main__":
#     data_manager = DataManager()
#     data_manager.update_plant_list()
#     data_manager.get_plants()
#     data_manager.get_channel_detail('1')