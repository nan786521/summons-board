"""
Generate abilities.min.json from abilities.json
Compact key mapping:
  h=hp, a=atk, s=soul_slots, l=leader_skill, k=active_skill,
  t=tp_skill, p=potentials, b=abilities, o=obtain, rs=recommended_souls
Inner skill keys: n=name, e=effect, u=turn, c=tp_cost
"""

import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")

INPUT = "abilities.json"
OUTPUT = "abilities.min.json"


def compact_skill(skill):
    """Compact a skill object: name→n, effect→e, turn→u, tp_cost→c"""
    if not skill:
        return None
    c = {}
    if skill.get("name"):
        c["n"] = skill["name"]
    if skill.get("effect"):
        c["e"] = skill["effect"]
    if skill.get("turn"):
        c["u"] = skill["turn"]
    if skill.get("tp_cost"):
        c["c"] = skill["tp_cost"]
    return c if c else None


def compact_ability(val):
    c = {}
    if val.get("hp"):
        c["h"] = val["hp"]
    if val.get("atk"):
        c["a"] = val["atk"]
    if val.get("soul_slots"):
        c["s"] = val["soul_slots"]
    if val.get("leader_skill"):
        c["l"] = compact_skill(val["leader_skill"])
    if val.get("active_skill"):
        c["k"] = compact_skill(val["active_skill"])
    if val.get("tp_skill"):
        c["t"] = compact_skill(val["tp_skill"])
    if val.get("potentials"):
        c["p"] = val["potentials"]
    if val.get("abilities"):
        c["b"] = val["abilities"]
    if val.get("obtain"):
        c["o"] = val["obtain"]
    if val.get("recommended_souls"):
        c["rs"] = val["recommended_souls"]
    return c


def main():
    with open(INPUT, "r", encoding="utf-8") as f:
        data = json.load(f)

    compact = {}
    for key, val in data.items():
        compact[key] = compact_ability(val)

    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(compact, f, ensure_ascii=False, separators=(",", ":"))

    orig_size = os.path.getsize(INPUT)
    new_size = os.path.getsize(OUTPUT)
    ratio = (1 - new_size / orig_size) * 100

    print(f"entries: {len(compact)}")
    print(f"original: {orig_size/1024:.1f} KB")
    print(f"compact:  {new_size/1024:.1f} KB")
    print(f"reduced:  {ratio:.1f}%")


if __name__ == "__main__":
    main()
