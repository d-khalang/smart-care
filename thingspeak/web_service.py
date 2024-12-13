import cherrypy
import time
from adaptor import Adaptor
from utility import create_response, case_insensitive
from config import Config


class WebAdaptor():
    exposed = True
    def __init__(self, adaptor: Adaptor) -> None:
        self.adaptor = adaptor

    @cherrypy.tools.json_out()
    @cherrypy.tools.json_in()
    def GET(self, *uri, **params):
        print({"uri":uri, "param":params})
        if len(uri) < 1:
            return create_response(False, message="No url inserted, try 'channels'")
        return create_response(False, message="No url inserted, try 'channels'")

    # @cherrypy.tools.json_out()
    # @cherrypy.tools.json_in()
    # def POST(self, *uri, **params):
    #     ### Must receive rooms in body like {"rooms": [1, 2, 3]}
    #     data = cherrypy.request.json
    #     if len(uri) < 1:
    #         return create_response(False, message="No url inserted, try 'rooms'", status=404)
        
    #     if case_insensitive(uri[0]) == 'rooms':
    #         rooms = data.get('rooms')
    #         if rooms:
    #             try:
    #                 checked_rooms = [int(room) for room in rooms]
    #                 return self.adaptor.add_rooms(new_rooms=checked_rooms)

    #             except ValueError as e:
    #                 return create_response(False, message=f"All room IDs must be numbers, not '{rooms}': {str(e)}", status=500)
            
    #         return create_response(False, message="Rooms not present in the body.", status=404)
    #     return create_response(False, message="No valid url inserted, try 'rooms'", status=404)
    

    # @cherrypy.tools.json_out()
    # @cherrypy.tools.json_in()
    # def PUT(self, *uri, **params):
    #     return create_response(False, message="No put request is foreseen.")
        

    # @cherrypy.tools.json_out()
    # @cherrypy.tools.json_in()
    # def DELETE(self, *uri, **params):
    #     ### Must receive rooms in path like /rooms/1,2,3"
    #     if len(uri) < 1:
    #         return create_response(False, message="No url inserted, try 'rooms'", status=404)
        
    #     if case_insensitive(uri[0]) == 'rooms':
    #         if len(uri) > 1:
    #             rooms = uri[1]

    #             try:
    #                 rooms_str = rooms.strip().split(',')
    #                 checked_rooms = [int(room) for room in rooms_str]
    #                 return self.adaptor.remove_rooms(removed_rooms=checked_rooms)

    #             except ValueError:
    #                 return create_response(False, message="Invalid room IDs provided, must be integers", status=500)

    #         return create_response(False, message="Unrecognizeable room IDs provided, must be set of numbers separated by ','.", status=500)
    #     return create_response(False, message="No url inserted, try 'rooms'", status=404)




if __name__ == "__main__":
    adaptor = Adaptor(config=Config)
    ## CherryPy setup
    conf = {
        "/": {
            'request.dispatch': cherrypy.dispatch.MethodDispatcher(),
            'tools.sessions.on': True
        }
    }
    cherrypy.config.update({'server.socket_port': Config.CU_PORT})

    webService = WebAdaptor(adaptor=Adaptor)
    cherrypy.tree.mount(webService, '/', conf)
    cherrypy.engine.start()
    try:
        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        print("Keyboard interrupt detected. Shutting down...")
        # Terminate the webservice    
        cherrypy.engine.block()
        
    finally:
        # Terminate the webservice 
        adaptor.stop_mqtt()   
        cherrypy.engine.block()