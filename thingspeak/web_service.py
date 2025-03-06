import cherrypy
import time
from adaptor import Adaptor
from utility import create_response
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
            return create_response(False, message="No url inserted, try 'channel_detail'", status=404)
        
        if uri[0] == "channel_detail":
            if len(uri) > 1:
                output = self.adaptor.get_channel_detail(uri[1]) 
            else: 
                output = self.adaptor.get_channel_detail()
            
            if output:
                return create_response(True, content=output, status=200)
            else: 
                return create_response(False, message="No cahnnel_detail or valid channel_id", status=400)
        
        elif uri[0] == "sensing_data":
            if len(uri) < 2:
                return create_response(False, message="Enter channel_id.", status=404)
            
            data = self.adaptor.get_sensing_data(uri[1], **params)
            if not data:
                return create_response(False, message=f"No sensing data found for channel_id: {uri[1]} and params: {params}", status=400)
            
            return create_response(True, content=data, status=200)

        return create_response(False, message="URL not valid, try 'channels'", status=404)



if __name__ == "__main__":
    adaptor = Adaptor(config=Config)
    ## CherryPy setup
    conf = {
        "/": {
            'request.dispatch': cherrypy.dispatch.MethodDispatcher(),
            'tools.sessions.on': True
        }
    }
    cherrypy.config.update({
                'server.socket_host': '0.0.0.0',
                'server.socket_port': Config.ADAPTOR_PORT
                })

    webService = WebAdaptor(adaptor=adaptor)
    cherrypy.tree.mount(webService, '/', conf)
    cherrypy.engine.start()
    cherrypy.engine.block()
    flag = True
    
    try:
        while flag:
            time.sleep(5)

    except KeyboardInterrupt:
        print("Keyboard interrupt detected. Shutting down...")
        # Terminate the webservice    
        flag = False
        
    finally:
        # Terminate the webservice 
        adaptor.stop_mqtt()   
        
