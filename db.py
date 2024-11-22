import os
from typing import Optional, List, Union
from pymongo import MongoClient
from pymongo.errors import PyMongoError
from dotenv import load_dotenv
from registry import logger


# Import environmental variables
load_dotenv()
MONGO_URL = os.getenv("MONGO_URL")
DB = os.getenv("DB")
GENERAL_COLLECTION = os.getenv("GENERAL_COLLECTION")
PLANTS_COLLECTION = os.getenv("PLANTS_COLLECTION")
ROOMS_COLLECTION =  os.getenv("ROOMS_COLLECTION")
DEVICES_COLLECTION = os.getenv("DEVICES_COLLECTION")
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


    def find_general(self, to_find: str = 'broker') -> dict:
        try:
            broker = self.general_collection.find_one({to_find: {"$exists": True}}, {"_id":0})
            if broker:
                return {"success": True, "content": broker}
            else:
                return {"success": False, "message": "No broker found"}
        
        except PyMongoError as e:
            self.child_logger.error(f"Error retrieving broker information: {str(e)}")
            return {"success": False, "message": str(e)}
        

    def find_plants(self, plant_id: Optional[int] = None, no_detail: bool = False) -> dict:
        # Excludes MongoDB id 
        projection = {"_id":0}
        # Shows only Ids
        if no_detail:
            projection["plantId"] = 1

        try:
            # List all plants
            if not plant_id:
                plants = list(self.plants_collection.find({"plantId": {"$exists": True}}, projection))
                return {"success": True, "content": plants}
            
            # An specific plant
            else:
                plant = self.plants_collection.find_one({"plantId": plant_id}, projection)
                if plant:
                    return {"success": True, "content": plant}
                else:
                    return {"success": False, "message": f"No plant found with ID {plant_id}"}
                
        except PyMongoError as e:
            self.child_logger.error(f"Error retrieving plants: {str(e)}")
            return {"success": False, "message": str(e)}
        

if __name__ == "__main__":
    db = Database()
    # print(db.find_general())
    print(db.find_plants(plant_id=101,no_detail=False))