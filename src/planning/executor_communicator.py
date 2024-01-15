import time
import threading
import paho.mqtt.client as mqtt
from compas_eve import Message
from compas_eve import Publisher
from compas_eve import Subscriber
from compas_eve import Topic
from compas_eve.mqtt import MqttTransport

class ExecutorCommunicator(object):
    """Class for managing communication between the AR interface and the robot
    
    Parameters



    Attributes
    
    
    """	

    def __init__(self, broker, directory_name): 
        self.tx = MqttTransport(broker)
        self.topic_top_directory = directory_name
        
        self.AR_users = {}
        self._users_to_add = []        
        self._users_to_cull = []
        self.print_flag = False
        self.initialize_mqtt()

    def remove_user(self, user_id):
        self._users_to_cull.append(user_id)

    def initialize_mqtt(self):
        """Initialize the MQTT transport and create the topics and publishers/subscribers"""	

        """create and subscribe to the user checkin topic, which is used to maintain a list of active users"""
        self.user_checkin_topic = Topic("/{}/user_checkin_topic".format(self.topic_top_directory), Message)
        user_checkin_subcriber = Subscriber(self.user_checkin_topic, callback = lambda msg: self.add_AR_user_id(msg.text), transport=self.tx)
        print("subscribed to {}".format(self.user_checkin_topic.name))
        user_checkin_subcriber.subscribe()

        """create the configuration topic, which is used to publish robot configurations the AR interface"""
        configuration_topic = Topic("/{}/configuration_topic".format(self.topic_top_directory), Message)
        self.configuration_publisher = Publisher(configuration_topic, transport=self.tx)

        """create the confirmation topic, which is used to get confirmations from the AR interface"""
        confirmation_topic = Topic("/{}/confirmation_topic".format(self.topic_top_directory), Message)
        self.confirmation_listener = Subscriber(confirmation_topic, callback = lambda msg: self.parse_confirmation(msg), transport=self.tx)

        """create the command topic, which is used to publish to the robot"""	
        command_topic = Topic("/{}/command_topic".format(self.topic_top_directory), Message)
        self.command_publisher = Publisher(command_topic, transport=self.tx)

        thread = threading.Thread(target=self.manage_users, args = (self.AR_users, self._users_to_add, self._users_to_cull), daemon=True)
        thread.start()

    def add_AR_user_id(self, user_id):
        if user_id not in self.AR_users.keys():
            print("adding {}".format(user_id))
            self._users_to_add.append(user_id)

    def send_to_robot(self, command):
        self.command_publisher.publish(Message(text=command))


    def send_to_interface(self, user_id, message):
        msg = Message(text="{}: {}".format(user_id, message))
        self.interface_publisher.publish(msg)


    def manage_users(self, users, to_add, to_cull):
        while True:
            while len(to_add) > 0:
                id = to_add.pop()
                users[id] = ARUser(id, self)
                print("User {} added".format(id))
                self.print_flag = True 
            for user in self.AR_users.values():
                if user.active_flags["to_delete"]:
                    to_cull.append(user.id)
            while len(self._users_to_cull) > 0:
                id = self._users_to_cull.pop()
                print("User {} removed".format(id))
                del users[id]
                self.print_flag = True


    def parse_confirmation(self, message):
        print("on topic {}, recieved message: {}".format(self.confirmation_listener.topic.name, message.text))
        user = self.AR_users.get(message["user_id"])
        if user:
            user.step_confirmations[message["step"]] = message["confirmation"]
        else:
            print("user {} does not exist".format(message["user_id"]))


    def test_messages(self, message, publisher):
        while True:
            publisher.publish(Message(text=message))
            time.sleep(0.1)
            print("user count = {}".format(len(self.AR_users)))
            for user in self.AR_users.values():
                print("user {}: {}".format(user.id, user.message.text))
            time.sleep(1.9)


    def send_configurations(self, step_index, configurations):
        print("send_configurations method called")
        configurations["type"] = "configurations"
        self.interface_publisher.publish(Message(configurations), retain=True)
        for user in self.AR_users.values():
            user.step_confirmations[step_index] = False


    def run(self):
        print("running")
        thread = threading.Thread(target=self.test_messages, args=("master comms", self.interface_publisher), daemon=True)
        thread.start()
        while True:
            print("managing users")
            self.manage_users()
            if self.print_flag:
                print("AR users: {}".format(self.AR_users.keys()))
                self.print_flag = False


class ARUser(object):
    
    def __init__(self, id, parent):
        self.id = id
        self.parent = parent
        self.step_confirmations = {}
        self.active_flags = {"is_active": True, "to_delete": False}
        self.message = None
        self.maintain_user()


    def confirm_active(self, message, active_flags):
        if message.text == str(self.id):
            active_flags["is_active"] = False


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