import os
import time
import requests
import docker
import json
import socket
import copy
from typing import Literal
from itertools import zip_longest
from config import Config, MyLogger


class ControllerManager:
    def __init__(self, config: Config):
        self.catalog_address = config.CATALOG_URL
        self.config = config
        self.STATE_FILE = config.STATE_FILE
        self.service_specification = {}
        self.logger = MyLogger.get_main_loggger()
        self.client = docker.from_env()
        self.endpoint_cache = {}
        self.controllers = {}
        self.load_state()
        self.load_service_specification()

    def load_state(self):
        """Load the state from a file to restore the controllers."""
        if os.path.exists(self.STATE_FILE):
            with open(self.STATE_FILE, 'r') as file:
                self.controllers = json.load(file)
            self.logger.info("Loaded state from file.")
            # Verify if controllers are running and restart if necessary
            for controller_name, room_ids in self.controllers.items():
                try:
                    container = self.client.containers.get(controller_name)
                    if container.status != 'running':
                        self.logger.warning(f"Controller {controller_name} is not running. Restarting...")
                        container.start()
                except docker.errors.NotFound:
                    self.logger.warning(f"Controller {controller_name} not found. Recreating...")
                    self.create_controller(room_ids)
        else:
            self.logger.info("No state file found. Starting fresh.")

    def save_state(self):
        """Save the current state to a file."""
        with open(self.STATE_FILE, 'w') as file:
            json.dump(self.controllers, file)
        self.logger.info("State saved to file.")

    def load_service_specification(self):
        # Read the JSON file
        try:
            with open(self.config.SERVICE_REGISTRY_FILE, 'r') as file:
                self.service_specification = json.load(file)
        except FileNotFoundError:
            self.logger.error(f"Service registry file not found: {self.config.SERVICE_REGISTRY_FILE}")
        except json.JSONDecodeError:
            self.logger.error(f"Error decoding JSON from file: {self.config.SERVICE_REGISTRY_FILE}")

    def _discover_service_plus(self, item: str, method: Literal['GET', 'POST', 'PUT', 'DELETE'], sub_path: str = None, microservice: str = Config.SERVICE_REGISTRY_NAME):
        internal_logger = MyLogger.set_logger("SERVICE_DISCOVERY")
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

            internal_logger.error("Failed to discover service endpoint")

        except requests.RequestException as e:
            internal_logger.error(f"Failed to fetch services endpoint: {e}")

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
        new_rooms_list_obj = self._get_rooms()
        new_rooms = [room.get("roomId") for room in new_rooms_list_obj]
        new_room_set = set(new_rooms)

        # Check for changes and update accordingly
        current_rooms = set(sum(self.controllers.values(), []))
        rooms_to_add = new_room_set - current_rooms
        rooms_to_remove = current_rooms - new_room_set
        self.logger.info(f"Rooms to add: {rooms_to_add}, rooms to remove: {rooms_to_remove}")

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
        internal_logger = MyLogger.set_logger("CREATOR")
        internal_logger.info(f"Creating controllers for rooms: {room_ids}")
        env_vars = self.construct_env_vars(room_ids)
        internal_logger.info(f"Env variables: {env_vars}")
        controller_name = "controller_" + '_'.join(list(map(str, room_ids)))
        container = self.client.containers.run(
            "controller_image",  # controller image name
            name=controller_name,
            network="smart_care_network",
            environment=env_vars,
            ports={f"{env_vars['CU_PORT']}/tcp": env_vars["CU_PORT"]},
            detach=True
        )
        self.post_service(controller_name, env_vars["CU_PORT"])
        self.controllers[container.name] = room_ids
        internal_logger.info(f"Container {container.name} is created.")
        self.save_state()

    def update_controller(self, controller, room_ids):
        internal_logger = MyLogger.set_logger("MODIFIER")
        internal_logger.info(f"Updating controller {controller}.")
        container = self.client.containers.get(controller)
        old_room_ids = self.controllers[controller]
        if old_room_ids == room_ids:
            internal_logger.info(f"No new config for controller {container.name}")
            return

        # Send API request to update the controller configuration
        response = self.send_update_request(container, room_ids)

        try:
            if response.get("success"):
                self.controllers[controller] = room_ids
            else:
                # Handle failed update, perhaps by restarting the container
                self.restart_controller(container, room_ids)
        except AttributeError as e:
            internal_logger.error(f"Invalid response: {e}")
            self.restart_controller(container, room_ids)

    def send_update_request(self, container, room_ids):
        """Send a request to the controller to update room assignments."""
        internal_logger = MyLogger.set_logger("MODIFIER_REQ")
        # Get the current rooms assigned to the controller
        current_room_ids = self.controllers.get(container.name, [])
        
        # Determine which rooms need to be added or removed
        rooms_to_add = set(room_ids) - set(current_room_ids)
        rooms_to_remove = set(current_room_ids) - set(room_ids)
        
        # Create the base URL -> container name
        # Extract the mapped port
        ports = container.ports
        port_mapping = next(iter(ports.values()), [{}])[0].get('HostPort', None)
        if not port_mapping:
            internal_logger.error(f"No port mapping found for container {container.name}")
            return
        internal_logger.info(f"container: {container}")
        # Use the port in the URL
        url = f"http://{container.name}:{port_mapping}/rooms"
        # Initialize response object
        response = None

        # If there are rooms to add, send a POST request
        if rooms_to_add:
            payload = {"rooms": list(rooms_to_add)}
            internal_logger.info(f"URL to update controller's config: {url} with body: {payload}")
            response = requests.post(url, json=payload)
            response_json = response.json()
            if response_json.get("success"):
                internal_logger.info(f"Successfully added rooms {list(rooms_to_add)} to controller {container.name}")
            else:
                internal_logger.error(f"Failed to add rooms to controller {container.name}, status code: {response_json.get('success')}")

        # If there are rooms to remove, send a DELETE request
        if rooms_to_remove:
            rooms_str = ",".join(list(map(str, rooms_to_remove)))
            url = url+rooms_str
            internal_logger.info(f"URL to update controller's config: {url}.")
            response = requests.delete(url=url)
            response_json = response.json()
            if response_json.get("success"):
                internal_logger.info(f"Successfully removed rooms {list(rooms_to_remove)} from controller {container.name}")
            else:
                internal_logger.error(f"Failed to remove rooms from controller {container.name}, status code: {response_json.get('success')}")
        
        # If the request was successful, update the controller's room configuration
        if response and response.json().get("success"):
            self.controllers[container.name] = room_ids

        return response


    def restart_controller(self, container, room_ids):
        container.stop()
        container.remove()
        self.create_controller(room_ids)

    def remove_controller(self, controller):
        self.logger.info(f"Removing controller {controller}.")
        container = self.client.containers.get(controller)
        container.stop()
        container.remove()
        del self.controllers[controller]
        self.save_state()
        self.delete_service(controller)

    def construct_env_vars(self, room_ids):
        env_vars = {
            "CATALOG_URL": self.config.CATALOG_URL,
            "CU_PORT": str(self.get_next_available_port()),
            "PLANTS_ENDPOINT": self.config.PLANTS_ENDPOINT,
            "DEVICES_ENDPOINT": self.config.DEVICES_ENDPOINT,
            "GENERAL_ENDPOINT": self.config.GENERAL_ENDPOINT,
            "SERVICES_ENDPOINT": self.config.SERVICES_ENDPOINT,
            "ROOMS_ENDPOINT": self.config.ROOMS_ENDPOINT,
            "SERVICE_REGISTRY_NAME": self.config.SERVICE_REGISTRY_NAME,
            "WEATHER_FORECAST_URL": self.config.WEATHER_FORECAST_URL,
            "WEATHER_FORECAST_API_KEY": self.config.WEATHER_FORECAST_API_KEY,
            "MQTT_CLIENT_ID": f"smart_care_4ss_controller___{'_'.join(map(str, room_ids))}",
            "BASE_LOGGER": self.config.CU_LOGGER,
            "MQTT_LOGGER": self.config.MQTT_LOGGER,
            "TOPICS_UPDATE_INTERVAL": int(self.config.TOPICS_UPDATE_INTERVAL),
            "ROOM_IDS": ','.join(map(str, room_ids))  # Pass room IDs as a comma-separated string
        }
        return env_vars

    def get_next_available_port(self):
        """Find and return the next available port starting from default."""
        self.logger.info("Finding next available port...")
        used_ports = self.get_docker_bound_ports()  # Get all ports currently used by Docker
        self.logger.debug(f"Used ports from Docker: {used_ports}")
        port = self.config.CONTROLLER_BASE_PORT
        
        while port in used_ports or not self._is_port_available(port):
            self.logger.debug(f"Port {port} is not available, checking next.")
            port += 1
        
        self.logger.info(f"Next available port found: {port}")
        return port

    def get_docker_bound_ports(self):
        """Retrieve a set of ports bound by Docker containers."""
        self.logger.debug("Retrieving Docker-bound ports...")
        used_ports = set()
        try:
            for container in self.client.containers.list():
                ports = container.attrs['NetworkSettings']['Ports']
                for port_mappings in ports.values():
                    if port_mappings:
                        host_ports = [int(mapping['HostPort']) for mapping in port_mappings if 'HostPort' in mapping]
                        self.logger.debug(f"Container {container.name} is using ports: {host_ports}")
                        used_ports.update(host_ports)
        except Exception as e:
            self.logger.error(f"Error retrieving Docker-bound ports: {e}")
        
        self.logger.debug(f"Docker-bound ports retrieved: {used_ports}")
        return used_ports

    def _is_port_available(self, port):
        """Check if the given port is available on the local machine."""
        self.logger.info("Checking avaiability of ports.")
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(('0.0.0.0', port))  # Try to bind to the port
                self.logger.debug(f"Port {port} is available.")
                return True
            except socket.error:
                return False  # Port is in use

    def check_existing_controllers(self):
        """Check for any existing controllers on startup."""
        internal_logger = MyLogger.set_logger("CHECKER")
        internal_logger.info("Checking existing rooms ....")
        internal_logger.debug(f"Type of self.client: {type(self.client)}")
        internal_logger.debug(f"Type of self.client.containers: {type(self.client.containers)}")
        for container in self.client.containers.list():
            if container.name.startswith("controller_"):
                try:
                    # Extract the mapped port
                    ports = container.ports
                    port_mapping = next(iter(ports.values()), [{}])[0].get('HostPort', None)
                    if not port_mapping:
                        internal_logger.error(f"No port mapping found for container {container.name}")
                        continue

                    # Use the port in the URL
                    url = f"http://{container.name}:{port_mapping}/rooms"
                    response = requests.get(url)
                    response.raise_for_status()
                
                    room_data = response.json()
                    internal_logger.info(f"rooms response with url {url}, response: {room_data}")
                    room_ids = room_data.get("content", [])
                    
                    self.controllers[container.name] = room_ids
                    self.post_service(container.name, port_mapping)
                except requests.RequestException as e:
                    internal_logger.error(f"Failed to fetch rooms for container {container.name}: {e}")

    def run(self):
        # Check for existing controllers on startup
        self.check_existing_controllers()

        while True:
            self.update_rooms()
            print()
            self.logger.info(f"""controllers: {self.controllers}""")
            time.sleep(self.config.CONTROLLER_CONFIG_INTERVAL)  # Check every x seconds

    def cleanup(self):
        """Stop and remove all controllers before stopping the manager."""
        for controller in list(self.controllers.keys()):
            self.remove_controller(controller)
            self.delete_service(controller)
        self.save_state()

    def post_service(self, controller_name, controller_port):
        # Post the data to the registry system
        url = f"{self.catalog_address}/{self.config.SERVICES_ENDPOINT}"
        data = copy.deepcopy(self.service_specification)
        data.update({"name": controller_name, "host": f"http://{controller_name}:{controller_port}"})
        try:
            response = requests.post(url, json=data)
            response.raise_for_status()
            if response.json().get("success"): 
                self.logger.info("Service registered successfully.")
            else:
                self.logger.error("Error registring the service.")
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Error posting service data: {str(e)}")

    def delete_service(self, controller_name):
        url = f"{self.catalog_address}/{self.config.SERVICES_ENDPOINT}/{controller_name}"

        try:
            response = requests.delete(url)
            response.raise_for_status()
            if response.json().get("success"): 
                self.logger.debug("Service registeration removed.")
            else:
                self.logger.debug("Error removing registration of the service.")
        except requests.exceptions.RequestException as e:
            self.logger.debug(f"Error deleting service data: {str(e)}")


if __name__ == "__main__":
    manager = ControllerManager(Config)
    try:
        manager.run()
    except KeyboardInterrupt:
        manager.cleanup()
