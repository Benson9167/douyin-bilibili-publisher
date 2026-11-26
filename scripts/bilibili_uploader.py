"""
Bilibili Creator Center Auto-Uploader (Local Playwright Persistent Chrome Profile).

Key features:
  - Uses isolated account profile (profiles/<account>/) -> multi-account safe
  - Auto-dismisses fresh-profile notification popups (`.videoup-notification-dialog`)
  - Waits for video upload completion before opening `.cover-editor`
  - Uploads BOTH 4:3 (首页推荐封面, active slot) and 16:9 (个人空间封面, `.inactive` slot)
  - Selects main topic via `参与话题 -> 搜索更多话题 >` with configurable fallback keywords
  - Fills up to 10 tags + description + `自制` + configurable creation declaration (`内容无需标注`)
  - SAFE BY DEFAULT: mode="draft" saves draft (`存草稿`). Final publish requires
    explicit mode="publish" AND confirm_publish=True!
"""
import os
import time

BILIBILI_UPLOAD_URL = "https://member.bilibili.com/platform/upload/video/frame"


def _dismiss_bili_popups(target):
    for _ in range(3):
        dismissed = False
        for sel in (
            ".videoup-notification-dialog button:has-text('知道了')",
            ".videoup-notification-dialog .bcc-dialog__close",
            "button:has-text('知道了')",
            ".bcc-dialog__wrap .bcc-dialog__close",
        ):
            try:
                loc = target.locator(sel).first
                if loc.is_visible(timeout=1000):
                    loc.click(timeout=3000)
                    time.sleep(0.6)
                    dismissed = True
                    print(f"[B站] 已关闭引导弹窗：{sel}")
                    break
            except Exception:
                pass
        if not dismissed:
            break


def _upload_bili_cover(target, page, cover_16x9, log_dir, cover_4x3=None):
    c43 = cover_4x3 if (cover_4x3 and os.path.exists(cover_4x3)) else cover_16x9
    c169 = cover_16x9 if (cover_16x9 and os.path.exists(cover_16x9)) else cover_4x3
    if not c43 and not c169:
        return False
    print(f"[B站] 正在上传自定义双比例封面：4:3={c43} | 16:9={c169}")
    editor = target.locator(".cover-editor").first
    try:
        cover_btn = target.locator(
            ":text('添加封面'), :text('更改封面'), :text('更换封面'), .cover-upload, .upload-cover"
        ).first
        cover_btn.scroll_into_view_if_needed(timeout=6000)
        cover_btn.click(timeout=6000)
        editor.wait_for(state="visible", timeout=10000)
        time.sleep(1.5)
        page.screenshot(path=os.path.join(log_dir, "bilibili_cover_open.png"))

        def _set_cover_file(img_path, label):
            inp = editor.locator("input[type='file'][accept*='image']").last
            if inp.count() == 0:
                inp = editor.locator("input[type='file']").last
            if inp.count() == 0:
                inp = target.locator("input[type='file'][accept*='image']").last
            inp.set_input_files(img_path)
            print(f"[B站] 已填入 {label} 封面：{os.path.basename(img_path)}")
            time.sleep(2.8)

        # 1. Default active slot is `首页推荐封面 (4:3)`
        if c43:
            _set_cover_file(c43, "4:3 首页推荐")

        # 2. Activate `个人空间封面 (16:9)` (`.inactive`)
        if c169:
            try:
                inact = editor.locator(".inactive").first
                if inact.is_visible(timeout=2000):
                    inact.click(timeout=4000)
                    time.sleep(1.0)
                else:
                    lbl169 = editor.locator(":text('个人空间封面')").first
                    if lbl169.is_visible(timeout=1500):
                        lbl169.click(timeout=4000)
                        time.sleep(1.0)
                _set_cover_file(c169, "16:9 个人空间")
            except Exception as e:
                print(f"[B站] 切换 16:9 个人空间封面槽异常（继续保留 4:3）：{e}")

        page.screenshot(path=os.path.join(log_dir, "bilibili_cover_modal.png"))

        # 3. Click `完成` inside `.cover-editor` (actual element is a <div>, not <button>)
        done_clicked = False
        for sel in (
            ".cover-editor-button :text-is('完成')",
            ":text-is('完成')",
            ":text-is('确定')",
            ":text-is('确认')",
        ):
            try:
                btn = editor.locator(sel).last
                if btn.is_visible(timeout=2000):
                    btn.click(timeout=5000)
                    done_clicked = True
                    print(f"[B站] 已点击封面弹窗完成按钮：{sel}")
                    break
            except Exception:
                pass

        if done_clicked:
            editor.wait_for(state="hidden", timeout=10000)
            time.sleep(1.5)
            print("[B站] 4:3 + 16:9 自定义封面已保存并关闭弹窗")
            return True
        raise RuntimeError("未命中封面弹窗「完成」按钮")
    except Exception as e:
        page.screenshot(path=os.path.join(log_dir, "bilibili_cover_err.png"))
        try:
            cancel = editor.locator(":text-is('取消'), .bcc-dialog__close").first
            if cancel.is_visible(timeout=1200):
                cancel.click(timeout=2000)
            else:
                page.keyboard.press("Escape")
            time.sleep(1.0)
        except Exception:
            pass
        print(f"[B站] 封面上传异常：{e}")
        return False


