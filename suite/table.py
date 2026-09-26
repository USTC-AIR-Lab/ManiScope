# -*- coding: utf-8 -*-
"""Declarative candidate scene table. L/R/C denote reachable spawn regions, deps identifies linked RoboTwin tasks, and GOAL supplies both expert action composition and final predicates."""
L  = [[-0.24, -0.14], [-0.15, -0.04]]
R  = [[0.14, 0.24], [-0.15, -0.04]]
C  = [[-0.05, 0.05], [-0.14, -0.04]]
LL = [[-0.26, -0.18], [-0.15, -0.05]]
RR = [[0.18, 0.26], [-0.15, -0.05]]
CB = [[-0.05, 0.05], [0.0, 0.08]]      # Reference/container region toward the rear.
L3, C3, R3 = [[-0.24, -0.17], [-0.13, -0.05]], [[-0.04, 0.04], [-0.13, -0.05]], [[0.17, 0.24], [-0.13, -0.05]]

QU = [1, 0, 0, 0]          # Upright pose.
QS = [0.5, 0.5, 0.5, 0.5]  # Side pose used by baskets, plates and bells.
QL = [0.707, 0.707, 0, 0]  # Lying pose for cans or toy cars, independent of side.
QM = [0.707, 0.707, 0, 0]  # Tested cup, mug and toy-car poses.
# Use side-dependent lying bottle/can poses; a shared quaternion can make one grasp side infeasible.

LR = [[0.707, 0.0, 0.0, -0.707], [0.707, 0.0, 0.0, 0.707]]

def box(role, color, region, half=0.025, desc=None, **kw):
    d = {"role": role, "kind": "box", "color": color, "half": half, "region": region}
    if desc: d["desc"] = desc
    d.update(kw); return d

def mdl(role, model, ids, region, qpos=QU, **kw):
    d = {"role": role, "kind": "model", "model": model, "ids": ids, "region": region, "qpos": qpos}
    d.update(kw); return d

def pad(role="pad", region=C, color=(0.45, 0.45, 0.45), **kw):
    d = {"role": role, "kind": "box", "color": color, "half_size": [0.055, 0.055, 0.0005],
         "region": region, "rot": False, "zlim": [0.7415], "pad": 0.12, "desc": "pad"}
    d.update(kw)   # Allow slot overrides such as side and side_x.
    return d

RED, BLUE, GREEN, GRAY, ORANGE = (0.9,0.15,0.15), (0.15,0.3,0.9), (0.15,0.75,0.2), (0.45,0.45,0.45), (0.95,0.6,0.1)

CL = [[-0.13, -0.03], [-0.15, -0.04]]   # Keep the destination on the compatible side, slightly behind the source for containers.
CBL = [[-0.10, -0.02], [-0.02, 0.06]]

def S(id, name, dim, tier, deps, ctx, instr, goal, spec, desc=None, mirror=False, note="",
      shuffle_slots=None, nearest=None):
    # shuffle_slots permutes attribute-task roles to prevent location shortcuts; do not use it when position is the ordinal cue.


    # nearest validates that the target is closer to the reference than its rivals, resampling distractors if necessary.

    return dict(id=id, name=name, dim=dim, tier=tier, deps=deps, ctx=ctx, instr=instr,
                goal=goal, spec=spec, desc=desc, mirror=mirror, note=note,
                shuffle_slots=shuffle_slots, nearest=nearest)

