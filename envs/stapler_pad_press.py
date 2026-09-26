from ._base_task import Base_Task
from .utils import *
import sapien
import os
import sys
import json
import random


class stapler_pad_press(Base_Task):
    """Sequential stapler placement and pressing for evaluation. The stapler is dynamic for placement; the expert explicitly latches the released placement before pressing. Optional staged instruction delivery uses privileged stage state."""

    # Staged instructions use move_stapler_pad then press_stapler templates with their respective placeholders. Switching uses privileged stage state and is an oracle protocol.


    #


    STAGED_INSTRUCTION = os.environ.get("STAPLER_STAGED_INSTRUCTION", "1") == "1"
    # move uses the placement instruction first; same uses the press instruction throughout without oracle switching. Fixed wording is an optional diagnostic control.


    STAGE1_TEMPLATE = os.environ.get("STAPLER_STAGE1_TEMPLATE", "move")
    # Use the configured seen/unseen pool. Fixed wording is an optional diagnostic control over instruction variation.
    INSTRUCTION_TYPE = os.environ.get("STAPLER_INSTRUCTION_TYPE", "unseen")

    INSTRUCTION_PIN = os.environ.get("STAPLER_INSTRUCTION_PIN", "0") == "1"

    def setup_demo(self, **kwags):
        # Retain the source table bias and stapler spawn region. The stapler must be dynamic because stage 1 lifts it.
        super()._init_task_env_(**kwags)

    def load_actors(self):

        def sample_stapler():
            return rand_pose(
                xlim=[-0.25, 0.25],
                ylim=[-0.2, 0.0],
                qpos=[0.5, 0.5, 0.5, 0.5],
                rotate_rand=True,
                rotate_lim=[0, np.pi, 0],
            )

        rand_pos = sample_stapler()
        for _ in range(100):
            if abs(rand_pos.p[0]) >= 0.05:
                break
            rand_pos = sample_stapler()

        self.stapler_id = np.random.choice([0, 1, 2, 3, 4, 5, 6], 1)[0]

        self.stapler = create_actor(
            scene=self,
            pose=rand_pos,
            modelname="048_stapler",
            convex=True,
            model_id=self.stapler_id,
        )

        # Restrict the pad to the stapler side and the press-task region. Bound rejection sampling and fall back to the far end of the x interval.
        xlim = [0.05, 0.2] if rand_pos.p[0] > 0 else [-0.2, -0.05]

        def sample_pad():
            return rand_pose(xlim=xlim, ylim=[-0.1, 0.0], qpos=[1, 0, 0, 0], rotate_rand=False)

        target_rand_pose = sample_pad()

        for _ in range(200):
            d = np.sqrt((target_rand_pose.p[0] - rand_pos.p[0])**2 + (target_rand_pose.p[1] - rand_pos.p[1])**2)
            if d >= 0.1:
                break
            target_rand_pose = sample_pad()
        else:
            far_x = xlim[1] if abs(xlim[1] - rand_pos.p[0]) > abs(xlim[0] - rand_pos.p[0]) else xlim[0]
            target_rand_pose = sapien.Pose([far_x, -0.05, target_rand_pose.p[2]], [1, 0, 0, 0])

        colors = {
            "Red": (1, 0, 0),
            "Green": (0, 1, 0),
            "Blue": (0, 0, 1),
            "Yellow": (1, 1, 0),
            "Cyan": (0, 1, 1),
            "Magenta": (1, 0, 1),
            "Black": (0, 0, 0),
            "Gray": (0.5, 0.5, 0.5),
        }
        color_items = list(colors.items())
        self.color_name, self.color_value = color_items[np.random.choice(len(color_items))]

        self.pad = create_box(
            scene=self.scene,
            pose=target_rand_pose,
            half_size=[0.055, 0.03, 0.0005],
            color=self.color_value,
            name="box",
        )
        self.add_prohibit_area(self.stapler, padding=0.1)
        self.add_prohibit_area(self.pad, padding=0.15)

        self.pad_pose = self.pad.get_pose().p.tolist() + [0.707, 0, 0, 0.707]
        # Both stages use the same arm. Initialize placeholders during actor loading, not only play_once.
        self.arm_tag = ArmTag("right" if rand_pos.p[0] > 0 else "left")
        self.stage = 0


        self._stapler_asset = f"048_stapler/base{self.stapler_id}"
        self._stage_instructions = None

    # ------------------------------------------------------------------ #
    # Expert feasibility rollout: stage 1 follows the adjust_bottle action sequence.
    # ------------------------------------------------------------------ #
    def play_once(self):
        arm_tag = self.arm_tag

        # Stage 1: move_stapler_pad sequence, then retreat so press planning can start and placement can settle.
        self.move(self.grasp_actor(self.stapler, arm_tag=arm_tag, pre_grasp_dis=0.1))
        self.move(self.move_by_displacement(arm_tag, z=0.1, move_axis="arm"))
        self.move(
            self.place_actor(
                self.stapler,
                target_pose=self.pad_pose,
                arm_tag=arm_tag,
                pre_dis=0.1,
                dis=0.0,
                constrain="align",
            ))


        self.move(self.move_by_displacement(arm_tag, z=0.1))

        # Explicitly latch stage 1 during the expert sequence: the final check alone occurs with closed grippers and would miss the earlier released placement.


        #
        # Check placement twice with settling between checks to avoid a transient false negative.

        self.stage_reward()
        self.delay(4)
        self.stage_reward()

        # Stage 2: press the stapler. Placement uses the actual pad footprint; orientation is not a placement prerequisite here.
        self.move(
            self.grasp_actor(self.stapler, arm_tag=arm_tag, pre_grasp_dis=0.1, grasp_dis=0.1, contact_point_id=2))
        self.move(self.close_gripper(arm_tag=arm_tag))
        self.move(
            self.grasp_actor(self.stapler, arm_tag=arm_tag, pre_grasp_dis=0.02, grasp_dis=0.02, contact_point_id=2))

        self.info["info"] = {
            "{A}": self._stapler_asset,
            "{B}": self.color_name,
            "{a}": str(arm_tag),
        }
        return self.info

    # ------------------------------------------------------------------ #
    # Success predicates and staged instructions.
    # ------------------------------------------------------------------ #
    def _on_pad(self):
        """Check stapler placement on the pad with released grippers."""
        stapler_pose = self.stapler.get_pose().p
        stapler_qpose = np.abs(self.stapler.get_pose().q)
        target_pos = self.pad.get_pose().p


        eps = np.array([0.055, 0.035, 0.02])
        return bool(
            np.all(np.abs(stapler_pose - target_pos) < eps)
            and self.robot.is_left_gripper_open()
            and self.robot.is_right_gripper_open())

    def _pressed(self):
        """Check pressing using the press_stapler predicate."""
        stapler_pose = self.stapler.get_contact_point(2)[:3]
        eps = [0.03, 0.03]
        for position in self.get_gripper_actor_contact_position("048_stapler"):
            if (np.all(np.abs(position[:2] - stapler_pose[:2]) < eps) and abs(position[2] - stapler_pose[2]) < 0.03):
                return True
        return False

    def stage_reward(self):
        # Require placement before pressing; pressing at the initial location must not satisfy the sequence.

        if self.stage >= 1 and self._pressed() and np.all(
                np.abs(self.stapler.get_pose().p - self.pad.get_pose().p) < np.array([0.055, 0.035, 0.02])):
            self.stage = 2
        elif self.stage < 1 and self._on_pad():
            self.stage = 1
        return self.stage / 2.0

    def check_success(self):
        self.stage_reward()
        return self.stage >= 2

    # ------------------------------------------------------------------ #

    # ------------------------------------------------------------------ #
    @staticmethod
    def _instruction_gen():
        """Load instruction utilities relative to this file rather than relying on the caller working directory."""
        utils_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "description", "utils")
        if utils_dir not in sys.path:
            sys.path.append(utils_dir)
        from generate_episode_instructions import generate_episode_descriptions
        return generate_episode_descriptions

    @staticmethod
    def _repo_root():
        return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def _pick_object_desc(self, asset, rng):
        """Choose and cache an asset description so both stages use the same name."""
        path = os.path.join(self._repo_root(), "description", "objects_description", asset + ".json")
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        pool = data.get(self.INSTRUCTION_TYPE) or data.get("seen") or []
        return f"the {rng.choice(pool)}" if pool else "the stapler"

    def _build_stage_instructions(self):
        """Generate and cache one instruction per stage; do not resample wording on each control step."""
        gen = self._instruction_gen()
        rng = random.Random(0) if self.INSTRUCTION_PIN else random.Random()
        if self.INSTRUCTION_PIN:
            # Seed the global shuffle used by filter_instructions; provide task-specific placeholder sets ({a} is optional).
            random.seed(0)

        stapler = self._pick_object_desc(self._stapler_asset, rng)
        arm = str(self.arm_tag)
        # Match placeholder sets exactly, cache one sentence per stage, and retain the compound instruction for fallback.
        stage2 = ("press_stapler", {"{A}": stapler, "{a}": arm})
        stage1 = (("move_stapler_pad", {"{A}": stapler, "{B}": self.color_name, "{a}": arm})
                  if self.STAGE1_TEMPLATE != "same" else stage2)

        def one(task_name, params):
            cands = gen(task_name, [params], 100)
            pool = cands[0].get(self.INSTRUCTION_TYPE, []) if cands else []
            if not pool:  # Fall back to seen templates if unseen is empty.
                pool = cands[0].get("seen", []) if cands else []
            if not pool:
                return None
            return pool[0] if self.INSTRUCTION_PIN else str(rng.choice(pool))

        if self.STAGE1_TEMPLATE == "same":

            only = one(*stage2)
            return None if only is None else (only, only)

        first, second = one(*stage1), one(*stage2)
        return None if (first is None or second is None) else (first, second)

    def set_instruction(self, instruction=None):

        super().set_instruction(instruction=instruction)
        self._stage_instructions = None
        if not self.STAGED_INSTRUCTION:
            return
        try:
            self._stage_instructions = self._build_stage_instructions()
        except Exception as e:
            print(f"[stapler_pad_press] Staged instruction generation failed; using compound instruction: {e}")
            self._stage_instructions = None

    def get_instruction(self, instruction=None):
        if not self.STAGED_INSTRUCTION or not self._stage_instructions:
            return super().get_instruction(instruction=instruction)
        self.stage_reward()  # Stage progress is monotonic: completing adjustment remains recorded even if later disposal fails.
        return self._stage_instructions[0 if self.stage < 1 else 1]
