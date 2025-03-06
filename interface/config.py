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
    USERS_ENDPOINT = os.getenv("USERS_ENDPOINT")
    SERVICE_REGISTRY_NAME = os.getenv("SERVICE_REGISTRY_NAME")
    THINGSPEAK_ADAPTOR_REGISTRY_NAME = os.getenv("THINGSPEAK_ADAPTOR_REGISTRY_NAME")
    MQTT_CLIENT_ID = os.getenv("MQTT_CLIENT_ID")
    LOGGER_NAME = os.getenv("BASE_LOGGER")
    MANAGER_LOGGER = os.getenv("MANAGER_LOGGER")
    ROOMS_ENDPOINT = os.getenv("ROOMS_ENDPOINT")
    AVAILABLE_MEASURE_TYPES = os.getenv("AVAILABLE_MEASURE_TYPES", "").split(",")
    MQTT_LOGGER = os.getenv("MQTT_LOGGER")
    UPDATE_INTERVAL = int(os.getenv("TOPICS_UPDATE_INTERVAL", 600))  # seconds
    ADAPTOR_CHANNEL_ENDPOINT = os.getenv("ADAPTOR_CHANNEL_ENDPOINT")
    ADAPTOR_SENSING_DATA_ENDPOINT = os.getenv("ADAPTOR_SENSING_DATA_ENDPOINT")
    CHANNEL_API = os.getenv("CHANNEL_API")
    CHANNELS_API = os.getenv("CHANNELS_API")
    USER_API_KEY = os.getenv("USER_API_KEY")

    SERVICE_REGISTRY_FILE = os.getenv("SERVICE_REGISTRY_FILE")
    SERVICE_REGISTERATION_INTERVAL = int(os.getenv("SERVICE_REGISTERATION_INTERVAL"))

    ADMIN_USERNAME = os.getenv("ADMIN_USERNAME")
    ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")
    FLASK_SECURITY_KEY = os.getenv("FLASK_SECURITY_KEY")

    REPORTER_REGISTRY_NAME = os.getenv("REPORTER_REGISTRY_NAME")
    REPORTER_ENDPOINT = os.getenv("REPORTER_ENDPOINT")
    REPORT_SAVE_PATH = os.getenv("REPORT_SAVE_PATH")




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
    