#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""番茄小说作家后台 - 手动登录并保存会话（只需运行一次，或登录过期后重跑）"""

from __future__ import annotations

import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from utils import load_config, writer_home_url  # noqa: E402


def main() -> None:
    cfg = load_config()
    state_path = ROOT / cfg["state_file"]

    print("=" * 60)
    print("番茄小说 - 登录助手")
    print("=" * 60)
    print("1. 将弹出 Chromium 浏览器")
    print("2. 请手动扫码/账号登录番茄作家后台")
    print("3. 登录成功并看到作家主页后，回到终端按回车")
    print("4. 登录状态将保存到:", state_path)
    print("=" * 60)

    state_path.parent.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        page.goto(writer_home_url(cfg), timeout=60000)

        input("\n>>> 登录完成后按回车保存会话... ")

        context.storage_state(path=str(state_path))
        browser.close()

    print(f"\n✅ 登录状态已保存: {state_path}")
    print("下一步: python scripts/fanqie_publish/publish.py --help")


if __name__ == "__main__":
    main()
