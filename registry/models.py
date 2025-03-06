"""Pydantic models for validations and registration of plants and devices"""

from pydantic import BaseModel, ValidationError, ConfigDict
from pymongo import MongoClient
from pymongo.errors import PyMongoError
from datetime import datetime
from typing import List, Optional, Dict, Literal, Any
from config import Config, MyLogger
from utility import to_lower_camel_case

client = MongoClient(Config.MONGO_URL)
db = client[Config.DB]
plants_collection = db[Config.PLANTS_COLLECTION]
rooms_collection = db[Config.ROOMS_COLLECTION]
devices_collection = db[Config.DEVICES_COLLECTION]

model_logger = MyLogger.set_logger(logger_name=Config.MODEL_LOGGER)

class BaseModelWithTimestamp(BaseModel):
    last_updated: Optional[str] = None
    
    # Lets the model to accept both camel and snake case. 
    # Plus, providing option to dump in both ways
    model_config = ConfigDict(
        alias_generator=to_lower_camel_case, populate_by_name=True
    )
    def model_dump_with_time(self, by_alias: bool = True, exclude_unset: bool = True) -> dict:
        """Adds a timestamp to the model before dumping"""
        self.last_updated = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        # Change the difult dump to be camelCase
        return self.model_dump(by_alias=by_alias, exclude_unset=exclude_unset)


class BaseModelAlias(BaseModel):
    # Lets the model to accept both camel and snake case. 
    # Plus, providing option to dump in both ways
    model_config = ConfigDict(
        alias_generator=to_lower_camel_case, populate_by_name=True
    )
    def model_dump(self, by_alias: bool = True, exclude_unset: bool = True) -> Dict[str, Any]:
        return super().model_dump(by_alias=by_alias, exclude_unset=exclude_unset)



class DeviceLocation(BaseModelAlias):
    plant_id: Optional[int] = None
    room_id: int

class ServicesDetail(BaseModelAlias):
    service_type: Literal["MQTT", "REST"]
    topic: Optional[List[str]] = None
    service_ip: Optional[str] = None

class Device(BaseModelWithTimestamp):
    device_id: int
    device_type: Literal["sensor", "actuator"]
    device_name: str
    device_location: DeviceLocation
    device_status: str
    status_options: List[str]
    measure_types: List[str]
    available_services: List[Literal["MQTT", "REST"]]
    services_details: List[ServicesDetail]
    room_location: Optional[dict] = {}

    def save_to_db(self):
        model_logger.debug(f"Entering save_to_db method for device_id: {self.device_id}")
        print()
        try:
            model_logger.info(f"""Starting update/insert for device {self.device_id} in room {self.device_location.room_id} for plant {self.device_location.plant_id}...""")
            plant_id = self.device_location.plant_id
            room_id = self.device_location.room_id

            # Check if the device's plant exists in the database
            if plant_id:
                self._check_plant_exists(plant_id)
                
            # Check if the device's room exist in the database
            self._check_room_exists(room_id)
            self._upsert_device()

            if plant_id:
                self._update_plant_device_inventory(plant_id)
            self._update_room_device_inventory(room_id)

        except Exception as e:
            model_logger.error(f"Error saving device {self.device_id} to database: {str(e)}")
            return {"success": False, "message": f"Failed to registere the device: {str(e)}"}

        return {"success": True, "message": "Device registered successfully"}


    ### Helper functions
    def _check_plant_exists(self, plant_id: int):
        plant = plants_collection.find_one({"plantId": plant_id})
        if not plant:
            model_logger.error(f"Plant with id {plant_id} does not exist.")
            raise ValueError(f"Plant with id {plant_id} does not exist.")
    
    def _check_room_exists(self, room_id: int):
        room = rooms_collection.find_one({'roomId': room_id})
        if not room:
            model_logger.error(f"Room with id {room_id} does not exist.")
            raise ValueError(f"Room with id {room_id} does not exist.")
        
    def _upsert_device(self):
        device_data = self.model_dump_with_time()
        device_update_result = devices_collection.update_one(
            {'deviceId': self.device_id},
            {'$set': device_data},
            upsert=True
        )
        if device_update_result.upserted_id:
            model_logger.info(f"Inserted new device with ID {self.device_id}.")
        else:
            model_logger.info(f"Updated existing device with ID {self.device_id}.")

    # Plus, updates plant's last update too
    def _update_plant_device_inventory(self, plant_id: int):
        plants_collection.update_one(
            {'plantId': plant_id},
            {
                '$addToSet': {'deviceInventory': self.device_id},
                '$set': {'lastUpdated': self.last_updated}
            }
        )
        model_logger.info(f"Device id {self.device_id} upserted to plant {plant_id} device_inventory.")

    def _update_room_device_inventory(self, room_id: int):
        rooms_collection.update_one(
            {'roomId': room_id},
            {
                '$addToSet': {'deviceInventory': self.device_id},
                '$set': {'location': self.room_location}
            }
        )
        model_logger.info(f"Device id {self.device_id} upserted to room {room_id} device_inventory.\n")