SCENES = [
# ============================== D1 skill × object ==============================
S("D1-01","move_cup_pad","D1",1,[16],"Office desk","Move the {A} onto the pad.",
  {"type":"on","ref":"pad"},
  [mdl("target","021_cup",[0,1,2,3,4,5],L,QS), pad(region=CL)], desc="cup"),
S("D1-03","move_can_coaster","D1",1,[26,30],"Bedside supplies","Put the {A} on the coaster.",
  {"type":"on","ref":"coaster"},
  [mdl("target","071_can",[0,1,2],L,[0.5,0.5,0.5,0.5],rot=False),
   # Keep pill bottles upright with the source-task quaternion and rotate_rand=False.


   mdl("coaster","019_coaster",[0],CL,QS,static=True,pad=0.05)], desc="pill bottle"),
S("D1-05","grasp_mallet_novel","D1",2,[2,8],"Workbench","Pick up the {A}.",
  # Use the configured clearance threshold and retain gripped-clearance diagnostics; dragging on the table is not a lift.


  {"type":"lift","dz":0.035},
  [mdl("target","084_woodenmallet",[0,1,2,3,4],L,QL)], desc="wooden mallet"),
S("D1-07","place_teabox_scale","D1",1,[34],"Supermarket weighing","Put the {A} on the scale.",
  {"type":"on","ref":"scale"},
  [mdl("target","112_tea-box",[0,1,2,3,4,5],L,QU),
   mdl("scale","072_electronicscale",[0,1,2],CL,QS,static=True,pad=0.06)], desc="tea box"),
S("D1-08","place_seal_coaster","D1",2,[49,30],"Kitchen preparation","Put the {A} on the coaster.",
  {"type":"on","ref":"coaster"},
  [mdl("target","100_seal",[0,1,2,3],L,[0.5,0.5,0.5,0.5],rot=False),
   mdl("coaster","019_coaster",[0],CL,QS,static=True,pad=0.05)], desc="seal"),
S("D1-09","lift_trophy","D1",2,[8],"Kitchen preparation","Pick up the {A}.",
  {"type":"lift","dz":0.06},
  [mdl("target","090_trophy",[0,1,2,3,4],L,QU,mass=0.2)], desc="trophy"),
S("D1-10","grab_dumbbell","D1",1,[8],"Exercise area","Pick up the {A}.",
  {"type":"lift","dz":0.035},
  [mdl("target","052_dumbbell",[0,1,2,3,4,5,6],L,QL)], desc="dumbbell"),
S("D1-12","place_teabox_stand","D1",2,[35],"Bookshelf","Put the {A} on the display stand.",
  {"type":"on","ref":"stand"},
  [mdl("target","112_tea-box",[0,1,2],L,QU),
   mdl("stand","074_displaystand",[0,1,2,3,4],CL,QS,static=True,pad=0.06)], desc="tea box"),
S("D1-14","place_toycar_plasticbox","D1",2,[33,27],"Entryway","Put the {A} into the plastic box.",
  {"type":"in","ref":"box","r":0.13},
  [mdl("target","057_toycar",[0,1,2,3,4,5],L,QM),
   mdl("box","062_plasticbox",[3,5],CBL,QS,mass=0.6,pad=0.05)], desc="toy car"),
S("D1-15","place_teabox_skillet","D1",2,[24],"Kitchen preparation","Put the {A} into the skillet.",
  # The tea box can be off-center within the wide skillet opening.
  {"type":"in","ref":"skillet","r":0.16},
  [mdl("target","112_tea-box",[0,1,2,3,4],L,QU),
   mdl("skillet","106_skillet",[0,1,2,3],CBL,QS,mass=0.6,pad=0.05)], desc="tea box"),
]

