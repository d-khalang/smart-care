import requests
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
        available_plants = [k for k,v in ownership_dict.items if v=={} ]
        return ownership_dict, available_plants


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
