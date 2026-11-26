"""
Independent Per-Account Browser Profile Manager (Local Playwright + System Chrome).
One account = one isolated persistent user_data_dir under profiles/<account_name>/.
Supports scaling to multiple concurrent accounts without session collision or cookie leakage.
"""
import json
import os
from playwright.sync_api import sync_playwright

SKILL_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_ACCOUNTS_PATH = os.path.join(SKILL_ROOT, "config", "accounts.json")


def resolve_accounts_config(accounts_config=None):
    """Resolve the accounts.json path from argument, env var, or default config/."""
    path = accounts_config or os.environ.get("DBP_ACCOUNTS_CONFIG") or DEFAULT_ACCOUNTS_PATH
    return os.path.abspath(path)


def _config_base_dir(cfg_path):
    parent = os.path.dirname(cfg_path)
    if os.path.basename(parent).lower() == "config":
        return os.path.dirname(parent)
    return parent


def load_accounts_config(accounts_config=None):
    cfg_path = resolve_accounts_config(accounts_config)
    if not os.path.exists(cfg_path):
        raise FileNotFoundError(
            f"未找到账号配置文件：{cfg_path}\n"
            f"请先复制 config/accounts.example.json 为 config/accounts.json 并填写本地账号与 profile_dir。"
        )
    with open(cfg_path, "r", encoding="utf-8-sig") as f:
        return json.load(f), cfg_path


def get_account_info(account_name=None, accounts_config=None):
    cfg, cfg_path = load_accounts_config(accounts_config)
    accounts = cfg.get("accounts", {})
    if not accounts:
        raise ValueError(f"账号配置 {cfg_path} 中的 accounts 为空。")

    if account_name is None:
        if len(accounts) == 1:
            account_name = next(iter(accounts.keys()))
        else:
            raise ValueError(
                f"配置中存在多个账号，请显式指定 --account。当前已注册：{list(accounts.keys())}"
            )

    if account_name not in accounts:
        raise KeyError(
            f"账号「{account_name}」未在 {cfg_path} 注册。当前已注册：{list(accounts.keys())}"
        )

    info = dict(accounts[account_name])
    info["account_name"] = account_name
    info["browser_channel"] = info.get("browser_channel") or cfg.get("browser_channel", "chrome")

    raw_profile = info.get("profile_dir") or os.path.join("profiles", account_name)
    if not os.path.isabs(raw_profile):
        base_dir = _config_base_dir(cfg_path)
        raw_profile = os.path.abspath(os.path.join(base_dir, raw_profile))
    info["profile_dir"] = raw_profile
    os.makedirs(info["profile_dir"], exist_ok=True)
    return info


class AccountBrowserSession:
    """Context manager opening a dedicated persistent Chrome context for one account."""

    def __init__(
        self,
        account_name=None,
        headless=False,
        accounts_config=None,
        viewport=None,
        locale="zh-CN",
        timezone_id="Asia/Shanghai",
    ):
        self.info = get_account_info(account_name, accounts_config=accounts_config)
        self.account_name = self.info["account_name"]
        self.headless = headless
        self.viewport = viewport or {"width": 1440, "height": 900}
        self.locale = locale
        self.timezone_id = timezone_id
        self._pw = None
        self.context = None

    def __enter__(self):
        self._pw = sync_playwright().start()
        self.context = self._pw.chromium.launch_persistent_context(
            user_data_dir=self.info["profile_dir"],
            channel=self.info["browser_channel"],
            headless=self.headless,
            viewport=self.viewport,
            locale=self.locale,
            timezone_id=self.timezone_id,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-first-run",
                "--no-default-browser-check",
            ],
            ignore_default_args=["--enable-automation"],
        )
        # Hide navigator.webdriver to reduce creator-platform false positives
        self.context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', { get: () => undefined });"
        )
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.context:
            try:
                self.context.close()
            except Exception:
                pass
        if self._pw:
            try:
                self._pw.stop()
            except Exception:
                pass
