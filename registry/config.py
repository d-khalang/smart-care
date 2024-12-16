'''Environmental variables provider'''
import os
import logging
from dotenv import load_dotenv

load_dotenv()

class Config:
    MONGO_URL = os.getenv("MONGO_URL")
    DB = os.getenv("DB")
    GENERAL_COLLECTION = os.getenv("GENERAL_COLLECTION")
    PLANT_KINDS_COLLECTION = os.getenv("PLANT_KINDS_COLLECTION")
    PLANTS_COLLECTION = os.getenv("PLANTS_COLLECTION")
    ROOMS_COLLECTION = os.getenv("ROOMS_COLLECTION")
    DEVICES_COLLECTION = os.getenv("DEVICES_COLLECTION")
    USERS_COLLECTION = os.getenv("USERS_COLLECTION")
    SERVICES_COLLECTION = os.getenv("SERVICES_COLLECTION")
    LOGGER_NAME = os.getenv("BASE_LOGGER")
    MODEL_LOGGER = os.getenv("MODEL_LOGGER")
    HANDLER_LOGGER = os.getenv("HANDLER_LOGGER")
    CLEANER_LOGGER = os.getenv("CLEANER_LOGGER")
    DB_LOGGER = os.getenv("DB_LOGGER")
    CLEANUP_THRESHOLD = int(os.getenv("CLEANUP_THRESHOLD"))
    CLEANUP_INTERVAL = int(os.getenv("CLEANUP_INTERVAL"))


class MyLogger:
    logger = logging.getLogger(Config.LOGGER_NAME)
    logger.setLevel(logging.INFO)
    
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    ch.setFormatter(formatter)
    
    logger.addHandler(ch)
    
    @classmethod
    def set_logger(cls, logger_name:str):
        return cls.logger.getChild(logger_name)
    