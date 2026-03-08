"""
補爬技能冷卻回合數
只爬取 abilities.json 中 active_skill 沒有 turn 的角色
"""

import json
import random
import re
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, ".")
from scrape_abilities import fetch_page, clean_html

OUTPUT_FILE = "abilities.json"
BASE_DELAY = 2.5
JITTER = 2.0
BACKOFF_403 = 30
MAX_CONSECUTIVE_403 = 5


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
        if ab and ab.get("active_skill") and not ab["active_skill"].get("turn"):
            targets.append((key, m))

    print(f"需補爬技能冷卻: {len(targets)} 個角色")

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
            consecutive_403 = 0

            # Extract skill turn from <th>スキルターン</th></tr><tr><td>Xターン → Yターン</td>
            turn_match = re.search(
                r"スキルターン</th>\s*</tr>\s*<tr>\s*<td[^>]*>(.*?)</td>",
                html, re.DOTALL
            )
            turn_text = clean_html(turn_match.group(1)).strip() if turn_match else ""

            if turn_text:
                abilities[key]["active_skill"]["turn"] = turn_text
                found += 1
                print(f"OK ({turn_text})")
            else:
                print("(無)")

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
            print(f"  --- 已儲存 (找到 {found} 筆冷卻) ---")

        delay = BASE_DELAY + random.uniform(0, JITTER)
        time.sleep(delay)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(abilities, f, ensure_ascii=False, indent=2)

    print(f"\n=== 完成 ===")
    print(f"成功: {success}，失敗: {fail}，找到冷卻: {found} 筆")


if __name__ == "__main__":
    main()
