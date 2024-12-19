import os
import time
import requests
import docker
import json
import socket
from typing import Literal
from itertools import zip_longest
from config import Config, MyLogger


class ControllerManager:
    STATE_FILE = "controller_manager_state.json"

    def __init__(self, config: Config):
        self.config = config
        self.logger = MyLogger.get_main_loggger()
        self.client = docker.from_env()
        self.endpoint_cache = {}
        self.controllers = {}
        self.load_state()
        self.run()

    def load_state(self):
        """Load the state from a file to restore the controllers."""
        if os.path.exists(self.STATE_FILE):
            with open(self.STATE_FILE, 'r') as file:
                self.controllers = json.load(file)
            self.logger.info("Loaded state from file.")
        else:
            self.logger.info("No state file found. Starting fresh.")

    def save_state(self):
        """Save the current state to a file."""
        with open(self.STATE_FILE, 'w') as file:
            json.dump(self.controllers, file)
        self.logger.info("State saved to file.")

    def _discover_service_plus(self, item: str, method: Literal['GET', 'POST', 'PUT', 'DELETE'], sub_path: str = None, microservice: str = Config.SERVICE_REGISTRY_NAME):
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

            self.logger.error("Failed to discover service endpoint")

        except requests.RequestException as e:
            self.logger.error(f"Failed to fetch services endpoint: {e}")

    def _get_rooms(self, room_id: str = None):
        endpoint, host = self._discover_service_plus(self.config.ROOMS_ENDPOINT, 'GET')
        output = []
        try:
            if endpoint:
                url = f"{self.config.CATALOG_URL}{endpoint}"
                if room_id:
                    url += f"/{room_id}"
            else:
                self.logger.error("Failed to get rooms endpoint")

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
        self.save_state()

    def update_controller(self, controller, room_ids):
        container = self.client.containers.get(controller)
        old_room_ids = self.controllers[controller]

        # Send API request to update the controller configuration
        response = self.send_update_request(container, room_ids)

        if response.status_code == 200:
            self.controllers[controller] = room_ids
        else:
            # Handle failed update, perhaps by restarting the container
            self.restart_controller(container, room_ids)

    def send_update_request(self, container, room_ids):
        """Send a request to the controller to update room assignments."""
        # Get the current rooms assigned to the controller
        current_room_ids = self.controllers.get(container.name, [])
        
        # Determine which rooms need to be added or removed
        rooms_to_add = set(room_ids) - set(current_room_ids)
        rooms_to_remove = set(current_room_ids) - set(room_ids)
        
        # Create the base URL
        url = f"http://{container.attrs['NetworkSettings']['IPAddress']}/rooms"
        
        # Initialize response object
        response = None

        # If there are rooms to add, send a POST request
        if rooms_to_add:
            payload = {"rooms": list(rooms_to_add)}
            response = requests.post(url, json=payload)
            if response.status_code == 200:
                self.logger.info(f"Successfully added rooms {list(rooms_to_add)} to controller {container.name}")
            else:
                self.logger.error(f"Failed to add rooms to controller {container.name}, status code: {response.status_code}")

        # If there are rooms to remove, send a DELETE request
        if rooms_to_remove:
            rooms_str = ",".join(list(map(str, rooms_to_remove)))
            response = requests.delete(url=url+rooms_str)
            if response.status_code == 200:
                self.logger.info(f"Successfully removed rooms {list(rooms_to_remove)} from controller {container.name}")
            else:
                self.logger.error(f"Failed to remove rooms from controller {container.name}, status code: {response.status_code}")
        
        # If the request was successful, update the controller's room configuration
        if response and response.status_code == 200:
            self.controllers[container.name] = room_ids

        return response


    def restart_controller(self, container, room_ids):
        container.stop()
        container.remove()
        self.create_controller(room_ids)

    def remove_controller(self, controller):
        container = self.client.containers.get(controller)
        container.stop()
        container.remove()
        del self.controllers[controller]
        self.save_state()

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
        """Find and return the next available port starting from 7090."""
        port = 7090
        while not self._is_port_available(port):
            port += 1
        return port

    def _is_port_available(self, port):
        """Check if the given port is available on the local machine."""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(('0.0.0.0', port))  # Try to bind to the port
                return True
            except socket.error:
                return False  # Port is in use

    def check_existing_controllers(self):
        """Check for any existing controllers on startup."""
        for container in self.client.containers.list():
            if container.name.startswith("controller_"):
                try:
                    url = f"http://{container.name}/rooms"
                    response = requests.get(url)
                    response.raise_for_status()

                    room_data = response.json()
                    room_ids = room_data.get("content", [])
                    
                    self.controllers[container.name] = room_ids
                except requests.RequestException as e:
                    self.logger.error(f"Failed to fetch rooms for container {container.name}: {e}")

    def run(self):
        # Check for existing controllers on startup
        self.check_existing_controllers()

        while True:
            self.update_rooms()
            time.sleep(self.config.CONTROLLER_CONFIG_INTERVAL)  # Check every 5 minutes

    def cleanup(self):
        """Stop and remove all controllers before stopping the manager."""
        for controller in list(self.controllers.keys()):
            self.remove_controller(controller)
        self.save_state()


if __name__ == "__main__":
    manager = ControllerManager(Config)
    try:
        manager.run()
    except KeyboardInterrupt:
        manager.cleanup()
