import math
from compas.geometry import Frame
from compas.geometry import Vector
from compas.datastructures import Mesh
from compas_fab.robots import AttachedCollisionMesh
from compas_fab.robots import CollisionMesh
from compas_fab.robots import Robot
from compas_fab.robots import JointConstraint
from compas_fab.robots import PlanningScene


class TimberAssemblyPlanner(object):
    def __init__(self, robot, assembly, building_plan, scene_objects = None, group = None, planner_id = None):
        self.robot = robot
        self.assembly = assembly
        self.building_plan = building_plan
        self.group = group or self.robot.main_group_name
        self.attached_beam_meshes = []
        self.planner_id = str(planner_id) if planner_id else "RRTConnect"
        self.current_configuration = self.start_configuration 
        self.robot_steps = {}
        self.scene_objects = scene_objects
            

    def plan_robot_steps(self):
        for index, step in enumerate(self.building_plan.steps):
            if step["actor"] == "ROBOT":
                robot_step =  RobotStep(self.robot, index, step, self.building_plan, self.assembly, scene_objects=self.scene_objects, group=self.group)
                robot_step.plan()
                self.robot_steps[index] = robot_step

    def get_configurations(self, trajectories):
        configurations = []
        for trajectory in trajectories:
            for point in trajectory.points:
                config = self.robot.merge_group_with_full_configuration(point, self.safe_configuration, self.group)
                configurations.append(config)



    



