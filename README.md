# douyin-bilibili-publisher

基于本地 Playwright + 系统原生 Chrome 持久化 Profile 的**抖音 + B 站双平台多账号隔离自动发布工具 & AI Agent Skill**。

## 核心特性

1. **单浏览器多账号严格隔离**
   - 一号一独立 `user_data_dir`（`profiles/<account>/`），直接驱动本机原生 Chrome（`channel="chrome"`），隐藏 `navigator.webdriver` 等自动化标记，多账号并行零串号、无需导出 Cookie。
   - 提供双平台同步扫码保活工具 `scripts/login_account.py`（支持 `--check-only` 巡检、`--auto-wait` 抖音扫完自动切 B 站、可选生成 Windows `.cmd` 快捷登录脚本）。
2. **抖音话题 + 游戏手柄实测强校验挂载**
   - 话题逐字键入 + 空格转蓝标，回滚顶部清浮层并自动截取 `douyin_topics_verify.png`。
   - 完整实录路径：`扩展信息 → 添加标签 → 切换「游戏手柄」→ 输入同款游戏关键词（兼容 summon.bytedance.com iframe）→ 兼容红字高亮拆分 DOM 精准点击游戏标题左侧（避开右侧「详情 >」）→ 弹窗关闭/占位符消失/同行文本三重强校验 + 截屏留痕`，失败立即抛错。
   - 内置实践铁律提醒：抖音存草稿后重开会清空游戏手柄，正式发布当次会话务必重新挂载校验。
3. **双平台双比例封面优化上传**
   - **抖音**：单弹窗内连续上传 `横封面 4:3` + `竖封面 3:4`（按几何距离 `<150px` 命中对应 `input[type=file]`，兜底鼠标中心 `expect_file_chooser`，最长 25s 等待关窗，异常自动 `Escape` 防阻塞后续表单操作）。
   - **B 站**：等待视频上传完成后打开 `.cover-editor`，依次上传 `4:3 首页推荐` 与切换 `.inactive` 槽位上传 `16:9 个人空间`，精准点击 `<div>完成</div>` 保存，并自动处理 `自制`、`创作声明` 与 `参与话题 → 搜索更多话题` 勾选。
4. **草稿优先安全闸门 + 随机间隔错峰批发**
   - 默认 `--mode draft` 仅保存草稿；正式发布必须显式同时传入 `--mode publish --confirm-publish`。
   - `scripts/stagger_publish.py` 支持批量任务前置全量校验，并在相邻任务间插入随机分钟级延迟（默认 `180–600s`），避免连续高频发布触发平台风控。

---

## 目录结构

```text
douyin-bilibili-publisher/
├── SKILL.md                             # Antigravity / Agent Skill 入口规范
├── README.md
├── LICENSE                              # MIT License
├── requirements.txt                     # playwright>=1.45.0
├── .gitignore                           # 强制忽略 profiles/、accounts.json 与媒体/日志产物
├── config/
│   └── accounts.example.json            # 多账号 Profile 注册表脱敏模板
├── examples/
│   ├── publish_job.example.json         # 单条双平台发布任务单模板
│   ├── batch_jobs.example.json          # 随机错峰批发清单模板
│   └── launch_qr_login.example.cmd      # Windows 原生 Chrome 独立扫码快捷脚本模板
├── references/
│   ├── multi-account-isolation.md       # 多号隔离架构与扫码保活说明
│   ├── douyin-game-handle-and-tags.md   # 抖音话题与游戏手柄实测 DOM 细节与校验机制
│   └── dual-ratio-cover-upload.md       # 抖音/B站双比例封面弹窗定位与容错说明
└── scripts/
    ├── __init__.py
    ├── browser_profile.py               # 独立 Chrome user_data_dir 会话管理器
    ├── login_account.py                 # 双平台扫码登录与状态巡检
    ├── douyin_uploader.py               # 抖音上传 + 双封面 + 话题 + 游戏手柄强校验
    ├── bilibili_uploader.py             # B站上传 + 双比例封面 + 话题弹窗 + 创作声明
    ├── publish_dual.py                  # 统一双平台发布入口（含 dry-run 与安全门禁）
    └── stagger_publish.py               # 多条任务随机分钟间隔错峰批发器
```

---

## 安装与环境准备

- Python 3.10+
- 本机已安装 Google Chrome（Playwright 通过 `channel="chrome"` 直接启动系统原生 Chrome）

```powershell
pip install -r requirements.txt
```

### 作为 Antigravity Skill 使用
将本仓库目录直接放入全局或工作区 Skills 目录即可自动发现：
- 全局：`~/.gemini/config/skills/douyin-bilibili-publisher/`
- 工作区：`<workspace>/.agents/skills/douyin-bilibili-publisher/`

---

## 快速上手

### 1. 配置账号（本地私有，已加入 `.gitignore`）
```powershell
Copy-Item config\accounts.example.json config\accounts.json
```
编辑 `config\accounts.json`，为每个账号指定独立的 `profile_dir`（如 `profiles/account_a`、`profiles/account_b`）。

### 2. 独立浏览器扫码登录（一次扫码，持久保活）
```powershell
python -X utf8 scripts/login_account.py --account demo_account_1 --auto-wait
```
仅检查当前登录态是否有效：
```powershell
python -X utf8 scripts/login_account.py --account demo_account_1 --check-only
```

### 3. 准备任务单并做 Dry-Run 校验
参考 `examples/publish_job.example.json` 创建你的 `job.json`，先在不启动浏览器的情况下校验文件、话题数与参数：
```powershell
python -X utf8 scripts/publish_dual.py examples/publish_job.example.json --dry-run
```

### 4. 单条双平台上传
```powershell
# 默认安全模式：保存双平台草稿（不直接公开）
python -X utf8 scripts/publish_dual.py path/to/job.json

# 开启抖音游戏手柄挂载并存草稿
python -X utf8 scripts/publish_dual.py path/to/job.json --game-handle on

# 显式确认后正式双平台发布
python -X utf8 scripts/publish_dual.py path/to/job.json --mode publish --confirm-publish --game-handle on
```

### 5. 随机间隔错峰批发
```powershell
# 校验批量清单
python -X utf8 scripts/stagger_publish.py --batch-file examples/batch_jobs.example.json --dry-run

# 每条间隔 3.5 ~ 9 分钟随机错峰发布
python -X utf8 scripts/stagger_publish.py --batch-file path/to/batch_jobs.json --min-delay 210 --max-delay 540 --mode publish --confirm-publish
```

---

## 安全与隐私边界

- **本地登录态严禁外传**：`profiles/` 目录保存真实浏览器会话数据，`config/accounts.json` 保存本地账号映射，均已在 `.gitignore` 中强制忽略，切勿提交到公开或共享仓库。
- **默认不自动公开发布**：所有上传脚本默认 `mode="draft"`，只有显式同时传入 `--mode publish --confirm-publish` 时才会点击最终发布按钮。
- **截图留痕**：每次执行会在 `log_dir` 下保存每一步的页面截图与 `publish_result.json`，方便排查平台 UI 变动或复核发布结果。
