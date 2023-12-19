import time
import random

from compas_eve import Message
from compas_eve import Publisher
from compas_eve import Subscriber
from compas_eve import Topic
from compas_eve.mqtt import MqttTransport


class MockAR(object):
    def __init__(self):
        self.confirm_step = {}
        self.id = random.randint(0, 100000)

        self._start_time = time.monotonic()
        self.tx = MqttTransport("broker.hivemq.com")
        self.server_topic = "T2_command_test"

        """checkin with the system"""
        self.user_checkin_topic = Topic("/{}/user_checkin_topic".format(self.server_topic), Message)
        self.user_checkin_publisher = Publisher(self.user_checkin_topic, transport=self.tx)

        """connect to publish topic"""
        self.user_data_topic = Topic("/{}/user_data_topic/{}".format(self.server_topic,self.id), Message)
        self.user_data_publisher = Publisher(self.user_data_topic, transport=self.tx)

        """subscribe to interface topic"""
        self.interface_topic = Topic("/{}/interface_topic".format(self.server_topic), Message)
        self.interface_subscriber = Subscriber(self.interface_topic, callback=lambda msg: self.respond(msg['text']), transport=self.tx)        
        self.interface_subscriber.subscribe()
        print("my name is cain, my number is {}".format(self.id))

    def check_in(self, interval = 2):
        if time.monotonic() - self._start_time > interval:
            self.user_checkin_publisher.publish(Message(text=str(self.id)))
            self._start_time = time.monotonic()

    def respond(self, name):
        print("publishing message: {} on topic: {}".format(name, self.user_data_publisher.topic.name))
        self.user_data_publisher.publish(Message(text="howdy {}, my name is cain #{}".format(name, self.id)))

    def run(self):
        print("running")
        while True:
            self.check_in()

if __name__ == "__main__":
    ar = MockAR()
    ar.run()
            