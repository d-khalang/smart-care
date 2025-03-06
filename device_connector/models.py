from pydantic import BaseModel, ValidationError, ConfigDict
from typing import List, Optional, Dict, Literal, Any
from utility import to_lower_camel_case


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

class Device(BaseModelAlias):
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


class Plant(BaseModelAlias):
    plant_id: int
    room_id: int
    plant_kind: str
    plant_date: str
    device_inventory: list 

    
