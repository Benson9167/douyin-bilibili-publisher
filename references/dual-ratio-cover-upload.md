# 抖音 & B 站双比例封面优化上传方案

## 1. 抖音统一双封面弹窗（`4:3 横封面` + `3:4 竖封面`）

抖音创作者后台点击 `选择封面` 后，会在同一 `.dy-creator-content-modal-content` 弹窗内同时提供 `设置横封面` 和 `设置竖封面` 两个 Tab：

1. **精准命中对应槽位的 `<input type="file">`**
   - 弹窗内可能同时存在多个隐藏文件输入框，直接取 `.first` 容易错传到错误比例槽位；
   - 本方案定位弹窗内可见的 `上传封面` 文本区域坐标 `lbox`，遍历所有 `input[type='file']` 父容器的几何中心，计算欧氏距离 `d`，优先命中 `best_dist < 150px` 的最近输入框并 `set_input_files(img_path)`；
   - 若未命中 `<150px` 输入框，则兜底用 `page.expect_file_chooser()` 配合 `page.mouse.click` 点击 `上传封面` 中心点。
2. **双 Tab 连传与关窗等待**
   - 先切 `设置横封面` 上传 `cover_4x3` 并截图 `douyin_cover_4x3_uploaded.png`；
   - 再切 `设置竖封面` 上传 `cover_3x4` 并截图 `douyin_cover_3x4_uploaded.png`；
   - 点击弹窗底部最后一个 `完成` 按钮，最长轮询等待 `25s` 直到弹窗与遮罩彻底关闭（若出现 `暂不设置` 提示框则自动处理）；
   - **异常必关窗原则**：一旦上传异常立即截图 `douyin_cover_dual_err.png` 并发送 `Escape`，确保半透明弹窗遮罩不会拦截后续的 `游戏手柄` 与 `暂存离开` 点击。

## 2. B 站投稿双比例封面编辑器（`4:3 首页推荐` + `16:9 个人空间`）

1. **时机控制**：必须等待视频进度出现 `上传完成` 或 `更换视频` 后再点击 `添加封面 / 更改封面 / 更换封面`，否则封面按钮处于不可交互状态。
2. **双槽位顺序填写**：
   - 打开 `.cover-editor` 后，默认激活槽位是 **`首页推荐封面 (4:3)`**，先调用 `set_input_files(cover_4x3)`（无裁切匹配）；
   - 随后定位 `.inactive` 或 `个人空间封面` 标签点击激活第二个槽位，再填入 `cover_16x9` 并截图 `bilibili_cover_modal.png`。
3. **非 `<button>` 完成按钮兼容**：
   - B 站 `.cover-editor` 内的蓝色 `完成` 按钮实际为 `<div>` 元素而非 `<button>`，因此按 `.cover-editor-button :text-is('完成')`、`text-is('完成')` 依次匹配点击，并等待 `.cover-editor` 变为 `hidden`。
   - 同样遵守**异常必关窗**：失败后自动点击 `取消` / `.bcc-dialog__close` 或 `Escape`，绝不遮挡后续 `参与话题`、标签与简介填写。
