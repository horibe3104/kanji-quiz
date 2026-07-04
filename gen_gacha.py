#!/usr/bin/env python3
"""
ガチャ演出 Phase1+2 動画生成
宇宙 → 隕石落下 → 富士山着陸  までを WebP アニメで生成。
Phase3（くうっちカード表示）は既存 CSS/JS が担当。

Output: gacha_video/gacha_normal.webp
        gacha_video/gacha_golden.webp
        gacha_video/gacha_eruption.webp

Usage: python3 gen_gacha.py
"""

import numpy as np
from PIL import Image, ImageDraw, ImageFilter
import math, random, os

# ── 解像度・タイミング ──────────────────────────────────────
W, H   = 360, 640
FPS    = 18          # フレームレート
SPF    = 1000 // FPS # ms/frame

T_LAND       = 2.8   # 着陸時刻 (秒)
T_END_NORMAL = 4.1   # 通常・金色の終了時刻 (最後は白フラッシュ)
T_END_ERUPT  = 5.6   # 噴火の終了時刻

FUJI_PEAK = (180, 215)  # 富士山頂 (ピクセル)

random.seed(42)

# ── 星の位置・パラメータ (固定) ───────────────────────────────
STARS = [(
    random.randint(6, W-6),
    random.randint(6, H // 2 - 20),
    random.uniform(0.6, 2.2),
    random.uniform(0, math.pi * 2),
    random.uniform(1.5, 4.5),
) for _ in range(200)]

# ── 富士山ポリゴン (Bezier 近似) ──────────────────────────────
def bezier(p0, p1, p2, p3, n=24):
    pts = []
    for i in range(n):
        t = i / (n - 1)
        x = (1-t)**3*p0[0]+3*(1-t)**2*t*p1[0]+3*(1-t)*t**2*p2[0]+t**3*p3[0]
        y = (1-t)**3*p0[1]+3*(1-t)**2*t*p1[1]+3*(1-t)*t**2*p2[1]+t**3*p3[1]
        pts.append((int(x), int(y)))
    return pts

# 左斜面 (頂上 → 左裾)
LEFT_SLOPE  = bezier((180,215),(155,295),(85,430),(0,590), 32)
# 右斜面 (頂上 → 右裾)
RIGHT_SLOPE = bezier((180,215),(205,295),(275,430),(360,590), 32)

FUJI_BODY = LEFT_SLOPE + [(0, H), (W, H)] + list(reversed(RIGHT_SLOPE))

# 雪帽子
SNOW_CAP = (
    bezier((180,215),(196,232),(218,250),(230,268), 18)
  + bezier((230,268),(205,262),(180,258),(155,262), 12)
  + bezier((155,262),(142,258),(132,252),(130,268), 12)
  + list(reversed(bezier((180,215),(164,232),(142,250),(130,268), 18)))
)

# 遠景山稜
BG_RIDGE = [(0,450),(50,410),(100,428),(160,398),(210,382),
            (260,392),(310,408),(360,422),(360,H),(0,H)]

# 木シルエット
TREES = [(int(i/26*W)+random.randint(-2,2), 580, 18+i%5*7+random.randint(-2,2))
         for i in range(27)]

# ── numpy ユーティリティ ──────────────────────────────────────
def add_glow(arr, cx, cy, radius, color_rgb, strength=1.0):
    """円形グロウをフレームに加算合成 (in-place)"""
    if radius <= 0: return
    r = int(radius * 1.6) + 1
    x0, x1 = max(0, cx-r), min(W, cx+r+1)
    y0, y1 = max(0, cy-r), min(H, cy+r+1)
    if x0 >= x1 or y0 >= y1: return
    ys, xs = np.mgrid[y0:y1, x0:x1].astype(np.float32)
    dist = np.sqrt((xs-cx)**2 + (ys-cy)**2)
    fall = np.clip(1 - dist/radius, 0, 1)**2 * strength
    for ch, c in enumerate(color_rgb):
        arr[y0:y1, x0:x1, ch] = np.clip(arr[y0:y1, x0:x1, ch] + fall*c, 0, 255)

def arr2img(arr): return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))
def img2arr(img): return np.array(img, dtype=np.float32)

# ── 静的レイヤー (事前描画) ──────────────────────────────────
def make_space_bg():
    """宇宙背景グラデーション"""
    ys = np.mgrid[0:H, 0:W][0].astype(np.float32) / H
    bg = np.stack([13*(1-ys)+5*ys, 27*(1-ys)+8*ys, 94*(1-ys)+16*ys], -1)
    # 中央に淡いネビュラ
    xs = np.mgrid[0:H, 0:W][1].astype(np.float32) / W
    neb = np.exp(-((xs-0.5)**2*8 + (ys-0.4)**2*6)) * 8
    bg[:,:,2] = np.clip(bg[:,:,2] + neb, 0, 255)
    return bg.astype(np.float32)

BG_BASE = make_space_bg()

