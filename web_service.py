import cherrypy
from handlers import Handlers
from utility import create_response

class WebCatalog():
    exposed = True
    def __init__(self) -> None:
        self.handler = Handlers()

    @cherrypy.tools.json_out()
    @cherrypy.tools.json_in()
    def GET(self, *uri, **params):
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
        return self.handler.handle_put(uri, params, data)

    @cherrypy.tools.json_out()
    @cherrypy.tools.json_in()
    def DELETE(self, *uri, **params):
        return self.handler.handle_delete(uri, params)


if __name__ == '__main__':
    conf = {
        "/": {
            'request.dispatch': cherrypy.dispatch.MethodDispatcher(),
            'tools.sessions.on': True
        }
    }
    webService = WebCatalog()
    cherrypy.tree.mount(webService, '/', conf)
    cherrypy.engine.start()
    cherrypy.engine.block()