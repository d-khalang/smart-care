'''Utility functions across the scripts'''

def to_camel_case(snake_str) -> str:
    return "".join(word.capitalize() for word in snake_str.lower().split("_"))

def to_lower_camel_case(snake_str) -> str:
    # We capitalize the first letter of each component except the first one
    # with the 'capitalize' method and join them together.
    camel_string = to_camel_case(snake_str)
    return snake_str[0].lower() + camel_string[1:]


def convert_to_bool(param):
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