class RobotStep(object):
    TOLERANCE_POSITION = 0.001          # 1 mm tolerance on position
    TOLERANCE_AXES = [1.0, 1.0, 1.0]    # 1 degree tolerance per axis

    def __init__(self, robot, index, step, building_plan, assembly, pickup_frame, scene_objects = None, path_constraints = None, group = None):
        self.robot = robot
        self.group = group
        self.index = index
        self.step = step
        self.building_plan = building_plan
        self.assembly = assembly
        self.beam = assembly.beams[step["element_ids"][0]]
        self.target_frame = Frame(self.beam.midpoint, self.beam.frame.xaxis, self.beam.frame.yaxis)
        self.scene = PlanningScene(robot)
        for mesh in scene_objects:
                self.scene.add_collision_meshes(CollisionMesh(mesh, "scene_mesh"))
        self.add_assembly_collision_meshes()
        self.trajectories = {}
        self.attached_collision_meshes = []
        self.path_constraints = list(path_constraints) if path_constraints else []
        self.path_constraints.extend(self.global_constraints)
        self.pickup_station_frame = pickup_frame

    def plan(self): 
        self.go_to_pickup(self.pickup_frame())
        self.grab_beam(Mesh.from_shape(self.beam.geometry))
        self.move_beam(self.get_target_frame())
        self.release_beam()
        self.retract()
        return self.trajectories


    def get_pickup_frame(self):
        beam = self.assembly.beams[self.step["element_ids"][0]]
        pickup_frame = Frame(beam.midpoint, beam.frame.xaxis, beam.frame.yaxis)
        return pickup_frame

    def add_assembly_collision_meshes(self):
        for i in range(0, self.index-1):                                                                        #all the steps before this one
            earlier_step = self.building_plan.steps[i]         
            for id in earlier_step["element_ids"]:                                                              #the ids of the beam objects in those steps    
                cm = CollisionMesh(Mesh.from_shape(self.assembly.beams[id].geometry), "beam_mesh_{}".format(i)) #create a collision mesh from the beam mesh and append to self.collision_meshes
                self.scene.add_collision_meshes(cm) 


    def go_to_pickup(self, pickup_frame):
        trajectories = []
        pickup_frame_offset = self.offset_frame(pickup_frame, 0.2)
        trajectories.append(self.get_trajectory(pickup_frame_offset))                     
        trajectories.append(self.get_trajectory(pickup_frame, linear=True))               
        self.trajectories["pickup"] = trajectories


    def move_beam(self, target_frame, approach_vector = None):
        trajectories = []
        pickup_frame_offset = self.offset_frame(self.current_frame,  0.2)
        if approach_vector:
            approach_frame = Frame(target_frame.point - approach_vector, target_frame.xaxis, target_frame.yaxis)
        else:
            approach_frame = self.offset_frame(target_frame, 0.5)      
        trajectories.append(self.get_trajectory(pickup_frame_offset, linear=True))
        trajectories.append(self.get_trajectory(approach_frame))
        trajectories.append(self.get_trajectory(target_frame, linear=True))
        self.trajectories["move"] = trajectories


    def retract(self):
        trajectories = []
        offset_frame = Frame(self.current_frame.point - self.current_frame.zaxis*0.5, self.current_frame.xaxis, self.current_frame.yaxis)
        trajectories.append(self.get_trajectory(offset_frame, linear=True))
        trajectories.append(self.get_trajectory(self.robot.forward_kinematics(self.safe_position, self.group)))
        self.trajectories["retract"] = trajectories


    def grab_beam(self, mesh):
        self.attached_collision_meshes = list(AttachedCollisionMesh(CollisionMesh(mesh, "0"), 'robot11_tool0', touch_links = ['robot11_link_6']))


    def release_beam(self):
        self.attached_collision_meshes = []


    def offset_frame(self, frame, offset):
        return Frame(frame.point - frame.zaxis * offset, frame.xaxis, frame.yaxis)


    def get_trajectory(self, target_frame, linear = False):
        if (self.robot.client and self.robot.client.is_connected):
            options = dict(
                    attached_collision_meshes = self.attached_collision_meshes,
                    path_constraints=self.path_constraints,
                    planner_id=self.planner_id
                    )
            if linear:
                this_trajectory = self.robot.plan_cartesian_motion([self.current_frame, target_frame], start_configuration=self.current_configuration, group=self.group, options = options)
            else:
                constraints = self.robot.constraints_from_frame(target_frame, RobotStep.TOLERANCE_POSITION, RobotStep.TOLERANCE_AXES, self.group)
                this_trajectory = self.robot.plan_motion(constraints, start_configuration=self.current_configuration, group=self.group, options = options)
        return this_trajectory


    @property
    def current_configuration(self):
        if len(self.trajectories) == 0:
            return self.safe_configuation
        else:
            return self.trajectories[-1].points[-1]


    @property
    def current_frame(self):
        return self.robot.forward_kinematics(self.current_configuration, self.group)
    

    @property
    def safe_configuation(self):
        configuration = self.robot.zero_configuration()
        configuration['robot11_joint_EA_Z'] = -4.5
        configuration['robot11_joint_2'] = 0
        configuration['robot11_joint_3'] = -math.pi/2
        configuration['bridge1_joint_EA_X'] = 9

        """ get robot_12 out of the way """
        configuration['robot12_joint_EA_Y'] = -12
        configuration['robot12_joint_EA_Z'] = -4.5
        configuration['robot12_joint_2'] = math.pi/2
        return configuration


    @property
    def global_constraints(self):
        constraints = []
        constraints.append(JointConstraint('robot11_joint_2', 0, -0.1, 0.1, 0.5))
        constraints.append(JointConstraint('robot11_joint_3', -math.pi/2, -0.1, 0.1, 0.5))
        constraints.append(JointConstraint('bridge1_joint_EA_X', 9, 3, 3, 1.0))
        return constraints
    

    @property
    def pickup_frame(self):
        offset_vector = [
            (self.beam.length / 2) * self.pickup_station_frame.xaxis,
            self.beam.width / 2 * self.pickup_station_frame.yaxis,
            self.beam.height / 2 * self.pickup_station_frame.zaxis
            ]
        return Frame(self.pickup_station_frame.point + offset_vector, self.pickup_station_frame.xaxis , self.pickup_station_frame.yaxis)
        