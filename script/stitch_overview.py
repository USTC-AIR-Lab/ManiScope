# 取每个任务一张代表图(默认 ep00)拼成总览大图，带序号+任务名标注。
import os, glob, argparse
from PIL import Image, ImageDraw, ImageFont

DEFAULT_TASKS = ["adjust_bottle","beat_block_hammer","blocks_ranking_rgb","blocks_ranking_size","click_alarmclock",
"click_bell","dump_bin_bigbin","grab_roller","handover_block","handover_mic","hanging_mug","lift_pot",
"move_can_pot","move_pillbottle_pad","move_playingcard_away","move_stapler_pad","open_laptop","open_microwave",
"pick_diverse_bottles","pick_dual_bottles","place_a2b_left","place_a2b_right","place_bread_basket",
"place_bread_skillet","place_burger_fries","place_can_basket","place_cans_plasticbox","place_container_plate",
"place_dual_shoes","place_empty_cup","place_fan","place_mouse_pad","place_object_basket","place_object_scale",
"place_object_stand","place_phone_stand","place_shoe","press_stapler","put_bottles_dustbin","put_object_cabinet",
"rotate_qrcode","scan_object","shake_bottle","shake_bottle_horizontally","stack_blocks_three","stack_blocks_two",
"stack_bowls_three","stack_bowls_two","stamp_seal","turn_switch"]

def load_font(sz):
    for p in ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
              "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]:
        if os.path.exists(p):
            return ImageFont.truetype(p, sz)
    return ImageFont.load_default()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gallery", default="scene_gallery")
    ap.add_argument("--out", default="scene_overview.png")
    ap.add_argument("--cols", type=int, default=5)
    ap.add_argument("--tile_w", type=int, default=400)
    ap.add_argument("--ep", type=int, default=0)
    ap.add_argument("--tasks", default="", help="逗号分隔的任务名；留空用默认 50")
    ap.add_argument("--title", default="")
    a = ap.parse_args()

    tasks = [t for t in a.tasks.split(",") if t] if a.tasks else DEFAULT_TASKS
    tile_w = a.tile_w; tile_h = int(tile_w*3/4); lab = 28; pad = 6
    font = load_font(18); fsmall = load_font(15); ftitle = load_font(30)
    cols = a.cols; rows = (len(tasks)+cols-1)//cols
    cw, ch = tile_w+2*pad, tile_h+lab+2*pad
    top = 46 if a.title else 0
    W, H = cols*cw, rows*ch + top
    canvas = Image.new("RGB", (W, H), (250,250,250))
    dr = ImageDraw.Draw(canvas)
    if a.title:
        dr.text((10, 8), a.title, fill=(0,0,0), font=ftitle)
    miss = []
    for idx, t in enumerate(tasks):
        r, c = divmod(idx, cols)
        x0, y0 = c*cw, r*ch + top
        cand = sorted(glob.glob(os.path.join(a.gallery, t, f"ep{a.ep:02d}_*.png"))) or \
               sorted(glob.glob(os.path.join(a.gallery, t, "ep*_*.png")))
        if cand:
            try:
                im = Image.open(cand[0]).convert("RGB").resize((tile_w, tile_h))
                canvas.paste(im, (x0+pad, y0+pad+lab))
            except Exception:
                miss.append(t)
        else:
            miss.append(t)
            dr.rectangle([x0+pad,y0+pad+lab,x0+pad+tile_w,y0+pad+lab+tile_h], fill=(230,230,230))
            dr.text((x0+pad+10,y0+pad+lab+tile_h//2), "(no image)", fill=(150,0,0), font=fsmall)
        dr.text((x0+pad, y0+pad), f"{idx+1:02d}. {t}", fill=(20,20,20), font=font)
    canvas.save(a.out)
    print(f"saved {a.out}  ({W}x{H}), 缺失 {len(miss)}: {miss}")

if __name__ == "__main__":
    main()
