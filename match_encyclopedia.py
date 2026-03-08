"""
從圖鑑影片辨識持有角色
亮的 = 持有，暗的 = 未持有
同時處理已進化和未進化的角色圖示
"""

import cv2
import json
import os
import sys
import hashlib
import numpy as np

sys.stdout.reconfigure(encoding="utf-8")

VIDEO_PATH = "ScreenRecording_03-07-2026 13-15-41_1.mp4"
ICONS_DIR = "icons"
MONSTERS_JSON = "monsters.json"

# Grid config for encyclopedia view (5 cols, 8 visible rows)
GRID = {
    "col_start": 188,
    "row_start": 495,
    "pitch": 131,
    "content": 121,
    "cols": 5,
    "rows": 8,
}

# Brightness threshold: owned icons are colorful/bright, unowned are dark/gray
# We use HSV saturation + value to distinguish
BRIGHT_SAT_THRESHOLD = 35   # owned icons have higher saturation
BRIGHT_VAL_THRESHOLD = 90   # owned icons have higher value


def extract_unique_frames(video_path, interval_ms=500):
    """Extract frames at intervals, deduplicate by grid area hash"""
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print("無法開啟影片")
        return []

    total_ms = cap.get(cv2.CAP_PROP_FRAME_COUNT) / cap.get(cv2.CAP_PROP_FPS) * 1000
    frames = []
    seen = set()
    ms = 0

    while ms < total_ms:
        cap.set(cv2.CAP_PROP_POS_MSEC, ms)
        ret, frame = cap.read()
        if not ret:
            break

        g = GRID
        roi = frame[g["row_start"]:g["row_start"] + g["rows"] * g["pitch"],
                     g["col_start"]:g["col_start"] + g["cols"] * g["pitch"]]
        small = cv2.resize(roi, (80, 80))
        h = hashlib.md5(small.tobytes()).hexdigest()

        if h not in seen:
            seen.add(h)
            frames.append(frame)

        ms += interval_ms

    cap.release()
    print(f"擷取 {len(frames)} 個不重複畫面")
    return frames


def is_bright_cell(cell):
    """Determine if a cell icon is bright (owned) or dark (unowned)"""
    # Use center area to avoid border effects
    h, w = cell.shape[:2]
    margin = int(h * 0.15)
    center = cell[margin:h - margin, margin:w - margin]

    hsv = cv2.cvtColor(center, cv2.COLOR_BGR2HSV)
    avg_sat = np.mean(hsv[:, :, 1])
    avg_val = np.mean(hsv[:, :, 2])

    # Bright/owned: higher saturation AND value
    return avg_sat > BRIGHT_SAT_THRESHOLD and avg_val > BRIGHT_VAL_THRESHOLD


def build_icon_db(monsters):
    """Build icon feature database for both y_ (original) and i_ (awakened) icons"""
    db = []
    for m in monsters:
        icon_url = m.get("icon", "")
        if not icon_url:
            continue

        # Try both y_ (original) and i_ (awakened) versions
        for variant_url in [icon_url, icon_url.replace("/gacha/y_", "/gacha/i_")]:
            fname = hashlib.md5(variant_url.encode()).hexdigest() + ".jpg"
            fpath = os.path.join(ICONS_DIR, fname)

            if not os.path.exists(fpath):
                continue

            img = cv2.imread(fpath)
            if img is None:
                continue

            # Center 60% area
            h, w = img.shape[:2]
            m1 = int(h * 0.2)
            m2 = int(w * 0.2)
            center = img[m1:h - m1, m2:w - m2]
            center = cv2.resize(center, (48, 48))

            hist = cv2.calcHist([center], [0, 1, 2], None, [8, 8, 8],
                                [0, 256, 0, 256, 0, 256])
            hist = cv2.normalize(hist, hist).flatten()

            db.append({
                "name": m["name"],
                "hist": hist,
                "center": center,
                "variant": "original" if "/y_" in variant_url else "awakened",
            })

    print(f"建立了 {len(db)} 個圖示特徵")
    return db


