"""
Douyin Creator Center Auto-Uploader (Local Playwright Persistent Chrome Profile).

Key features:
  - Uses isolated account profile (profiles/<account>/) -> multi-account safe
  - Enforces topic entry with space conversion + top-scroll unobstructed verification
  - Custom Cover Upload: supports BOTH 横封面 4:3 (`cover_4x3`) and 竖封面 3:4 (`cover_3x4`)
  - Verified Game Handle Attachment Flow:
      1) 扩展信息 -> 添加标签 -> click tag-type dropdown (`位置`) -> select `游戏手柄`
      2) Click right-side input `添加作品同款游戏` -> type `game_keyword`
      3) Handle red-highlighted keyword split spans -> click game title text (NEVER click `详情 >`!)
      4) Strict 3-layer row verification + screenshot capture (`douyin_handle_attached.png`)
  - SAFE BY DEFAULT: mode="draft" saves draft (`暂存离开`). Final publish requires
    explicit mode="publish" AND confirm_publish=True.
  - IMPORTANT: Douyin clears attached game handles when reopening a saved draft, so always
    re-attach & verify the game handle during the publishing session!
"""
import os
import re
import time

DOUYIN_UPLOAD_URL = "https://creator.douyin.com/creator-micro/content/upload"
DOUYIN_FORM_URL_RE = re.compile(r"/content/(post/video|publish)")


def _dismiss_douyin_popups(page):
    for label in ("我知道了", "知道了", "跳过"):
        try:
            btn = page.locator(f"button:has-text('{label}'), div:has-text('{label}')").first
            if btn.is_visible(timeout=600):
                btn.click(timeout=1500)
                time.sleep(0.4)
        except Exception:
            pass


def _derive_match_token(search_keyword, expected_title, match_substring=None):
    """
    Douyin wraps matched search keywords inside a separate red <span>, splitting the DOM text node.
    Derive the non-highlighted substring (or use explicit match_substring) for reliable row matching.
    """
    if match_substring and match_substring.strip():
        return match_substring.strip()
    title = (expected_title or "").strip()
    kw = (search_keyword or "").strip()
    if title and kw and kw in title:
        remainder = title.replace(kw, "", 1).lstrip(" ：:·-—|/").strip()
        if remainder:
            return remainder
    for sep in ("：", ":", "·", "-", "—"):
        if sep in title:
            tail = title.split(sep, 1)[1].strip()
            if tail:
                return tail
    return title or kw


