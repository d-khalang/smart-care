'''Environmental variables provider'''
import os
import logging
from dotenv import load_dotenv

load_dotenv()

class Config:
    CATALOG_URL = os.getenv("CATALOG_URL")
    PLANTS_ENDPOINT = os.getenv("PLANTS_ENDPOINT")
    ROOMS_ENDPOINT = os.getenv("ROOMS_ENDPOINT")
    DEVICES_ENDPOINT = os.getenv("DEVICES_ENDPOINT")
    GENERAL_ENDPOINT = os.getenv("GENERAL_ENDPOINT")
    SERVICES_ENDPOINT = os.getenv("SERVICES_ENDPOINT")
    SERVICE_REGISTRY_NAME = os.getenv("SERVICE_REGISTRY_NAME")
    THINGSPEAK_ADAPTOR_REGISTRY_NAME = os.getenv("THINGSPEAK_ADAPTOR_REGISTRY_NAME")
    ADAPTOR_SENSING_DATA_ENDPOINT = os.getenv("ADAPTOR_SENSING_DATA_ENDPOINT")
    DATA_MANAGER_LOGGER = os.getenv("DATA_MANAGER_LOGGER")
    LOGGER_NAME = os.getenv("BASE_LOGGER")
    SERVICE_REGISTRY_FILE = os.getenv("SERVICE_REGISTRY_FILE")
    AVAILABLE_MEASURE_TYPES = os.getenv("AVAILABLE_MEASURE_TYPES", "").split(",")
    REPORTER_PORT = int(os.getenv("REPORTER_PORT"))
    SERVICE_REGISTRY_FILE = os.getenv("SERVICE_REGISTRY_FILE")
    SERVICE_REGISTERATION_INTERVAL = int(os.getenv("SERVICE_REGISTERATION_INTERVAL"))
    # LLM_API_KEY = os.getenv("LLM_API_KEY")
    # LLM_MODEL = os.getenv("LLM_MODEL")
    




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
    