SCENES += [
# ============================== D2 skill × spatial ==============================
S("D2-01","place_a2b_left_novel","D2",1,[21],"General tabletop","Put the {A} to the left of the mug.",
  {"type":"rel","ref":"ref","dir":"left","gap":[0.05,0.24],"lat":0.13},
  [mdl("target","073_rubikscube",[0,1,2],L,QU),
   mdl("ref","039_mug",[0,1,2,3],CL,QS,static=True,pad=0.06)], desc="cube"),
S("D2-02","place_a2b_right_novel","D2",1,[22],"General tabletop","Put the {A} to the right of the mug.",
  {"type":"rel","ref":"ref","dir":"right","gap":[0.05,0.24],"lat":0.13},
  [mdl("target","073_rubikscube",[0,1,2],LL,QU),
   mdl("ref","039_mug",[0,1,2,3],[[-0.15,-0.09],[-0.15,-0.04]],QS,static=True,pad=0.06)], desc="cube"),
S("D2-05","place_between_bowls","D2",3,[21,22,48],"Table setting","Put the {A} between the two bowls.",
  {"type":"between","refs":["b1","b2"],"lat":0.10},
  [mdl("target","073_rubikscube",[0,1,2],[[-0.24,-0.18],[-0.15,-0.08]],QU),
   mdl("b1","002_bowl",[1,2,3],[[-0.16,-0.12],[-0.04,0.02]],QS,static=True,pad=0.05),
   mdl("b2","002_bowl",[4,5,6],[[-0.02,0.02],[-0.04,0.02]],QS,static=True,pad=0.05)], desc="cube"),
S("D2-06","place_cube_right_of_plate","D2",2,[21,22,28],"Table setting","Put the {A} to the right of the plate.",
  # The right-of gap must exceed plate radius so a target still over the plate does not pass.

  {"type":"rel","ref":"plate","dir":"right","gap":[0.14,0.26],"lat":0.13},
  [mdl("target","073_rubikscube",[0,1,2],LL,QU),
   mdl("plate","003_plate",[0],[[-0.16,-0.10],[-0.14,-0.04]],QS,static=True,pad=0.05)], desc="cube"),
S("D2-08","put_toycar_left_basket","D2",2,[33,21],"Household sorting","Put the {A} into the left basket.",
  {"type":"in","ref":"basket_l","r":0.12},
  [mdl("target","057_toycar",[0,1,2,3,4,5],LL,[0.707,0.707,0,0]),
   mdl("basket_l","110_basket",[0,1],[[-0.14,-0.08],[0.0,0.06]],QS,mass=0.5,pad=0.05),
   # Move the right basket farther out to clear the toy-car grasp path.
   mdl("basket_r","110_basket",[2,3],[[0.10,0.16],[0.0,0.06]],QS,mass=0.5,pad=0.05,
       side=1,side_x=0.195)], desc="toy car"),
S("D2-10","place_can_right_of_plasticbox","D2",2,[27,21],"Storage shelf","Put the {A} to the right of the plastic box.",
  # Require uprightness for placement so rolling a fallen can into the region does not pass.

  {"type":"rel","ref":"pbox","dir":"right","gap":[0.05,0.24],"lat":0.14,"upright":True},
  [mdl("target","071_can",[0,1,2,3],L,QU,rot=False,half=0.035),
   mdl("pbox","062_plasticbox",[3,5],[[-0.04,0.02],[-0.06,0.02]],QS,static=True,pad=0.06,side=-1)],
  desc="can",
  note="Use right-of placement with the reference on the left to leave reachable destination space. "
       "The source and destination must fit within the configured workspace."),
S("D2-11","place_teabox_front_of_skillet","D2",2,[24,21],"Kitchen preparation","Put the {A} in front of the skillet.",
  {"type":"rel","ref":"skillet","dir":"front","gap":[0.05,0.22],"lat":0.14},
  [mdl("target","112_tea-box",[0,1,2,3,4],[[-0.24,-0.16],[-0.02,0.06]],QU),
   mdl("skillet","106_skillet",[0,1,2,3],[[-0.16,-0.06],[-0.02,0.06]],QS,static=True,pad=0.06)], desc="tea box"),
]

# Combine the configured lift/displacement requirement with target-selection exclusivity; origin rise from upright adjustment alone is insufficient.


LIFT = {"type": "lift", "dz": 0.06}

