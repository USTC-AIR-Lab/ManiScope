"""Physical joint sensors. RoboTwin's get_*_gripper_val returns a command."""
import math

def gripper_aperture(robot, side):
    entity = getattr(robot, side + '_entity')
    joint, multiplier, offset = getattr(robot, side + '_gripper')[0]
    joints = entity.get_active_joints()
    # RoboTwin ALOHA active joints are one-DOF; mirror its real-joint getter.
    index = joints.index(joint)
    position = float(entity.get_qpos()[index])
    closed, opened = map(float, getattr(robot, side + '_gripper_scale'))
    if not math.isfinite(position) or abs(opened - closed) < 1e-12 or abs(multiplier) < 1e-12:
        raise ValueError('Invalid physical gripper sensor or calibration')
    position = (position - offset) / multiplier
    return max(0., min(1., (position - closed) / (opened - closed)))

def measured_joint_vector(robot):
    result = []
    for side in ('left', 'right'):
        result.extend(float(x) for x in getattr(robot, 'get_' + side + '_arm_real_jointState')()[:-1])
        result.append(gripper_aperture(robot, side))
    return result
