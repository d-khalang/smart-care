import os
import cherrypy
import time
import json
from reporter import Reporter
from utility import create_response
from config import Config


class WebReporter():
    exposed = True
    def __init__(self, reporter: Reporter) -> None:
        self.reporter = reporter


    @cherrypy.tools.json_in()
    def GET(self, *uri, **params):
        print({"uri": uri, "param": params})
        if len(uri) < 1:
            return json.dumps(create_response(False, message="No url inserted, try 'report'", status=404))

        if uri[0] == "report":
            if len(uri) > 1:
                plant_id = uri[1]

                local_params = {
                    "room_id": params.get("room_id", None),
                    "results": params.get("results", None),
                    "start_date": params.get("start_date", None),
                    "end_date": params.get("end_date", None)
                }

                # Create the report for the given plant_id and save as PDF
                pdf_file_path = self.reporter.generate_and_deliver_report(plant_id, **local_params)
                # pdf_file_path = "Plant_Report_101_v1.pdf"

                # If PDF is generated successfully, return the file as response
                if os.path.exists(pdf_file_path):
                    with open(pdf_file_path, 'rb') as file:
                        cherrypy.response.headers['Content-Type'] = 'application/pdf'
                        cherrypy.response.headers['Content-Disposition'] = f'attachment; filename=report_{plant_id}.pdf'
                        cherrypy.response.headers['Content-Length'] = os.path.getsize(pdf_file_path)
                        return file.read()
                else:
                    return json.dumps(create_response(False, message="Report generation failed.", status=500))
            else:
                return json.dumps(create_response(False, message="No plant_id reported", status=404))

        return json.dumps(create_response(False, message="URL is not valid, try 'report'", status=404))




if __name__ == "__main__":
    reporter = Reporter(config=Config)
    ## CherryPy setup
    conf = {
        "/": {
            'request.dispatch': cherrypy.dispatch.MethodDispatcher(),
            'tools.sessions.on': True
        }
    }
    cherrypy.config.update({
                'server.socket_host': '0.0.0.0',
                'server.socket_port': Config.REPORTER_PORT
                })

    webService = WebReporter(reporter=reporter)
    cherrypy.tree.mount(webService, '/', conf)
    cherrypy.engine.start()
    flag = True
    i = 0
    try:
        while flag:
            time.sleep(5)
            if not i % Config.SERVICE_REGISTERATION_INTERVAL:
                reporter.data_manager.post_service()
            i+= 5
    except KeyboardInterrupt:
        flag = False
