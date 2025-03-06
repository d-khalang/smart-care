'''Each handler extracts and validates parameters, ensuring they are correctly 
formatted before passing them to the database methods.'''

from utility import convert_to_bool, create_response
from models import DeviceParam, ValidationError, Plant, Device
from db.db import Database



class Handler:
    def __init__(self, database_agent: Database, logger) -> None:
        self.db = database_agent
        self.logger = logger

    def _uri_normalizer(self, uri):
        return [part.lower() for part in uri]
    
    def handle_get(self, uri, params):
        normalized_uri = self._uri_normalizer(uri)
        if normalized_uri[0] == 'general':
            return self._handle_get_general(normalized_uri)
        
        elif normalized_uri[0] == 'plants':
            return self._handle_get_plants(normalized_uri, params)
        
        elif normalized_uri[0] == 'plant_kinds':
            return self._handle_get_plant_kinds(normalized_uri, params)
        
        elif normalized_uri[0] == 'devices':
            return self._handle_get_devices(normalized_uri, params)
        
        elif normalized_uri[0] == 'users':
            return self._handle_get_users(normalized_uri, params)
        
        elif normalized_uri[0] == 'services':
            return self._handle_get_services(normalized_uri, params)
        
        elif normalized_uri[0] == 'rooms':
            return self._handle_get_rooms(normalized_uri, params)
        
        return create_response(False, message="Invalid path.", status=404)

    def _handle_get_rooms(self, uri, params):
        room_id = None
        if len(uri) > 1:
            try:
                room_id = int(uri[1])
            except ValueError as e:
                return create_response(False, message=f"Room ID must be a number, not '{uri[1]}': {str(e)}", status=400)
                
        return self.db.find_rooms(room_id=room_id)    

    def _handle_get_services(self, uri, params):
        service_name = None
        if len(uri) > 1:
            service_name = uri[1]
        
        return self.db.find_services(service_name)

    def _handle_get_general(self, uri):
        if len(uri) < 2:
            return create_response(False, message="Choose your general subpath from 'broker' ...", status=400)
            
        if uri[1] == "broker":
            return self.db.find_general(to_find="broker")
        elif uri[1] == "template":
            return self.db.find_general(to_find="template")
        elif uri[1] == "llm":
            return self.db.find_general(to_find="llm")
        elif uri[1] == "weather_forecast":
            return self.db.find_general(to_find="weatherForecast")
        elif uri[1] == "telegram_bot":
            return self.db.find_general(to_find="telegramBot")
        
        return create_response(False, message="Invalid general subpath.", status=404)
    
    def _handle_get_plants(self, uri, params):    
        plant_id = None
        no_detail = convert_to_bool(params.get("no_detail"))
            
        if len(uri) > 1:
            try:
                plant_id = int(uri[1])
            except ValueError as e:
                return create_response(False, message=f"Plant ID must be a number, not '{uri[1]}': {str(e)}", status=400)
                
        return self.db.find_plants(plant_id=plant_id, no_detail=no_detail)    
    
    def _handle_get_plant_kinds(self, uri, params):    
        kind_name = uri[1] if len(uri) > 1 else None
        no_detail = convert_to_bool(params.get("no_detail"))
        return self.db.find_plant_kinds(kind_name=kind_name, no_detail=no_detail)

    def _handle_get_devices(self, uri, params):
        device_id = None
        if len(uri) > 1:
            try:
                device_id = int(uri[1])
            except ValueError as e:
                return create_response(False, message=f"Device ID must be a number, not '{uri[1]}': {str(e)}", status=400)
            
        try:
            device_params = DeviceParam(**params)
        except ValidationError as e:
            return create_response(False, message=f"Invalid parameters: {e}", status=400)
        return self.db.find_devices(device_params, device_id=device_id)

    def _handle_get_users(self, normalized_uri, params):
        plant_id = params.get("plant_id")
        if plant_id:
            try:
                plant_id = int(plant_id)
            except ValueError as e:
                return create_response(False, message=f"Plant ID must be a changeable to integer, not '{plant_id}': {str(e)}", status=400)
        
        return self.db.find_users(params)




    def handle_post(self, uri, params, data):
        normalized_uri = self._uri_normalizer(uri)

        if normalized_uri[0] == 'plants':
            return self._handle_post_plants(data)
        
        elif normalized_uri[0] == 'devices':
            return self._handle_post_devices(data)
        
        elif normalized_uri[0] == 'users':
            return self._handle_post_users(data)

        elif normalized_uri[0] == 'services':
            return self._handle_post_service(data)
        
        return create_response(False, message="Invalid path.", status=404)

    
    def _handle_post_plants(self, data):
        try:
            plant = Plant(**data)
        except ValidationError as e:
            return create_response(False, message=f"Plant validation failed: {str(e)}", status=400)
        
        plant_presence_response = self.db.find_plants(plant.plant_id, no_detail=True)
        if plant_presence_response.get('status') == 200:
            self.logger.error(f"POST request for the plant {plant.plant_id} that already exists.")
            return create_response(False, message=f"Plant with id {plant.plant_id} already exists. Use PUT to update the resource.", status=409)
        
        response = plant.save_to_db()
        response.update({"status":201}) if response.get("success") else response
        return response
    
    def _handle_post_devices(self, data):
        try:
            device = Device(**data)
        except ValidationError as e:
            return create_response(False, message=f"Device validation failed: {str(e)}", status=400)
        
        device_presence_response = self.db.find_devices(device_id=device.device_id)
        if device_presence_response.get('status') == 200:
            self.logger.error(f"POST request for the device {device.device_id} that already exists.")
            return create_response(False, message=f"Device with id {device.device_id} already exists. Use PUT to update the resource.", status=409)
        
        response = device.save_to_db()
        response.update({"status":201}) if response.get("success") else response
        return response

    def _handle_post_users(self, data):
        if 'userName' not in data or 'plantId' not in data or 'password' not in data:
            return create_response(False, message="Invalid input. 'plantId', 'userName' and 'password' are neccessary.", status=400)
        try:
            data["plantId"] = int(data["plantId"])
        except ValueError as e:
            return create_response(False, message=f"Plant ID must be a changeable to integer, not {data['plantId']}: {str(e)}", status=400)
        
        insertion_response = self.db.add_user(data)
        return insertion_response

    def _handle_post_service(self, data):
        if 'name' not in data or 'endpoints' not in data or 'host' not in data:
            return create_response(False, message="Invalid input.", status=400)
        service = self.db.add_service(data)
        return service
    


    def handle_put(self, uri, params, data):
        normalized_uri = self._uri_normalizer(uri)

        if normalized_uri[0] == 'plants':
            return self._handle_put_plants(data)
        
        elif normalized_uri[0] == 'devices':
            if len(normalized_uri) > 2:
                if normalized_uri[2] == "status":
                    return self._handle_put_device_status(normalized_uri, data)
            return self._handle_put_devices(data)
        
        elif normalized_uri[0] == 'users':
            return self._handle_put_users(data)

        elif normalized_uri[0] == 'services':
            return self._handle_put_service(normalized_uri, data)
        
        return create_response(False, message="Invalid path.", status=404)
        
    def _handle_put_plants(self, data):
        try:
            plant = Plant(**data)
        except ValidationError as e:
            return create_response(False, message=f"Plant validation failed: {str(e)}", status=400)
        
        self.logger.info(f"PUT request for the plant {plant.plant_id}.")
        plant_presence_response = self.db.find_plants(plant.plant_id, no_detail=True)
        response = plant.save_to_db()
        if plant_presence_response.get('status') == 200:
            response.update({"status":200}) if response.get("success") else response
        if plant_presence_response.get('status') == 404:
            response.update({"status":201}) if response.get("success") else response
        return response
            
    def _handle_put_devices(self, data):
        try:
            device = Device(**data)
        except ValidationError as e:
            return create_response(False, message=f"Device validation failed: {str(e)}", status=400)
        
        self.logger.info(f"PUT request for the device {device.device_id}.")
        device_presence_response = self.db.find_devices(device_id=device.device_id)
        response = device.save_to_db()
        if device_presence_response.get('status') == 200:
            response.update({"status":200}) if response.get("success") else response
        if device_presence_response.get('status') == 404:
            response.update({"status":201}) if response.get("success") else response
        return response

    def _handle_put_users(self, data):
        if 'userName' not in data or 'plantId' not in data or 'password' not in data:
            return create_response(False, message="Invalid input. 'plantId', 'userName' and 'password' are neccessary.", status=400)
        try:
            data["plantId"] = int(data["plantId"])
        except ValueError as e:
            return create_response(False, message=f"Plant ID must be a changeable to integer, not {data['plantId']}: {str(e)}", status=400)
        
        insertion_response = self.db.add_user(data)
        return insertion_response

    def _handle_put_device_status(self, uri, data):
        try:
            device_id = int(uri[1])
        except ValueError as e:
            return create_response(False, message=f"Device ID must be a number, not '{uri[1]}': {str(e)}", status=400)
        
        status = data.get("status")
        self.logger.info(f"status: {status}")
        if status:
            return self.db.update_device_status(device_id=device_id, status=status)
        return create_response(False, message=f"No status present in the body.", status=500)

    def _handle_put_service(self, data):
            if 'name' not in data or 'endpoints' not in data or 'host' not in data:
                return create_response(False, message="Invalid input.", status=400)
            service = self.db.add_service(data)
            return service


    def handle_delete(self, uri, params):
        normalized_uri = self._uri_normalizer(uri)

        if normalized_uri[0] == 'plants':
            return self._handle_delete_plants(normalized_uri)
        
        elif normalized_uri[0] == 'devices':
            return self._handle_delete_devices(normalized_uri)
        
        elif normalized_uri[0] == 'users':
            return self._handle_delete_users(normalized_uri, params)
        
        elif normalized_uri[0] == 'services':
            return self._handle_delete_service(normalized_uri)
        
        return create_response(False, message="Invalid path.", status=404)

    def _handle_delete_plants(self, uri):
        if len(uri) < 2:
            return create_response(False, message="Invalid path, Insert a plant_id.", status=404)

        try:
            plant_id = int(uri[1])
        except ValueError as e:
            return create_response(False, message=f"Plant ID must be a number, not '{uri[1]}': {str(e)}", status=400)
        return self.db.delete_plant(plant_id=plant_id)

    def _handle_delete_devices(self, uri):
        if len(uri) < 2:
            return create_response(False, message="Invalid path, Insert a device_id.", status=404)
        
        try:
            device_id = int(uri[1])
        except ValueError as e:
            return create_response(False, message=f"Device ID must be a number, not '{uri[1]}': {str(e)}", status=400)
        return self.db.delete_device(device_id=device_id)

    def _handle_delete_users(self, normalized_uri, params):
        plant_id = params.get("plant_id")
        telegram_id = params.get("telegram_id")
        if not plant_id:
            return create_response(False, message="No plant ID inserted.", status=400)
        return self.db.delete_plant_from_user_inventory(int(plant_id), int(telegram_id))

    def _handle_delete_service(self, uri):
        if len(uri) < 2:
            return create_response(False, message="Service name not specified.", status=400)
        service_name = uri[1]
        return self.db.delete_service(service_name)