def _select_bili_main_topic(target, page, main_topic, log_dir, fallback_keywords=None):
    """Click `搜索更多话题 >` under `参与话题`, search `main_topic`, select row, and click `确定`."""
    topic_name = (main_topic or "").lstrip("#").strip()
    if not topic_name:
        print("[B站] 未指定主话题，跳过「参与话题」选择。")
        return False

    print(f"[B站] 正在从「参与话题」搜索并勾选主话题：#{topic_name}")
    modal = target.locator(".bcc-dialog__wrap:has-text('参与话题'), .dialog:has-text('参与话题')").last
    try:
        direct = target.locator(f".topic-item:has-text('{topic_name}'), .topic-tag:has-text('{topic_name}')").first
        if direct.is_visible(timeout=1200):
            direct.click(timeout=3000)
            time.sleep(1.0)
            print(f"[B站] 直接点选了主话题：#{topic_name}")
            return True

        more_btn = target.locator(":text('搜索更多话题')").first
        more_btn.scroll_into_view_if_needed(timeout=5000)
        more_btn.click(timeout=6000)
        time.sleep(1.8)

        modal.wait_for(state="visible", timeout=8000)
        search_box = modal.locator("input[placeholder*='请输入'], input[placeholder*='搜索'], input").first
        search_box.wait_for(state="visible", timeout=6000)
        search_box.click()
        search_box.fill("")
        search_box.type(topic_name, delay=45)
        time.sleep(2.2)
        page.screenshot(path=os.path.join(log_dir, "bilibili_topic_search.png"))

        search_candidates = [topic_name]
        for kw in (fallback_keywords or []):
            clean_kw = (kw or "").lstrip("#").strip()
            if clean_kw and clean_kw not in search_candidates:
                search_candidates.append(clean_kw)

        clicked = False
        for kw in search_candidates:
            for sel in (
                f".topic-card:has-text('{kw}')",
                f".topic-item:has-text('{kw}')",
                f".topic-list-item:has-text('{kw}')",
                f"li:has-text('{kw}')",
                f":text('{kw}')",
            ):
                try:
                    loc = modal.locator(sel).first
                    if loc.is_visible(timeout=1200):
                        loc.click(timeout=4000)
                        clicked = True
                        print(f"[B站] 已在话题弹窗内选中：{kw} ({sel})")
                        time.sleep(1.0)
                        break
                except Exception:
                    pass
            if clicked:
                break

        if clicked:
            ok_btn = modal.locator("button:has-text('确定'), .bcc-button:has-text('确定'), :text-is('确定')").last
            ok_btn.click(timeout=5000)
            time.sleep(1.2)
        else:
            cancel_btn = modal.locator("button:has-text('取消'), :text-is('取消')").last
            if cancel_btn.is_visible(timeout=1500):
                cancel_btn.click(timeout=3000)
                time.sleep(0.8)

        page.screenshot(path=os.path.join(log_dir, "bilibili_topic_selected.png"))
        print(f"[B站] 主话题选择完成：{clicked}（请核对 bilibili_topic_selected.png）")
        return clicked
    except Exception as e:
        page.screenshot(path=os.path.join(log_dir, "bilibili_topic_err.png"))
        try:
            cancel_btn = modal.locator("button:has-text('取消'), :text-is('取消')").last
            if cancel_btn.is_visible(timeout=1200):
                cancel_btn.click(timeout=2000)
            else:
                page.keyboard.press("Escape")
            time.sleep(0.8)
        except Exception:
            pass
        print(f"[B站] 主话题勾选异常：{e}")
        return False


