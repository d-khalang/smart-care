import random
from config import SensorConfig
from utility import case_insensitive

class TempSen():
    def __init__(self):
        self.MIN_TEMP = int(SensorConfig.MIN_TEMP)
        self.MAX_TEMP = int(SensorConfig.MAX_TEMP)
        self.unit = "Cel"
        self.senKind = "temperature"
        self.last_value = random.randint(self.MIN_TEMP, self.MAX_TEMP)  # Initialize with a first value

    def generate_data(self):
        # Gradually change the temperature based on the last value
        delta = random.randint(-2, 2)  # Define a small range for the change (can be adjusted)
        new_value = self.last_value + delta
        
        # Make sure the new value stays within the allowed range
        new_value = max(self.MIN_TEMP, min(self.MAX_TEMP, new_value))
        
        # Update the last value for the next reading
        self.last_value = new_value
        
        return new_value
    
    def get_info(self):
        return self.senKind, self.unit


class LightSen():
    def __init__(self):
        self.MIN_LIGHT = int(SensorConfig.MIN_LIGHT)
        self.MAX_LIGHT = int(SensorConfig.MAX_LIGHT)
        self.unit = "μmol/m²/s"
        self.senKind = "light"
        self.last_value = random.randint(self.MIN_LIGHT, self.MAX_LIGHT)  # Initialize with a first value

    def generate_data(self):
        # Gradually change the light intensity based on the last value
        delta = random.randint(-5, 5)  # Small random change in the range
        new_value = self.last_value + delta
        
        # Ensure the new value is within the valid range
        new_value = max(self.MIN_LIGHT, min(self.MAX_LIGHT, new_value))
        
        # Update the last value
        self.last_value = new_value
        
        return new_value
    
    def get_info(self):
        return self.senKind, self.unit


class PHSen():
    def __init__(self):
        self.MIN_PH = float(SensorConfig.MIN_PH)
        self.MAX_PH = float(SensorConfig.MAX_PH)
        self.unit = "Range"
        self.senKind = "PH"
        self.last_value = round(random.uniform(self.MIN_PH, self.MAX_PH), 2)  # Initialize with a first value

    def generate_data(self):
        # Gradually change the pH value based on the last value
        delta = round(random.uniform(-0.05, 0.05), 3)  # Small fluctuation
        new_value = self.last_value + delta
        
        # Ensure the new value stays within the allowed pH range
        new_value = round(max(self.MIN_PH, min(self.MAX_PH, new_value)), 2)
        
        # Update the last value
        self.last_value = round(new_value, 2)
        new_value = float(f"{new_value:.2f}")
        
        return new_value
    
    def get_info(self):
        return self.senKind, self.unit


class SoilMoistureSen():
    def __init__(self):
        self.MIN_DISTANCE = int(SensorConfig.MIN_SOIL_MOISTURE)
        self.MAX_DISTANCE = int(SensorConfig.MAX_SOIL_MOISTURE)
        self.unit = "percentage"
        self.senKind = "soilMoisture"
        self.last_value = random.randint(self.MIN_DISTANCE, self.MAX_DISTANCE)  # Initialize with a first value

    def generate_data(self):
        # Gradually change the soil moisture value based on the last value
        delta = random.randint(-3, 3)  # Small change in moisture percentage
        new_value = self.last_value + delta
        
        # Ensure the new value stays within the valid range
        new_value = max(self.MIN_DISTANCE, min(self.MAX_DISTANCE, new_value))
        
        # Update the last value
        self.last_value = new_value
        
        return new_value
        
    def get_info(self):
        return self.senKind, self.unit



def create_sensor(sensor_type):
    # Normalize to lowercase
    sensor_type = case_insensitive(sensor_type)  
    sensor_to_class_dict = case_insensitive(SensorConfig.SENSORS_TO_CLASS_DICT)

    if not sensor_to_class_dict:
        raise ValueError(f"No recongnized key in '{SensorConfig.SENSORS_TO_CLASS_DICT}'")
    
    class_name = sensor_to_class_dict.get(sensor_type)
    if not class_name:
        raise ValueError(f"No class found for sensor type '{sensor_type}'")
    
    sensor_class = globals()[class_name]
    if not sensor_class:
        raise ValueError(f"No class definition found for '{class_name}'")

    return sensor_class()

if __name__ == "__main__":
    # import time
    # tempsen, lightsen, phsen, soilsen = TempSen(), LightSen(), PHSen(), SoilMoistureSen()
    # senList = [tempsen, lightsen, phsen, soilsen]

    
        
    # for sen in senList:
    #     if sen == phsen:
    #         print(sen.get_info())
    #         for i in range(15):
    #             print(sen.generate_data())
    #             time.sleep(1)

    sensor_type = "Temperature"
    sensor = create_sensor(sensor_type)
    print(sensor.get_info())
    print(sensor.generate_data())