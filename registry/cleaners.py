'''Cleaner is responsible for removing outdated items'''

import datetime
import sched
import time
from config import Config


class Cleaner():
    def __init__(self, database_agent, logger) -> None:
        self.db = database_agent
        self.logger = logger
        
        # Scheduler config  
        self.threshold = Config.CLEANUP_THRESHOLD
        self.interval = Config.CLEANUP_INTERVAL
        self.scheduler = sched.scheduler(time.time, time.sleep)
        self.scheduler.enter(0, 1, self.cleanup, ())
        self.scheduler.run(blocking=False)


    def cleanup(self):
        self.logger.info("Cleaning up outdated Plants and Devices...")
        self._cleanup_plants()
        self._cleanup_devices()
        self._cleanup_empty_rooms()
        self.logger.info("Clean up completed.")

        # Reschedule the periodic cleanup every x seconds
        self.scheduler.enter(self.interval, 1, self.cleanup, ())


    # Removes outdated plants
    def _cleanup_plants(self):
        a_threshold_ago = datetime.datetime.now() - datetime.timedelta(minutes=self.threshold)
        find_plants_respose = self.db.find_plants()
        if find_plants_respose.get("success"):
            plants = find_plants_respose.get("content", [])
        else:
            self.logger.error(f"Unable to get plants: {str(find_plants_respose)}")
            plants =[]

        for plant in plants:
            last_updated = datetime.datetime.strptime(plant['lastUpdated'], "%Y-%m-%d %H:%M:%S")
            if last_updated < a_threshold_ago:
                self.db.delete_plant(plant['plantId'])


    # Removes outdated devices
    def _cleanup_devices(self):
        a_threshold_ago = datetime.datetime.now() - datetime.timedelta(minutes=self.threshold)
        find_devices_response = self.db.find_devices()

        if find_devices_response.get("success"):
            devices = find_devices_response.get("content", [])
        else:
            self.logger.error(f"Unable to get plants: {str(find_devices_response)}")
            devices = []

        for device in devices:
            last_updated = datetime.datetime.strptime(device['lastUpdated'], "%Y-%m-%d %H:%M:%S")
            if last_updated < a_threshold_ago:
                self.db.delete_device(device['deviceId'])


    # Removes empty rooms
    def _cleanup_empty_rooms(self):
        self.db.remove_empty_rooms()

    


    