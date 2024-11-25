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
