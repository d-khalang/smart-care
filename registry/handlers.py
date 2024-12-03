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
        
        return create_response(False, message="Invalid path.", status=404)


    def _handle_get_general(self, uri):
        if len(uri) < 2:
            return create_response(False, message="Choose your general subpath from 'broker' ...", status=400)
            
        if uri[1] == "broker":
            return self.db.find_general(to_find="broker")
        
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


    def _handle_get_users(normalized_uri, params):
        # TODO
        pass




    def handle_post(self, uri, params, data):
        normalized_uri = self._uri_normalizer(uri)

        if normalized_uri[0] == 'plants':
            return self._handle_post_plants(data)
        
        #TODO
        # elif normalized_uri[0] == 'plant_kinds':
        #     return self._handle_post_plant_kinds(normalized_uri, params)
        
        elif normalized_uri[0] == 'devices':
            return self._handle_post_devices(data)
        
        # elif normalized_uri[0] == 'users':
        #     return self._handle_post_users(normalized_uri, params)
        
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


    def handle_put(self, uri, params, data):
        normalized_uri = self._uri_normalizer(uri)

        if normalized_uri[0] == 'plants':
            return self._handle_put_plants(data)
        
        #TODO
        # elif normalized_uri[0] == 'plant_kinds':
        #     return self._handle_put_plant_kinds(normalized_uri, params)
        
        if normalized_uri[0] == 'devices':
            if len(normalized_uri) > 2:
                if normalized_uri[2] == "status":
                    return self._handle_put_device_status(normalized_uri, data)

            return self._handle_put_devices(data)
        
        # elif normalized_uri[0] == 'users':
        #     return self._handle_put_users(normalized_uri, params)
        
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


    def _handle_put_device_status(self, uri, data):
        try:
            device_id = int(uri[1])
        except ValueError as e:
            return create_response(False, message=f"Device ID must be a number, not '{uri[1]}': {str(e)}", status=400)
        
        status = data.get("status")
        print("status: ", status)
        if status:
            return self.db.update_device_status(device_id=device_id, status=status)
        return create_response(False, message=f"No status present in the body.", status=500)


    def handle_delete(self, uri, params):
        normalized_uri = self._uri_normalizer(uri)

        if normalized_uri[0] == 'plants':
            return self._handle_delete_plants(normalized_uri)
        
        #TODO
        # elif normalized_uri[0] == 'plant_kinds':
        #     return self._handle_delete_plant_kinds(normalized_uri, params)
        
        if normalized_uri[0] == 'devices':
            return self._handle_delete_devices(normalized_uri)
        
        # elif normalized_uri[0] == 'users':
        #     return self._handle_delete_users(normalized_uri, params)
        
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



