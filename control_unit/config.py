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
    ROOMS_ENDPOINT = os.getenv("ROOMS_ENDPOINT")
    MQTT_LOGGER = os.getenv("MQTT_LOGGER")
    TOPICS_UPDATE_INTERVAL = int(os.getenv("TOPICS_UPDATE_INTERVAL", 200))  # seconds
    CU_PORT = int(os.getenv("CU_PORT"))
    # WEATHER_FORECAST_URL = os.getenv("WEATHER_FORECAST_URL")
    # WEATHER_FORECAST_API_KEY = os.getenv("WEATHER_FORECAST_API_KEY")
    ROOM_IDS = list(map(int, os.getenv("ROOM_IDS", "").split(",")))




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
    