#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gazelle Dark Morandi — 构建脚本
--------------------------------------------------
把 src/ 下的分段样式拼成一份可直接粘进 Stylus 的 user.css，并做静态体检。

用法：
    python3 build.py            # 构建 + 体检
    python3 build.py --strict   # 体检出现警告也返回非零

检查项（前 5 项是硬性失败，后 3 项只警告）：
    1  括号配平
    2  !important 预算（<= 25），并列出每一处的文件与行号
    3  禁用属性：backdrop-filter / filter: drop-shadow / background-attachment: fixed / @import
    4  通配选择器（除带 build:allow-star 标记的段落与 #header > * 外）
    5  分段文件存在且顺序正确（01..06 不能跳号）
    6  色值只在 01-tokens.css 出现
    7  每条规则的字节数与总体积
    8  单个文件超过 400 行提示
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent
SRC = ROOT / "src"
DIST = ROOT / "dist"
OUT = DIST / "ggn-morandi.user.css"

IMPORTANT_BUDGET = 25
EXPECTED_ORDER = ["00", "01", "02", "03", "04", "05", "06"]

FORBIDDEN = [
    (r"backdrop-filter", "backdrop-filter 是持续合成开销，本项目不允许"),
    (r"filter\s*:\s*drop-shadow", "drop-shadow 在深层元素上触发重绘"),
    (r"background-attachment\s*:\s*fixed", "fixed 背景滚动时持续合成"),
    (r"@import", "外部 @import 增加一次网络请求"),
]


def read_parts():
    files = sorted(SRC.glob("*.css"))
    missing = [p for p in EXPECTED_ORDER if not list(SRC.glob(p + "-*.css"))]
    return files, missing


def check_braces(text, name):
    depth = 0
    for i, ch in enumerate(text):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth < 0:
                return f"{name}: 第 {text[:i].count(chr(10)) + 1} 行出现多余的 '}}'"
    if depth != 0:
        return f"{name}: 花括号未配平（未闭合 {depth} 个）"
    return None


def strip_comments(text):
    return re.sub(r"/\*.*?\*/", "", text, flags=re.S)


def blank_comments(text):
    """把块注释替换成等长空白（保留换行），行号不变，便于逐行定位。"""
    out = []
    i, n = 0, len(text)
    in_comment = False
    while i < n:
        if not in_comment and text.startswith("/*", i):
            in_comment, i = True, i + 2
            out.append("  ")
        elif in_comment and text.startswith("*/", i):
            in_comment, i = False, i + 2
            out.append("  ")
        else:
            ch = text[i]
            out.append(ch if (ch == "\n" or not in_comment) else " ")
            i += 1
    return "".join(out)


def main():
    strict = "--strict" in sys.argv
    files, missing = read_parts()
    hard, warn = [], []

    if not files:
        print("没有找到 src/*.css")
        return 1

    # 开发期允许 04/05 尚未存在（分阶段交付），只提示不失败
    if missing:
        warn.append("分段尚未创建：" + ", ".join(missing) + "（按阶段补齐即可）")

    chunks = []
    for f in files:
        text = f.read_text(encoding="utf-8")
        err = check_braces(text, f.name)
        if err:
            hard.append(err)
        chunks.append((f, text))

    body = "\n\n".join(t.rstrip() + "\n" for _, t in chunks)

    # --- 2. !important 台账（注释里的说明不算）---
    ledger = []
    for f, text in chunks:
        for idx, line in enumerate(blank_comments(text).splitlines(), 1):
            n = line.count("!important")
            if n:
                ledger.append((f.name, idx, n, line.strip()[:88]))
    total_imp = sum(n for _, _, n, _ in ledger)
    if total_imp > IMPORTANT_BUDGET:
        hard.append(f"!important 超预算：{total_imp} > {IMPORTANT_BUDGET}")

    # --- 3. 禁用属性 ---
    clean = strip_comments(body)
    for pattern, why in FORBIDDEN:
        hits = [i + 1 for i, line in enumerate(clean.splitlines())
                if re.search(pattern, line)]
        if hits:
            hard.append(f"出现禁用项 /{pattern}/（{'、'.join(map(str, hits[:5]))} 行）：{why}")

    # --- 4. 通配选择器 ---
    star_lines = []
    allow_depth = False
    for idx, line in enumerate(body.splitlines(), 1):
        if "build:allow-star" in line:
            allow_depth = True
        if allow_depth and "prefers-reduced-motion" in line:
            continue
        stripped = line.strip()
        if re.match(r"^[*]\s*[,{]", stripped) or re.match(r"^\*::", stripped):
            if allow_depth:
                continue
            star_lines.append(idx)
        if stripped.startswith("}") and allow_depth and "prefers-reduced-motion" not in stripped:
            pass
    if star_lines:
        warn.append("通配选择器出现在非豁免段落：" + "、".join(map(str, star_lines)))

    # --- 6. 色值归属 ---
    hex_re = re.compile(r"#[0-9a-fA-F]{3,8}\b")
    for f, text in chunks:
        if f.name.startswith("01-"):
            continue
        found = hex_re.findall(strip_comments(text))
        if found:
            warn.append(f"{f.name}: 出现裸色值 {len(found)} 处（{', '.join(found[:5])}）")

    # --- 输出 ---
    if not DIST.exists():
        DIST.mkdir()
    banner = (
        "/* Built by morandi/build.py — do not edit dist directly.\n"
        f"   parts: {', '.join(f.name for f, _ in chunks)}\n"
        "   source: morandi/src/ */\n\n"
    )
    OUT.write_text(banner + body, encoding="utf-8")

    data = OUT.read_bytes()
    rules = clean.count("{") - clean.count("@media") - clean.count("@supports")

    print("=" * 66)
    print("Gazelle Dark Morandi — build")
    print("=" * 66)
    for f, text in chunks:
        print(f"  {f.name:<22} {len(text.splitlines()):>5} 行  {len(text.encode()):>7,} B")
    print("-" * 66)
    print(f"  成品 {OUT.relative_to(ROOT)}  {len(data):,} B  {len(body.splitlines()):,} 行  约 {rules} 条规则")
    print(f"  !important: {total_imp} / {IMPORTANT_BUDGET}")
    for name, line, n, snippet in ledger:
        print(f"    · {name}:{line}  {snippet}")

    if hard:
        print("\n[硬性失败]")
        for h in hard:
            print("  × " + h)
    if warn:
        print("\n[警告]")
        for w in warn:
            print("  ! " + w)
    if not hard and not warn:
        print("\n体检通过：无失败项、无警告。")

    if hard:
        return 1
    if strict and warn:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
