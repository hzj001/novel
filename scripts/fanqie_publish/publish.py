#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
番茄小说 - 浏览器自动填章/发布脚本

使用前请先运行 login.py 完成手动登录。

示例:
  # 查看将发布哪些章（不打开浏览器填表）
  python scripts/fanqie_publish/publish.py --dry-run

  # 只发第1章草稿（推荐先试）
  python scripts/fanqie_publish/publish.py --start 1 --end 1 --mode draft

  # 正式发布第1-5章（会点「下一步」「确认发布」）
  python scripts/fanqie_publish/publish.py --start 1 --end 5 --mode publish

  # 从断点续发（跳过 published_log.json 里已记录的章节）
  python scripts/fanqie_publish/publish.py --resume --mode draft
"""

from __future__ import annotations

import argparse
import re
import sys
import time
from pathlib import Path

from playwright.sync_api import Page, TimeoutError as PlaywrightTimeout, sync_playwright

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from utils import (  # noqa: E402
    chapters_path,
    extract_word_count,
    list_chapter_files,
    load_config,
    load_published_log,
    new_chapter_url,
    parse_chapter_file,
    save_published_log,
)

# 番茄章节编辑器选择器（若页面改版，可在此调整）
SEL_TITLE = 'input.serial-editor-input-hint-area[placeholder="请输入标题"]'
SEL_EDITOR = '.serial-editor-container .ProseMirror[contenteditable="true"]'
SEL_SAVE_DRAFT = 'button.auto-editor-save-btn'
SEL_HEADER = '.publish-header'
SEL_STATUS = '.publish-maintain-info-status'


def dismiss_guides(page: Page) -> None:
    for _ in range(3):
        page.keyboard.press("Escape")
        page.wait_for_timeout(200)

    for _ in range(8):
        clicked = False
        for text in ("下一步", "完成", "我知道了", "跳过"):
            try:
                for btn in page.get_by_text(text, exact=True).element_handles():
                    box = btn.bounding_box()
                    if box and box["y"] > 100:
                        btn.click()
                        page.wait_for_timeout(500)
                        clicked = True
            except Exception:
                pass
        if not clicked:
            break


def fill_title(page: Page, title: str) -> None:
    loc = page.locator(SEL_TITLE).first
    loc.wait_for(state="visible", timeout=15000)
    loc.click()
    loc.fill("")
    loc.fill(title)
    page.wait_for_timeout(300)
    # 触发 React 表单更新
    loc.press("End")
    loc.press(" ")
    loc.press("Backspace")
    actual = loc.input_value()
    if actual.strip() != title.strip():
        raise RuntimeError(f"标题写入失败，当前值: {actual!r}")


def fill_body(page: Page, text: str) -> None:
    editor = page.locator(SEL_EDITOR).first
    editor.wait_for(state="visible", timeout=15000)
    editor.click()
    page.wait_for_timeout(300)

    page.keyboard.press("Control+A")
    page.keyboard.press("Backspace")
    page.wait_for_timeout(200)

    # 优先剪贴板粘贴（快）
    try:
        page.evaluate("async (v) => await navigator.clipboard.writeText(v)", text)
        page.keyboard.press("Control+V")
        page.wait_for_timeout(1500)
    except Exception:
        pass

    body = editor.evaluate("el => (el.innerText || '').trim()")
    if len(body) < 20:
        # 退回逐行输入
        editor.click()
        for line in text.replace("\r\n", "\n").split("\n"):
            if line == "":
                page.keyboard.press("Enter")
            else:
                page.keyboard.type(line, delay=5)
                page.keyboard.press("Enter")
        page.wait_for_timeout(1000)

    body = editor.evaluate("el => (el.innerText || '').trim()")
    if len(body) < 20:
        raise RuntimeError("正文写入过短，可能失败")


def wait_word_count(page: Page, min_words: int, timeout_sec: int) -> int:
    header = page.locator(SEL_HEADER)
    start = time.time()
    while time.time() - start < timeout_sec:
        header_text = header.inner_text(timeout=2000) if header.count() else ""
        count = extract_word_count(header_text)
        if count is not None and count >= min_words:
            return count
        page.wait_for_timeout(500)
    raise RuntimeError("等待正文字数同步超时")


def click_save_draft(page: Page) -> None:
    btn = page.locator(SEL_SAVE_DRAFT).first
    btn.wait_for(state="visible", timeout=10000)
    if btn.is_disabled():
        raise RuntimeError("「存草稿」按钮不可用")
    btn.click()
    wait_saved(page, 20)


def wait_saved(page: Page, timeout_sec: int) -> None:
    start = time.time()
    while time.time() - start < timeout_sec:
        header_text = page.locator(SEL_HEADER).inner_text(timeout=1000) if page.locator(SEL_HEADER).count() else ""
        status_text = page.locator(SEL_STATUS).inner_text(timeout=1000) if page.locator(SEL_STATUS).count() else ""
        combined = header_text + status_text
        if re.search(r"已保存|保存成功|草稿已保存", combined):
            return
        page.wait_for_timeout(500)
    raise RuntimeError("等待保存成功超时")


def try_publish(page: Page) -> None:
    """点击发布流程：下一步 -> 处理弹窗 -> 确认发布"""

    # 是否使用 AI：选「否」（部分账号有该选项）
    try:
        ai_no = page.get_by_text("否", exact=True).first
        if ai_no.is_visible(timeout=1500):
            ai_no.click()
            page.wait_for_timeout(400)
    except Exception:
        pass

    candidates = [
        page.get_by_role("button", name=re.compile(r"下一步|发布")),
        page.locator('button:has-text("下一步"), button:has-text("发布")'),
    ]
    entry = None
    for loc in candidates:
        if loc.count() > 0 and loc.first.is_visible():
            entry = loc.first
            break
    if entry is None:
        raise RuntimeError("未找到「下一步」或「发布」按钮")

    if entry.is_disabled():
        raise RuntimeError("发布按钮当前不可用")

    entry.click()
    page.wait_for_timeout(1500)

    confirm = page.get_by_role("button", name=re.compile(r"确认发布|确定")).first
    try:
        if confirm.is_visible(timeout=5000):
            confirm.click()
            page.wait_for_timeout(2500)
    except PlaywrightTimeout:
        # 有的流程没有二次确认
        pass


def publish_one_chapter(
    page: Page,
    cfg: dict,
    chapter_num: int,
    title: str,
    body: str,
    mode: str,
) -> None:
    url = new_chapter_url(cfg)
    print(f"  -> 打开编辑器: {url}")
    page.goto(url, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(2000)

    dismiss_guides(page)

    page.locator(SEL_TITLE).first.wait_for(state="visible", timeout=15000)
    page.locator(SEL_EDITOR).first.wait_for(state="visible", timeout=15000)

    print(f"  -> 填写标题: {title}")
    fill_title(page, title)

    print(f"  -> 填写正文 ({len(body)} 字)...")
    fill_body(page, body)

    min_words = max(20, min(100, len(body) // 2))
    count = wait_word_count(page, min_words, cfg.get("word_count_timeout", 20))
    print(f"  -> 编辑器字数: {count}")

    if mode == "draft":
        print("  -> 存草稿...")
        click_save_draft(page)
        print("  -> ✅ 草稿已保存")
    elif mode == "publish":
        print("  -> 尝试正式发布...")
        try_publish(page)
        page.wait_for_timeout(2000)
        print("  -> ✅ 已执行发布流程（请在后台核对章节状态）")
    else:
        raise ValueError(f"未知模式: {mode}")


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="番茄小说自动填章/发布")
    p.add_argument("--start", type=int, default=1, help="起始章节序号（含）")
    p.add_argument("--end", type=int, default=0, help="结束章节序号（含），0=到最后一章")
    p.add_argument("--count", type=int, default=0, help="最多发布 N 章（与 start/end 二选一逻辑，优先 count）")
    p.add_argument("--mode", choices=["draft", "publish"], default=None, help="draft=只存草稿; publish=正式发布")
    p.add_argument("--resume", action="store_true", help="跳过 published_log 中已发布章节")
    p.add_argument("--dry-run", action="store_true", help="只打印计划，不启动浏览器")
    p.add_argument("--no-headless", action="store_true", default=True, help="显示浏览器（默认开启）")
    p.add_argument("--delay", type=int, default=None, help="章间间隔秒数")
    return p


def main() -> None:
    args = build_arg_parser().parse_args()
    cfg = load_config()
    mode = args.mode or cfg.get("default_mode", "draft")
    delay = args.delay if args.delay is not None else cfg.get("delay_between_chapters", 8)

    state_path = ROOT / cfg["state_file"]
    if not args.dry_run and not state_path.exists():
        print(f"❌ 未找到登录状态: {state_path}")
        print("请先运行: python scripts/fanqie_publish/login.py")
        sys.exit(1)

    files = list_chapter_files(cfg)
    if not files:
        print(f"❌ 未找到章节文件: {chapters_path(cfg)}")
        sys.exit(1)

    chapters: list[tuple[int, str, str, Path]] = []
    for f in files:
        num, title, body = parse_chapter_file(f)
        chapters.append((num, title, body, f))
    chapters.sort(key=lambda x: x[0])

    published = load_published_log(cfg) if args.resume else set()

    selected = [c for c in chapters if c[0] >= args.start]
    if args.end and args.end > 0:
        selected = [c for c in selected if c[0] <= args.end]
    if args.count and args.count > 0:
        selected = selected[: args.count]
    if args.resume:
        selected = [c for c in selected if c[0] not in published]

    if not selected:
        print("没有待发布的章节。")
        return

    print("=" * 60)
    print(f"模式: {mode} | 待处理: {len(selected)} 章 | 章间间隔: {delay}s")
    print("=" * 60)
    for num, title, body, path in selected:
        print(f"  [{num:02d}] {title}  ({len(body)} 字)  <- {path.name}")
    print("=" * 60)

    if args.dry_run:
        print("dry-run 结束，未启动浏览器。")
        return

    if mode == "publish":
        ans = input("⚠️  publish 模式将尝试正式发布。确认继续? [y/N] ").strip().lower()
        if ans != "y":
            print("已取消。")
            return

    success: list[int] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not args.no_headless)
        context = browser.new_context(storage_state=str(state_path))
        page = context.new_page()

        for i, (num, title, body, path) in enumerate(selected, 1):
            print(f"\n[{i}/{len(selected)}] 第{num}章 {title}")
            try:
                publish_one_chapter(page, cfg, num, title, body, mode)
                success.append(num)
                published.add(num)
                save_published_log(cfg, published)
            except Exception as e:
                print(f"  ❌ 失败: {e}")
                ans = input("  按回车跳过本章继续，或输入 q 退出: ").strip().lower()
                if ans == "q":
                    break
            if i < len(selected):
                print(f"  ... 等待 {delay} 秒")
                time.sleep(delay)

        browser.close()

    print("\n" + "=" * 60)
    print(f"完成。成功: {len(success)} 章 -> {success}")
    print("请到番茄作家后台核对章节列表。")
    print("=" * 60)


if __name__ == "__main__":
    main()
