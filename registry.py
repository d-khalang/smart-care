import os
import datetime
import logging
from dotenv import load_dotenv
from typing import Dict, Literal, Optional

# Import environmental variables
load_dotenv()
MONGO_URL = os.getenv("MONGO_URL")
DB = os.getenv("DB")
LOGGER_NAME = os.getenv("BASE_LOGGER")


### Logger configuartion
logger = logging.getLogger(LOGGER_NAME)
logger.setLevel(logging.INFO) # Set the logging level to INFO

# Create a console handler to stream log messages to the console
ch = logging.StreamHandler()
ch.setLevel(logging.INFO)  # The console handler will handle logs of INFO level and above

# Create a formatter for the log messages
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
ch.setFormatter(formatter)  # Set the formatter for the console handler

# Add the console handler to the logger
logger.addHandler(ch)



# To adhere python snake_case and JSON camelCase
def camel_to_snake(s) -> str:
    return ''.join(['_'+c.lower() if c.isupper() else c for c in s]).lstrip('_')

def to_camel_case(snake_str) -> str:
    return "".join(word.capitalize() for word in snake_str.lower().split("_"))

def to_lower_camel_case(snake_str) -> str:
    # We capitalize the first letter of each component except the first one
    # with the 'capitalize' method and join them together.
    camel_string = to_camel_case(snake_str)
    return snake_str[0].lower() + camel_string[1:]

def camel_snake_handler_for_dict(input_dict:dict, from_type: Literal["camel", "snake"]) -> dict:
    if from_type == "camel":
        return {camel_to_snake(key):value for key, value in input_dict.items()}
    elif from_type == "snake":
        return {to_lower_camel_case(key):value for key, value in input_dict.items()}
    return {}

# logger.info("lets see a logg here")


