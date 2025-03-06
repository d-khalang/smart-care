'''Environmental variables provider'''
import os
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
    SERVICE_REGISTRY_FILE = os.getenv("SERVICE_REGISTRY_FILE")
    AVAILABLE_MEASURE_TYPES = os.getenv("AVAILABLE_MEASURE_TYPES", "").split(",")
    MQTT_LOGGER = os.getenv("MQTT_LOGGER")
    UPDATE_INTERVAL = int(os.getenv("TOPICS_UPDATE_INTERVAL", 600))  # seconds
    # CU_PORT = int(os.getenv("CU_PORT"))
    # CHANNEL_API = os.getenv("CHANNEL_API")
    # CHANNELS_API = os.getenv("CHANNELS_API")
    ADAPTOR_PORT = int(os.getenv("ADAPTOR_PORT"))
    SERVICE_REGISTERATION_INTERVAL = int(os.getenv("SERVICE_REGISTERATION_INTERVAL"))

    THINGSPEAK_URL = os.getenv("THINGSPEAK_URL")
    THINGSPEAK_UPDATE_ENDPOINT = os.getenv("THINGSPEAK_UPDATE_ENDPOINT")
    THINGSPEAK_CHANNELS_ENDPOINT = os.getenv("THINGSPEAK_CHANNELS_ENDPOINT")
    USER_API_KEY = os.getenv("USER_API_KEY")




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
    