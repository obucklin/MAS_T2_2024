from timber_assembly_planner import TimberAssemblyPlanner

class TimberAssemblyExecutioner(object):
    def __init__(self, ros_client, assembly, building_plan, scene_objects = None, group = None, planner_id = None):
        self.ros_client = ros_client
        self.assembly = assembly
        self.building_plan = building_plan
        self.robot = self.ros_client.load_robot()

        self.planner = TimberAssemblyPlanner(self.robot, self.assembly, self.building_plan)
        self.planner.plan_robot_steps()


    def __main__(self):
        step, index = self.get_current_step()
        if step["actor"] == "ROBOT":
            self.execute_step(index)


    def get_current_step(self):
        for index, step in self.building_plan.steps:
            if step['is_built'] == 'false':
                return (step, index)
            

    def execute_step(self, index):
        self.execute_substep(self.planner.trajectories[index]["pickup"])
        self.close_gripper()
        self.execute_substep(self.planner.trajectories[index]["move"])
        self.open_gripper()
        self.execute_substep(self.planner.trajectories[index]["retract"])


    def execute_substep(self, configurations):
        self.send_configs(configurations)
        self.await_command()
        self.execute_trajectory(configurations)


    def send_configs(self, trajectories):
        configs = []
        for trajectory in trajectories:
            for config in trajectory.points:
                configs.append(config)
        send(configs.to_json())


    def await_command(self):
        while True:
            if self.ros_client.is_command_ready():
                break
            time.sleep(0.1)


    def execute_trajectory(self, trajectory):
        self.ros_client.execute_trajectory(trajectory)