def _upload_dual_covers(page, cover_4x3, cover_3x4, log_dir):
    """
    Upload BOTH 横封面4:3 and 竖封面3:4 inside Douyin's unified Dual-Cover Modal:
      1) Click `选择封面` (opens modal on `设置横封面`)
      2) Match nearest <input type='file'> (<150px) or fallback to mouse click + expect_file_chooser
      3) Switch to `设置竖封面` tab -> upload cover_3x4
      4) Click `完成` -> wait up to 25s for modal to close cleanly (Escape on error)
    """
    res = {"4x3": False, "3x4": False}
    if not (cover_4x3 and os.path.exists(cover_4x3)) and not (cover_3x4 and os.path.exists(cover_3x4)):
        return res

    _dismiss_douyin_popups(page)
    print("  [抖音封面] 正在打开双封面设置弹窗...")
    trigger = page.locator("text=选择封面").first
    trigger.scroll_into_view_if_needed(timeout=5000)
    trigger.click(timeout=6000)
    time.sleep(2.0)

    def _upload_in_current_tab(img_path, tag_name):
        modal = page.locator(".dy-creator-content-modal-content").first
        lbl = modal.locator("text=上传封面").last
        lbl.wait_for(state="visible", timeout=6000)
        lbox = lbl.bounding_box()
        best_idx = -1
        best_dist = 1e9
        inputs = modal.locator("input[type='file']")
        n_in = inputs.count()
        for i in range(n_in):
            parent = inputs.nth(i).locator("xpath=..")
            pbox = parent.bounding_box()
            if pbox and lbox:
                dx = (pbox["x"] + pbox["width"] / 2) - (lbox["x"] + lbox["width"] / 2)
                dy = (pbox["y"] + pbox["height"] / 2) - (lbox["y"] + lbox["height"] / 2)
                d = (dx * dx + dy * dy) ** 0.5
                if d < best_dist:
                    best_dist = d
                    best_idx = i
        if best_idx >= 0 and best_dist < 150:
            inputs.nth(best_idx).set_input_files(img_path)
            print(f"  [抖音封面] 命中距离 {best_dist:.0f}px 的 input[{best_idx}] 上传 {tag_name}")
        else:
            with page.expect_file_chooser(timeout=8000) as fc_info:
                page.mouse.click(lbox["x"] + lbox["width"] / 2, lbox["y"] + lbox["height"] / 2)
            fc_info.value.set_files(img_path)
            print(f"  [抖音封面] 通过鼠标点击上传封面中心上传 {tag_name}")
        time.sleep(3.2)
        page.screenshot(path=os.path.join(log_dir, f"douyin_cover_{tag_name}_uploaded.png"))
        return True

    try:
        if cover_4x3 and os.path.exists(cover_4x3):
            tab_h = page.locator(".dy-creator-content-modal-content >> text=设置横封面").first
            if tab_h.is_visible(timeout=2000):
                tab_h.click()
                time.sleep(0.8)
            res["4x3"] = _upload_in_current_tab(cover_4x3, "4x3")

        if cover_3x4 and os.path.exists(cover_3x4):
            tab_v = page.locator(".dy-creator-content-modal-content >> text=设置竖封面").first
            tab_v.click(timeout=5000)
            time.sleep(1.5)
            res["3x4"] = _upload_in_current_tab(cover_3x4, "3x4")

        done_btn = page.locator(".dy-creator-content-modal-content button:has-text('完成')").last
        done_btn.click(timeout=6000)

        modal_deadline = time.time() + 25.0
        modal_closed = False
        while time.time() < modal_deadline:
            try:
                skip_v = page.locator("button:has-text('暂不设置')").first
                if skip_v.is_visible(timeout=400):
                    skip_v.click()
                    time.sleep(0.8)
            except Exception:
                pass
            try:
                modal_visible = page.locator(".dy-creator-content-modal-content").first.is_visible(timeout=400)
                wrap_visible = page.locator(".dy-creator-content-modal-wrap").first.is_visible(timeout=200)
                if not modal_visible and not wrap_visible:
                    modal_closed = True
                    break
            except Exception:
                modal_closed = True
                break
            time.sleep(0.8)

        if not modal_closed:
            close_x = page.locator(".dy-creator-content-modal-close, .dy-creator-content-modal-content [aria-label='Close']").first
            if close_x.is_visible(timeout=1500):
                close_x.click()
                time.sleep(1.5)
        time.sleep(1.0)
        print(f"  [抖音封面] 双封面保存完成：{res} (modal_closed={modal_closed})")
        return res
    except Exception as e:
        page.screenshot(path=os.path.join(log_dir, "douyin_cover_dual_err.png"))
        try:
            page.keyboard.press("Escape")
            time.sleep(1.0)
        except Exception:
            pass
        print(f"  [抖音封面] 双封面上传异常：{e}")
        return res


