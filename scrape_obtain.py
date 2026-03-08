"""
補爬入手方法資料
只爬取 abilities.json 中沒有 obtain 的角色
"""

import json
import random
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, ".")
from scrape_abilities import fetch_page, parse_detail_page

OUTPUT_FILE = "abilities.json"
BASE_DELAY = 2.5
JITTER = 2.0
BACKOFF_403 = 30
MAX_CONSECUTIVE_403 = 5

# 入手方法翻譯
OBTAIN_DICT = {
    "レアガチャ": "稀有轉蛋",
    "フェス限": "Fes限定",
    "コラボ限定": "聯動限定",
    "コラボガチャ": "聯動轉蛋",
    "降臨": "降臨",
    "ダンジョンドロップ": "關卡掉落",
    "ドロップ": "掉落",
    "交換": "交換",
    "報酬": "獎勵",
    "ログインボーナス": "登入獎勵",
    "イベント": "活動",
    "パック": "禮包",
    "セット": "套組",
    "初心者限定": "新手限定",
    "期間限定": "期間限定",
    "ポイント交換": "點數交換",
}


def translate_obtain(text):
    for ja, zh in sorted(OBTAIN_DICT.items(), key=lambda x: -len(x[0])):
        text = text.replace(ja, zh)
    return text


def main():
    with open("monsters.json", "r", encoding="utf-8") as f:
        monsters = json.load(f)

    with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
        abilities = json.load(f)

    targets = []
    for m in monsters:
        if not m.get("url"):
            continue
        key = str(m["no"]) if m.get("no") else m["name"]
        ab = abilities.get(key)
        if ab and not ab.get("obtain"):
            targets.append((key, m))

    print(f"需補爬入手方法: {len(targets)} 個角色")

    success = 0
    fail = 0
    found = 0
    consecutive_403 = 0

    for i, (key, m) in enumerate(targets):
        url = m["url"]
        if not url.startswith("http"):
            url = "https://gamewith.jp" + url

        try:
            print(f"[{i+1}/{len(targets)}] {m['name']}...", end=" ", flush=True)
            html = fetch_page(url)
            result = parse_detail_page(html)
            consecutive_403 = 0

            if result.get("obtain"):
                abilities[key]["obtain"] = result["obtain"]
                found += 1
                print(f"OK ({result['obtain']})")
            else:
                print("(無)")

            # Also grab potentials if missing
            if not abilities[key].get("potentials") and result.get("potentials"):
                abilities[key]["potentials"] = result["potentials"]
                print(f"    + 潛在效果 {len(result['potentials'])} levels")

            success += 1

        except Exception as e:
            err_str = str(e)
            if "403" in err_str:
                consecutive_403 += 1
                print(f"403 (連續 {consecutive_403} 次)")
                if consecutive_403 >= MAX_CONSECUTIVE_403:
                    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
                        json.dump(abilities, f, ensure_ascii=False, indent=2)
                    wait = BACKOFF_403 * consecutive_403
                    print(f"  === 暫停 {wait} 秒 ===")
                    time.sleep(wait)
                    consecutive_403 = 0
                else:
                    time.sleep(BACKOFF_403)
            else:
                print(f"FAIL: {e}")
            fail += 1

        if (success + fail) % 50 == 0 and (success + fail) > 0:
            with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
                json.dump(abilities, f, ensure_ascii=False, indent=2)
            print(f"  --- 已儲存 (找到 {found} 筆入手方法) ---")

        delay = BASE_DELAY + random.uniform(0, JITTER)
        time.sleep(delay)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(abilities, f, ensure_ascii=False, indent=2)

    print(f"\n=== 完成 ===")
    print(f"成功: {success}，失敗: {fail}，找到入手方法: {found} 筆")


if __name__ == "__main__":
    main()
