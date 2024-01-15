from timber_assembly_planner import TimberAssemblyPlanner
import threading
import time

from executor_communicator import ExecutorCommunicator


class TimberAssemblyExecutioner(object):
    def __init__(self, ros_client = None, assembly = None, building_plan = None, scene_objects = None, group = None, planner_id = None):
        self.ros_client = ros_client
        self.assembly = assembly
        self.building_plan = building_plan
        # self.robot = self.ros_client.load_robot()
        print("instanting communicator")
        self.comms = ExecutorCommunicator("broker.hivemq.com", "T2_command_test")
        # self.planner = TimberAssemblyPlanner(self.robot, self.assembly, self.building_plan)
        # self.planner.plan_robot_assembly()

    def run(self):
        print("running executioner")
        dummy_configs = [[0,15,3,0,468,0,86,488,56,79,56], [0,15,3,0,468,0,86,488,56,79,56]]

        self.execute_robot_motion(0, dummy_configs)

        # thread = threading.Thread(target=self.send_configs_to_app, args=(0,dummy_configs,), daemon=True)
        # thread.start()
        while True:
            pass

            # self.execute_()

    def execute_(self):
        step, index = self.get_current_step()
        if step["actor"] == "ROBOT":
            self.execute_step(index)

    def plan_next_robot_step(self):
        for index, step in self.building_plan.steps:
            if step['actor'] == 'ROBOT' and step['is_built'] == 'false':
                self.planner.plan_robot_assembly(index)


    def get_first_unbuilt_step(self):
        for index, step in self.building_plan.steps:
            if step['is_built'] == 'false':
                return (step, index)
            

    def execute_step(self, step_index):
        self.execute_robot_motion(step_index, self.planner.trajectories[step_index]["pickup"])
        self.close_gripper()
        self.execute_robot_motion(step_index, self.planner.trajectories[step_index]["move"])
        self.open_gripper()
        self.execute_robot_motion(step_index, self.planner.trajectories[step_index]["retract"])
        self.building_plan.steps[step_index]["is_built"] = "true"


    def execute_robot_motion(self, step_index, configurations):
        self.send_configs_to_app(step_index, configurations)
        if self.await_confirmation(step_index):
            self.execute_trajectory(configurations)
        time.sleep(5)

    def send_configs_to_app(self, step_index, configurations):
        print("sending configs")
        configs = {"type": "configurations", "step": step_index}
        index = 0
        for config in configurations:
            print("config = {}".format(config))
            configs[index]=(config)
            index += 1
        self.comms.send_configurations(step_index, configs)
        print("configs sent")


    def await_confirmation(self, step_index):
        print("awaiting confirmation")
        while True:
            if len(self.comms.AR_users) == 0:
                print("no users")
                time.sleep(1)
                continue
            confirmed = True
            for user in self.comms.AR_users.values():
                confirmed = confirmed and user.step_confirmations.get(step_index, False) 
                if confirmed:
                    print("user {} confirmed step {}".format(user.id, step_index))                   
            if confirmed:
                print("step {} confirmed".format(step_index))
                return True
            

    def execute_trajectory(self, trajectory):
        print("executing trajectory")


if __name__ == '__main__':
    print("instanting executioner")
    exc = TimberAssemblyExecutioner()
    exc.run()
    pass