class Plant(BaseModelWithTimestamp):
    plant_id: int
    room_id: int
    plant_kind: str
    plant_date: str
    device_inventory: list 

    def __init__(self, **data):
        super().__init__(**data)
        # Ensures device inventory remains empty as a plant is supposed to be presented solely
        self.device_inventory = []


    def save_to_db(self) -> dict:
        model_logger.debug(f"Entering save_to_db method for plant_id: {self.plant_id}")
        print()
        try:
            model_logger.info(f"""Starting update/insert for plant {self.plant_id} in room {self.room_id} ...""")

            # Check if the plant already exists in the database
            existing_plant = plants_collection.find_one({"plantId": self.plant_id})
    
            # Prepare the data to update, excluding device_inventory if the plant already exists
            updated_data = self.model_dump_with_time()

            if existing_plant:
                model_logger.info(f"Plant {self.plant_id} already exists in the database. Preparing to update.")
                # If the plant exists, we want to update only specific fields excluding device_inventory
                updated_data.pop("deviceInventory", None)
            
            # Perform the update or insert (upsert) for the plant in the transaction
            self._upsert_plant(updated_data)

            # Perform the upsert for the room (adding plant_id to plant_inventory)
            self._upsert_room()

        except PyMongoError as e:
            model_logger.error(f"Error occurred durring update/insert: {e}.")
            return {"success": False, "message": f"Failed to registere the plant: {str(e)}"}

        model_logger.debug(f"Exiting save_to_db method for plant_id: {self.plant_id}\n")
        return {"success": True, "message": "Plant registered successfully"}

    def _upsert_plant(self, updated_data: dict) -> None:
        plant_update_result = plants_collection.update_one(
            {"plantId": self.plant_id},
            {"$set": updated_data},
            upsert=True,
        )
        if plant_update_result.upserted_id:
            model_logger.info(f"Inserted new plant with ID {self.plant_id}.")
        else:
            model_logger.info(f"Updated existing plant with ID {self.plant_id}.")

    def _upsert_room(self) -> None:
        # Update the room by adding the plant_id to plantInventory if it doesn't exist yet
        room_update_result = rooms_collection.update_one(
            {"roomId": self.room_id},
            {   
                "$addToSet": {"plantInventory": self.plant_id},    # ensures no duplicates
                '$set': {'plantKind': self.plant_kind, 'plantDate': self.plant_date},
            },  
            upsert=True,  # If the room doesn't exist, this will create the room with the plant_id
        )
        if room_update_result.upserted_id:
            model_logger.info(f"Created new room with ID {self.room_id} and added plant {self.plant_id}.")
        else:
            if room_update_result.raw_result.get("nModified", 0) > 0:
                model_logger.info(f"Plant {self.plant_id} is added to room {self.room_id}'s inventory.")
            else:
                model_logger.info(f"Plant {self.plant_id} is already in room {self.room_id}'s inventory.")
        
        


### Param models
class DeviceParam(BaseModelAlias):
    measure_type: Optional[str]=None
    device_type: Optional[str]=None
    plant_id: Optional[int] = None
    room_id: Optional[int] = None
    no_detail: bool=False







if __name__ == "__main__":
    ## test plant
    def p():
        plant_dict = {
        "plantId": 201,
        "roomId": 2,
        "plantKind": "Lettuce",
        "plantDate": "2024-07-28",
        "deviceInventory": [],
        "lastUpdated": "2024-03-14 12:41:45"
    }       
        try:
            plant1 = Plant(**plant_dict)
            print(plant1.model_dump(by_alias=False))
            plant1.save_to_db()
        except ValidationError as e:
            print(e.json())

    ### test device
    def d():
        device_dict = {
            "deviceId": 20009,
            "deviceType": "sensor", 
            "deviceName": "tempsen",
            "deviceStatus": "ON",
            "statusOptions": [
                "DISABLE",
                "ON"
            ],
            "deviceLocation": {
                "plantId": 102,
                "roomId": 2
            },
            "measureTypes": [
                "temperature"
            ],
            "availableServices": [
                "MQTT"
            ],
            "servicesDetails": [
                {
                    "serviceType": "MQTT",
                    "topic": [
                        "SC4SS/sensor/1/000/temperature"
                    ]
                }
            ],
            "lastUpdate": "2024-03-14 12:41:45"
        }
        device1 = Device(**device_dict)
        model_logger.info(device1.model_dump_with_time())
        device1.save_to_db()
    
    def pa():
        params ={
            "device_type": "sensor",
            "deviceLocation": {
                "plantId": 102,
                "roomId": 2
            },
            "measureType": "temperature",
            "noDetail":"True"
        }
        param1 = DeviceParam(**params)
        model_logger.info(param1.model_dump())

    def dparam():
        dparams = {
            'device_type': 'sensor', 'room_id': 1
        }
        param = DeviceParam(**dparams)
        model_logger.info(param.model_dump())
    # plant1 = Plant(**camel_snake_handler_for_dict(plant_dict, from_type="camel"))
    # plant_dict =plant1.model_dump()
    # plant_dict_updated = plant1.model_dump_with_time()
    # child_logger.info(plant_dict)
    # child_logger.info(plant_dict_updated)
    
    # plant1.remove_from_db()
    # p()
    # d()
    # pa()
    # dparam()
