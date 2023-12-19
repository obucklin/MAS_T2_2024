import time

from compas_eve import Message
from compas_eve import Publisher
from compas_eve import Subscriber
from compas_eve import Topic
from compas_eve.mqtt import MqttTransport

class ExecutorCommunicator(object):
    def __init__(self): 
        self.tx = MqttTransport("broker.hivemq.com")
        self.topic_top_directory = "T2_command_test"

        self.user_checkin_topic = Topic("/{}/user_checkin_topic".format(self.topic_top_directory), Message)
        self.user_checkin_subcriber = Subscriber(self.user_checkin_topic, callback=lambda msg: self.subscribe_to_AR_user(msg['text']), transport=self.tx)
        self.user_checkin_subcriber.subscribe()
        self.AR_users = {}
        self.user_subscriptions = {}
        self.user_timeout_start = time.monotonic()

        self.interface_topic = Topic("/{}/interface_topic".format(self.topic_top_directory), Message)
        self.interface_publisher = Publisher(self.interface_topic, transport=self.tx)


        self.command_topic = Topic("/{}/command_topic".format(self.topic_top_directory), Message)
        self.command_publisher = Publisher(self.command_topic, transport=self.tx)


    def subscribe_to_AR_user(self, user_id):
        if user_id not in self.AR_users.keys():
            self.AR_users[user_id] = ARUser(user_id)
            
            sub = Subscriber(Topic("/{}/user_data_topic/{}".format(self.topic_top_directory, user_id), Message), callback=lambda msg: print(f"Received DATA message: {msg.text}"), transport=self.tx)
            print("Subscribing to user {}".format(sub.topic.name))
            sub.subscribe()
            self.user_subscriptions[user_id] = sub
            print("User {} added".format(user_id))
        else:
            self.AR_users[user_id].last_seen = time.monotonic()

    def cull_inactive_users(self):
        if time.monotonic() - self.user_timeout_start > 5:  # every 60 seconds
            to_cull = []
            for user in self.AR_users.values():
                if self.user_timeout_start > user.last_seen:
                    self.user_subscriptions[user.id].unsubscribe()
                    print("User {} removed".format(user.id))
                    to_cull.append(user.id)
            for key in to_cull:
                del self.AR_users[key]
            self.user_timeout_start = time.monotonic()
            print("Current users: {}".format(self.AR_users.keys()))

    def run(self):
        print("running")
        message_timeout = time.monotonic()
        while True:
            self.cull_inactive_users()
            if time.monotonic() - message_timeout > 5:
                print("publishing")
                self.interface_publisher.publish(Message(text="Albuquerque"))
                message_timeout = time.monotonic()


class ARUser(object):
    def __init__(self, id):
        self.id = id
        self.confirm_step = {}
        self.last_seen = time.monotonic()

    def send_command(self, command):
        self.ros_client.send_command(command)


if __name__ == "__main__":
    ex_comm = ExecutorCommunicator()
    ex_comm.run()