def _attach_game_handle(page, search_keyword, expected_title, log_dir, match_substring=None):
    """
    Verified Douyin Game Handle Attachment Flow:
      1) Under `扩展信息` -> `添加标签`, click dropdown (`位置`) -> select `游戏手柄`
      2) Click right-side combobox `添加作品同款游戏` (or iframe fallback) -> type `search_keyword`
      3) Wait for popover -> match `match_token` inside popover bounds -> click title left-side (NEVER `详情 >`!)
      4) Strict 3-layer verification scoped to `添加标签` row + screenshot capture!
    """
    if not search_keyword or not expected_title:
        raise ValueError("[游戏手柄] 已启用挂载，但缺少 game_keyword 或 expected_game_title！")

    match_token = _derive_match_token(search_keyword, expected_title, match_substring=match_substring)
    print(f"  [游戏手柄] 开始挂载同款游戏：{expected_title} (搜索词={search_keyword!r}, 节点匹配词={match_token!r})")
    _dismiss_douyin_popups(page)

    # Step 1: Scroll to 添加标签 & switch dropdown (`位置`) -> `游戏手柄`
    try:
        lbl = page.get_by_text("添加标签", exact=False).first
        lbl.scroll_into_view_if_needed(timeout=6000)
        time.sleep(0.6)

        already_handle = False
        try:
            if page.locator("input[placeholder*='添加作品同款游戏']").first.is_visible(timeout=1200):
                already_handle = True
        except Exception:
            pass

        if not already_handle:
            dropdown = page.locator("div:has(> span:text-is('位置')), div:text-is('位置')").first
            if dropdown.is_visible(timeout=3000):
                dropdown.click(timeout=5000)
            else:
                lbl.locator("xpath=following::div[contains(@class,'select')][1]").click(timeout=5000)
            time.sleep(1.0)

            handle_opt = page.get_by_text("游戏手柄", exact=True).last
            handle_opt.wait_for(state="visible", timeout=5000)
            handle_opt.click(timeout=5000)
            time.sleep(1.2)
    except Exception as e:
        page.screenshot(path=os.path.join(log_dir, "douyin_handle_step1_err.png"))
        raise RuntimeError(f"[游戏手柄] 第1步切换「游戏手柄」下拉失败：{e}")

    # Step 2 & 3: Click `添加作品同款游戏` & type keyword
    target_ctx = page
    try:
        placeholder_el = page.get_by_text("添加作品同款游戏", exact=True).first
        if placeholder_el.is_visible(timeout=4000):
            placeholder_el.scroll_into_view_if_needed()
            placeholder_el.click(timeout=5000)
            time.sleep(0.6)
            page.keyboard.type(search_keyword, delay=85)
        else:
            game_input = page.locator("input[placeholder*='添加作品同款游戏']").first
            if not game_input.is_visible(timeout=2000):
                iframe_loc = page.frame_locator("iframe[src*='summon.bytedance.com']").first
                game_input = iframe_loc.locator("input").first
                game_input.wait_for(state="visible", timeout=8000)
                target_ctx = iframe_loc
            game_input.click(timeout=5000)
            time.sleep(0.4)
            game_input.fill("")
            game_input.type(search_keyword, delay=85)
    except Exception as e:
        page.screenshot(path=os.path.join(log_dir, "douyin_handle_step2_err.png"))
        raise RuntimeError(f"[游戏手柄] 第2步点击并输入「添加作品同款游戏」失败：{e}")

    time.sleep(2.4)
    page.screenshot(path=os.path.join(log_dir, "douyin_handle_dropdown.png"))

    # Step 4: Click exact game row INSIDE popover bounds (NEVER click `详情 >`!)
    try:
        hdr = target_ctx.locator("text=添加作品同款游戏，可获得").first
        hdr.wait_for(state="visible", timeout=6000)
        hbox = hdr.bounding_box()
        if not hbox:
            raise RuntimeError("未获取到游戏手柄搜索弹窗坐标")

        picked = None
        scan_tokens = [match_token]
        if expected_title and expected_title not in scan_tokens:
            scan_tokens.append(expected_title)
        if search_keyword and search_keyword not in scan_tokens:
            scan_tokens.append(search_keyword)

        total_scanned = 0
        for tok in scan_tokens:
            candidates = target_ctx.locator(f"text={tok}")
            n_cand = candidates.count()
            total_scanned += n_cand
            for i in range(n_cand):
                c = candidates.nth(i)
                try:
                    if not c.is_visible(timeout=500):
                        continue
                    cbox = c.bounding_box()
                    if not cbox:
                        continue
                    if (
                        cbox["y"] > hbox["y"] + hbox["height"] - 4
                        and cbox["y"] < hbox["y"] + 260
                        and cbox["x"] >= hbox["x"] - 40
                        and cbox["x"] < hbox["x"] + 260
                    ):
                        picked = (c, cbox)
                        break
                except Exception:
                    continue
            if picked:
                break

        if not picked:
            raise RuntimeError(
                f"在搜索弹窗内未找到目标游戏项「{expected_title}」（扫描 {total_scanned} 个候选节点）"
            )

        _, cbox = picked
        page.mouse.click(cbox["x"] + min(cbox["width"] / 2, 40), cbox["y"] + cbox["height"] / 2)
        time.sleep(1.8)
    except Exception as e:
        page.screenshot(path=os.path.join(log_dir, "douyin_handle_step4_err.png"))
        raise RuntimeError(f"[游戏手柄] 第4步点选「{expected_title}」失败：{e}")

    # Step 5: STRICT 3-layer post-click verification scoped to `添加标签` row
    try:
        lbl = page.get_by_text("添加标签", exact=False).first
        lbl.scroll_into_view_if_needed(timeout=4000)
        time.sleep(0.5)
    except Exception:
        pass
    page.screenshot(path=os.path.join(log_dir, "douyin_handle_attached.png"))

    # 5a. Dropdown popover MUST be closed
    try:
        if page.locator("text=添加作品同款游戏，可获得").first.is_visible(timeout=800):
            raise RuntimeError("[游戏手柄] 校验失败：搜索下拉框仍未关闭，可能未真正选中！")
    except RuntimeError:
        raise
    except Exception:
        pass

    # 5b. Empty placeholder MUST be gone
    try:
        if page.get_by_text("添加作品同款游戏", exact=True).first.is_visible(timeout=800):
            raise RuntimeError("[游戏手柄] 校验失败：输入框仍是空的「添加作品同款游戏」，未成功挂载！")
    except RuntimeError:
        raise
    except Exception:
        pass

    # 5c. Target title token MUST be visibly rendered on the SAME horizontal row as `添加标签`
    lbl_el = page.get_by_text("添加标签", exact=False).first
    lbox = lbl_el.bounding_box()
    row_verified = False
    verify_tokens = list(dict.fromkeys([t for t in (match_token, search_keyword, expected_title) if t]))
    if lbox:
        for tok in verify_tokens:
            t_nodes = page.locator(f"text={tok}")
            for i in range(t_nodes.count()):
                tn = t_nodes.nth(i)
                try:
                    if not tn.is_visible(timeout=500):
                        continue
                    tbox = tn.bounding_box()
                    if tbox and abs(tbox["y"] - lbox["y"]) < 36 and tbox["x"] > lbox["x"]:
                        row_verified = True
                        break
                except Exception:
                    continue
            if row_verified:
                break

    if not row_verified:
        row_text = ""
        for depth in (3, 4, 5):
            try:
                txt = lbl_el.locator("xpath=" + "/".join([".."] * depth)).inner_text()
                if "游戏手柄" in txt:
                    row_text = txt
                    if any(tok in txt for tok in verify_tokens):
                        row_verified = True
                    break
            except Exception:
                pass
        if not row_verified:
            raise RuntimeError(
                f"[游戏手柄] 校验失败：「添加标签」同一行未检测到「{expected_title}」！（行文本：{row_text!r}）"
            )

    print(f"  [游戏手柄] 挂载并严格同行校验成功：{expected_title}（已截屏 douyin_handle_attached.png）")
    return True