def download_awakened_icons(monsters, max_workers=15):
    """Download i_ (awakened) icons that we don't have yet"""
    import urllib.request
    from concurrent.futures import ThreadPoolExecutor, as_completed

    os.makedirs(ICONS_DIR, exist_ok=True)
    to_download = []

    for m in monsters:
        icon_url = m.get("icon", "")
        if not icon_url:
            continue
        # Awakened version
        awakened_url = icon_url.replace("/gacha/y_", "/gacha/i_")
        fname = hashlib.md5(awakened_url.encode()).hexdigest() + ".jpg"
        fpath = os.path.join(ICONS_DIR, fname)
        if not os.path.exists(fpath):
            to_download.append((awakened_url, fpath, m["name"]))

    if not to_download:
        print("所有覺醒圖示已下載完畢")
        return

    print(f"需要下載 {len(to_download)} 個覺醒圖示...")

    def dl(item):
        url, fpath, name = item
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = resp.read()
            with open(fpath, "wb") as f:
                f.write(data)
            return True
        except Exception:
            return False

    done = 0
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = [pool.submit(dl, item) for item in to_download]
        for f in as_completed(futures):
            done += 1
            if done % 200 == 0:
                print(f"  下載進度: {done}/{len(to_download)}")

    ok = sum(1 for f in futures if f.result())
    print(f"下載完成: {ok} 成功, {len(to_download) - ok} 失敗")


def match_crop(crop, db):
    """Match a crop against the icon database"""
    h, w = crop.shape[:2]
    # Use center area, avoid badges and border
    top = int(h * 0.1)
    bottom = int(h * 0.75)
    left = int(w * 0.1)
    right = int(w * 0.9)
    center = crop[top:bottom, left:right]
    center = cv2.resize(center, (48, 48))

    hist = cv2.calcHist([center], [0, 1, 2], None, [8, 8, 8],
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
    # 1. Load monster data
    print("=== Step 1: 載入角色資料 ===")
    with open(MONSTERS_JSON, "r", encoding="utf-8") as f:
        monsters = json.load(f)
    print(f"共 {len(monsters)} 個角色")

    # 2. Download awakened icons (for matching unevolved monsters too)
    print("\n=== Step 2: 下載覺醒圖示 ===")
    download_awakened_icons(monsters)

    # 3. Build feature database (both original and awakened)
    print("\n=== Step 3: 建立圖示特徵資料庫 ===")
    db = build_icon_db(monsters)

    # 4. Extract frames
    print("\n=== Step 4: 擷取影片畫面 ===")
    frames = extract_unique_frames(VIDEO_PATH, interval_ms=400)

    # 5. Process each frame: crop cells, check brightness, match if bright
    print("\n=== Step 5: 辨識持有角色 ===")
    g = GRID
    owned = {}  # name -> best_score
    total_bright = 0
    total_dark = 0
    total_cells = 0

    for fi, frame in enumerate(frames):
        for r in range(g["rows"]):
            for c in range(g["cols"]):
                x = g["col_start"] + c * g["pitch"]
                y = g["row_start"] + r * g["pitch"]
                cell = frame[y:y + g["content"], x:x + g["content"]]

                if cell.shape[0] != g["content"] or cell.shape[1] != g["content"]:
                    continue

                # Skip empty/transition cells
                if np.mean(cell) < 30:
                    continue

                total_cells += 1

                if is_bright_cell(cell):
                    total_bright += 1
                    # Match this bright cell to a monster
                    name, score = match_crop(cell, db)
                    if name and score > 0.3:
                        if name not in owned or score > owned[name]:
                            owned[name] = score
                else:
                    total_dark += 1

        if (fi + 1) % 50 == 0:
            print(f"  畫面 {fi + 1}/{len(frames)}, 持有: {len(owned)}")

    print(f"\n=== 統計 ===")
    print(f"總格子數: {total_cells}")
    print(f"亮(持有): {total_bright}")
    print(f"暗(未持有): {total_dark}")
    print(f"辨識出持有: {len(owned)} 個不重複角色")

    # 6. Save
    owned_list = sorted(owned.keys())
    with open("owned.json", "w", encoding="utf-8") as f:
        json.dump(owned_list, f, ensure_ascii=False, indent=2)
    print(f"\n已儲存至 owned.json ({len(owned_list)} 個)")

    # Show confidence distribution
    by_score = sorted(owned.items(), key=lambda x: -x[1])
    print(f"\n高信心度（前 20）:")
    for name, score in by_score[:20]:
        print(f"  {score:.3f} {name}")

    print(f"\n低信心度（後 10）:")
    for name, score in by_score[-10:]:
        print(f"  {score:.3f} {name}")


if __name__ == "__main__":
    main()
