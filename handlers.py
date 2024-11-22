from db import Database
from utility import convert_to_bool, create_response

class Handlers:
    def __init__(self) -> None:
        self.db = Database()
    
    def handle_get(self, uri, params):
        normalized_uri = [part.lower() for part in uri]
        if normalized_uri[0] == 'general':
            return self._handle_general(normalized_uri)
        
        elif normalized_uri[0] == 'plants':
            return self._handle_plants(normalized_uri, params)
        
        return create_response(False, message="Invalid path.")

    def _handle_general(self, uri):
        if len(uri) < 2:
            return create_response(False, message="Choose your general subpath from 'broker' ...")
            
        if uri[1] == "broker":
            return self.db.find_general(to_find="broker")
        
        return create_response(False, message="Invalid general subpath.")
    

    def _handle_plants(self, uri, params):    
        plant_id = None
        no_detail = convert_to_bool(params.get("no_detail"))
            
        if len(uri) > 1:
            try:
                plant_id = int(uri[1])
            except ValueError as e:
                return create_response(False, message=f"Plant ID must be a number, not '{uri[1]}': {str(e)}")
                
        return self.db.find_plants(plant_id=plant_id, no_detail=no_detail)    
        
            


    def handle_post(uri, params, data):
        # Add your logic to handle POST request
        result = Database.insert_data(uri, data)
        return result


    def handle_put(uri, params, data):
        # Add your logic to handle PUT request
        result = Database.update_data(uri, data)
        return result


    def handle_delete(uri, params):
        # Add your logic to handle DELETE request
        result = Database.delete_data(uri)
        return result

