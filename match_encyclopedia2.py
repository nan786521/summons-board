"""
圖鑑影片辨識 v2
策略：逐格比對圖示 + 亮度判斷持有狀態
改進：更緊密裁切、多幀投票、雙向比對(原始+覺醒圖示)
"""
import cv2
import json
import os
import sys
import hashlib
import numpy as np
from collections import defaultdict

sys.stdout.reconfigure(encoding="utf-8")

VIDEO = "ScreenRecording_03-07-2026 13-15-41_1.mp4"
ICONS_DIR = "icons"

GRID = {
    "col_start": 188,
    "row_start": 495,
    "pitch": 131,
    "content": 121,
    "cols": 5,
    "rows": 8,
}
INSET = 13  # pixel inset from grid border to avoid bleeding


def build_db(monsters):
    """Build icon DB with both y_ and i_ variants"""
    db = []
    for m in monsters:
        url = m.get("icon", "")
        if not url:
            continue
        for prefix in ["/gacha/y_", "/gacha/i_"]:
            variant_url = url.replace("/gacha/y_", prefix)
            fname = hashlib.md5(variant_url.encode()).hexdigest() + ".jpg"
            fpath = os.path.join(ICONS_DIR, fname)
            if not os.path.exists(fpath):
                continue
            img = cv2.imread(fpath)
            if img is None:
                continue
            h, w = img.shape[:2]
            # Use center 70% to avoid badges
            m1 = int(h * 0.15)
            m2 = int(w * 0.15)
            center = img[m1:h - m1, m2:w - m2]
            center = cv2.resize(center, (40, 40))
            hist = cv2.calcHist([center], [0, 1, 2], None, [8, 8, 8],
                                [0, 256, 0, 256, 0, 256])
            hist = cv2.normalize(hist, hist).flatten()
            db.append({"name": m["name"], "hist": hist})
    print(f"DB: {len(db)} entries")
    return db


def crop_cell(frame, row, col):
    """Crop a tight cell region avoiding border bleeding"""
    g = GRID
    x = g["col_start"] + col * g["pitch"] + INSET
    y = g["row_start"] + row * g["pitch"] + INSET
    sz = g["content"] - 2 * INSET
    return frame[y:y + sz, x:x + sz]


def cell_brightness(cell):
    """Get brightness value of a cell"""
    hsv = cv2.cvtColor(cell, cv2.COLOR_BGR2HSV)
    return float(np.mean(hsv[:, :, 2]))


def match_cell(cell, db):
    """Match cell against DB, return top match"""
    resized = cv2.resize(cell, (40, 40))
    hist = cv2.calcHist([resized], [0, 1, 2], None, [8, 8, 8],
                        [0, 256, 0, 256, 0, 256])
    hist = cv2.normalize(hist, hist).flatten()

    best_score = -1
    best_name = None
    for entry in db:
        score = cv2.compareHist(hist, entry["hist"], cv2.HISTCMP_CORREL)
        if score > best_score:
            best_score = score
            best_name = entry["name"]
    return best_name, best_score


def main():
    with open("monsters.json", "r", encoding="utf-8") as f:
        monsters = json.load(f)
    print(f"角色數: {len(monsters)}")

    db = build_db(monsters)

    cap = cv2.VideoCapture(VIDEO)
    total_ms = cap.get(cv2.CAP_PROP_FRAME_COUNT) / cap.get(cv2.CAP_PROP_FPS) * 1000

    # Collect all cell observations: name -> list of (brightness, match_score)
    observations = defaultdict(list)
    seen_frames = set()
    ms = 0
    frame_count = 0

    g = GRID
    while ms < total_ms:
        cap.set(cv2.CAP_PROP_POS_MSEC, ms)
        ret, frame = cap.read()
        if not ret:
            break

        # Dedup frames
        roi = frame[g["row_start"]:g["row_start"] + g["rows"] * g["pitch"],
                     g["col_start"]:g["col_start"] + g["cols"] * g["pitch"]]
        small = cv2.resize(roi, (64, 64))
        fhash = hashlib.md5(small.tobytes()).hexdigest()
        if fhash in seen_frames:
            ms += 300
            continue
        seen_frames.add(fhash)
        frame_count += 1

        for r in range(g["rows"]):
            for c in range(g["cols"]):
                cell = crop_cell(frame, r, c)
                if cell.shape[0] < 50 or cell.shape[1] < 50:
                    continue
                if np.mean(cell) < 25:
                    continue

                brightness = cell_brightness(cell)
                name, score = match_cell(cell, db)

                if name and score > 0.5:
                    observations[name].append((brightness, score))

        if frame_count % 50 == 0:
            unique_names = len(observations)
            print(f"  幀 {frame_count}, 已辨識 {unique_names} 個角色")

        ms += 300

    cap.release()
    print(f"\n處理 {frame_count} 個不重複幀")
    print(f"辨識到 {len(observations)} 個不重複角色")

    # Determine owned/not-owned for each matched monster
    # Use brightness voting: if majority of observations are bright -> owned
    # Use Otsu threshold on all brightness values
    all_bright = []
    for name, obs_list in observations.items():
        for b, s in obs_list:
            all_bright.append(b)

    all_bright_arr = np.array(all_bright)
    # Simple threshold: use the median as rough guide, then refine
    # Actually use Otsu on the brightness histogram
    _, bin_edges = np.histogram(all_bright_arr, bins=50, range=(50, 200))
    # Find valley between two peaks
    best_t = 100
    best_var = 0
    for i in range(5, 45):
        t = bin_edges[i]
        below = all_bright_arr[all_bright_arr <= t]
        above = all_bright_arr[all_bright_arr > t]
        if len(below) == 0 or len(above) == 0:
            continue
        w0 = len(below) / len(all_bright_arr)
        w1 = len(above) / len(all_bright_arr)
        var = w0 * w1 * (np.mean(below) - np.mean(above)) ** 2
        if var > best_var:
            best_var = var
            best_t = t

    print(f"亮度閾值: {best_t:.0f}")

    # Vote: for each monster, if >50% of observations are bright -> owned
    owned_list = []
    not_owned_list = []

    for name, obs_list in observations.items():
        bright_count = sum(1 for b, s in obs_list if b > best_t)
        total = len(obs_list)
        ratio = bright_count / total if total > 0 else 0

        if ratio > 0.5:
            owned_list.append(name)
        else:
            not_owned_list.append(name)

    owned_list.sort()
    print(f"\n=== 結果 ===")
    print(f"持有: {len(owned_list)}")
    print(f"未持有: {len(not_owned_list)}")

    with open("owned.json", "w", encoding="utf-8") as f:
        json.dump(owned_list, f, ensure_ascii=False, indent=2)
    print(f"已儲存 owned.json")


if __name__ == "__main__":
    main()