def upload_to_bilibili(
    session,
    video_path,
    title,
    desc,
    main_topic=None,
    topic_fallback_keywords=None,
    tags=None,
    cover_16x9=None,
    cover_4x3=None,
    declaration="内容无需标注",
    mode="draft",
    confirm_publish=False,
    log_dir=".",
):
    os.makedirs(log_dir, exist_ok=True)
    page = session.context.new_page()
    page.goto(BILIBILI_UPLOAD_URL, wait_until="domcontentloaded", timeout=30000)
    time.sleep(3.5)

    if "passport.bilibili.com" in page.url.lower():
        page.screenshot(path=os.path.join(log_dir, "bilibili_need_login.png"))
        raise RuntimeError(
            f"B站账号「{session.account_name}」未登录或会话已过期！请先执行：\n"
            f"  python -X utf8 scripts/login_account.py --account {session.account_name} --auto-wait"
        )

    target = page
    try:
        if page.locator("iframe[name='videoUpload'], iframe[src*='upload/video']").count() > 0:
            target = page.frame_locator("iframe[name='videoUpload'], iframe[src*='upload/video']").first
    except Exception:
        pass

    print(f"[B站] 正在上传视频：{video_path}")
    file_input = target.locator("input[type='file'][accept*='mp4'], input[type='file']").first
    file_input.set_input_files(video_path)
    time.sleep(4.0)
    _dismiss_bili_popups(target)
    page.screenshot(path=os.path.join(log_dir, "bilibili_uploading.png"))

    # Fill Title (max 80 chars on Bilibili)
    clean_title = (title or "")[:80]
    try:
        title_input = target.locator("input[placeholder*='标题']").first
        title_input.wait_for(state="visible", timeout=20000)
        title_input.click()
        title_input.press("Control+A")
        title_input.press("Backspace")
        title_input.fill(clean_title)
        print(f"[B站] 已填标题：{clean_title}")
    except Exception as e:
        print(f"[B站] 标题填写异常：{e}")

    # Ensure 自制 (Original) radio is checked
    try:
        orig = target.get_by_text("自制", exact=True).first
        if orig.is_visible(timeout=2000):
            orig.click()
    except Exception:
        pass

    # Select `* 创作声明`
    if declaration:
        try:
            decl_box = target.locator("input[placeholder*='创作声明'], :text('请选择符合您视频内容的创作声明')").first
            if decl_box.is_visible(timeout=2000):
                decl_box.scroll_into_view_if_needed()
                decl_box.click(timeout=4000)
                time.sleep(0.8)
                opt = target.locator(f":text-is('{declaration}')").last
                if opt.is_visible(timeout=2500):
                    opt.click(timeout=4000)
                    time.sleep(0.6)
                    print(f"[B站] 已选择创作声明：{declaration}")
        except Exception as e:
            print(f"[B站] 创作声明选择跳过/异常：{e}")

    # Wait for video upload completion BEFORE uploading cover so `+ 添加封面` is active
    print("[B站] 等待视频上传完成...")
    deadline = time.time() + 180
    while time.time() < deadline:
        try:
            txt = target.locator("body").inner_text()
            if ("上传完成" in txt) or ("更换视频" in txt):
                break
        except Exception:
            break
        time.sleep(2.0)
    time.sleep(1.5)

    # Upload custom 4:3 (首页推荐) + 16:9 (个人空间) covers
    cover_ok = False
    if cover_16x9 or cover_4x3:
        cover_ok = _upload_bili_cover(target, page, cover_16x9, log_dir, cover_4x3=cover_4x3)

    # Select Main Topic via `参与话题 -> 搜索更多话题 >`
    topic_ok = _select_bili_main_topic(
        target, page, main_topic, log_dir, fallback_keywords=topic_fallback_keywords
    )

    # Fill Tags (max 10)
    try:
        tag_list = [t.lstrip("#").strip() for t in (tags or []) if t and t.lstrip("#").strip()][:10]
        if tag_list:
            tag_input = target.locator("input[placeholder*='按回车键Enter创建标签'], input[placeholder*='标签']").first
            tag_input.scroll_into_view_if_needed(timeout=5000)
            for tg_clean in tag_list:
                tag_input.click()
                tag_input.fill(tg_clean)
                tag_input.press("Enter")
                time.sleep(0.35)
            print(f"[B站] 已填写标签：{tag_list}")
    except Exception as e:
        print(f"[B站] 标签填写异常：{e}")

    # Fill Description
    full_desc = (desc or "").strip()
    if main_topic:
        topic_line = main_topic if main_topic.startswith("#") else f"#{main_topic}"
        full_desc = f"{full_desc}\n{topic_line}".strip()
    try:
        desc_box = target.locator(".ql-editor, textarea[placeholder*='简介']").first
        desc_box.scroll_into_view_if_needed(timeout=5000)
        desc_box.click()
        desc_box.fill(full_desc)
        print("[B站] 已填写视频简介")
    except Exception as e:
        print(f"[B站] 简介填写异常：{e}")

    _dismiss_bili_popups(target)
    page.screenshot(path=os.path.join(log_dir, "bilibili_ready.png"), full_page=True)

    # Save draft OR explicitly authorized Publish
    if mode == "publish" and confirm_publish:
        pub_btn = target.locator("span:has-text('立即投稿'), button:has-text('立即投稿')").last
        pub_btn.scroll_into_view_if_needed()
        pub_btn.click()
        time.sleep(4.0)
        page.screenshot(path=os.path.join(log_dir, "bilibili_published.png"))
        print("[B站] 已点击立即投稿（请核对 bilibili_published.png）")
        return {"status": "published", "cover_uploaded": cover_ok, "main_topic_selected": topic_ok, "url": page.url}

    saved = False
    for label in ("存草稿", "保存草稿"):
        btn = target.locator(f"span:has-text('{label}'), button:has-text('{label}')").first
        try:
            if btn.is_visible(timeout=2500):
                btn.scroll_into_view_if_needed()
                btn.click()
                time.sleep(3.5)
                saved = True
                break
        except Exception:
            pass
    page.screenshot(path=os.path.join(log_dir, "bilibili_draft.png"))
    status = "draft_saved" if saved else "uploaded_pending_confirm"
    print(f"[B站] 安全停在草稿阶段：{status}（未正式发布）")
    return {"status": status, "cover_uploaded": cover_ok, "main_topic_selected": topic_ok, "url": page.url}
