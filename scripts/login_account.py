"""
One-time (or renewal) QR login helper for an isolated account Profile.
Opens Douyin Creator Center and/or Bilibili Creator Center in the account's dedicated
Chrome user_data_dir so the creator can scan QR codes once and keep sessions persistent.

Usage:
  python -X utf8 scripts/login_account.py --account demo_account_1 --auto-wait
  python -X utf8 scripts/login_account.py --account demo_account_1 --check-only
"""
import argparse
import os
import sys
import time

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from browser_profile import AccountBrowserSession, get_account_info

DOUYIN_UPLOAD_URL = "https://creator.douyin.com/creator-micro/content/upload"
BILIBILI_UPLOAD_URL = "https://member.bilibili.com/platform/upload/video/frame"


def check_login_state(page, platform):
    try:
        url = page.url.lower()
    except Exception:
        return False
    if platform == "douyin":
        if ("creator.douyin.com/creator-micro" in url) and ("login" not in url):
            try:
                txt = page.locator("body").inner_text(timeout=1500)
                if ("上传视频" in txt) or ("发布视频" in txt) or ("内容管理" in txt) or ("高清发布" in txt):
                    return True
            except Exception:
                return True
        return False
    if platform == "bilibili":
        return ("member.bilibili.com/platform" in url) and ("passport.bilibili.com" not in url)
    return False


def generate_windows_cmd(account_name, out_path, accounts_config=None):
    info = get_account_info(account_name, accounts_config=accounts_config)
    chrome_exe = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
    content = (
        "@echo off\n"
        f'start "" "{chrome_exe}" --user-data-dir="{info["profile_dir"]}" '
        '--no-first-run --no-default-browser-check '
        f'"{DOUYIN_UPLOAD_URL}" "{BILIBILI_UPLOAD_URL}"\n'
    )
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"[OK] 已生成独立 Chrome 扫码快捷脚本：{out_path}")
    return out_path


def run_login(
    account_name=None,
    accounts_config=None,
    platforms=("douyin", "bilibili"),
    check_only=False,
    auto_wait=False,
    timeout_sec=360,
):
    use_dy = "douyin" in platforms
    use_bi = "bilibili" in platforms
    if not use_dy and not use_bi:
        raise ValueError("platforms 至少需包含 douyin 或 bilibili。")

    with AccountBrowserSession(account_name, headless=False, accounts_config=accounts_config) as sess:
        dy_page = None
        b_page = None

        if use_dy:
            dy_page = sess.context.pages[0] if sess.context.pages else sess.context.new_page()
            dy_page.goto(DOUYIN_UPLOAD_URL, wait_until="domcontentloaded", timeout=30000)

        if use_bi:
            b_page = sess.context.new_page() if dy_page else (
                sess.context.pages[0] if sess.context.pages else sess.context.new_page()
            )
            b_page.goto(BILIBILI_UPLOAD_URL, wait_until="domcontentloaded", timeout=30000)

        if dy_page:
            try:
                dy_page.bring_to_front()
            except Exception:
                pass

        time.sleep(3)
        dy_ok = check_login_state(dy_page, "douyin") if dy_page else True
        b_ok = check_login_state(b_page, "bilibili") if b_page else True

        print(f"=== 账号「{sess.account_name}」独立 Chrome 登录状态 ===", flush=True)
        print(f"  Profile 目录: {sess.info['profile_dir']}", flush=True)
        if dy_page:
            print(f"  抖音创作者中心: {'已登录' if dy_ok else '等待扫码'} | URL={dy_page.url}", flush=True)
        if b_page:
            print(f"  B站创作中心   : {'已登录' if b_ok else '等待扫码'} | URL={b_page.url}", flush=True)

        if check_only:
            return dy_ok and b_ok

        if auto_wait:
            switched_to_b = False
            deadline = time.time() + timeout_sec
            while time.time() < deadline:
                if dy_page and not dy_ok and check_login_state(dy_page, "douyin"):
                    dy_ok = True
                    print("  [OK] 抖音登录成功！", flush=True)
                    if b_page and not b_ok and not switched_to_b:
                        try:
                            b_page.bring_to_front()
                            switched_to_b = True
                        except Exception:
                            pass
                if b_page and not b_ok and check_login_state(b_page, "bilibili"):
                    b_ok = True
                    print("  [OK] B站创作中心登录成功！", flush=True)
                if dy_ok and b_ok:
                    print("  [DONE] 目标平台均已登录，等待 4 秒写入持久化登录态...", flush=True)
                    time.sleep(4)
                    return True
                time.sleep(2)
            print(f"  [TIMEOUT] 等待超时 -> 抖音: {dy_ok} | B站: {b_ok}", flush=True)
            return dy_ok and b_ok

        print("\n请在弹出的独立 Chrome 窗口中完成扫码登录，完成后按 Enter 退出...", flush=True)
        try:
            input()
        except EOFError:
            pass

        dy_ok = check_login_state(dy_page, "douyin") if dy_page else True
        b_ok = check_login_state(b_page, "bilibili") if b_page else True
        print(f"保存前复核 -> 抖音: {'已登录' if dy_ok else '未登录'} | B站: {'已登录' if b_ok else '未登录'}", flush=True)
        return dy_ok and b_ok


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Login Douyin + Bilibili in an isolated Playwright Chrome profile")
    ap.add_argument("--account", default=None, help="Account name in accounts.json (optional if only 1 account)")
    ap.add_argument("--accounts-config", default=None, help="Path to accounts.json")
    ap.add_argument("--platforms", default="douyin,bilibili", help="Comma-separated: douyin,bilibili")
    ap.add_argument("--check-only", action="store_true", help="Only check session status and exit")
    ap.add_argument("--auto-wait", action="store_true", help="Poll until selected platforms are logged in")
    ap.add_argument("--timeout", type=int, default=360, help="Auto-wait timeout seconds (default 360)")
    ap.add_argument("--generate-cmd", default=None, help="Generate a Windows .cmd launcher for this account and exit")
    args = ap.parse_args()

    if args.generate_cmd:
        info = get_account_info(args.account, accounts_config=args.accounts_config)
        generate_windows_cmd(info["account_name"], args.generate_cmd, accounts_config=args.accounts_config)
        sys.exit(0)

    plats = tuple(p.strip() for p in args.platforms.split(",") if p.strip())
    ok = run_login(
        account_name=args.account,
        accounts_config=args.accounts_config,
        platforms=plats,
        check_only=args.check_only,
        auto_wait=args.auto_wait,
        timeout_sec=args.timeout,
    )
    sys.exit(0 if ok else 1)
