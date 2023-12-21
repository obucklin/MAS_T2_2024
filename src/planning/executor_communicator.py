import time
import threading

from compas_eve import Message
from compas_eve import Publisher
from compas_eve import Subscriber
from compas_eve import Topic
from compas_eve.mqtt import MqttTransport

class ExecutorCommunicator(object):
    def __init__(self): 
        self.tx = MqttTransport("broker.hivemq.com")
        self.topic_top_directory = "T2_command_test"

        self.initialize_mqtt()

        self.AR_users = {}
        self.users_to_add = []        
        self.users_to_cull = []
        self.print_flag = False



    def initialize_mqtt(self):
        self.user_checkin_topic = Topic("/{}/user_checkin_topic".format(self.topic_top_directory), Message)
        user_checkin_subcriber = Subscriber(self.user_checkin_topic, callback=lambda msg: self.add_AR_user_id(msg['text']), transport=self.tx)
        user_checkin_subcriber.subscribe()

        interface_topic = Topic("/{}/interface_topic".format(self.topic_top_directory), Message)
        self.interface_publisher = Publisher(interface_topic, transport=self.tx)

        command_topic = Topic("/{}/command_topic".format(self.topic_top_directory), Message)
        self.command_publisher = Publisher(command_topic, transport=self.tx)

    def add_AR_user_id(self, user_id):
        if user_id not in self.AR_users.keys():
            self.users_to_add.append(user_id)

    def send_to_robot(self, command):
        self.command_publisher.publish(Message(text=command))


    def send_to_interface(self, user_id, message):
        msg = Message(text="{}: {}".format(user_id, message))
        self.interface_publisher.publish(msg)


    def manage_users(self):
            while len(self.users_to_add) > 0:
                id = self.users_to_add.pop()
                self.AR_users[id] = ARUser(id, self)
                print("User {} added".format(id))
                self.print_flag = True 
            for user in self.AR_users.values():
                if user.active_flags["to_delete"]:
                    self.users_to_cull.append(user.id)
            while len(self.users_to_cull) > 0:
                id = self.users_to_cull.pop()
                print("User {} removed".format(id))
                del self.AR_users[id]
                self.print_flag = True


    def test_messages(self, message, publisher):
        while True:
            publisher.publish(Message(text=message))
            time.sleep(0.1)
            print("user count = {}".format(len(self.AR_users)))
            for user in self.AR_users.values():
                print("user {}: {}".format(user.id, user.message.text))
            time.sleep(1.9)


    def run(self):
        print("running")
        thread = threading.Thread(target=self.test_messages, args=("master comms", self.interface_publisher), daemon=True)
        thread.start()
        while True:
            self.manage_users()
            if self.print_flag:
                print("AR users: {}".format(self.AR_users.keys()))
                self.print_flag = False


class ARUser(object):
    def __init__(self, id, parent):
        self.id = id
        self.parent = parent
        self.confirm_step = {}
        self.active_flags = {"is_active": True, "to_delete": False}
        self.message = None
        self.subscribe_to_AR_user()
        self.maintain_user()


    def set_message(self, message):
        self.message = message


    def subscribe_to_AR_user(self):
        topic = Topic("/{}/user_data_topic/{}".format(self.parent.topic_top_directory, self.id), Message)
        self.user_subscription =  Subscriber(topic, callback=lambda msg: self.set_message(msg), transport=self.parent.tx)
        self.user_subscription.subscribe()
        

    def confirm_active(self, message, active_flags):
        if message.text == str(self.id):
            active_flags["is_active"] = True



    def checkin_thread(self, active_dict, interval = 2):
        user_checkin_subcriber = Subscriber(self.parent.user_checkin_topic, callback=lambda msg: self.confirm_active(msg, active_dict), transport=self.parent.tx)
        user_checkin_subcriber.subscribe()
        while active_dict["is_active"]:
            active_dict["is_active"] = False
            time.sleep(interval)
        active_dict["to_delete"] = True


    def maintain_user(self, interval = 2):
        thread = threading.Thread(target=self.checkin_thread, args=(self.active_flags, interval), daemon=True)
        thread.start()


if __name__ == "__main__":
    ex_comm = ExecutorCommunicator()
    ex_comm.run()