def upload_to_douyin(
    session,
    video_path,
    title,
    desc,
    topics,
    cover_4x3=None,
    cover_3x4=None,
    enable_game_handle=False,
    game_keyword=None,
    expected_game_title=None,
    game_match_substring=None,
    mode="draft",
    confirm_publish=False,
    log_dir=".",
    reuse_existing_draft=False,
):
    """
    mode:
      - "draft"   : Upload video, fill title/desc/topics, upload covers, attach game handle, save draft.
      - "publish" : Only clicks 发布 when confirm_publish=True!
    """
    os.makedirs(log_dir, exist_ok=True)
    page = session.context.new_page()
    page.goto(DOUYIN_UPLOAD_URL, wait_until="domcontentloaded", timeout=30000)
    time.sleep(3.0)

    if "login" in page.url.lower() or "creator-micro" not in page.url.lower():
        page.screenshot(path=os.path.join(log_dir, "douyin_need_login.png"))
        raise RuntimeError(
            f"抖音账号「{session.account_name}」未登录或会话已过期！请先执行：\n"
            f"  python -X utf8 scripts/login_account.py --account {session.account_name} --auto-wait"
        )

    if reuse_existing_draft:
        try:
            cont = page.get_by_text("继续编辑", exact=True).first
            if cont.is_visible(timeout=2500):
                print("[抖音] 命中草稿箱恢复入口，点击「继续编辑」（注意：草稿重开会清空游戏手柄，后续将重新挂载）...")
                cont.click()
                page.wait_for_url(DOUYIN_FORM_URL_RE, timeout=30000)
                time.sleep(3.0)
        except Exception:
            reuse_existing_draft = False

    if not reuse_existing_draft or not DOUYIN_FORM_URL_RE.search(page.url):
        try:
            disc = page.get_by_text("放弃", exact=True).first
            if disc.is_visible(timeout=1500):
                disc.click()
                time.sleep(1.0)
                ok_d = page.locator("button:has-text('确定'), button:has-text('确认')").last
                if ok_d.is_visible(timeout=1500):
                    ok_d.click()
                    time.sleep(1.0)
        except Exception:
            pass

        print(f"[抖音] 正在上传视频：{video_path}")
        file_input = page.locator("input[type='file']").first
        file_input.set_input_files(video_path)
        page.wait_for_url(DOUYIN_FORM_URL_RE, timeout=90000)
        time.sleep(3.0)

    _dismiss_douyin_popups(page)
    page.screenshot(path=os.path.join(log_dir, "douyin_form_loaded.png"))

    # Fill title (max 30 chars)
    short_title = (title or "")[:30]
    try:
        title_box = page.locator("input[placeholder*='标题'], input[placeholder*='作品标题']").first
        if title_box.is_visible(timeout=5000):
            title_box.click()
            title_box.press("Control+A")
            title_box.press("Backspace")
            title_box.fill(short_title)
            print(f"[抖音] 已填标题：{short_title}")
    except Exception as e:
        print(f"[抖音] 标题框未命中：{e}")

    # Fill description + hashtags
    editor = page.locator(".zone-container, div[contenteditable='true']").first
    editor.wait_for(state="visible", timeout=15000)
    editor.click()
    page.keyboard.press("Control+A")
    page.keyboard.press("Backspace")
    if desc and desc.strip():
        page.keyboard.type(desc.strip() + " ", delay=12)

    topics_list = list(topics or [])[:5]
    for tag in topics_list:
        clean_tag = tag if tag.startswith("#") else f"#{tag}"
        page.keyboard.type(clean_tag, delay=30)
        time.sleep(0.75)
        page.keyboard.press("Space")
        time.sleep(0.35)
    print(f"[抖音] 已写入简介与 {len(topics_list)} 个话题：{topics_list}")

    # Wait for video upload completion
    print("[抖音] 等待视频上传完成...")
    deadline = time.time() + 180
    while time.time() < deadline:
        body_txt = page.locator("body").inner_text()
        if ("重新上传" in body_txt) or ("上传成功" in body_txt) or ("预览" in body_txt and "上传中" not in body_txt):
            break
        time.sleep(2.0)

    # Upload custom horizontal (4:3) & vertical (3:4) covers inside Douyin's dual-cover modal
    covers_ok = _upload_dual_covers(page, cover_4x3, cover_3x4, log_dir)

    # Game Handle attachment (STRICT verification when enabled)
    handle_ok = False
    if enable_game_handle:
        handle_ok = _attach_game_handle(
            page,
            game_keyword,
            expected_game_title,
            log_dir,
            match_substring=game_match_substring,
        )
    else:
        print("[抖音] 游戏手柄开关=OFF（跳过挂载）")

    # Scroll to top & dismiss tooltips so all hashtags are unobstructed in screenshot
    _dismiss_douyin_popups(page)
    try:
        page.evaluate("window.scrollTo(0, 0)")
        time.sleep(0.8)
    except Exception:
        pass
    page.screenshot(path=os.path.join(log_dir, "douyin_topics_verify.png"))
    page.screenshot(path=os.path.join(log_dir, "douyin_ready.png"), full_page=True)

    # Save draft OR explicitly authorized Publish
    if mode == "publish" and confirm_publish:
        pub_btn = page.locator("button:has-text('发布')").last
        pub_btn.scroll_into_view_if_needed()
        pub_btn.click()
        time.sleep(4.0)
        page.screenshot(path=os.path.join(log_dir, "douyin_published.png"))
        print("[抖音] 已点击正式发布（请核对 douyin_published.png）")
        return {"status": "published", "game_handle_attached": handle_ok, "covers": covers_ok, "url": page.url}

    saved_draft = False
    for label in ("暂存离开", "存草稿", "保存草稿"):
        btn = page.locator(f"button:has-text('{label}')").first
        try:
            if btn.is_visible(timeout=2500):
                btn.scroll_into_view_if_needed()
                btn.click()
                time.sleep(3.0)
                saved_draft = True
                break
        except Exception:
            pass
    page.screenshot(path=os.path.join(log_dir, "douyin_draft.png"))
    status = "draft_saved" if saved_draft else "uploaded_pending_confirm"
    print(f"[抖音] 安全停在草稿阶段：{status}（未正式发布）")
    return {"status": status, "game_handle_attached": handle_ok, "covers": covers_ok, "url": page.url}
