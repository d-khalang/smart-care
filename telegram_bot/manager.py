import os
import requests
import json
from datetime import date, datetime
from typing import Literal
from config import Config, MyLogger

class DataManager():
    def __init__(self, config: Config):
        self.config = config
        self.logger = MyLogger.set_logger(config.DATA_MANAGER_LOGGER)
        self.catalog_address = self.config.CATALOG_URL
        self.endpoint_cache = {}
        # self.post_service()
        self.logger.info("Initiating the data manager...")



    def update_ownership(self) -> tuple: 
        ownership_dict = {}
        plants = self._get_plant()
        users = self._get_user()

        # Create a mapping of plant IDs to their respective owner user objects
        plant_to_user_map = {}
        for user in users:
            for plant_id in user["plantInventory"]:
                plant_to_user_map[plant_id] = user

        # Update ownership_dict with plant IDs and their respective owner user object or empty dict if no owner
        for plant in plants:
            plant_id = plant["plantId"]
            if plant_id in plant_to_user_map:
                ownership_dict[plant_id] = plant_to_user_map[plant_id]
            else:
                ownership_dict[plant_id] = {}
        available_plants = [k for k,v in ownership_dict.items() if v=={} ]
        return ownership_dict, available_plants


    def delete_plant_from_user_inventory(self, plant_id, user_id):
        endpoint, host = self._discover_service_plus(self.config.USERS_ENDPOINT, 'DELETE')
        params = {
            "plant_id": int(plant_id),
            "telegram_id": user_id
        }
        try:
            if endpoint:    
                url = f"{self.catalog_address}{endpoint}"
            else:
                self.logger.error(f"Failed to get users endpoint")
                
            self.logger.info(f"Removing req send to {url} with params: {params}")
            response = requests.delete(url, params=params)
            response.raise_for_status()
            users_response = response.json()

            if users_response.get("success"):
                return True

        except requests.RequestException as e:
            self.logger.error(f"Failed to delete plant {plant_id} from user: {e}")
            return
        except Exception as e:
            self.logger.error(f"Failed to delete plant {plant_id} from user: {e}")
            return


    def post_user(self, plant_id, username, password, telegram_id):
        endpoint, host = self._discover_service_plus(self.config.USERS_ENDPOINT, 'POST')
        body = {
            "userName": username,
            "password": password,
            "plantId": int(plant_id),
            "telegramId": telegram_id
        }
        try:
            if endpoint:    
                url = f"{self.catalog_address}{endpoint}"
            else:
                self.logger.error(f"Failed to get users endpoint")
                
            self.logger.info(f"Posting users information to {url} with body: {body}")
            response = requests.post(url, json=body)
            response.raise_for_status()
            users_response = response.json()

            if users_response.get("success"):
                return True

        except requests.RequestException as e:
            self.logger.error(f"Failed to post user: {e}")
            return
        except Exception as e:
            self.logger.error(f"Failed to post user: {e}")
            return


    # Getting the age of the plant
    def get_plant_age(self, plant_id):
        plants = self._get_plant(plant_id)
        if plants:
            plant = plants[0]
        else:
            return 99
        # 7 weeks to be ripe
        
        plante_date = plant["plantDate"]

        today = date.today()

        # Convert the format from string to date obj
        the_date = datetime.strptime(plante_date, "%Y-%m-%d").date()

        # Calculate the difference in days
        difference = (today - the_date).days
        days_until_ready = self.config.FULL_GROWING_TIME - difference

        return days_until_ready if days_until_ready else 99


    def show_actuators_status(self, plant_id):
        room_id = int(self._get_room_for_plant(plant_id))
        devices = self.get_devices_for_plant(room_id, int(plant_id))
        status_dict = {device.get("deviceName"): device.get("deviceStatus") for device in devices}
        return status_dict

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


    def _get_user(self, user_name: str=None, plant_id: int=None, telegram_id: str=None):
        endpoint, host = self._discover_service_plus(self.config.USERS_ENDPOINT, 'GET')
        output = []
        params = {k: v for k, v in {
            "user_name": user_name,
            "plant_id": plant_id,
            "telegram_id": telegram_id
        }.items() if v is not None}
        try:
            if endpoint:    
                url = f"{self.catalog_address}{endpoint}"
            else:
                self.logger.error(f"Failed to get users endpoint")
                
            self.logger.info(f"Fetching users information from {url} with param: {params}")
            response = requests.get(url, params=params)
            response.raise_for_status()
            users_response = response.json()

            if users_response.get("success"):
                users_list = users_response["content"]
                if users_list:
                    output = users_list
        
        except requests.RequestException as e:
            self.logger.error(f"Failed to fetch users information: {e}")
            
        return output


    def _get_plant(self, plant_id=None):
        endpoint, host = self._discover_service_plus(self.config.PLANTS_ENDPOINT, 'GET')
        output = []
        try:
            if endpoint:    
                url = f"{self.catalog_address}{endpoint}"
                if plant_id:
                    url += f"/{plant_id}"
            else:
                self.logger.error(f"Failed to get plant endpoint")
                
            
            self.logger.info(f"Fetching sensors information from {url}")
            response = requests.get(url)
            response.raise_for_status()
            plants_response = response.json()

            if plants_response.get("success"):
                plants_list = plants_response["content"]
                if plants_list:
                    output = plants_list
        
        except requests.RequestException as e:
            self.logger.error(f"Failed to fetch devices information: {e}")
            
        return output


    def _get_rooms(self, room_id: str):
        endpoint, host = self._discover_service_plus(self.config.ROOMS_ENDPOINT, 'GET')
        output = []
        try:
            if endpoint:    
                url = f"{self.catalog_address}{endpoint}"
                if room_id:
                    url += f"/{room_id}"
            else:
                self.logger.error(f"Failed to get rooms endpoint")
                
            self.logger.info(f"Fetching rooms information from {url}")
            response = requests.get(url)
            response.raise_for_status()
            rooms_response = response.json()

            if rooms_response.get("success"):
                rooms_list = rooms_response["content"]
                if rooms_list:
                    output = rooms_list
        
        except requests.RequestException as e:
            self.logger.error(f"Failed to fetch rooms information: {e}")
            
        return output


    def _get_room_for_plant(self, plant_id):
        plants = self._get_plant(plant_id=plant_id)
        for plant in plants:
            if plant["plantId"] == int(plant_id):
                return plant["roomId"]
        return 0    


    def get_sensing_data(self, plant_id: str, room_id: str = None, results: int = 4, start_date: str = None, end_date: str = None):
        endpoint, host = self._discover_service_plus(item=self.config.ADAPTOR_SENSING_DATA_ENDPOINT, 
                                                    method='GET',
                                                    microservice=self.config.THINGSPEAK_ADAPTOR_REGISTRY_NAME)
        
        if not room_id:
            room_id = self._get_room_for_plant(plant_id)
            if not room_id:
                self.logger.error(f"No room_id detected for plant {plant_id}")
                return
        
        local_vars = {
        'results': results,
        'start_date': start_date,
        'end_date': end_date,
        'plant_id': plant_id
        }
        
        params = {k: v for k, v in local_vars.items() if v is not None}
        try:
            if endpoint and host:    
                url = f"{host}{endpoint}/{room_id}"
                req_g = requests.get(url=url, params=params)
                req_g.raise_for_status()
                self.logger.info(f"Sensing data for room {room_id} with params: {params} received.")
                sensing_data_response = req_g.json()
                if not sensing_data_response.get("success"):
                    self.logger.error(f"Failed to get sensing data with response: {sensing_data_response}.")
                    return {}
                return sensing_data_response.get("content")
                
            else:
                self.logger.error(f"Failed to get sensing data endpoint")
                return {}
            
        except requests.RequestException as e:
            self.logger.error(f"Failed to fetchsensing data: {e}")
            return {}


    def get_report(self, plant_id, results: int=100):
        endpoint, host = self._discover_service_plus(item=self.config.REPORTER_ENDPOINT, 
                                                    method='GET',
                                                    microservice=self.config.REPORTER_REGISTRY_NAME)
        try:
            if endpoint and host:    
                url = f"{host}{endpoint}/{plant_id}"
                req = requests.get(url=url, params={"results": results}, headers={"Accept": "application/pdf"})
                req.raise_for_status()
                
                # Ensure the directory exists
                if not os.path.exists(self.config.REPORT_SAVE_PATH):
                    os.makedirs(self.config.REPORT_SAVE_PATH)
                
                # Ensure REPORT_SAVE_PATH points to a file
                base_file_name = f"report_{plant_id}.pdf"
                save_path = os.path.join(self.config.REPORT_SAVE_PATH, base_file_name)

                # Check if file with same name exists and modify the name slightly if it does
                if os.path.exists(save_path):
                    base_name, extension = os.path.splitext(base_file_name)
                    counter = 1
                    while os.path.exists(save_path):
                        new_file_name = f"{base_name}_{counter}{extension}"
                        save_path = os.path.join(self.config.REPORT_SAVE_PATH, new_file_name)
                        counter += 1

                with open(save_path, 'wb') as file:
                    file.write(req.content)
                    self.logger.info(f"Report received for plant {plant_id}, saved as {save_path}")
                    return save_path
                    
            else:
                self.logger.error(f"Failed to get the report endpoint")
                return 
            
        except requests.RequestException as e:
            self.logger.error(f"Failed to fetch the report: {e}")
            return 
        

    def get_bot_token(self):
        endpoint, host = self._discover_service_plus(self.config.GENERAL_ENDPOINT, 'GET')
        output = ""
        try:
            if endpoint:    
                url = f"{self.catalog_address}{endpoint}/telegram_bot"
            else:
                self.logger.error(f"Failed to get telegram bot's endpoint")
                
            self.logger.info(f"Fetching telgram bot information from {url}")
            response = requests.get(url)
            response.raise_for_status()
            json_data = response.json()

            if json_data.get("success"):
                data = json_data.get("content", [[]])
                output = data.get("telegramBot",{}).get("token","")
                if output:
                    self.logger.info("Bot token received.")
        
        except requests.RequestException as e:
            self.logger.error(f"Failed to fetch Telegram bot's information: {e}")
        return output


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


if __name__ == "__main__":
    manager = DataManager(Config)
    # data = manager.get_sensing_data(101, results=1)
    data = manager.get_report(101)
    print(data)