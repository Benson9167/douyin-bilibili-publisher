# 单浏览器多账号隔离架构（`browser_profile.py` & `login_account.py`）

## 1. 核心隔离原理

本方案**不使用跨进程注入登录态或人工搬运敏感凭证**，而是让每个发布账号独占一个物理隔离的原生 Chrome `user_data_dir`：

```text
profiles/
├── account_a/   # 账号 A 的本地缓存、IndexedDB、登录态、窗口偏好
├── account_b/   # 账号 B 的本地缓存、IndexedDB、登录态、窗口偏好
└── account_c/   # 账号 C ...
```

通过 Playwright 的 `launch_persistent_context(..., channel="chrome")` 直接调起系统原生 Chrome：
- **真浏览器指纹**：非 Chromium 测试壳，极大降低创作者后台异常环境风控概率；
- **反检测参数**：启用 `--disable-blink-features=AutomationControlled`、`ignore_default_args=["--enable-automation"]`，并注入 `Object.defineProperty(navigator, 'webdriver', { get: () => undefined })`；
- **固定中文环境**：统一 `locale="zh-CN"`、`timezone_id="Asia/Shanghai"`、`viewport={"width": 1440, "height": 900}`，保证上传弹窗坐标与 DOM 布局稳定可复现；
- **多号零串号**：不同账号同时或交替运行均读写各自 `profile_dir`，不会串号、互踢或污染主浏览器日常账号。

## 2. 扩号步骤

1. 在 `config/accounts.json` 的 `accounts` 字典新增一条记录，指定独立 `profile_dir`（建议使用相对路径 `profiles/<account_name>`）。
2. 执行扫码脚本一次性登录双平台：
   ```powershell
   python -X utf8 scripts/login_account.py --account <account_name> --auto-wait
   ```
   - 脚本会同时打开抖音创作者中心与 B 站创作中心两个标签页；
   - 抖音扫码通过后自动切到 B 站标签页；
   - 两边均登录后额外等待 4 秒让 Chrome 将持久会话刷盘再退出。
3. 后续自动发布前可用 `--check-only` 快速巡检是否掉线。

## 3. 并发锁与隐私纪律

- **同账号单实例**：同一个 `user_data_dir` 同一时间只能被一个 Chrome 进程打开；运行自动化前若曾手动打开过该账号的独立窗口，需先关闭，否则会报目录锁冲突。
- **严禁入库**：`profiles/` 与 `config/accounts.json` 已在 `.gitignore` 中排除，切勿提交到公开或第三方仓库。
