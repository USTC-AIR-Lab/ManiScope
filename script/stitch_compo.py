# -*- coding: utf-8 -*-
"""按维度分组拼组合泛化场景总览图：每条维度一个色带标题，每格标注序号/场景名/难度。"""
import os, glob, argparse, yaml
from PIL import Image, ImageDraw, ImageFont

DIM = {"skill_x_object":   ("D1  SKILL x OBJECT",       (14, 110, 98)),
       "skill_x_spatial":  ("D2  SKILL x SPATIAL",      (58, 76, 168)),
       "attribute_binding":("D3  ATTRIBUTE BINDING",    (166, 51, 84)),
       "instruction_structure": ("D4  INSTRUCTION STRUCTURE", (138, 90, 12)),
       "skill_x_skill_temporal":("D5  SKILL x SKILL (TEMPORAL)", (59, 110, 42)),
       "mixture":          ("D7  MIXTURE",              (110, 58, 156))}

def font(sz, bold=False):
    for p in ["/usr/share/fonts/truetype/dejavu/DejaVuSans%s.ttf" % ("-Bold" if bold else ""),
              "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]:
        if os.path.exists(p):
            return ImageFont.truetype(p, sz)
    return ImageFont.load_default()

def cjk(sz):
    # 这台机器只装了 DejaVu，没有 CJK 字体；标题一律用英文，中文说明放 SCENE_GOALS.md
    return font(sz, True)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--yaml", default="suite/scenes_v2.yaml")
    ap.add_argument("--gallery", default="scene_gallery_compo")
    ap.add_argument("--out", default="compo_v2_overview.png")
    ap.add_argument("--cols", type=int, default=5)
    ap.add_argument("--tile_w", type=int, default=400)
    ap.add_argument("--title", default="RoboTwin Compositional-Generalization  --  Formal Eval, %d scenes x 100 episodes (frozen seeds, tag formal-eval-v1)")
    a = ap.parse_args()

    y = yaml.safe_load(open(a.yaml, encoding="utf-8"))
    groups = []
    for key, ax in y["axes"].items():
        sc = ax.get("scenes") or []
        if sc:
            groups.append((key, sc))

    tw = a.tile_w; th = int(tw * 3 / 4); lab = 30; pad = 6; band = 46
    cw, ch = tw + 2 * pad, th + lab + 2 * pad
    cols = a.cols
    f_name, f_tier, f_band = font(17, True), font(15), cjk(23)

    H = 60
    for _, sc in groups:
        H += band + ((len(sc) + cols - 1) // cols) * ch
    W = cols * cw
    canvas = Image.new("RGB", (W, H), (250, 250, 248))
    dr = ImageDraw.Draw(canvas)
    dr.text((14, 16), a.title % sum(len(s) for _, s in groups) if "%d" in a.title else a.title,
            fill=(20, 20, 20), font=font(26, True))

    idx, yoff, miss = 1, 60, []
    for key, sc in groups:
        title, col = DIM.get(key, (key, (70, 70, 70)))
        dr.rectangle([0, yoff, W, yoff + band - 6], fill=col)
        dr.text((14, yoff + 9), "%s   --   %d scenes" % (title, len(sc)), fill=(255, 255, 255), font=f_band)
        yoff += band
        for i, s in enumerate(sc):
            r, c = divmod(i, cols)
            x0, y0 = c * cw, yoff + r * ch
            name = s["name"]
            cand = sorted(glob.glob(os.path.join(a.gallery, name, "*.png")))
            if cand:
                try:
                    canvas.paste(Image.open(cand[0]).convert("RGB").resize((tw, th)), (x0 + pad, y0 + pad + lab))
                except Exception:
                    miss.append(name)
            else:
                miss.append(name)
                dr.rectangle([x0 + pad, y0 + pad + lab, x0 + pad + tw, y0 + pad + lab + th], fill=(232, 232, 230))
                dr.text((x0 + pad + 12, y0 + pad + lab + th // 2), "(no image)", fill=(160, 0, 0), font=f_tier)
            dr.text((x0 + pad, y0 + pad + 2), "%02d. %s" % (idx, name), fill=(20, 20, 20), font=f_name)
            tier = "L%s" % s.get("tier", "?")
            tb = dr.textbbox((0, 0), tier, font=f_tier)
            dr.rectangle([x0 + pad + tw - (tb[2] - tb[0]) - 12, y0 + pad + 2,
                          x0 + pad + tw, y0 + pad + 2 + (tb[3] - tb[1]) + 8], fill=col)
            dr.text((x0 + pad + tw - (tb[2] - tb[0]) - 6, y0 + pad + 3), tier, fill=(255, 255, 255), font=f_tier)
            idx += 1
        yoff += ((len(sc) + cols - 1) // cols) * ch
    canvas.save(a.out)
    print("saved %s (%dx%d), 缺图 %d: %s" % (a.out, W, H, len(miss), miss))

if __name__ == "__main__":
    main()
