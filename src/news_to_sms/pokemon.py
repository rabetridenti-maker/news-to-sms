"""Deterministic "Pokemon of the day" — always present, catgirl tone.

Picks from a curated list by day-of-year so every digest reliably includes a
【今日宝可梦】 line, without relying on the LLM to remember to add it.
"""

from __future__ import annotations

from datetime import date

_POKEMON: list[tuple[str, str]] = [
    ("皮卡丘", "电"),
    ("喷火龙", "火/飞行"),
    ("水箭龟", "水"),
    ("妙蛙花", "草/毒"),
    ("伊布", "一般"),
    ("快龙", "龙/飞行"),
    ("耿鬼", "幽灵/毒"),
    ("路卡利欧", "格斗/钢"),
    ("拉普拉斯", "水/冰"),
    ("梦幻", "超能力"),
    ("超梦", "超能力"),
    ("卡比兽", "一般"),
    ("风速狗", "火"),
    ("暴鲤龙", "水/飞行"),
    ("班基拉斯", "岩石/恶"),
    ("烈咬陆鲨", "龙/地面"),
    ("沙奈朵", "超能力/妖精"),
    ("甲贺忍蛙", "水/恶"),
]


def pokemon_of_the_day(day: date) -> str:
    """Return today's Pokemon line in catgirl tone."""
    name, types = _POKEMON[day.toordinal() % len(_POKEMON)]
    return f"【今日宝可梦】{name}，{types}属性，超可爱的说喵～"
