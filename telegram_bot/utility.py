'''Utility functions across the scripts'''
from typing import Union, Dict

def to_camel_case(snake_str) -> str:
    return "".join(word.capitalize() for word in snake_str.lower().split("_"))

def to_lower_camel_case(snake_str) -> str:
    # We capitalize the first letter of each component except the first one
    # with the 'capitalize' method and join them together.
    camel_string = to_camel_case(snake_str)
    return snake_str[0].lower() + camel_string[1:]


def convert_to_bool(param) -> Union[bool, None]:
    if param and param.lower() in ["true", "1"]:
        return bool(param)

def create_response(success: bool, content: dict = None, message: str = "", status: int = 200) -> dict:
    response = {
        "success": success,
        "status": status,
    }
    if content is not None:
        response["content"] = content
    if message:
        response["message"] = message
    return response


def case_insensitive(item: Union[str, Dict[str, str]]) -> Union[str, Dict[str, str]]:
    if isinstance(item, str):
        return item.lower()
    
    elif isinstance(item, dict):
        try:
            return {k.lower(): v for k, v in item.items()}
        except Exception as e:
            print(f"Failed to make the dictionary key lowercase: {e}")
            raise e
    else:
        raise TypeError("Unsupported type for case_insensitive function")