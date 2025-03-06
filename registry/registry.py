'''Main file of registry system'''
import cherrypy
from config import Config, MyLogger
from web_service import WebCatalog
from db.db import Database
from cleaners import Cleaner
from handlers import Handler



if __name__ == '__main__':
    database = Database(logger=MyLogger.set_logger(logger_name=Config.DB_LOGGER))
    cleaner = Cleaner(database_agent=database, logger=MyLogger.set_logger(logger_name=Config.CLEANER_LOGGER))
    handler = Handler(database_agent=database, logger=MyLogger.set_logger(logger_name=Config.HANDLER_LOGGER))

    ## CherryPy setup
    conf = {
        "/": {
            'request.dispatch': cherrypy.dispatch.MethodDispatcher(),
            'tools.sessions.on': True
        }
    }
    cherrypy.config.update({
        'server.socket_host': '0.0.0.0',  # Bind to all network interfaces
        'server.socket_port': 8080,       # Ensure it's listening on port 8080
    })
    webService = WebCatalog(handler=handler)
    cherrypy.tree.mount(webService, '/', conf)
    cherrypy.engine.start()
    cherrypy.engine.block()
    # handler.handle_get(("plants",), {})
