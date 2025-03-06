'''Environmental variables provider'''
import os
import json
import logging
from dotenv import load_dotenv

load_dotenv()

class Config:
    CATALOG_URL = os.getenv("CATALOG_URL")
    PLANTS_ENDPOINT = os.getenv("PLANTS_ENDPOINT")
    DEVICES_ENDPOINT = os.getenv("DEVICES_ENDPOINT")
    GENERAL_ENDPOINT = os.getenv("GENERAL_ENDPOINT")
    SERVICES_ENDPOINT = os.getenv("SERVICES_ENDPOINT")
    SERVICE_REGISTRY_NAME = os.getenv("SERVICE_REGISTRY_NAME")
    MQTT_CLIENT_ID = os.getenv("MQTT_CLIENT_ID")
    LOGGER_NAME = os.getenv("BASE_LOGGER")
    # MODEL_LOGGER = os.getenv("MODEL_LOGGER")
    GAP_BETWEEN_PUBLISHES = int(os.getenv("GAP_BETWEEN_PUBLISHES", 10))
    MQTT_LOGGER = os.getenv("MQTT_LOGGER")
    DATA_COLLECTION_INTERVAL = int(os.getenv("DATA_COLLECTION_INTERVAL", 3))  # seconds
    DATA_POINTS_FOR_AVERAGE = int(os.getenv("DATA_POINTS_FOR_AVERAGE", 10))
    CONFIG_FILE = os.getenv("CONFIG_FILE")
    REGISTERATION_INTERVAL = int(os.getenv("REGISTERATION_INTERVAL"))


class SensorConfig:
    MIN_TEMP = os.getenv("MIN_TEMP")
    MAX_TEMP = os.getenv("MAX_TEMP")
    MIN_LIGHT = os.getenv("MIN_LIGHT")
    MAX_LIGHT = os.getenv("MAX_LIGHT")
    MIN_PH = os.getenv("MIN_PH")
    MAX_PH = os.getenv("MAX_PH")
    MIN_SOIL_MOISTURE = os.getenv("MIN_SOIL_MOISTURE")
    MAX_SOIL_MOISTURE = os.getenv("MAX_SOIL_MOISTURE")
    SENSORS_TO_CLASS_DICT = json.loads(os.getenv("SENSORS_TO_CLASS_DICT", "{}"))


class MyLogger:
    logger = logging.getLogger(Config.LOGGER_NAME)
    logger.setLevel(logging.INFO)
    
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    ch.setFormatter(formatter)
    
    logger.addHandler(ch)

    @classmethod
    def get_main_loggger(cls):
        return cls.logger
    
    @classmethod
    def set_logger(cls, logger_name:str):
        return cls.logger.getChild(logger_name)
    