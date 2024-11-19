import os
import cherrypy
import datetime
import logging
from dotenv import load_dotenv

# Import environmental variables
load_dotenv()
MONGO_URL = os.getenv("MONGO_URL")
DB = os.getenv("DB")
LOGGER_NAME = os.getenv("BASE_LOGGER")


# Logger configuartion
logging.basicConfig()
logger = logging.getLogger(LOGGER_NAME)
logger.setLevel(logging.INFO)


# To adhere python snake_case and JSON camelCase
def camel_to_snake(s):
    return ''.join(['_'+c.lower() if c.isupper() else c for c in s]).lstrip('_')

def to_camel_case(snake_str):
    return "".join(x.capitalize() for x in snake_str.lower().split("_"))

def to_lower_camel_case(snake_str):
    # We capitalize the first letter of each component except the first one
    # with the 'capitalize' method and join them together.
    camel_string = to_camel_case(snake_str)
    return snake_str[0].lower() + camel_string[1:]

