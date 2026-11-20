#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
dist 样式表静态审计
--------------------------------------------------
不做秒表测量（headless 的虚拟时间会让耗时失真），只统计能核实的结构指标：
体积、规则数、选择器特异度分布、可能昂贵的选择器特征、!important 台账。

用法：python3 audit.py
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent
CSS = ROOT / "dist" / "ggn-morandi.user.css"
if not CSS.exists():
    CSS = ROOT / "ggn-morandi.css"


def strip_comments(t):
    return re.sub(r"/\*.*?\*/", "", t, flags=re.S)


def split_selectors(css):
    """粗粒度拆分：每个 { 之前的选择器列表。"""
    out = []
    for m in re.finditer(r"([^{}]+)\{", css):
        sel = m.group(1).strip()
        if not sel or sel.startswith("@"):
            continue
        for s in sel.split(","):
            s = s.strip()
            if s:
                out.append(s)
    return out


def specificity(sel):
    ids = len(re.findall(r"#[a-zA-Z]", sel))
    classes = len(re.findall(r"\.[a-zA-Z]|\[[^\]]+\]|:(?!:)[a-z-]+", sel))
    types = len(re.findall(r"(?:^|[\s>+~])([a-zA-Z][a-zA-Z0-9]*)", sel))
    return ids, classes, types


def main():
    if not CSS.exists():
        print("先跑 build.py")
        return 1
    raw = CSS.read_text(encoding="utf-8")
    css = strip_comments(raw)
    sels = split_selectors(css)

    feats = {
        "通配 *": [s for s in sels if re.search(r"(^|[\s>+~])\*(?![\w-])", s)],
        ":has()": [s for s in sels if ":has(" in s],
        "属性子串 *=": [s for s in sels if "*=" in s],
        ":not()": [s for s in sels if ":not(" in s],
        "后代 ≥4 层": [s for s in sels if s.count(" ") >= 4],
        "!important 规则": [m.group(0)[:60] for m in re.finditer(r"[^{}]+\{[^{}]*!important[^{}]*\}", css)],
    }

    print("=" * 62)
    print("dist 静态审计")
    print("=" * 62)
    print(f"  体积        {len(raw.encode()):>9,} B   {len(raw.splitlines()):>5} 行")
    print(f"  规则数      {len(sels):>9} 条选择器（逗号拆分后）")
    print(f"  DOM 无关    不含 JS / 字体 / 图片请求：{raw.count('url(')} 个内联 url()")
    print()
    print("  特异度分布（id-类-元素）：")
    buckets = {}
    for s in sels:
        i, c, t = specificity(s)
        key = f"{min(i,3)}+ id / {min(c,5)}+ 类 / {min(t,4)}+ 元素"
        buckets[key] = buckets.get(key, 0) + 1
    for k, v in sorted(buckets.items(), key=lambda x: -x[1])[:6]:
        print(f"    {v:>4}  {k}")

    print()
    print("  选择器特征：")
    for name, items in feats.items():
        flag = "" if len(items) <= 3 else "  ← 需要留意"
        print(f"    {name:<16} {len(items):>4}{flag}")
        if items and name != "!important 规则":
            for s in items[:2]:
                print(f"        · {s[:78]}")

    print()
    print("  最长的 3 条选择器：")
    for s in sorted(sels, key=len, reverse=True)[:3]:
        print(f"    {len(s):>4} 字符  {s[:88]}")

    print()
    print("  色值归属：", "通过（全部在 01-tokens）"
          if not re.search(r"#[0-9a-fA-F]{3,8}", strip_comments(
              "".join(p.read_text(encoding="utf-8") for p in sorted((ROOT / "src").glob("*.css"))
                      if not p.name.startswith("01-"))))
          else "存在裸色值")
    return 0


if __name__ == "__main__":
    sys.exit(main())
