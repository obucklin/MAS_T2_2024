from timber_assembly_planner import TimberAssemblyPlanner
import time

from compas_eve import Message
from compas_eve import Publisher
from compas_eve import Subscriber
from compas_eve import Topic
from compas_eve.mqtt import MqttTransport
from executor_communicator import ExecutorCommunicator


class TimberAssemblyExecutioner(object):
    def __init__(self, ros_client, assembly, building_plan, scene_objects = None, group = None, planner_id = None):
        self.ros_client = ros_client
        self.assembly = assembly
        self.building_plan = building_plan
        self.robot = self.ros_client.load_robot()
        self.comms = ExecutorCommunicator()
        self.planner = TimberAssemblyPlanner(self.robot, self.assembly, self.building_plan)
        self.planner.plan_robot_assembly()

    def add_AR_users(self, user_id):
        if user_id not in self.AR_users.keys():
            self.AR_users[user_id] = ARUser(user_id)
            print("User {} added".format(user_id))
        else:
            self.AR_users[user_id].last_seen = time.monotonic()

    def cull_inactive_users(self):
        if time.monotonic() - self.user_timeout_start > 60:  # every 60 seconds
            for user in self.AR_users.values():
                if self.user_timeout_start > user.last_seen:
                    print("User {} removed".format(user.id))
                    del user
            self.user_timeout_start = time.monotonic()

    def run(self):
        while True:
            self.execute_()

    def execute_(self):

        step, index = self.get_current_step()
        if step["actor"] == "ROBOT":
            self.execute_step(index)


    def get_current_step(self):
        for index, step in self.building_plan.steps:
            if step['is_built'] == 'false':
                return (step, index)
            

    def execute_step(self, index):
        self.execute_robot_motion(self.planner.trajectories[index]["pickup"])
        self.close_gripper()
        self.execute_robot_motion(self.planner.trajectories[index]["move"])
        self.open_gripper()
        self.execute_robot_motion(self.planner.trajectories[index]["retract"])
        self.building_plan.steps[index]["is_built"] = "true"


    def execute_robot_motion(self, configurations):
        self.send_configs_to_app(configurations)
        self.await_command()
        self.execute_trajectory(configurations)


    def send_configs_to_app(self, trajectories):
        configs = {}
        index = 0
        for trajectory in trajectories:
            for config in trajectory.points:
                configs[index] = config
                index += 1
        self.publisher.publish(configs.to_json())


    def await_command(self):
        while True:
            if self.ros_client.is_command_ready():
                break
            time.sleep(0.1)


    def execute_trajectory(self, trajectory):
        self.ros_client.execute_trajectory(trajectory)


class ARUser(object):
    def __init__(self, id):
        self.id = id
        self.confirm_step = {}
        self.last_seen = time.monotonic()

    def send_command(self, command):
        self.ros_client.send_command(command)


if __name__ == '__main__':
    executioner = TimberAssemblyExecutioner()
    executioner.run()
    pass