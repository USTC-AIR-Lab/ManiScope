"""One small EEF movement through the policy adapter, without any API calls.
Run from the RoboTwin-Compo root. Results are not a benchmark trial.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd()))
import argparse
import json
import time
import cv2
import numpy as np
import yaml
from envs.attr_color_bottle_basket import attr_color_bottle_basket
from envs.utils.create_actor import UnStableError
from policy.GPT6.deploy_policy import eval as policy_eval, get_model


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--seed", type=int, default=100000)
    parser.add_argument("--mock-bridge-url")
    parser.add_argument("--bridge-token-file")
    args = parser.parse_args()
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    cfg = yaml.safe_load(Path("task_config/demo_clean.yml").read_text())
    emb = yaml.safe_load(Path("task_config/_embodiment_config.yml").read_text())
    robot_path = emb[cfg["embodiment"][0]]["file_path"]
    robot_cfg = yaml.safe_load((Path(robot_path)/"config.yml").read_text())
    camera = yaml.safe_load(Path("task_config/_camera_config.yml").read_text())[cfg["camera"]["head_camera_type"]]
    cfg.update(task_name="attr_color_bottle_basket", task_config="demo_clean", eval_mode=True,
               left_robot_file=robot_path, right_robot_file=robot_path, dual_arm_embodied=True,
               left_embodiment_config=robot_cfg, right_embodiment_config=robot_cfg,
               head_camera_h=camera["h"], head_camera_w=camera["w"],
               save_path=str(out), collect_data=False, save_data=False, eval_video_log=False)
    env = attr_color_bottle_basket()
    start = time.monotonic()
    try:
        for scene_seed in range(args.seed, args.seed + 8):
            try:
                env.setup_demo(now_ep_num=0, seed=scene_seed, is_test=True, **cfg)
                break
            except UnStableError:
                env.close_env()
                if scene_seed == args.seed + 7:
                    raise
        env.set_instruction("Pick up the green bottle and place it in the basket.")
        obs = env.get_obs()
        for name in ("head_camera", "left_camera", "right_camera"):
            cv2.imwrite(str(out/(name+".png")), cv2.cvtColor(obs["observation"][name]["rgb"], cv2.COLOR_RGB2BGR))

        class FakeLocalBridge:
            calls, limit, feedback = 0, 1, None
            def request(self, route, payload):
                assert route == "/infer"
                assert set(payload) == {"instruction", "images", "eef_state", "joint_state", "feedback", "step"}
                (out/"observation_metadata.json").write_text(json.dumps({k:v for k,v in payload.items() if k != "images"}, indent=2))
                pose = payload["eef_state"]["left_endpose"]
                return {"type": "move_eef", "arm": "left", "position": [pose[0], pose[1], pose[2]+0.01],
                        "quaternion_wxyz": pose[3:], "gripper": payload["eef_state"]["left_gripper"],
                        "note": "Smoke test: lift empty hand 1 cm; no model involved."}

        model = (get_model({"base_url": args.mock_bridge_url, "bridge_token_file": args.bridge_token_file,
                            "max_llm_calls": 1}) if args.mock_bridge_url else FakeLocalBridge())
        after = policy_eval(env, model, obs)
        actual = np.asarray(after["endpose"]["left_endpose"][:3])-np.asarray(obs["endpose"]["left_endpose"][:3])
        report = {"smoke_only": True, "api_calls": 0, "seed": scene_seed,
                  "elapsed_seconds": time.monotonic()-start, "left_translation_m": actual.tolist(),
                  "feedback": model.feedback, "passed": bool(abs(actual[2]-0.01)<0.005 and np.linalg.norm(actual[:2])<0.005)}
        (out/"smoke_result.json").write_text(json.dumps(report, indent=2))
        print(json.dumps(report), flush=True)
        if not report["passed"]:
            raise RuntimeError("EEF movement did not match the requested small displacement")
    finally:
        env.close_env()


if __name__ == "__main__":
    main()
