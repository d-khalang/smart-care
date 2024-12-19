import os
import time
import requests
import docker
from typing import Literal
from itertools import zip_longest
from config import Config, MyLogger


class ControllerManager:
    def __init__(self, config: Config):
        self.config = config
        self.logger = MyLogger.get_main_loggger()
        self.client = docker.from_env()
        self.endpoint_cache = {}
        self.controllers = {}
        self.run()


    def _discover_service_plus(self, item: str, method: Literal['GET', 'POST', 'PUT', 'DELETE'], sub_path: str=None, microservice: str=Config.SERVICE_REGISTRY_NAME):
        # Return the endpoint from the cache
        if item in self.endpoint_cache and method in self.endpoint_cache[item]:
            return self.endpoint_cache[item][method], self.endpoint_cache[item]['host']

        try:
            url = f"{self.config.CATALOG_URL}/{self.config.SERVICES_ENDPOINT}/{microservice}"
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


    def _get_rooms(self, room_id: str=None):
        endpoint, host = self._discover_service_plus(self.config.ROOMS_ENDPOINT, 'GET')
        output = []
        try:
            if endpoint:    
                url = f"{self.config.CATALOG_URL}{endpoint}"
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


    def update_rooms(self):
        # Get rooms from catalog
        new_rooms_obj = self._get_rooms()
        new_rooms = [room.get("roomId") for room in new_rooms_obj]
        new_room_set = set(new_rooms)
        
        # Check for changes and update accordingly
        current_rooms = set(sum(self.controllers.values(), []))
        rooms_to_add = new_room_set - current_rooms
        rooms_to_remove = current_rooms - new_room_set
        
        # Update controllers
        if rooms_to_add or rooms_to_remove:
            self.manage_controllers(new_rooms)


    # user service descovery
    def get_rooms_from_catalog(self):
        response = requests.get(f"{self.config.CATALOG_URL}/rooms")
        response.raise_for_status()
        return response.json()


    def manage_controllers(self, new_rooms):
        current_controllers = list(self.controllers.keys())
        new_controller_config = list(zip_longest(*[iter(new_rooms)]*2, fillvalue=None))

        # Adjust the current configuration
        for controller, rooms in zip_longest(current_controllers, new_controller_config):
            if controller and rooms:
                self.update_controller(controller, list(filter(None, rooms)))
            elif controller and not rooms:
                self.remove_controller(controller)
            elif rooms and not controller:
                self.create_controller(list(filter(None, rooms)))


    def create_controller(self, room_ids):
        env_vars = self.construct_env_vars(room_ids)
        container = self.client.containers.run(
            "controller_image",  # controller image name
            name="controller_" + '_'.join(list(map(str, room_ids))),
            network="smart_care_network",
            environment=env_vars,
            ports={'80/tcp': env_vars["CU_PORT"]},  
            detach=True
        )
        self.controllers[container.name] = room_ids
        self.logger.info(f"Container {container.name} is created.")


    def update_controller(self, controller, room_ids):
        container = self.client.containers.get(controller)
        old_room_ids = self.controllers[controller]
        
        # Send API request to update the controller configuration
        # Assuming the controller has an endpoint to update its room allocation
        response = self.send_update_request(container, room_ids)
        
        if response.status_code == 200:
            self.controllers[controller] = room_ids
        else:
            # Handle failed update, perhaps by restarting the container
            self.restart_controller(container, room_ids)


    def send_update_request(self, container, room_ids):
        url = f"http://{container.attrs['NetworkSettings']['IPAddress']}/update_rooms"
        payload = {"room_ids": room_ids}
        return requests.post(url, json=payload)


    def restart_controller(self, container, room_ids):
        container.stop()
        container.remove()
        self.create_controller(room_ids)


    def remove_controller(self, controller):
        container = self.client.containers.get(controller)
        container.stop()
        container.remove()
        del self.controllers[controller]


    def construct_env_vars(self, room_ids):
        env_vars = {
            "CATALOG_URL": "http://host.docker.internal:8080",
            "CU_PORT": str(self.get_next_available_port()),
            "PLANTS_ENDPOINT": self.config.PLANTS_ENDPOINT,
            "DEVICES_ENDPOINT": self.config.DEVICES_ENDPOINT,
            "GENERAL_ENDPOINT": self.config.GENERAL_ENDPOINT,
            "SERVICES_ENDPOINT": self.config.SERVICES_ENDPOINT,
            "ROOMS_ENDPOINT": self.config.ROOMS_ENDPOINT,
            "SERVICE_REGISTRY_NAME": self.config.SERVICE_REGISTRY_NAME,
            "WEATHER_FORECAST_URL": self.config.WEATHER_FORECAST_URL,
            "WEATHER_FORECAST_API_KEY": self.config.WEATHER_FORECAST_API_KEY,
            "MQTT_CLIENT_ID": f"smart_care_4ss_controller_{'_'.join(map(str, room_ids))}",
            "BASE_LOGGER": self.config.CU_LOGGER,
            "MQTT_LOGGER": self.config.MQTT_LOGGER,
            "TOPICS_UPDATE_INTERVAL": int(self.config.TOPICS_UPDATE_INTERVAL),
            "ROOM_IDS": ','.join(map(str, room_ids))  # Pass room IDs as a comma-separated string
        }
        return env_vars
    
    def get_next_available_port(self):
        # Implement logic to find the next available port
        # Placeholder for actual implementation
        return 7090

    def run(self):
        while True:
            self.update_rooms()
            time.sleep(self.config.CONTROLLER_CONFIG_INTERVAL)  # Check every 5 minutes

if __name__ == "__main__":
    manager = ControllerManager(Config)
    
    # print()
    # client = docker.from_env()