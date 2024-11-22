def convert_to_bool(param):
    if param and param.lower() in ["true", "1"]:
        return bool(param)

def create_response(success: bool, content=None, message=None):
    return {"success": success, "content": content, "message": message}
