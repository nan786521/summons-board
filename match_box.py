"""
サモンズボード背包影片辨識工具
從螢幕錄影中辨識持有角色，輸出 owned.json
"""

import cv2
import json
import os
import sys
import hashlib
import urllib.request
import numpy as np
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.stdout.reconfigure(encoding="utf-8")

VIDEO_PATH = "ScreenRecording_03-07-2026 09-54-34_1.mp4"
ICONS_DIR = "icons"
MONSTERS_JSON = "monsters.json"

# Grid config (from calibration)
GRID = {
    "col_start": 222,   # x of first visible column (col1) content left edge
    "row_start": 497,   # y of first row content top edge
    "pitch": 148,        # cell pitch (border to border)
    "content": 119,      # cell content size (without borders)
    "cols": 4,           # visible columns (col0 hidden by menu)
    "rows": 8,           # visible rows per screen
}


def extract_unique_frames(video_path, interval_ms=500):
    """每 interval_ms 擷取一幀，用 hash 去重（只比較格子區域）"""
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

        # Hash only the grid area
        g = GRID
        roi = frame[g["row_start"]:g["row_start"] + g["rows"] * g["pitch"],
                     g["col_start"]:g["col_start"] + g["cols"] * g["pitch"]]
        small = cv2.resize(roi, (64, 64))
        h = hashlib.md5(small.tobytes()).hexdigest()

        if h not in seen:
            seen.add(h)
            frames.append(frame)

        ms += interval_ms

    cap.release()
    print(f"擷取 {len(frames)} 個不重複畫面")
    return frames


def crop_cells(frames):
    """從畫面裁切角色圖示，去重"""
    g = GRID
    crops = []
    seen = set()

    for frame in frames:
        for r in range(g["rows"]):
            for c in range(g["cols"]):
                x = g["col_start"] + c * g["pitch"]
                y = g["row_start"] + r * g["pitch"]
                cell = frame[y:y + g["content"], x:x + g["content"]]

                if cell.shape[0] != g["content"] or cell.shape[1] != g["content"]:
                    continue

                # Skip empty/dark cells
                if np.mean(cell) < 40:
                    continue

                # Hash for dedup
                small = cv2.resize(cell, (24, 24))
                h = hashlib.md5(small.tobytes()).hexdigest()
                if h not in seen:
                    seen.add(h)
                    crops.append(cell)

    print(f"裁切到 {len(crops)} 個不重複的角色圖示")
    return crops


def download_icons(monsters, max_workers=15):
    """下載 GameWith 角色圖示"""
    os.makedirs(ICONS_DIR, exist_ok=True)

    to_download = []
    for m in monsters:
        icon_url = m.get("icon", "")
        if not icon_url:
            continue
        fname = hashlib.md5(icon_url.encode()).hexdigest() + ".jpg"
        fpath = os.path.join(ICONS_DIR, fname)
        if not os.path.exists(fpath):
            to_download.append((icon_url, fpath, m["name"]))

    if not to_download:
        total = sum(1 for m in monsters if m.get("icon"))
        print(f"所有 {total} 個圖示已下載完畢")
        return

    print(f"需要下載 {len(to_download)} 個圖示...")

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


def build_icon_db(monsters):
    """建立圖示特徵資料庫（只用中心區域，避開邊框和覆蓋 UI）"""
    db = []
    for m in monsters:
        icon_url = m.get("icon", "")
        if not icon_url:
            continue
        fname = hashlib.md5(icon_url.encode()).hexdigest() + ".jpg"
        fpath = os.path.join(ICONS_DIR, fname)

        img = cv2.imread(fpath)
        if img is None:
            continue

        # 取中心 60% 區域（避開邊框和角落的屬性/星數 badge）
        h, w = img.shape[:2]
        m1 = int(h * 0.2)
        m2 = int(w * 0.2)
        center = img[m1:h - m1, m2:w - m2]
        center = cv2.resize(center, (48, 48))

        # 色彩直方圖
        hist = cv2.calcHist([center], [0, 1, 2], None, [8, 8, 8],
                            [0, 256, 0, 256, 0, 256])
        hist = cv2.normalize(hist, hist).flatten()

        db.append({
            "name": m["name"],
            "hist": hist,
            "center": center,
        })

    print(f"建立了 {len(db)} 個圖示特徵")
    return db


def match_crop(crop, db):
    """比對裁切圖示與資料庫"""
    # 取中心區域（避開遊戲內的 "30000" 文字和角落 badge）
    h, w = crop.shape[:2]
    # 遊戲內圖示下半部有 "30000" 文字，取上方 65% + 中間區域
    top = int(h * 0.05)
    bottom = int(h * 0.6)
    left = int(w * 0.15)
    right = int(w * 0.85)
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
    # 1. 載入角色資料
    print("=== Step 1: 載入角色資料 ===")
    with open(MONSTERS_JSON, "r", encoding="utf-8") as f:
        monsters = json.load(f)
    print(f"共 {len(monsters)} 個角色")

    # 2. 下載圖示
    print("\n=== Step 2: 下載 GameWith 圖示 ===")
    download_icons(monsters)

    # 3. 建立特徵資料庫
    print("\n=== Step 3: 建立圖示特徵資料庫 ===")
    db = build_icon_db(monsters)

    # 4. 擷取影片畫面
    print("\n=== Step 4: 擷取影片不重複畫面 ===")
    frames = extract_unique_frames(VIDEO_PATH, interval_ms=400)

    # 5. 裁切角色圖示
    print("\n=== Step 5: 裁切角色圖示 ===")
    crops = crop_cells(frames)

    # 6. 比對
    print(f"\n=== Step 6: 比對辨識（{len(crops)} 個 vs {len(db)} 個）===")
    matched = {}
    for i, crop in enumerate(crops):
        name, score = match_crop(crop, db)
        if name and score > 0.35:
            if name not in matched or score > matched[name]:
                matched[name] = score

        if (i + 1) % 100 == 0:
            print(f"  進度: {i + 1}/{len(crops)}，已辨識: {len(matched)} 個")

    print(f"\n=== 結果 ===")
    print(f"成功辨識: {len(matched)} 個角色")

    # 7. 輸出
    owned_list = sorted(matched.keys())
    with open("owned.json", "w", encoding="utf-8") as f:
        json.dump(owned_list, f, ensure_ascii=False, indent=2)
    print(f"已儲存至 owned.json")

    # 顯示高信心度的前 30 個
    by_score = sorted(matched.items(), key=lambda x: -x[1])
    print(f"\n高信心度辨識結果（前 30）:")
    for name, score in by_score[:30]:
        print(f"  {score:.3f} {name}")

    print(f"\n低信心度辨識結果（後 10）:")
    for name, score in by_score[-10:]:
        print(f"  {score:.3f} {name}")


if __name__ == "__main__":
    main()
