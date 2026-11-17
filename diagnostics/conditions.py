"""Conditions of the language-following diagnostics (paper Section 5.3 and Appendices D.5, D.6, E, G).

ROTATION        target reassignment on held-out scenes: the frozen initial states of the formal run; the
                instruction names a different candidate and CompoScene.TARGET is reassigned to it. Each scene
                also gets one empty-instruction condition (the instruction-independent preference).
TRAINING_CONTROL  instruction change on unmodified RoboTwin training tasks: the training instruction, a
                single-attribute pick instruction for each block, and an empty instruction.
SOURCE_TASKS    source-task baseline: the RoboTwin tasks each rotation scene links to, run with their
                training instruction under the same harness.
SELECTION_SCENES  pick-type formal scenes on which selection events and gripper-state contact classes are
                recorded with the formal instructions and frozen seeds.
FIRST_DECISION  first-decision sensitivity: instruction (red / blue) x layout (red and blue blocks exchanged),
                three repeats per condition; the episode stops after the first 16 commands.
"""

# scene -> [(condition, target role, instruction)]
ROTATION = {
    "attr_color_block_3way": [
        ("red", "target", "Pick up the red block."),
        ("green", "d1", "Pick up the green block."),
        ("blue", "d2", "Pick up the blue block."),
    ],
    "ref_not_the_red_one": [
        ("not_red", "target", "Pick up the block that is not red."),
        ("not_blue", "distractor", "Pick up the block that is not blue."),
    ],
    "attr_size_block_pick": [
        ("smaller", "target", "Pick up the smaller block."),
        ("larger", "distractor", "Pick up the larger block."),
    ],
    "attr_size_rank_middle": [
        ("medium", "target", "Pick up the medium block."),
        ("smallest", "small", "Pick up the smallest block."),
        ("largest", "big", "Pick up the largest block."),
    ],
    "ref_second_from_left": [
        ("second_left", "target", "Pick up the second block from the left."),
        ("leftmost", "d1", "Pick up the leftmost block."),
        ("rightmost", "d2", "Pick up the rightmost block."),
    ],
    "ref_leftmost_of_four": [
        ("leftmost", "target", "Pick up the leftmost block."),
        ("second_left", "d1", "Pick up the second block from the left."),
        ("third_left", "d2", "Pick up the third block from the left."),
        ("rightmost", "d3", "Pick up the rightmost block."),
    ],
    "ref_block_on_plate": [
        ("on_plate", "target", "Pick up the block on the plate."),
        ("next_to_plate", "distractor", "Pick up the block next to the plate."),
    ],
    "ref_cup_on_tray": [
        ("on_tray", "target", "Pick up the block on the tray."),
        ("next_to_tray", "distractor", "Pick up the block next to the tray."),
    ],
    "ref_block_behind_can": [
        ("behind_can", "target", "Pick up the block behind the can."),
        ("farther_can", "distractor", "Pick up the block farther from the can."),
    ],
    "ref_mug_next_to_bowl": [
        ("next_to_bowl", "target", "Pick up the mug next to the bowl."),
        ("farther_bowl", "distractor", "Pick up the mug farther from the bowl."),
    ],
}
for _scene, _conds in ROTATION.items():
    _conds.append(("empty", "target", ""))
ROTATION_STATES = 10  # frozen initial states per scene (the first ten of suite/seeds/<scene>.json)

# Instruction change on unmodified RoboTwin training tasks. `None` keeps the task's own training instruction.
TRAINING_CONTROL = {
    "stack_blocks_three": dict(roles={"red": "block1", "green": "block2", "blue": "block3"}, conditions=[
        ("train", None), ("red", "Pick up the red block."), ("green", "Pick up the green block."),
        ("blue", "Pick up the blue block."), ("empty", "")]),
    "blocks_ranking_rgb": dict(roles={"red": "block1", "green": "block2", "blue": "block3"}, conditions=[
        ("train", None), ("red", "Pick up the red block."), ("green", "Pick up the green block."),
        ("blue", "Pick up the blue block."), ("empty", "")]),
    # three blocks of random colour that differ only in size (block1 largest, block3 smallest)
    "blocks_ranking_size": dict(roles={"largest": "block1", "medium": "block2", "smallest": "block3"}, conditions=[
        ("train", None), ("largest", "Pick up the largest block."), ("medium", "Pick up the medium block."),
        ("smallest", "Pick up the smallest block."), ("empty", "")]),
}
TRAINING_CONTROL_SEEDS = (0, 1, 2, 3)  # RoboTwin seeds; episodes per seed are set on the command line

# RoboTwin source tasks each rotation scene links to (from the scene docstrings).
SOURCE_LINKS = {
    "attr_color_block_3way": ["stack_blocks_three", "handover_block"],
    "attr_size_block_pick": ["blocks_ranking_size", "stack_blocks_three"],
    "attr_size_rank_middle": ["blocks_ranking_size", "place_container_plate"],
    "ref_block_on_plate": ["place_container_plate"],
    "ref_block_behind_can": ["place_a2b_left", "place_a2b_right"],
    "ref_cup_on_tray": ["place_burger_fries"],
    "ref_leftmost_of_four": ["blocks_ranking_rgb", "stack_blocks_three"],
    "ref_mug_next_to_bowl": ["hanging_mug", "stack_bowls_two"],
    "ref_not_the_red_one": ["blocks_ranking_rgb"],
    "ref_second_from_left": ["blocks_ranking_rgb", "stack_blocks_three"],
}
SOURCE_TASKS = sorted({t for ts in SOURCE_LINKS.values() for t in ts})
# The other 20 RoboTwin tasks that any of the 48 scenes links to; with SOURCE_TASKS, the 30 linked source tasks.
SOURCE_TASKS_EXTRA = ["place_object_basket", "place_cans_plasticbox", "grab_roller", "click_bell", "place_bread_skillet",
                      "beat_block_hammer", "scan_object", "rotate_qrcode", "place_empty_cup", "place_bread_basket",
                      "pick_diverse_bottles", "move_stapler_pad", "stamp_seal", "place_phone_stand", "place_object_stand",
                      "place_object_scale", "place_can_basket", "open_laptop", "lift_pot", "click_alarmclock"]
SOURCE_SEEDS = (0, 1)

# Pick-type formal scenes for gripper-state contact classes (formal instructions, frozen seeds).
SELECTION_SCENES = ["attr_color_block_3way", "attr_size_block_pick", "attr_size_rank_middle", "attr_bind_bottle",
                    "attr_bind_soap_box", "ref_block_on_plate", "ref_block_behind_can", "ref_cup_on_tray",
                    "ref_leftmost_of_four", "ref_mug_next_to_bowl", "ref_not_the_red_one", "ref_second_from_left"]
# The eleven selection scenes of the failure decomposition (formal run, 100 episodes per scene and policy).
DECOMPOSITION_SCENES = ["attr_color_block_3way", "attr_size_block_pick", "attr_size_rank_middle", "attr_bind_bottle",
                        "ref_block_on_plate", "ref_block_behind_can", "ref_cup_on_tray", "ref_leftmost_of_four",
                        "ref_mug_next_to_bowl", "ref_not_the_red_one", "ref_second_from_left"]
DISPLACEMENT_M = 0.05  # an object counts as selected once it is displaced this far from its initial position

FIRST_DECISION = dict(task="attr_color_block_3way", colors=(("red", "target"), ("blue", "d2")),
                      layouts=("original", "swapped"), swap="target,d2", repeats=3, states=20, commands=16)
