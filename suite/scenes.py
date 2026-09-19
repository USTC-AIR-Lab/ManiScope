BASE = """adjust_bottle beat_block_hammer blocks_ranking_rgb blocks_ranking_size click_alarmclock click_bell dump_bin_bigbin grab_roller handover_block handover_mic hanging_mug lift_pot move_can_pot move_pillbottle_pad move_playingcard_away move_stapler_pad open_laptop open_microwave pick_diverse_bottles pick_dual_bottles place_a2b_left place_a2b_right place_bread_basket place_bread_skillet place_burger_fries place_can_basket place_cans_plasticbox place_container_plate place_dual_shoes place_empty_cup place_fan place_mouse_pad place_object_basket place_object_scale place_object_stand place_phone_stand place_shoe press_stapler put_bottles_dustbin put_object_cabinet rotate_qrcode scan_object shake_bottle shake_bottle_horizontally stack_blocks_three stack_blocks_two stack_bowls_three stack_bowls_two stamp_seal turn_switch""".split()
assert len(BASE)==50
# (id, dim, tier, name, instruction, deps[1-indexed], core)
S = [
 # D1 skill x object
 ("D1-01","D1",1,"move_cup_pad","Move the cup onto the pad",[16],1),
 ("D1-02","D1",1,"press_novel_bell","Press the call bell",[6,5],1),
 ("D1-03","D1",1,"move_pillbottle_coaster","Move the pill bottle onto the coaster",[14,30],0),
 ("D1-04","D1",2,"place_wineglass_coaster","Put the wine glass on the coaster",[30,28],1),
 ("D1-05","D1",2,"hammer_with_mallet","Beat the block with the wooden mallet",[2],1),
 ("D1-06","D1",2,"stamp_seal_notebook","Stamp the seal onto the notebook",[49],0),
 ("D1-07","D1",1,"place_teabox_scale","Put the tea box on the scale",[34],1),
 ("D1-08","D1",2,"shake_vinegar_bottle","Shake the vinegar bottle",[43,44],0),
 ("D1-09","D1",3,"lift_steamer","Lift the steamer with both hands",[12],1),
 ("D1-10","D1",1,"grab_dumbbell","Grab the dumbbell",[8],0),
 ("D1-11","D1",2,"handover_marker","Hand the marker over to the other arm",[9,10],1),
 ("D1-12","D1",2,"open_notebook_cover","Open the notebook",[17],0),
 ("D1-13","D1",2,"place_book_stand","Put the book on the display stand",[35],1),
 ("D1-14","D1",3,"stack_cups_three","Stack the three cups",[47,48],1),
 ("D1-15","D1",2,"place_shoe_novel","Put the shoe into the shoe box",[37,29],0),
 # D2 skill x spatial
 ("D2-01","D2",1,"place_a2b_left_novel","Put A to the left of B (unseen objects)",[21],1),
 ("D2-02","D2",1,"place_a2b_right_novel","Put A to the right of B (unseen objects)",[22],1),
 ("D2-03","D2",2,"place_a2b_behind_novel","Put A behind B",[21,22],1),
 ("D2-04","D2",2,"place_a2b_front_novel","Put A in front of B",[21,22],1),
 ("D2-05","D2",3,"place_mug_between_bowls","Put the mug between the two bowls",[21,22,48],1),
 ("D2-06","D2",2,"place_cup_right_of_plate","Put the cup to the right of the plate",[21,22,28],1),
 ("D2-07","D2",3,"hang_mug_right_rack","Hang the mug on the right rack",[11,22],1),
 ("D2-08","D2",2,"put_toycar_left_basket","Put the toy car into the left basket",[33,21],0),
 ("D2-09","D2",3,"stack_on_left_block","Stack the block onto the left one",[46,21],1),
 ("D2-10","D2",2,"place_can_left_of_plasticbox","Put the can to the left of the plastic box",[27,21],0),
 ("D2-11","D2",2,"place_bread_left_of_skillet","Put the bread to the left of the skillet",[24,21],0),
 # D3 attribute binding
 ("D3-01","D3",1,"attr_color_bottle","Pick up the green bottle",[1,19],1),
 ("D3-02","D3",2,"attr_color_block_3way","Pick up the blue block (3 colors)",[45,9],1),
 ("D3-03","D3",2,"attr_state_empty_cup","Pick up the empty cup",[30],1),
 ("D3-04","D3",2,"attr_size_block_basket","Put the smaller block into the basket",[4,33],1),
 ("D3-05","D3",2,"attr_category_can_plasticbox","Put the can (not the bottle) into the plastic box",[27,19],1),
 ("D3-06","D3",3,"attr_color_x_category_soap","Pick up the yellow soap",[40,42],1),
 ("D3-07","D3",2,"attr_color_cup_coaster","Put the black cup on the coaster",[30,28],1),
 ("D3-08","D3",3,"attr_rank_second_largest","Put the second largest block on the plate",[4,28],1),
 ("D3-09","D3",3,"attr_color_scan_can","Scan the red can",[42,26],0),
 ("D3-10","D3",1,"attr_color_press_bell","Press the red bell",[6],1),
 ("D3-11","D3",3,"attr_color_dual_bottles","Pick up the two green bottles, one per arm",[20,19],1),
 # D4 instruction structure
 ("D4-01","D4",1,"ref_block_on_plate","Pick up the block on the plate",[28],1),
 ("D4-02","D4",1,"ref_block_in_basket","Pick up the block in the basket",[33],1),
 ("D4-03","D4",2,"ref_block_behind_can","Pick up the block behind the can",[21,22],1),
 ("D4-04","D4",2,"ref_second_from_left","Pick up the second block from the left",[3,45],1),
 ("D4-05","D4",2,"ref_third_from_right","Pick up the third block from the right",[3,45],0),
 ("D4-06","D4",2,"ref_mug_next_to_bowl","Pick up the mug next to the bowl",[11,48],1),
 ("D4-07","D4",2,"ref_not_the_red_one","Pick up the block that is not red",[3],1),
 ("D4-08","D4",2,"ref_cup_on_tray","Pick up the cup on the tray",[25],1),
 ("D4-09","D4",2,"ref_bottle_left_of_can","Pick up the bottle to the left of the can",[19,21],1),
 ("D4-10","D4",3,"ref_cube_on_plate_to_pad","Move the cube on the plate onto the pad",[16,28],1),
 ("D4-11","D4",3,"ref_object_in_drawer","Pick up the object inside the drawer",[40],1),
 # D5 skill x skill temporal
 ("D5-01","D5",2,"adjust_bottle_dustbin","Stand the bottle up, then drop it in the bin",[1,39],1),
 ("D5-02","D5",2,"stapler_pad_press","Move the stapler onto the pad, then press it",[16,38],1),
 ("D5-03","D5",2,"click_bell_press_stapler","Ring the bell, then press the stapler",[6,38],1),
 ("D5-04","D5",2,"shake_bottle_then_coaster","Shake the bottle, then put it on the coaster",[43,30],1),
 ("D5-05","D5",2,"scan_then_basket","Scan the can, then put it in the basket",[42,26],1),
 ("D5-06","D5",3,"rotate_card_then_scan","Turn the card face up, then scan it",[41,42,15],1),
 ("D5-07","D5",3,"open_microwave_put_bread","Open the microwave, then put the bread in",[18,23],1),
 ("D5-08","D5",3,"open_laptop_place_mouse","Open the laptop, then put the mouse on the pad",[17,32],1),
 ("D5-09","D5",3,"saucecan_pot_then_lift","Put the sauce can in the pot, then lift the pot",[13,12],1),
 ("D5-10","D5",3,"bread_basket_then_scan","Put the bread in the basket, then scan it",[23,42],0),
 ("D5-11","D5",3,"phone_stand_then_switch","Put the phone on the stand, then flip the switch",[36,50],1),
 ("D5-12","D5",2,"pick_trash_then_dustbin","Pick up the trash, then drop it in the bin",[39,7],1),
 ("D5-13","D5",2,"stack_block_then_bell","Stack the block, then ring the bell",[46,6],0),
 ("D5-14","D5",2,"alarmclock_then_open_laptop","Turn off the alarm clock, then open the laptop",[5,17],1),
 ("D5-15","D5",3,"dump_bin_then_bell","Empty the desk bin into the trash can, then ring the bell",[7,6],0),
 ("D5-16","D5",2,"place_fan_then_switch","Set the fan upright, then flip the switch",[31,50],1),
 # D7 mixture
 ("D7-01","D7",3,"red_block_left_basket","Put the red block into the left basket",[33,21,3],1),
 ("D7-02","D7",3,"red_block_on_plate_pick","Pick up the red block on the plate",[28,3],1),
 ("D7-03","D7",2,"bigger_block_in_basket","Put the bigger block into the basket",[4,33],1),
 ("D7-04","D7",3,"green_bottle_upright_to_bin","Stand the green bottle up, then recycle it",[1,39,19],1),
 ("D7-05","D7",2,"scan_apple_then_basket","Scan the apple, then bag it",[42,33],1),
 ("D7-06","D7",4,"scan_green_can_on_plate_basket","Scan the green can on the plate, then bag it",[42,28,26],1),
 ("D7-07","D7",4,"sort_two_blocks_two_baskets","Red block in the left basket, blue in the right",[33,21,22,3],1),
 ("D7-08","D7",4,"set_the_table","Plate in the middle, cup on its left, bowl on its right",[28,21,22,30],1),
]
if __name__=="__main__":
    from collections import Counter
    cov=Counter()
    for s in S:
        for d in s[5]: cov[d]+=1
    miss=[BASE[i] for i in range(50) if cov[i+1]==0]
    print("scenes:",len(S))
    print("base tasks covered:",50-len(miss),"/50   missing:",miss)
    print("dim counts:",Counter(s[1] for s in S))
    print("tier counts:",Counter(s[2] for s in S))
    print("core:",sum(s[6] for s in S))
    print("max deps on one base task:",cov.most_common(6))