SCENES += [
# D3 attribute binding across object properties and actions.
S("D3-02","attr_color_block_3way","D3",2,[45,9],"Block arrangement","Pick up the {A}.", LIFT,
  [box("target",RED,L3,desc="red block"), box("d1",GREEN,C3), box("d2",BLUE,R3)],
  desc="red block", shuffle_slots=['target', 'd1', 'd2'], mirror=True, note="Three-way color selection"),
S("D3-04","attr_size_block_pick","D3",2,[4,45],"Block arrangement","Pick up the {A}.", LIFT,
  [box("target",GRAY,LL,half=0.016,desc="smaller block"),
   box("distractor",GRAY,[[-0.24,-0.18],[-0.02,0.06]],half=0.030)],
  desc="smaller block", mirror=True,
  note="Size selection using liftable bare blocks. "
       "Container-placement requirements are evaluated in separate scenes."),
S("D3-05","attr_category_can_plasticbox","D3",2,[27,19],"Storage shelf","Put the {A} into the plastic box.",
  {"type":"in","ref":"pbox","r":0.13},
  [mdl("target","071_can",[0,1,2,3],LL,QL,desc="can"),
   mdl("distractor","001_bottle",[13,16],[[-0.24,-0.18],[-0.02,0.06]],QL),
   mdl("pbox","062_plasticbox",[3,5],CBL,QS,mass=0.6,pad=0.05)],
  desc="can", note="Category selection with container placement"),
S("D3-08","attr_size_rank_middle","D3",3,[4,28],"Household sorting","Pick up the {A}.", LIFT,
  [box("target",GRAY,C3,half=0.023,desc="medium block"),
   box("small",GRAY,L3,half=0.015), box("big",GRAY,R3,half=0.031)],
  shuffle_slots=['target', 'd1', 'd2'], desc="medium block", note="Select the middle-sized object among three candidates"),
S("D3-10","attr_category_press_bell","D3",1,[6,5],"Reception desk","Press the {A}.",
  {"type":"press","ref":"target","model":"050_bell","cp":0},
  [mdl("target","050_bell",[0,1],L,QS,mass=0.3,pad=0.1,desc="bell"),
   mdl("distractor","046_alarm-clock",[0,1,2],R,QS,mass=0.3,pad=0.1)],
  desc="bell", mirror=True,
  note="Attribute selection with a press action rather than grasping"),

# D4 referring expressions: relational, ordinal, adjacent and negated targets.
S("D4-01","ref_block_on_plate","D4",1,[28],"Table clearing","Pick up the {A}.", LIFT,
  [mdl("plate","003_plate",[0],L,QS,static=True,pad=0.03),
   {"role":"target","kind":"box","color":ORANGE,"half":0.025,"rel":"plate","offset":[0,0,0.035],
    "desc":"block on the plate"},
   box("distractor",ORANGE,R)], desc="block on the plate", mirror=True,
  note="Visually identical blocks identified by their relation to a plate"),
# The former basket-block candidate was excluded; use the current scene membership.

S("D4-03","ref_block_behind_can","D4",2,[21,22],"General tabletop","Pick up the {A}.", LIFT,
  [mdl("can","071_can",[0,1,2],[[-0.20,-0.14],[-0.14,-0.08]],[0.5,0.5,0.5,0.5],rot=False,static=True,pad=0.03),
   {"role":"target","kind":"box","color":ORANGE,"half":0.025,"rel":"can","offset":[0,0.11,-0.02],
    "desc":"block behind the can"},
   box("distractor",ORANGE,R)], desc="block behind the can", mirror=True),
S("D4-04","ref_second_from_left","D4",2,[3,45],"Block arrangement","Pick up the {A}.", LIFT,
  [box("d1",ORANGE,L3), box("target",ORANGE,C3,desc="second block from the left"), box("d2",ORANGE,R3)],
  desc="second block from the left", note="Ordinal selection; disable MIRROR because mirroring changes the answer"),
S("D4-05","ref_leftmost_of_four","D4",2,[3,45],"Block arrangement","Pick up the {A}.", LIFT,
  [box("target",ORANGE,[[-0.26,-0.22],[-0.13,-0.05]],desc="leftmost block"),
   box("d1",ORANGE,[[-0.13,-0.09],[-0.13,-0.05]]), box("d2",ORANGE,[[0.00,0.04],[-0.13,-0.05]]),
   box("d3",ORANGE,[[0.13,0.17],[-0.13,-0.05]])], desc="leftmost block",
  note="Ordinal selection among four candidates"),
S("D4-06","ref_mug_next_to_bowl","D4",2,[11,48],"Table clearing","Pick up the {A}.", LIFT,
  # Keep the requested mug clearly nearer to the bowl than the distractor. Disable mirroring because relative offsets are not mirrored.


  [mdl("bowl","002_bowl",[1,2,3],[[-0.18,-0.12],[-0.12,-0.04]],QS,static=True,pad=0.03),
   {"role":"target","kind":"model","model":"039_mug","ids":[0,1,2],"rel":"bowl","offset":[-0.10,0,0],
    "qpos":QS,"desc":"mug next to the bowl"},
   mdl("distractor","039_mug",[0,1,2],[[0.15,0.22],[-0.14,-0.04]],QS)], desc="mug next to the bowl",
  mirror=True, nearest={"who":"target","ref":"bowl","rivals":["distractor"],"ratio":1.6}),
S("D4-07","ref_not_the_red_one","D4",2,[3],"Block arrangement","Pick up the {A}.", LIFT,
  [box("target",BLUE,L,desc="block that is not red"), box("distractor",RED,R)],
  desc="block that is not red", mirror=True, note="Negated referring expression"),
S("D4-08","ref_cup_on_tray","D4",2,[25],"Food pickup","Pick up the {A}.", LIFT,
  [mdl("tray","008_tray",[0,1,2,3],L,QS,static=True,pad=0.03),
   {"role":"target","kind":"box","color":ORANGE,"half":0.025,"rel":"tray","offset":[0,0,0.035],
    "desc":"block on the tray"},
   box("distractor",ORANGE,R)], desc="block on the tray", mirror=True),
]

