import os
from typing import Optional, List
from pymongo import MongoClient
from pymongo.errors import PyMongoError
from config import Config
from utility import create_response
from models import DeviceParam


class Database:
    def __init__(self, logger) -> None:
        # Logger configuartion (child from the main logger)
        self.child_logger = logger
        
        # Initialize the MongoDB client and database
        self.client = MongoClient(Config.MONGO_URL)
        db = self.client[Config.DB]
        self.general_collection = db[Config.GENERAL_COLLECTION]
        self.services_collection = db[Config.SERVICES_COLLECTION]
        self.plants_collection = db[Config.PLANTS_COLLECTION]
        self.rooms_collection = db[Config.ROOMS_COLLECTION]
        self.devices_collection = db[Config.DEVICES_COLLECTION]
        self.plant_kinds_collection = db[Config.PLANT_KINDS_COLLECTION]
        # Excludes MongoDB id
        self.defult_projection = {"_id":0}

    def _create_case_insensitive_query(self, variable):
        return {"$regex": f"^{variable}$", "$options": "i"}

    def find_general(self, to_find: str = 'broker') -> dict:
        try:
            item = self.general_collection.find_one({to_find: {"$exists": True}}, {"_id":0})
            if item:
                return create_response(True, content=item, status=200)
            else:
                return create_response(False, message=f"No {to_find} found", status=404)
        
        except PyMongoError as e:
            self.child_logger.error(f"Error retrieving {to_find} information: {str(e)}")
            return create_response(False, message= str(e), status=500)
        

    def find_services(self, service_name: str=None):
        projection = self.defult_projection.copy()
        
        try:
            if not service_name:
                services = list(self.services_collection.find({}))
                return create_response(True, content=services, status=200)
            
            service = self.services_collection.find_one({'name': service_name}, projection)
            return create_response(True, content=[service], status=200)
            
        except PyMongoError as e:
            self.child_logger.error(f"Error retrieving services: {str(e)}")
            return create_response(False, message=str(e), status=500)


    def find_plants(self, plant_id: Optional[int] = None, no_detail: bool = False) -> dict:
        projection = self.defult_projection.copy()
        # Shows only Ids
        if no_detail:
            projection["plantId"] = 1

        try:
            # List all plants
            if not plant_id:
                plants = list(self.plants_collection.find({"plantId": {"$exists": True}}, projection))
                return create_response(True, content=plants, status=200)
            
            # An specific plant
            else:
                plant = self.plants_collection.find_one({"plantId": plant_id}, projection)
                if plant:
                    return create_response(True, content=[plant], status=200)
                else:
                    return create_response(False, message=f"No plant found with ID {plant_id}", status=404)
                
        except PyMongoError as e:
            self.child_logger.error(f"Error retrieving plants: {str(e)}")
            return create_response(False, message=str(e), status=500)
    

    def find_plant_kinds(self, kind_name: Optional[str] = None, no_detail: bool = False) -> dict:
        projection = self.defult_projection.copy()
        # Shows only names
        if no_detail:
            projection["plantKind"] = 1

        try:
            # List all plant kinds (case-insensitive)
            if not kind_name: 
                kinds = list(self.plant_kinds_collection.find({"plantKind": {"$exists": True}}, projection))
                return create_response(True, content=kinds, status=200)
            
            # An specific plant kind
            else:
                kind = self.plant_kinds_collection.find_one({"plantKind": self._create_case_insensitive_query(kind_name)}, projection)
                if kind:
                    return create_response(True, content=[kind], status=200)
                else:
                    return create_response(False, message=f"No kind found with name {kind_name}", status=404)
                
        except PyMongoError as e:
            self.child_logger.error(f"Error retrieving plant kinds: {str(e)}")
            return create_response(False, message=str(e), status=500)
        

    def find_devices(self, device_params: Optional[DeviceParam]=None, device_id: Optional[int]=None) -> dict:
        query = {}
        projection = self.defult_projection.copy()
        if device_id:
            query['deviceId'] = device_id
        # Shows only Ids
        if device_params:
            if device_params.no_detail:
                projection["deviceId"] = 1
            if device_params.room_id:
                query['deviceLocation.roomId'] = device_params.room_id
            if device_params.plant_id:
                query['deviceLocation.plantId'] = device_params.plant_id
            if device_params.measureType:
                query['measureTypes'] = self._create_case_insensitive_query(device_params.measureType)
            if device_params.device_type:
                query['deviceType'] = device_params.device_type

        try:
            if not device_id:
                devices = list(self.devices_collection.find(query, projection))
                return create_response(True, content=devices, status=200)
            # An specific device
            else:
                device = self.devices_collection.find_one(query, projection)
                if device:
                    return create_response(True, content=[device], status=200)
                else:
                    return create_response(False, message=f"No device found with ID {device_id}", status=404)
        except PyMongoError as e:
            self.child_logger.error(f"Error retrieving devices: {str(e)}")
            return create_response(False, message=str(e), status=500)


    def update_device_status(self, device_id: int, status: str) -> dict:
        try:
            device = self.devices_collection.find_one({'deviceId': device_id})

            if not device:
                return create_response(False, message=f"Device with ID {device_id} not found.", status=404)

            # Check if the new status is in statusOptions
            if status not in device.get('statusOptions', []):
                return create_response(False, message=f"Status {status} is not a valid status for device {device_id}.", status=400)

            # Proceed to update the status
            device_update_result = self.devices_collection.update_one(
                {'deviceId': device_id},
                {'$set': {"deviceStatus": status}},
            )

            if device_update_result.modified_count:
                self.child_logger.info(f"Device {device_id}'s status updated to {status}.")
                return create_response(True, message=f"Device {device_id}'s status updated to {status}.", status=200)
            else:
                return create_response(False, message=f"Device {device_id}'s status already the same as {status}.", status=200)

        except PyMongoError as e:
            self.child_logger.error(f"Error updating device status: {str(e)}")
            return create_response(False, message=str(e), status=500)

    def find_users(self):
        # TODO
        pass


    def delete_plant(self, plant_id: int) -> dict:
        try:
            # First, delete the plant from the plants collection
            result = self.plants_collection.delete_one({"plantId": plant_id})
            if result.deleted_count == 0:
                return create_response(False, message=f"No plant found with ID {plant_id}", status=404)
            print()
            self.child_logger.info(f"Plant with ID {plant_id} deleted from plants collection.")

            # Then, remove the plant from the 'plantInventory' in the associated room(s)
            room_update_result = self.rooms_collection.update_many(
                {"plantInventory": plant_id}, 
                {"$pull": {"plantInventory": plant_id}}
            )
            # Check if any rooms were affected by the pull operation
            if room_update_result.modified_count > 0:
                self.child_logger.info(f"Pulled plant ID {plant_id} from room(s) plantInventory. "
                                    f"{room_update_result.modified_count} room(s) affected.")
            else:
                self.child_logger.info(f"No room(s) found with plant ID {plant_id} in plantInventory.")

            # Return a success message if the plant was deleted successfully
            return create_response(True, message=f"Plant with ID {plant_id} deleted successfully", status=200)

        except PyMongoError as e:
            self.child_logger.error(f"Error deleting plant {plant_id}: {str(e)}")
            return create_response(False, message=str(e), status=500)


    def delete_device(self, device_id: int) -> dict:
        try:
            # Delete the device from the devices collection
            result = self.devices_collection.delete_one({"deviceId": device_id})
            if result.deleted_count == 0:
                return create_response(False, message=f"No device found with ID {device_id}", status=404)
            print()           
            self.child_logger.info(f"Device with ID {device_id} deleted from devices collection.")

            # Remove the device from the associated plant's deviceInventory
            # Find the plant associated with the device and remove it from its deviceInventory
            plant_update_result = self.plants_collection.update_many(
                {"deviceInventory": device_id},
                {"$pull": {"deviceInventory": device_id}}
            )
            # Check if any plants were affected by the pull operation
            if plant_update_result.modified_count > 0:
                self.child_logger.info(f"Pulled device ID {device_id} from plant(s) deviceInventory. "
                                    f"{plant_update_result.modified_count} plant(s) affected.")
            else:
                self.child_logger.info(f"No plant(s) found with device ID {device_id} in deviceInventory.")

            # Remove the device from the associated room's deviceInventory
            # Find the room associated with the device and remove it from its deviceInventory
            room_update_result = self.rooms_collection.update_many(
                {"deviceInventory": device_id},
                {"$pull": {"deviceInventory": device_id}}
            )
            # Check if any rooms were affected by the pull operation
            if room_update_result.modified_count > 0:
                self.child_logger.info(f"Pulled device ID {device_id} from room(s) deviceInventory. "
                                    f"{room_update_result.modified_count} room(s) affected.")
            else:
                self.child_logger.info(f"No room(s) found with device ID {device_id} in deviceInventory.")

            # Return a success message if the device was deleted successfully
            return create_response(True, message=f"Device with ID {device_id} deleted successfully", status=200)

        except PyMongoError as e:
            self.child_logger.error(f"Error deleting device {device_id}: {str(e)}")
            return create_response(False, message=str(e), status=500)


    def remove_empty_rooms(self):
        # Check if any room has an empty 'plantInventory' and 'deviceInventory', and delete those rooms
        rooms_to_delete = self.rooms_collection.find({
            "$and": [
                {"plantInventory": {"$size": 0}},  # No plants in the inventory
                {"deviceInventory": {"$size": 0}}  # No devices in the inventory
            ]
        })
        for room in rooms_to_delete:
            self.rooms_collection.delete_one({"roomId": room["roomId"]})


if __name__ == "__main__":
    db = Database("logger")
    # print(db.find_general())
    # print(db.find_plants(plant_id=101,no_detail=False))
    # print(db.find_plant_kinds(kind_name="Lettuce",no_detail=False))
    # print(db.find_devices(DeviceParam(**{"no_detail":True, "roomId":1})))
    # print(db.find_plants(plant_id=108))
    # print(db.delete_plant(205))
    db.update_device_status(10011, 'in')