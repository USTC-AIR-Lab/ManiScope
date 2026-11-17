"""policy.GPT6.local_bridge for the relay: GPT-6 performs only the first stage on the object the
instruction refers to and then finishes; a learned policy (DM0.5) continues from there.
RELAY_STAGE selects where control is handed over:
  hover     open gripper about 8 cm above the object
  pregrasp  open gripper lowered around the object at grasp height
  grasp     gripper closed on the object, not lifted
The relay reported in the paper hands over at pregrasp. Run from the repository root with the local_bridge
arguments."""
import os
import sys

sys.path.insert(0, os.getcwd())
import policy.GPT6.local_bridge as lb  # noqa: E402

STAGES = {
    "hover": "keep that gripper fully open and move it so the gripper hovers about 8 cm directly above "
             "that object, pointing down, without touching anything. Do not grasp, lift or place. As soon "
             "as the open gripper is above the object, call finish",
    "pregrasp": "keep that gripper fully open, align it above that object pointing down, then lower it so "
                "the open fingers are on either side of the object at grasp height, without pushing the "
                "object or touching anything else. Do not close the gripper, lift or place. As soon as the "
                "open fingers surround the object, call finish",
    "grasp": "grasp that object: align above it pointing down, lower the open gripper around it and close "
             "the gripper on it. Do not lift or place it. As soon as the gripper is closed on the object, "
             "call finish",
}

lb.PROMPT = lb.PROMPT + f"""
RELAY MODE (overrides the task-completion rules above): you perform only the first stage. Identify
the single object the user's instruction refers to, choose the arm closer to it, and
{STAGES[os.environ.get("RELAY_STAGE", "pregrasp")]} with a note naming the object; a learned
visuomotor policy then takes over and completes the instruction. Use as few calls as possible.
"""

if __name__ == "__main__":
    lb.main()
