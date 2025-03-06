'''Environmental variables & logger provider'''
import os
import logging
from dotenv import load_dotenv

load_dotenv()

class Config:
    CATALOG_URL = os.getenv("CATALOG_URL")
    PLANTS_ENDPOINT = os.getenv("PLANTS_ENDPOINT")
    DEVICES_ENDPOINT = os.getenv("DEVICES_ENDPOINT")
    GENERAL_ENDPOINT = os.getenv("GENERAL_ENDPOINT")
    ROOMS_ENDPOINT = os.getenv("ROOMS_ENDPOINT")
    SERVICES_ENDPOINT = os.getenv("SERVICES_ENDPOINT")
    SERVICE_REGISTRY_NAME = os.getenv("SERVICE_REGISTRY_NAME")
    
    LOGGER_NAME = os.getenv("BASE_LOGGER")
    # MODEL_LOGGER = os.getenv("MODEL_LOGGER")
    STATE_FILE = os.getenv("STATE_FILE")
    
    CONTROLLER_CONFIG_INTERVAL = int(os.getenv("CONTROLLER_CONFIG_INTERVAL", 300))  # seconds
    CONTROLLER_BASE_PORT = int(os.getenv("CONTROLLER_BASE_PORT", 7090))
    ROOMS_PER_CONTROLLER = int(os.getenv("ROOMS_PER_CONTROLLER", 2))
    CONTROLLER_IMAGE = os.getenv("CONTROLLER_IMAGE")
    SERVICE_REGISTRY_FILE = os.getenv("SERVICE_REGISTRY_FILE")

    CU_LOGGER = os.getenv("CU_LOGGER")
    MQTT_LOGGER = os.getenv("MQTT_LOGGER")
    TOPICS_UPDATE_INTERVAL = int(os.getenv("TOPICS_UPDATE_INTERVAL", 600))  # seconds
    
    WEATHER_FORECAST_URL = os.getenv("WEATHER_FORECAST_URL")
    WEATHER_FORECAST_API_KEY = os.getenv("WEATHER_FORECAST_API_KEY")



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
    