import os
from pydantic import BaseModel
from pymongo import MongoClient
from pymongo.errors import PyMongoError
from datetime import datetime
from typing import List, Optional, Dict, Literal
from dotenv import load_dotenv
from registry import logger, to_camel_case, to_lower_camel_case, camel_to_snake

# Import environmental variables
load_dotenv()
MONGO_URL = os.getenv("MONGO_URL")
DB = os.getenv("DB")
PLANTS_COLLECTION = os.getenv("PLANTS_COLLECTION")
ROOMS_COLLECTION =  os.getenv("ROOMS_COLLECTION")
LOGGER_NAME = os.getenv("MODEL_LOGGER")

child_logger = logger.getChild(LOGGER_NAME)

# MongoDB client and collections
mongo_client = MongoClient(MONGO_URL)
db = mongo_client[DB]
plants_collection = db[PLANTS_COLLECTION]
rooms_collection = db[ROOMS_COLLECTION]




class Plant(BaseModel):
    plant_id: int
    room_id: int
    plant_kind: str
    plant_date: str
    device_inventory: list 
    last_updated: Optional[str] = None

    def __init__(self, **data):
        super().__init__(**data)
        self.device_inventory = []

    def model_dump_with_time(self) -> dict:
        self.last_updated = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return self.model_dump()



    def save_to_db(self) -> None:
        child_logger.debug(f"Entering save_to_db method for plant_id: {self.plant_id}")
        try:
            child_logger.info(f"""Starting update/insert for plant {self.plant_id} in room {self.room_id} ...""")

            # Check if the plant already exists in the database
            existing_plant = plants_collection.find_one({"plantId": self.plant_id})
            
    
            # Prepare the data to update, excluding device_inventory if the plant already exists
            updated_data = self.model_dump_with_time()

            if existing_plant:
                child_logger.info(f"Plant {self.plant_id} already exists in the database. Preparing to update.")
                # If the plant exists, we want to update only specific fields excluding device_inventory
                updated_data.pop("device_inventory", None)
            
            # Perform the update or insert (upsert) for the plant in the transaction
            plant_update_result = plants_collection.update_one(
                {"plantId": self.plant_id},
                {"$set": updated_data},
                upsert=True,
            )
            if plant_update_result.upserted_id:
                child_logger.info(f"Inserted new plant with ID {self.plant_id}.")
            else:
                child_logger.info(f"Updated existing plant with ID {self.plant_id}.")

            # Perform the upsert for the room (adding plant_id to plant_inventory)
            self.upsert_room()

        except PyMongoError as e:
            child_logger.error(f"Error occurred durring update/insert: {e}.")


        child_logger.debug(f"Exiting save_to_db method for plant_id: {self.plant_id}\n")



    def upsert_room(self) -> None:
        # Update the room by adding the plant_id to plantInventory if it doesn't exist yet
        room_update_result = rooms_collection.update_one(
            {"roomId": self.room_id},
            {"$addToSet": {"plantInventory": self.plant_id}},  # ensures no duplicates
            upsert=True,  # If the room doesn't exist, this will create the room with the plant_id
        )
        if room_update_result.upserted_id:
            child_logger.info(f"Created new room with ID {self.room_id} and added plant {self.plant_id}.")
        else:
            if room_update_result.raw_result.get("nModified", 0) > 0:
                child_logger.info(f"Plant {self.plant_id} is added to room {self.room_id}'s inventory.")
            else:
                child_logger.info(f"Plant {self.plant_id} is already in room {self.room_id}'s inventory.")
        
        

    def remove_from_db(self) -> None:
        child_logger.debug(f"Entering remove_from_db method for plant_id: {self.plant_id}")
        try:
            child_logger.info(f"Starting removal process for plant {self.plant_id} in room {self.room_id}...")

            # Remove the plant document from the database
            delete_result = plants_collection.delete_one({"plantId": self.plant_id})

            if delete_result.deleted_count > 0:
                child_logger.info(f"Successfully deleted plant {self.plant_id} from the database.")
            else:
                child_logger.warning(f"Plant {self.plant_id} does not exist in the database. No action taken.")

            # Perform the pull for the room (removing plant_id from plant_inventory)
            self.pull_room()

        except PyMongoError as e:
            # Handle database errors
            child_logger.error(f"Error occurred during plant removal: {e}.")

        child_logger.debug(f"Exiting remove_from_db method for plant_id: {self.plant_id}\n")



    def pull_room(self):
        # Remove the plant_id from the room's plantInventory
        room_update_result = rooms_collection.update_one(
            {"roomId": self.room_id},
            {"$pull": {"plantInventory": self.plant_id}},  # Remove plant_id from inventory
        )
        if room_update_result.modified_count > 0:
            child_logger.info(f"Removed plant {self.plant_id} from room {self.room_id}'s inventory.")
        else:
            child_logger.warning(f"Plant {self.plant_id} was not found in room {self.room_id}'s inventory.")
    
    
# class Device:
#     def __init__(self, device_id: int, device_type: Literal["sensor", "actuator"], 
#                  device_name: str, device_status: str, status_options: List[str],
#                  measure_types: List[str], available_services: List[Literal["MQTT", "REST"]],
#                  device_location: Dict["room_id", Optional["plant_Id"]], services_details: List[dict]):
        
#         self.device_id = f"{device_location['plantId']}_{device_id}"  # plantId + deviceId as unique ID
#         self.device_name = device_name
#         self.device_status = device_status
#         self.status_options = status_options
#         self.measure_types = measure_types
#         self.communication_methods = available_services
#         self.device_location = device_location
#         self.communication_details = services_details

if __name__ == "__main__":
    plant_dict = {
    "plantId": 201,
    "roomId": 2,
    "plantKind": "Lettuce",
    "plantDate": "2024-07-28",
    "deviceInventory": [10102, 10101, {}]
}
    # camel_case_data = {camel_to_snake(key):value for key, value in plant_dict.items()}
    
    plant1 = Plant(**{camel_to_snake(key):value for key, value in plant_dict.items()})
    # plant_dict =plant1.model_dump()
    # plant_dict_updated = plant1.model_dump_with_time()
    # child_logger.info(plant_dict)
    # child_logger.info(plant_dict_updated)
    plant1.save_to_db()
    # plant1.remove_from_db()