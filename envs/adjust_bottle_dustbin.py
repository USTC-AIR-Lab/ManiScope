from ._base_task import Base_Task
from .utils import *
import sapien
import os
import random
import sys
import json


class adjust_bottle_dustbin(Base_Task):
    """Sequential upright adjustment and bottle disposal for evaluation. Uses the adjust_bottle pose and left-arm put_bottles_dustbin routine. Optional staged instructions and scripted bridges use privileged simulator state and must be reported separately from end-to-end runs."""

    # Keep the grasp after upright adjustment by default. Releasing requires a new grasp and can bias expert-feasibility filtering; COMBO_RELEASE_AFTER_ADJUST enables that diagnostic variant.
    #


    #


    #


    RELEASE_AFTER_ADJUST = os.environ.get("COMBO_RELEASE_AFTER_ADJUST", "0") == "1"
    BOTTLE_MODEL = os.environ.get("COMBO_BOTTLE", "001_bottle")
    # Use bottle variant 13 by default; COMBO_BOTTLE_ID=random restores sampling from variants 13 and 16.


    BOTTLE_ID = os.environ.get("COMBO_BOTTLE_ID", "13")

    # Prefill the bin with two static background bottles to approximate the last disposal stage. They are excluded from success and prohibit-area checks.
    #


    #


    DUSTBIN_PREFILL = int(os.environ.get("COMBO_DUSTBIN_PREFILL", "2"))

    # Staged instructions use adjust_bottle at stage 0 and single-bottle disposal templates afterward. Switching uses privileged simulator stage state and must be reported as oracle instruction delivery. COMBO_STAGED_INSTRUCTION=0 uses the compound instruction.


    #


    STAGED_INSTRUCTION = os.environ.get("COMBO_STAGED_INSTRUCTION", "1") == "1"
    # Use the configured seen/unseen pool. Fixed wording is an optional diagnostic control over instruction variation.
    INSTRUCTION_TYPE = os.environ.get("COMBO_INSTRUCTION_TYPE", "unseen")


    INSTRUCTION_PIN = os.environ.get("COMBO_INSTRUCTION_PIN", "0") == "1"

    # Stage-2 templates: hold uses transport verbs (default); throw uses disposal verbs; grasp includes a new pickup. Select wording consistent with whether the bottle is already held.


    #


    #


    STAGE2_TEMPLATE = os.environ.get("COMBO_STAGE2_TEMPLATE", "hold")

    # Stage-1 templates: adjust requests upright adjustment; same uses the stage-2 sentence throughout with no oracle switch. The grasp variant is appropriate when same starts with the bottle on the table.


    #


    #


    STAGE1_TEMPLATE = os.environ.get("COMBO_STAGE1_TEMPLATE", "adjust")
    _STAGE2_TASKS = {
        "hold": "_combo_stage_dustbin_hold",
        "throw": "_combo_stage_dustbin_throw",
        "grasp": "_combo_stage_dustbin",
    }

    # Optional stage bridge lowers only end-effector z to BRIDGE_Z, preserving xy and orientation. Disabled by default; this scripted, simulator-stage intervention is not an end-to-end policy action.


    #


    STAGE2_BRIDGE = os.environ.get("COMBO_STAGE2_BRIDGE", "0") == "1"
    BRIDGE_Z = float(os.environ.get("COMBO_BRIDGE_Z", "0.93"))

    def setup_demo(self, **kwags):
        # Shift the table in +x to leave clearance above the bin. Actor positions use world coordinates and do not shift with the table.


        super()._init_task_env_(table_xy_bias=[float(os.environ.get("COMBO_TABLE_BIAS", "0.38")), 0], **kwags)

    def load_actors(self):
        # Use the left-side lying pose from adjust_bottle; bin-prefill objects are background scenery.
        self.qpose_tag = 0
        self.model_id = (int(np.random.choice([13, 16]))
                         if self.BOTTLE_ID == "random" else int(self.BOTTLE_ID))
        self.bottle = rand_create_actor(
            self,
            xlim=[-0.12, -0.08],
            ylim=[-0.13, -0.08],
            zlim=[0.752],
            rotate_rand=True,
            qpos=[0.707, 0.0, 0.0, -0.707],
            modelname=self.BOTTLE_MODEL,
            convex=True,
            rotate_lim=(0, 0, 0.4),
            model_id=self.model_id,
        )
        self.delay(4)
        self.add_prohibit_area(self.bottle, padding=0.15)

        self.dustbin = create_actor(
            self.scene,
            pose=sapien.Pose([-0.45, 0, 0], [0.5, 0.5, 0.5, 0.5]),
            modelname="011_dustbin",
            convex=True,
            is_static=True,
        )
        self.delay(2)


        #
        # Prefill bottles must be static to avoid failing scene stability checks. Their resting heights approximate disposed bottles; scaled length is 0.216 m and diameter 0.069 m.


        #


        self.prefill_bottles = []
        for i in range(max(0, self.DUSTBIN_PREFILL)):
            b = create_actor(
                self.scene,
                pose=sapien.Pose([-0.45 + 0.05 * i, 0.07 - 0.14 * i, 0.22 + 0.05 * i],
                                 [0.707, 0.0, 0.707, 0.0]),   # Use a lying pose and the source task variant IDs.
                modelname="114_bottle",
                convex=True,
                model_id=i + 1,
                is_static=True,
            )
            self.prefill_bottles.append(b)

        # This upright-placement target affects play_once and expert feasibility, not the evaluated policy rollout. Changing it can change accepted seeds; the optional bridge separately addresses handover height.
        #


        #


        self.left_target_pose = [-0.22, 0.10, 0.95, 0, 1, 0, 0]
        # Release pose above the bin follows put_bottles_dustbin.left_end_action.
        self.dustbin_drop_action = [-0.35, -0.1, 0.93, 0.65, -0.25, 0.25, 0.65]
        self.stage = 0

        # Initialize staged-instruction placeholders in load_actors, which runs on every reset. Stage 1 uses {A} and optional {a}; stage 2 uses {A}{B}. Placeholder sets must match exactly.


        self._bottle_asset = f"{self.BOTTLE_MODEL}/base{self.model_id}"
        self._dustbin_asset = "011_dustbin/base0"
        self._stage_instructions = None
        self._bridged = False

    # ------------------------------------------------------------------ #
    # Expert feasibility rollout: stage 1 follows the adjust_bottle action sequence.
    # ------------------------------------------------------------------ #
    def play_once(self):
        arm_tag = ArmTag("left")


        self.move(self.grasp_actor(self.bottle, arm_tag=arm_tag, pre_grasp_dis=0.1))
        self.move(self.move_by_displacement(arm_tag=arm_tag, z=0.1, move_axis="arm"))
        self.move(
            self.place_actor(
                self.bottle,
                target_pose=self.left_target_pose,
                arm_tag=arm_tag,
                functional_point_id=0,
                pre_dis=0.0,
                is_open=False,
            ))

        # Expert mode does not poll check_success at every physics step.
        # Observe the completed first stage before starting the second.
        self.stage_reward()

        if self.RELEASE_AFTER_ADJUST:
            # Optional release, retreat, and regrasp before disposal.
            self.move(self.open_gripper(arm_tag))
            self.move(self.move_by_displacement(arm_tag=arm_tag, z=0.1))
            self.move(self.grasp_actor(self.bottle, arm_tag=arm_tag, pre_grasp_dis=0.1))
            self.move(self.move_by_displacement(arm_tag=arm_tag, z=0.1))

        # Stage 2 follows the left-arm put_bottles_dustbin sequence.
        self.move((arm_tag, [Action("left", "move", self.dustbin_drop_action)]))
        self.move(self.open_gripper(arm_tag))

        self.info["info"] = {
            "{A}": f"{self.BOTTLE_MODEL}/base{self.model_id}",
            "{B}": "011_dustbin/base0",
            "{a}": str(arm_tag),
        }
        return self.info

    # ------------------------------------------------------------------ #
    # Success predicates and staged instructions.
    # ------------------------------------------------------------------ #
    def _is_upright_on_left(self):
        """Check the left-side position requirement and upward alignment of the bottle long axis."""
        pose = self.bottle.get_functional_point(0)
        # Bottle asset geometry is elongated along its local neck axis.
        # Functional point 0 is near the grasp center, not the bottle cap.
        extents=np.asarray(self.bottle.config['extents'])*np.asarray(self.bottle.config.get('scale',1))
        axis=int(np.argmax(extents))
        rotation=self.bottle.get_pose().to_transformation_matrix()[:3,:3]
        return bool(pose[0] < -0.15 and pose[2] > 0.9 and rotation[2,axis] > 0.85)

    def _is_in_dustbin(self):
        """Check bottle containment using the put_bottles_dustbin predicate."""
        target_pose = [-0.45, 0]
        eps = np.array([0.221, 0.325])
        p = self.bottle.get_pose().p
        return bool(np.all(np.abs(p[:2] - target_pose) < eps) and 0.2 < p[2] < 0.7)

    # ------------------------------------------------------------------ #

    # ------------------------------------------------------------------ #
    @staticmethod
    def _instruction_gen():
        """Load instruction utilities relative to this file rather than relying on the caller working directory."""
        utils_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                 "description", "utils")
        if utils_dir not in sys.path:
            sys.path.append(utils_dir)
        from generate_episode_instructions import generate_episode_descriptions
        return generate_episode_descriptions

    @staticmethod
    def _repo_root():
        return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def _pick_object_desc(self, asset, rng):
        """Choose one asset description with an article and cache it for the episode so both stages use the same object name."""
        path = os.path.join(self._repo_root(), "description", "objects_description", asset + ".json")
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        pool = data.get(self.INSTRUCTION_TYPE) or data.get("seen") or []
        return f"the {rng.choice(pool)}" if pool else "the object"

    def _build_stage_instructions(self):
        """Generate and cache one instruction per stage; do not resample wording on each control step."""
        gen = self._instruction_gen()
        rng = random.Random(0) if self.INSTRUCTION_PIN else random.Random()
        if self.INSTRUCTION_PIN:
            # Seed the global shuffle used by filter_instructions; provide task-specific placeholder sets ({a} is optional).
            random.seed(0)

        bottle = self._pick_object_desc(self._bottle_asset, rng)
        dustbin = self._pick_object_desc(self._dustbin_asset, rng)

        stage2_task = self._STAGE2_TASKS.get(self.STAGE2_TEMPLATE, self._STAGE2_TASKS["hold"])

        stage2 = (stage2_task, {"{A}": bottle, "{B}": dustbin})
        stage1 = (("adjust_bottle", {"{A}": bottle, "{a}": "left"})
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
            # Return the identical sentence for both stages, not two samples from one pool.
            only = one(*stage2)
            return None if only is None else (only, only)

        first, second = one(*stage1), one(*stage2)
        return None if (first is None or second is None) else (first, second)

    def set_instruction(self, instruction=None):
        # Retain the supplied compound instruction for logging and fallback; staged delivery returns the cached per-stage sentences.

        super().set_instruction(instruction=instruction)
        self._stage_instructions = None
        if not self.STAGED_INSTRUCTION:
            return
        try:
            self._stage_instructions = self._build_stage_instructions()
        except Exception as e:
            # On generation failure, use the compound instruction and do not retry on every control step.
            print(f"[adjust_bottle_dustbin] Staged instruction generation failed; using compound instruction: {e}")
            self._stage_instructions = None

    def maybe_bridge_to_stage2(self):
        """Optionally lower end-effector z once before stage-2 policy control, retaining xy and orientation. This is a scripted oracle intervention."""
        if not self.STAGE2_BRIDGE or self._bridged:
            return False
        self.stage_reward()
        if self.stage < 1:
            return False
        self._bridged = True
        try:
            pose = list(np.asarray(self.get_arm_pose(ArmTag("left")), dtype=float)[:7])
            if pose[2] <= self.BRIDGE_Z:
                return False
            pose[2] = self.BRIDGE_Z
            self.move((ArmTag("left"), [Action("left", "move", pose)]))
            return True
        except Exception as e:
            print(f"[adjust_bottle_dustbin] Stage-2 bridge failed; returning control unchanged: {e}")
            return False

    def get_instruction(self, instruction=None):
        if not self.STAGED_INSTRUCTION or not self._stage_instructions:
            return super().get_instruction(instruction=instruction)
        self.stage_reward()  # Stage progress is monotonic: completing adjustment remains recorded even if later disposal fails.
        return self._stage_instructions[0 if self.stage < 1 else 1]

    def stage_reward(self):


        if self.stage >= 1 and self._is_in_dustbin():
            self.stage = 2
        elif self.stage < 1 and self._is_upright_on_left():
            self.stage = 1
        return self.stage / 2.0

    def check_success(self):
        self.stage_reward()
        return self.stage >= 2 and self._is_in_dustbin()
