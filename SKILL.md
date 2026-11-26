---
name: douyin-bilibili-publisher
description: >-
  Isolated multi-account Chrome profile auto-publisher for Douyin and Bilibili via local Playwright.
  Use whenever the user asks to set up multi-account creator login isolation, scan QR codes for
  persistent sessions, upload videos to Douyin and/or Bilibili with dual-ratio covers (Douyin 4:3+3:4,
  Bilibili 4:3+16:9), attach Douyin hashtags and verified game handles (游戏手柄), save drafts safely,
  or run randomized staggered batch publishing across multiple episodes.
---

# Douyin & Bilibili Multi-Account Auto-Publisher (`douyin-bilibili-publisher`)

将「一号一独立原生 Chrome 持久化隔离 + 抖音/B 站双平台双比例封面上传 + 抖音游戏手柄实测强校验挂载 + 草稿优先安全闸门 + 随机分钟错峰批发」封装为可复用的标准产线。

## 核心铁律（执行前必读）

1. **多号隔离与隐私边界**：
   - 每个账号绑定独立 `user_data_dir`（`profiles/<account>/`），通过原生 Chrome（`channel="chrome"`）持久化登录态，**严禁导出/搬运/共享 Cookie 或将 `profiles/`、`config/accounts.json` 提交到任何仓库**。
   - 详见 [references/multi-account-isolation.md](./references/multi-account-isolation.md)。
2. **抖音游戏手柄与草稿箱重开铁律**：
   - 严格路径：`扩展信息` → `添加标签` → 下拉选 `游戏手柄` → `添加作品同款游戏` 输入关键词（兼容 `summon.bytedance.com` iframe）→ 精准点击下拉项游戏标题左侧文字（**严禁误点右侧 `详情 >`**，且兼容抖音红字高亮拆分 `<span>` 的 DOM 结构）→ 弹窗关闭 + 占位符消失 + 与 `添加标签` 同行三重强校验 + 截屏 `douyin_handle_attached.png`；失败直接抛错，绝不静默跳过。
   - **草稿重开清空陷阱**：抖音点击「暂存离开」后再点「继续编辑」，虽保留视频/封面/话题，但**会清空 `游戏手柄` 已选游戏**。因此正式发布当次会话**必须重新挂载并强校验游戏手柄**。
   - 详见 [references/douyin-game-handle-and-tags.md](./references/douyin-game-handle-and-tags.md)。
3. **双平台双比例封面上传**：
   - **抖音**：单弹窗内连续完成 `设置横封面 (4:3)` 与 `设置竖封面 (3:4)`（几何距离 `<150px` 匹配 `input[type=file]`，兜底鼠标中心 `expect_file_chooser`），等待保存关闭，异常必按 `Escape` 防阻塞后续挂载。
   - **B 站**：等视频上传完成后打开 `.cover-editor`，依次填入 `4:3 首页推荐` 与切换 `.inactive` 槽位填入 `16:9 个人空间`，点击 `<div>完成</div>`。
   - 详见 [references/dual-ratio-cover-upload.md](./references/dual-ratio-cover-upload.md)。
4. **安全发布与错峰间隔**：
   - 默认 `--mode draft` 存草稿；正式发布必须获用户当次明确授权并同时传入 `--mode publish --confirm-publish`。
   - 批量发布多条成片时禁止连续无间隔推送，必须使用 [scripts/stagger_publish.py](./scripts/stagger_publish.py) 按随机分钟间隔（默认 `180–600s`）错峰逐条执行。

---

## 标准操作流程

### 1. 注册账号与独立扫码保活
1. 复制 [config/accounts.example.json](./config/accounts.example.json) 为 `config/accounts.json`（已 gitignore），按需配置账号与相对路径 `profiles/<account>`。
2. 首次登录或登录态失效时运行（Windows 也可参考 [examples/launch_qr_login.example.cmd](./examples/launch_qr_login.example.cmd)）：
   ```powershell
   python -X utf8 scripts/login_account.py --account demo_account_1 --auto-wait
   ```
3. 巡检双平台登录态：
   ```powershell
   python -X utf8 scripts/login_account.py --account demo_account_1 --check-only
   ```

### 2. 编写任务单并做 Dry-Run 校验
参考 [examples/publish_job.example.json](./examples/publish_job.example.json) 准备 `job.json`，先跑前置校验（不启动浏览器）：
```powershell
python -X utf8 scripts/publish_dual.py path/to/publish_job.json --dry-run
```

### 3. 双平台上传（默认存草稿 → 授权后正式发布）
```powershell
# 默认安全模式：上传视频/双比例封面/话题/可选游戏手柄并存草稿
python -X utf8 scripts/publish_dual.py path/to/publish_job.json

# 按需强制开关游戏手柄（on / off）
python -X utf8 scripts/publish_dual.py path/to/publish_job.json --game-handle on

# 仅在用户明确授权本次发布后执行正式发布
python -X utf8 scripts/publish_dual.py path/to/publish_job.json --mode publish --confirm-publish --game-handle on
```

### 4. 多条随机间隔错峰批发
参考 [examples/batch_jobs.example.json](./examples/batch_jobs.example.json)：
```powershell
# 先 dry-run 校验全部任务单
python -X utf8 scripts/stagger_publish.py --batch-file path/to/batch_jobs.json --dry-run

# 授权后随机间隔 3~9 分钟错峰双平台正式发布
python -X utf8 scripts/stagger_publish.py --batch-file path/to/batch_jobs.json --min-delay 180 --max-delay 540 --mode publish --confirm-publish
```

### 5. 截屏核验清单
每次运行后检查 `log_dir`（默认 `<job_dir>/publish_logs/`）下的关键留痕：
- 抖音：`douyin_topics_verify.png`（滚回顶部后确认话题全部转蓝）、`douyin_cover_4x3_uploaded.png`、`douyin_cover_3x4_uploaded.png`、`douyin_handle_attached.png`、`douyin_draft.png` / `douyin_published.png`。
- B 站：`bilibili_cover_modal.png`、`bilibili_topic_selected.png`、`bilibili_ready.png`、`bilibili_draft.png` / `bilibili_published.png`。
