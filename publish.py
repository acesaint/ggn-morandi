#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
发布：把 src/*.css 拼成两个可直接消费的成品。

    ggn-morandi.css        纯样式表，供 GazelleGames 的 External CSS 字段引用
    ggn-morandi.user.css   带 UserStyle 元信息，供 Stylus 安装

用法：
    python3 publish.py            # 输出到当前目录
    python3 publish.py ../out     # 输出到指定目录
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent
SRC = ROOT / "src"
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT


def main():
    parts = sorted(SRC.glob("*.css"))
    if not parts:
        print("src/ 下没有 .css")
        return 1

    body = []
    for p in parts:
        text = p.read_text(encoding="utf-8").rstrip()
        if p.name.startswith("00-"):
            continue                     # 元信息单独处理
        body.append(text)
    css = "\n\n".join(body) + "\n"

    header_file = next(SRC.glob("00-*.css"))
    header = header_file.read_text(encoding="utf-8").rstrip()

    if not OUT.exists():
        OUT.mkdir(parents=True)

    user_css = header + "\n\n" + css
    (OUT / "ggn-morandi.user.css").write_text(user_css, encoding="utf-8")

    # 纯 CSS：去掉 ==UserStyle== 元信息块，其余原样（对浏览器来说它本来就是注释）
    pure = re.sub(r"/\* ==UserStyle==.*?==/UserStyle== \*/", "", user_css,
                  flags=re.S).lstrip()
    (OUT / "ggn-morandi.css").write_text(pure, encoding="utf-8")

    for name in ("ggn-morandi.css", "ggn-morandi.user.css"):
        f = OUT / name
        print(f"  {name:<24} {len(f.read_bytes()):>7,} B  {len(f.read_text(encoding='utf-8').splitlines()):>5} 行")
    return 0


if __name__ == "__main__":
    sys.exit(main())
