import os
import json
import requests
import time
import sched
from typing import Literal
from models import Device, Plant
from config import Config, MyLogger


class DeviceConnector:
    def __init__(self, config_file: str, catalog_address: str):
        self.devices = []
        self.plants = []
        self.catalog_address = catalog_address
        self.logger = MyLogger.get_main_loggger()
        self._initiate(config_file=config_file)
        # # Scheduler config
        # self.run_scheduler()
        

    # TODO: serivice registry    

    # def run_scheduler(self):
    #     self.registration_interval = Config.REGISTERATION_INTERVAL
    #     self.scheduler = sched.scheduler(time.time, time.sleep)
    #     self.scheduler.enter(self.registration_interval, 1, self.register, ())
    #     self.scheduler.run(blocking=False)


    def _initiate(self, config_file: str):
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

        # Register plants and devices on catalog
        self.register(initial=True)


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

        # if not initial:
        #     # Reschedule the periodic registration every x seconds
        #     self.logger.info("Reshceduling registration...")
        #     self.scheduler.enter(self.registration_interval, 1, self.register, ())


    def _register_plants(self, initial: bool=False):
        url = f"{self.catalog_address}/{Config.PLANTS_ENDPOINT}"
        method = "POST" if initial else "PUT"
        for plant in self.plants:
            self.logger.info(f"Registring plant {plant.plant_id} ...")
            self._send_request(method, url, plant.model_dump(), 
                               plant.plant_id, item_type="plant")


    def _register_devices(self, initial: bool=False):
        url = f"{self.catalog_address}/{Config.DEVICES_ENDPOINT}"
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

            self.logger.info(f"Successfully registered {item_type} {item_id}.")

        except requests.RequestException as e:
            self.logger.error(f"Failed to register {item_type} {item_id}: {e}")









if __name__ == "__main__":
    dc = DeviceConnector(config_file=Config.CONFIG_FILE, catalog_address=Config.CATALOG_URL)

    t = 1
    while t < 600:
        if t%Config.REGISTERATION_INTERVAL == 0:
            dc.register()

        time.sleep(1)
        t+=1