def make_fuji_img(erupting=False):
    """富士山レイヤー (RGBA PIL Image)"""
    img = Image.new('RGBA', (W, H), (0,0,0,0))
    d   = ImageDraw.Draw(img)

    # 遠景山稜
    d.polygon(BG_RIDGE, fill=(12,9,24,180))

    # 富士山本体
    d.polygon(FUJI_BODY, fill=(32,24,52,255))

    # 右面 (少し明るめ)
    right_body = [(180,215)] + list(reversed(RIGHT_SLOPE)) + [(W,H),(180,H)]
    d.polygon(right_body, fill=(46,36,72,255))

    # 雪帽子
    d.polygon(SNOW_CAP, fill=(232,236,248,255))
    # 雪ハイライト
    d.polygon(
        bezier((180,215),(190,228),(202,240),(210,252),10)
      + [(180,240)],
        fill=(255,255,255,200)
    )

    # 三日月
    mx, my = 55, 95
    d.ellipse([mx-17,my-17,mx+17,my+17], fill=(255,253,220,220))
    d.ellipse([mx+5 ,my-14,mx+25,my+14], fill=(7,4,26,220))

    # 木シルエット
    for tx, ty, th in TREES:
        d.polygon([(tx,ty),(tx+7,ty),(tx+3,ty-th)], fill=(5,3,14,255))

    # 噴火クレーター光
    if erupting:
        px, py = FUJI_PEAK
        gd = ImageDraw.Draw(img)
        gd.ellipse([px-18,py-10,px+18,py+10], fill=(255,100,0,160))
        gd.ellipse([px-8, py-5, px+8, py+5],  fill=(255,220,40,200))

    return img

FUJI_NORMAL = make_fuji_img(erupting=False)
FUJI_ERUPT  = make_fuji_img(erupting=True)

# ── 隕石の軌道 ────────────────────────────────────────────────
def egg_pos(t_norm):
    """t_norm: 0→1 で頂上まで落下"""
    ease = t_norm ** 1.55
    sx, sy = W * 0.80, -65
    ex, ey = FUJI_PEAK[0], FUJI_PEAK[1] - 35
    drift = math.sin(t_norm * math.pi * 1.3) * 18
    return int(sx + (ex-sx)*ease + drift), int(sy + (ey-sy)*ease)

