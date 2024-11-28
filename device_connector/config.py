'''Environmental variables provider'''
import os
import logging
from dotenv import load_dotenv

load_dotenv()

class Config:
    CATALOG_URL = os.getenv("CATALOG_URL")
    PLANTS_ENDPOINT = os.getenv("PLANTS_ENDPOINT")
    DEVICES_ENDPOINT = os.getenv("DEVICES_ENDPOINT")
    # REGISTERATION_INTERVAL = os.getenv("PLANT_KINDS_COLLECTION")
    # PLANTS_COLLECTION = os.getenv("PLANTS_COLLECTION")
    # ROOMS_COLLECTION = os.getenv("ROOMS_COLLECTION")
    # DEVICES_COLLECTION = os.getenv("DEVICES_COLLECTION")
    LOGGER_NAME = os.getenv("BASE_LOGGER")
    # MODEL_LOGGER = os.getenv("MODEL_LOGGER")
    # HANDLER_LOGGER = os.getenv("HANDLER_LOGGER")
    # CLEANER_LOGGER = os.getenv("CLEANER_LOGGER")
    # DB_LOGGER = os.getenv("DB_LOGGER")
    CONFIG_FILE = int(os.getenv("CONFIG_FILE"))
    REGISTERATION_INTERVAL = int(os.getenv("REGISTERATION_INTERVAL"))


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
    