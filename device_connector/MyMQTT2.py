import json
import paho.mqtt.client as PahoMQTT


class MyMQTT:
    def __init__(self, clientID, broker, port, notifier, child_logger):
        self.broker = broker
        self.port = port
        self.notifier = notifier
        self.clientID = clientID
        self.logger = child_logger

        self._topic = []
        self._isSubscriber = False
        # create an instance of paho.mqtt.client
        self._paho_mqtt = PahoMQTT.Client(clientID, True)
        # register the callback
        self._paho_mqtt.on_connect = self.myOnConnect
        self._paho_mqtt.on_message = self.myOnMessageReceived

    def myOnConnect(self, paho_mqtt, userdata, flags, rc):
        self.logger.info("Connected to %s with result code: %d" % (self.broker, rc))

    def myOnMessageReceived(self, paho_mqtt, userdata, msg):
        # A new message is received
        self.notifier.notify(msg.topic, msg.payload)


    def myPublish(self, topic, msg):
        # publish a message with a certain topic
        try:
            self._paho_mqtt.publish(topic, json.dumps(msg), qos=2)
        except Exception as e:
            self.logger.error(f"Error publishing message: {e}")


    def mySubscribe(self, topic):
        # subscribe for a topic
        try:
            self._paho_mqtt.subscribe(topic, qos=2)
            self._isSubscriber = True
            self._topic.append(topic)
            self.logger.info(f"Subscribed to {topic}")
            
        except Exception as e:
            self.logger.error(f"Error subscribing to topic {topic}: {e}")


    def start(self):
        # manage connection to broker
        try:
            self._paho_mqtt.connect(self.broker, self.port)
            self._paho_mqtt.loop_start()
        except Exception as e:
            self.logger.error(f"Error starting MQTT client: {e}")


    def unsubscribe(self, topic):
        if self._isSubscriber:
            try:
                self._paho_mqtt.unsubscribe(topic)
            except Exception as e:
                self.logger.error(f"Error unsubscribing from topic {topic}: {e}")

    def stop(self):
        if self._isSubscriber:
            for topic in self._topic:
                self.unsubscribe(topic)
        self._paho_mqtt.loop_stop()
        self._paho_mqtt.disconnect()