# ── フレーム描画 ──────────────────────────────────────────────
def draw_frame(fi, anim_type, trail_buf):
    t = fi / FPS
    t_end = T_END_ERUPT if anim_type=='eruption' else T_END_NORMAL

    # ---- 背景 ----
    arr = BG_BASE.copy()

    # ---- 星 (たわいなくチカチカ) ----
    for sx, sy, sr, ph, spd in STARS:
        twinkle = 0.45 + 0.55 * math.sin(t * spd + ph)
        bright  = (0.35 + 0.65 * twinkle)
        glow_r  = sr * (1.5 + twinkle * 0.8)
        add_glow(arr, sx, sy, glow_r * 3, (220*bright, 220*bright, 230*bright), strength=0.6)
        add_glow(arr, sx, sy, glow_r,     (255*bright, 255*bright, 255*bright), strength=1.0)

    # ---- 隕石の色設定 ----
    if anim_type == 'golden':
        egg_col  = (255, 205, 60)
        glow_col = (255, 175, 0)
        trail_col= (255, 160, 0)
    elif anim_type == 'eruption':
        egg_col  = (255, 130, 40)
        glow_col = (255, 55, 0)
        trail_col= (255, 80, 10)
    else:
        egg_col  = (255, 215, 95)
        glow_col = (255, 145, 25)
        trail_col= (255, 130, 20)

    # ---- 落下フェーズ ----
    fall_dur = T_LAND
    if t < T_LAND + 0.15:
        t_fall = min(t, T_LAND) / fall_dur
        ex, ey = egg_pos(t_fall)

        # バウンス (着陸直後)
        if t >= T_LAND:
            bounce_t = (t - T_LAND) / 0.3
            ex, ey = FUJI_PEAK[0], FUJI_PEAK[1] - 35 - int(math.sin(bounce_t*math.pi)*22)

        trail_buf.append((ex, ey))
        if len(trail_buf) > 22: trail_buf.pop(0)

        # トレイル
        for i, (tx, ty) in enumerate(trail_buf):
            pct = (i+1) / len(trail_buf)
            add_glow(arr, tx, ty, 18*pct,  trail_col, strength=pct*0.35)
            add_glow(arr, tx, ty, 6*pct,   trail_col, strength=pct*0.55)

        # 隕石グロウ + 本体
        add_glow(arr, ex, ey, 55, glow_col, strength=0.8)
        add_glow(arr, ex, ey, 25, glow_col, strength=1.0)
        img = arr2img(arr)
        d = ImageDraw.Draw(img)
        d.ellipse([ex-23, ey-29, ex+23, ey+29], fill=egg_col)
        # ハイライト
        d.ellipse([ex-10, ey-20, ex-3, ey-11], fill=(255,255,240))
        arr = img2arr(img)

    # ---- 富士山フェードイン ----
    fuji_alpha = 0.0
    if t >= 2.1:
        fuji_alpha = min(1.0, (t - 2.1) / 0.75)

    if fuji_alpha > 0:
        base_img = arr2img(arr).convert('RGBA')
        fuji_src = FUJI_ERUPT if anim_type=='eruption' else FUJI_NORMAL
        fuji_img = fuji_src.copy()
        # アルファスケール
        fa = fuji_img.split()[3]
        fa = fa.point(lambda p: int(p * fuji_alpha))
        fuji_img.putalpha(fa)
        base_img = Image.alpha_composite(base_img, fuji_img)
        arr = img2arr(base_img.convert('RGB'))

    # ---- 着陸後: 卵が頂上に鎮座 ----
    if T_LAND + 0.15 <= t < t_end - 0.55:
        pulse = 0.7 + 0.3 * math.sin(t * 5.5)
        cx, cy = FUJI_PEAK[0], FUJI_PEAK[1] - 35
        add_glow(arr, cx, cy, int(48*pulse), glow_col, strength=0.75)
        add_glow(arr, cx, cy, 20,            glow_col, strength=0.9)
        img = arr2img(arr)
        d = ImageDraw.Draw(img)
        d.ellipse([cx-23, cy-29, cx+23, cy+29], fill=egg_col)
        d.ellipse([cx-10, cy-20, cx-3, cy-11], fill=(255,255,240))
        arr = img2arr(img)

    # ---- 着陸衝撃パーティクル ----
    if T_LAND <= t <= T_LAND + 0.75:
        land_t = t - T_LAND
        fade   = 1 - land_t / 0.75
        random.seed(42)
        for _ in range(18):
            angle = random.uniform(0, math.pi * 2)
            dist  = land_t * 75 * random.uniform(0.4, 1.4)
            px = int(FUJI_PEAK[0] + math.cos(angle) * dist)
            py = int(FUJI_PEAK[1] - 35 + math.sin(angle) * dist * 0.55)
            r  = random.uniform(0.4, 1.2)
            add_glow(arr, px, py, int(14*r*fade), (255, int(180*fade), int(50*fade)), strength=fade*0.7)

    # ---- 噴火: 溶岩パーティクル ----
    if anim_type == 'eruption' and t >= T_LAND + 0.6:
        erupt_t  = t - T_LAND - 0.6
        ep       = min(1.0, erupt_t / 1.5)
        erupt_seed = int(erupt_t * 20)
        random.seed(erupt_seed)
        for _ in range(10):
            angle = -math.pi/2 + (random.random()-0.5) * 1.4
            spd   = random.uniform(2.5, 7)
            age   = random.uniform(0, 0.8)
            px = int(FUJI_PEAK[0] + math.cos(angle)*spd*age*25)
            py = int(FUJI_PEAK[1] + math.sin(angle)*spd*age*25 + 0.5*9.8*age**2*12)
            hue = random.uniform(0, 0.35)
            col = (255, int(180*hue*ep), 0)
            add_glow(arr, px, py, int(14*ep), col, strength=ep*0.8)

        # 噴火口グロウ
        add_glow(arr, FUJI_PEAK[0], FUJI_PEAK[1], int(60*ep), (255, 100, 0), strength=ep*0.9)
        add_glow(arr, FUJI_PEAK[0], FUJI_PEAK[1], int(25*ep), (255, 220, 50), strength=ep*1.0)

    # ---- エンドフェードアウト (白フラッシュ → CSS リビールへ繋ぐ) ----
    if t >= t_end - 0.55:
        fade = (t - (t_end - 0.55)) / 0.55
        white_arr = np.full_like(arr, 255)
        alpha = min(1.0, fade)
        arr = arr * (1 - alpha) + white_arr * alpha

    return arr2img(arr).convert('RGB')


# ── メイン生成 ────────────────────────────────────────────────
def generate(anim_type):
    t_end   = T_END_ERUPT if anim_type=='eruption' else T_END_NORMAL
    n_total = int(t_end * FPS) + 1
    frames  = []
    trail   = []

    print(f'\n[{anim_type}] {n_total}フレーム生成中...')
    for fi in range(n_total):
        frames.append(draw_frame(fi, anim_type, trail))
        if (fi+1) % 10 == 0 or fi == n_total-1:
            print(f'  {fi+1}/{n_total}', end='\r')
    print()

    return frames


def save_webp(frames, path):
    dur = [SPF] * len(frames)
    frames[0].save(
        path, format='WEBP', save_all=True,
        append_images=frames[1:],
        duration=dur, loop=1,   # loop=1 → 1回再生で止まる
        quality=72, method=4,
    )
    kb = os.path.getsize(path) // 1024
    print(f'  → {path}  ({kb}KB, {len(frames)}枚)')


if __name__ == '__main__':
    os.makedirs('gacha_video', exist_ok=True)
    for atype in ['normal', 'golden', 'eruption']:
        frames = generate(atype)
        save_webp(frames, f'gacha_video/gacha_{atype}.webp')
    print('\n完了！gacha_video/ フォルダを確認してください。')
