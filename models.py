import os
from typing import List, Optional, Dict
from dotenv import load_dotenv

# Import environmental variables
load_dotenv()
MONGO_URL = os.getenv("MONGO_URL")
DB = os.getenv("DB")
PLANTS_COLLECTION = os.getenv("PLANTS_COLLECTION")
LOGGER_NAME = os.getenv("MODEL_LOGGER")


class Plant:
    def __init__(self, plant_id: int, room_id: int, plant_kind: str, plant_date: str, device_inventory: list = []):
        self.plant_id = plant_id
        self.room_id = room_id
        self.plant_kind = plant_kind
        self.plant_date = plant_date
        self.device_inventory = device_inventory

    def add_device(self, device:Device) -> None:
        self.device_inventory.append(device)

    def save_to_db(self):
        PLANTS_COLLECTION.update_one(
            {"plantId": self.plant_id},
            {"$set": self.to_dict()},
            upsert=True
        )
