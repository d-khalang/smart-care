import os
import copy
from typing import Optional, List, Union
from pymongo import MongoClient
from pymongo.errors import PyMongoError
from dotenv import load_dotenv
from registry import logger
from utility import create_response
from models import DeviceParam



# Import environmental variables
load_dotenv()
MONGO_URL = os.getenv("MONGO_URL")
DB = os.getenv("DB")
GENERAL_COLLECTION = os.getenv("GENERAL_COLLECTION")
PLANTS_COLLECTION = os.getenv("PLANTS_COLLECTION")
ROOMS_COLLECTION =  os.getenv("ROOMS_COLLECTION")
DEVICES_COLLECTION = os.getenv("DEVICES_COLLECTION")
PLANT_KINDS_COLLECTION = os.getenv("PLANT_KINDS_COLLECTION")
LOGGER_NAME = os.getenv("DB_LOGGER")




class Database:
    def __init__(self) -> None:
        # Logger configuartion (child from the main logger)
        self.child_logger = logger.getChild(LOGGER_NAME)
        
        # Initialize the MongoDB client and database
        self.client = MongoClient(MONGO_URL)
        db = self.client[DB]
        self.general_collection = db[GENERAL_COLLECTION]
        self.plants_collection = db[PLANTS_COLLECTION]
        self.rooms_collection = db[ROOMS_COLLECTION]
        self.devices_collection = db[DEVICES_COLLECTION]
        self.plant_kinds_collection = db[PLANT_KINDS_COLLECTION]
        # Excludes MongoDB id
        self.defult_projection = {"_id":0}

    def _create_case_insensitive_query(self, variable):
        return {"$regex": f"^{variable}$", "$options": "i"}

    def find_general(self, to_find: str = 'broker') -> dict:
        try:
            broker = self.general_collection.find_one({to_find: {"$exists": True}}, {"_id":0})
            if broker:
                return create_response(True, content= broker, status=200)
            else:
                return create_response(False, message= "No broker found", status=404)
        
        except PyMongoError as e:
            self.child_logger.error(f"Error retrieving broker information: {str(e)}")
            return create_response(False, message= str(e), status=500)
        

    def find_plants(self, plant_id: Optional[int] = None, no_detail: bool = False) -> dict:
        projection = self.defult_projection.copy()
        # Shows only Ids
        if no_detail:
            projection["plantId"] = 1

        try:
            # List all plants
            if not plant_id:
                plants = list(self.plants_collection.find({"plantId": {"$exists": True}}, projection))
                return create_response(True, content= plants, status=200)
            
            # An specific plant
            else:
                plant = self.plants_collection.find_one({"plantId": plant_id}, projection)
                if plant:
                    return create_response(True, content= plant, status=200)
                else:
                    return create_response(False, message= f"No plant found with ID {plant_id}", status=404)
                
        except PyMongoError as e:
            self.child_logger.error(f"Error retrieving plants: {str(e)}")
            return create_response(False, message= str(e), status=500)
    

    def find_plant_kinds(self, kind_name: Optional[str] = None, no_detail: bool = False) -> dict:
        projection = self.defult_projection.copy()
        # Shows only names
        if no_detail:
            projection["plantKind"] = 1

        try:
            # List all plant kinds (case-insensitive)
            if not kind_name: 
                kinds = list(self.plant_kinds_collection.find({"plantKind": {"$exists": True}}, projection))
                return create_response(True, content= kinds, status=200)
            
            # An specific plant kind
            else:
                kind = self.plant_kinds_collection.find_one({"plantKind": self._create_case_insensitive_query(kind_name)}, projection)
                if kind:
                    return create_response(True, content= kind, status=200)
                else:
                    return create_response(False, message= f"No kind found with name {kind_name}", status=404)
                
        except PyMongoError as e:
            self.child_logger.error(f"Error retrieving plant kinds: {str(e)}")
            return create_response(False, message= str(e), status=500)
        

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
                    return create_response(True, content= device, status=200)
                else:
                    return create_response(False, message= f"No device found with ID {device_id}", status=404)
        except PyMongoError as e:
            self.child_logger.error(f"Error retrieving devices: {str(e)}")
            return create_response(False, message=str(e), status=500)


    def find_users(self):
        # TODO
        pass




if __name__ == "__main__":
    db = Database()
    # print(db.find_general())
    # print(db.find_plants(plant_id=101,no_detail=False))
    # print(db.find_plant_kinds(kind_name="Lettuce",no_detail=False))
    # print(db.find_devices(DeviceParam(**{"no_detail":True, "roomId":1})))
    print(db.find_plants(plant_id=108))