import cherrypy
from utility import create_response
from handlers import Handler

class WebCatalog():
    exposed = True
    def __init__(self, handler: Handler) -> None:
        self.handler = handler

    @cherrypy.tools.json_out()
    @cherrypy.tools.json_in()
    def GET(self, *uri, **params):
        print({"uri":uri, "param":params})
        if len(uri) < 1:
            return create_response(False, message="No url inserted, try from 'general', 'plants', 'devices', plant_kinds, ...")
        return self.handler.handle_get(uri, params)

    @cherrypy.tools.json_out()
    @cherrypy.tools.json_in()
    def POST(self, *uri, **params):
        data = cherrypy.request.json
        if len(uri) < 1:
            return create_response(False, message="No url inserted, try from 'plants', 'devices', ...")
        return self.handler.handle_post(uri, params, data)

    @cherrypy.tools.json_out()
    @cherrypy.tools.json_in()
    def PUT(self, *uri, **params):
        data = cherrypy.request.json
        if len(uri) < 1:
            return create_response(False, message="No url inserted, try from 'plants', 'devices', ...")
        return self.handler.handle_put(uri, params, data)

    @cherrypy.tools.json_out()
    @cherrypy.tools.json_in()
    def DELETE(self, *uri, **params):
        if len(uri) < 1:
            return create_response(False, message="No url inserted, try from 'plants', 'devices', ...")
        return self.handler.handle_delete(uri, params)


