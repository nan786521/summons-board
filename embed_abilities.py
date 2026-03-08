"""將 abilities.json 嵌入 index.html 的 ABILITY_DATA 常數"""

import json
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")

with open("abilities.json", "r", encoding="utf-8") as f:
    abilities = json.load(f)

print(f"載入 {len(abilities)} 筆能力資料")

with open("index.html", "r", encoding="utf-8") as f:
    html = f.read()

compact = json.dumps(abilities, ensure_ascii=False, separators=(",", ":"))

# 如果已有 ABILITY_DATA，替換它
if "const ABILITY_DATA =" in html:
    # 用字串定位取代，避免 regex 的 lazy/greedy 問題
    start = html.index("const ABILITY_DATA = ")
    # 找到這行結尾的換行符
    end_of_line = html.index("\n", start)
    html = html[:start] + f"const ABILITY_DATA = {compact};" + html[end_of_line:]
    print("已更新現有 ABILITY_DATA")
else:
    # 插入在 MONSTER_DATA 之後
    html = html.replace(
        "const MONSTER_DATA = ",
        f"const ABILITY_DATA = {compact};\nconst MONSTER_DATA = ",
        1,
    )
    print("已插入 ABILITY_DATA")

with open("index.html", "w", encoding="utf-8") as f:
    f.write(html)

print(f"index.html 已更新 ({len(html):,} bytes)")