def seq(*g): return {"type": "seq", "stages": list(g)}
def ON(ref, who=None, dz=0.03, eps=(0.05,0.05,0.035)):
    d = {"type":"on","ref":ref,"dz":dz,"eps":list(eps)}
    if who: d["who"]=who
    return d
def IN(ref, who=None, r=0.12):
    d = {"type":"in","ref":ref,"r":r}
    if who: d["who"]=who
    return d
def PRESS(ref, model, cp=0):
    return {"type":"press","ref":ref,"model":model,"cp":cp}
def REL(ref, dir, who=None, gap=(0.05,0.22), lat=0.14):
    d = {"type":"rel","ref":ref,"dir":dir,"gap":list(gap),"lat":lat}
    if who: d["who"]=who
    return d
BELL = lambda region=[[-0.06,0.00],[0.02,0.08]]: mdl("bell","050_bell",[0,1],region,QS,mass=0.3,pad=0.08)

SCENES += [
# D5 ordered skill composition with distinct dependent actions.
S("D5-02","serve_teabox_then_ring","D5",2,[23,6],"Kitchen preparation",
  "Put the {A} into the basket, then press the bell.",
  seq(IN("breadbasket"), PRESS("bell","050_bell")),
  [mdl("target","112_tea-box",[0,1,2,3],LL,QU,desc="tea box"),
   mdl("breadbasket","110_basket",[0,1,2,3],[[-0.14,-0.08],[-0.02,0.05]],QS,mass=0.5,pad=0.05),
   BELL()], desc="tea box", note="Place the item, then ring the bell"),
S("D5-06","pack_toycar_then_ring","D5",3,[33,27,6],"Entryway",
  "Put the {A} into the plastic box, then press the bell.",
  seq(IN("box", r=0.13), PRESS("bell","050_bell")),
  [mdl("target","057_toycar",[0,1,2,3,4,5],LL,QM,desc="toy car"),
   mdl("box","062_plasticbox",[3,5],[[-0.14,-0.08],[-0.02,0.05]],QS,mass=0.6,pad=0.05),
   BELL()], desc="toy car"),

# ================================ D7 mixture ================================
S("D7-06","attr_teabox_basket_then_ring","D7",3,[23,6,19],"Kitchen preparation",
  "Put the {A} into the basket, then press the bell.",
  seq(IN("breadbasket"), PRESS("bell","050_bell")),
  [mdl("target","112_tea-box",[0,1,2],[[-0.28,-0.23],[-0.14,-0.07]],QU,desc="tea box"),
   mdl("distractor","035_apple",[0,1],[[-0.28,-0.23],[0.01,0.07]],QU),
   mdl("breadbasket","110_basket",[0,1,2,3],[[-0.16,-0.10],[-0.02,0.05]],QS,mass=0.5,pad=0.05),
   BELL([[-0.02,0.04],[0.02,0.08]])], desc="tea box", note="Attributes x sequence"),

# Additional candidate scenes use tested graspable objects; exclude unsupported microwave insertion geometry.


  S("D1-16","roller_to_plate","D1",2,[8,28],"Kitchen preparation","Put the {A} on the plate.",
    {"type":"on","ref":"plate"},
    [mdl("target","102_roller",[0,1,2],C,[0.5,0.5,0.5,0.5],rot=False),
     mdl("plate","003_plate",[0],CL,QS,static=True,pad=0.05)], desc="rolling pin",
    note="Use the roller handling skill, then place it on the plate"),

  S("D2-12","card_right_of_scanner","D2",2,[41,42,22],"Checkout counter",
    "Put the {A} to the right of the barcode scanner.",
    {"type":"rel","ref":"scanner","dir":"right","gap":[0.05,0.22],
     # Require a minimum initial separation from the scanner, not merely failure of the final predicate.


     "min_start":0.18},
    [mdl("target","070_paymentsign",[0,1,2],C,[0.5,0.5,0.5,0.5],rot=False),
     mdl("scanner","024_scanner",[0,1,2,3,4],CL,[0,0,0.707,0.707],static=True,pad=0.08)],
    desc="payment card",
    note="Payment-card object with a spatial-relation goal"),

  S("D2-13","phone_right_of_laptop","D2",2,[17,36,22],"Office desk",
    "Put the {A} to the right of the laptop.",
    {"type":"rel","ref":"laptop","dir":"right","gap":[0.05,0.22]},
    # Create the laptop before its relatively placed phone. The phone starts on the laptop and must move right without overlap.


    [{"role":"laptop","kind":"urdf","model":"015_laptop","ids":[0],
      "region":[[-0.16,-0.06],[-0.06,0.04]],"qpos":[0.7,0,0,0.7],"rot":False,
      "fix_root":True,"mass":1.0,"pad":0.08},
     {"role":"target","kind":"model","model":"077_phone","ids":[0,1,2,3],
      "rel":"laptop","offset":[0,0,0.07],"qpos":[0.5,0.5,0.5,0.5],"desc":"phone"}],
    desc="phone",
    note="Spatial phone/laptop placement; laptop opening is not a goal here"),


  # Use lift_pot_to_pad to include placement after the source lift skill.


# Hammer tasks reuse beat_block_hammer actions and contact predicates. Static target blocks are scored by contact location, not displacement.


S("D3-12","attr_color_beat_block","D3",2,[2,45],"Block arrangement",
  "Beat the {A} with the hammer.",
  {"type":"beat","tool":"hammer"},
  [mdl("hammer","020_hammer",[0],[[-0.02,0.02],[-0.08,-0.04]],[0,0,0.995,0.105],
       rot=False,zlim=[0.783],mass=0.001),
   # Separate block regions so random rotations do not produce overlap.
   box("target",(0.55,0.20,0.75),[[-0.22,-0.17],[0.01,0.07]],half=0.025,static=True,zlim=[0.76],desc="purple block"),
   box("d1",(0.10,0.65,0.62),[[-0.03,0.03],[0.01,0.07]],half=0.025,static=True,zlim=[0.76]),
   box("d2",(0.92,0.82,0.15),[[0.17,0.22],[0.01,0.07]],half=0.025,static=True,zlim=[0.76])],
  desc="purple block", shuffle_slots=["target","d1","d2"],
  note="Select purple, cyan or yellow blocks according to the instruction"),
S("D3-13","attr_size_beat_smaller","D3",2,[2,4],"Block arrangement",
  "Beat the {A} with the hammer.",
  {"type":"beat","tool":"hammer"},
  [mdl("hammer","020_hammer",[0],[[-0.02,0.02],[-0.08,-0.04]],[0,0,0.995,0.105],
       rot=False,zlim=[0.783],mass=0.001),
   box("target",(0.10,0.65,0.62),[[-0.24,-0.16],[0.01,0.07]],half=0.020,static=True,zlim=[0.76],desc="smaller block"),
   box("d1",(0.10,0.65,0.62),[[0.16,0.24],[0.01,0.07]],half=0.038,static=True,zlim=[0.76])],
  desc="smaller block", shuffle_slots=["target","d1"],
  note="Same-color objects with different sizes"),
S("D5-11","lift_pot_to_pad","D5",3,[12,16],"Kitchen preparation",
  "Lift the {A} with both arms and put it on the pad.",
  {"type":"dual_carry_to","ref":"pad","dz":0.06,"eps":[0.09,0.09]},
  # Use fix_root=False for the pot so it can be lifted.
  [{"role":"target","kind":"urdf","model":"060_kitchenpot","ids":[0,1],"fix_root":False,
    # Retain the source lift_pot spawn region and keep the pad close enough for coordinated dual-arm IK.
    "region":[[-0.05,0.05],[-0.05,0.05]],"qpos":[0.704141,0,0,0.71006],"rot":True,"rotlim":[0,0,0.39]},

   pad(region=[[0.09,0.13],[-0.05,0.05]])], desc="pot",
  note="Lift the pot with both handles, move it to the pad, then release"),
]
