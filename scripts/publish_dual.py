"""
Unified Dual-Platform (Douyin + Bilibili) Sync Publisher with Pre-Flight Validation & Safe Draft Gate.

Usage:
  # Dry-run validation (checks files, topics, covers & game-handle config without launching Chrome):
  python -X utf8 scripts/publish_dual.py examples/publish_job.example.json --dry-run

  # Default SAFE mode (saves drafts on Douyin and Bilibili; never auto-publishes):
  python -X utf8 scripts/publish_dual.py path/to/publish_job.json

  # Override Douyin game handle toggle:
  python -X utf8 scripts/publish_dual.py path/to/publish_job.json --game-handle on

  # Explicit authorized publish (ONLY after user explicitly confirms publishing this job):
  python -X utf8 scripts/publish_dual.py path/to/publish_job.json --mode publish --confirm-publish
"""
import argparse
import json
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from bilibili_uploader import upload_to_bilibili
from browser_profile import AccountBrowserSession, get_account_info
from douyin_uploader import upload_to_douyin


def _resolve_path(raw_path, base_dir):
    if not raw_path:
        return None
    if os.path.isabs(raw_path):
        return raw_path
    if os.path.exists(raw_path):
        return os.path.abspath(raw_path)
    return os.path.abspath(os.path.join(base_dir, raw_path))


def load_job(job_json_path):
    job_path = os.path.abspath(job_json_path)
    if not os.path.exists(job_path):
        raise FileNotFoundError(f"未找到任务单：{job_path}")
    with open(job_path, "r", encoding="utf-8-sig") as f:
        job = json.load(f)
    return job, os.path.dirname(job_path), job_path


def validate_job(
    job_json_path,
    account_override=None,
    accounts_config=None,
    platforms=("douyin", "bilibili"),
    mode="draft",
    confirm_publish=False,
    game_handle_override=None,
    log_dir_override=None,
    check_account_config=True,
):
    job, base_dir, job_path = load_job(job_json_path)
    errors = []
    warnings = []

    if mode == "publish" and not confirm_publish:
        errors.append("安全拦截：正式发布必须同时传入 --mode publish --confirm-publish，避免误发布！")

    video_path = _resolve_path(job.get("video_path"), base_dir)
    if not video_path or not os.path.exists(video_path):
        errors.append(f"视频文件不存在：{video_path or job.get('video_path')!r}")

    account = account_override or job.get("account")
    if check_account_config:
        try:
            acct_info = get_account_info(account, accounts_config=accounts_config)
            account = acct_info["account_name"]
        except Exception as e:
            errors.append(f"账号配置校验失败：{e}")

    dy_cfg = dict(job.get("douyin") or {})
    bi_cfg = dict(job.get("bilibili") or {})

    enable_handle = bool(dy_cfg.get("enable_game_handle", False))
    if game_handle_override == "on":
        enable_handle = True
    elif game_handle_override == "off":
        enable_handle = False

    c_4x3 = _resolve_path(dy_cfg.get("cover_4x3"), base_dir)
    c_3x4 = _resolve_path(dy_cfg.get("cover_3x4"), base_dir)
    bi_4x3 = _resolve_path(bi_cfg.get("cover_4x3"), base_dir) or c_4x3
    bi_16x9 = _resolve_path(bi_cfg.get("cover_16x9"), base_dir)

    if "douyin" in platforms:
        if not dy_cfg:
            errors.append("任务单缺少 douyin 配置段。")
        else:
            topics = list(dy_cfg.get("topics") or [])
            if len(topics) > 5:
                warnings.append(f"抖音话题超过 5 个（当前 {len(topics)} 个），运行时将自动截取前 5 个。")
            if dy_cfg.get("cover_4x3") and not (c_4x3 and os.path.exists(c_4x3)):
                errors.append(f"抖音 4:3 横封面不存在：{c_4x3}")
            if dy_cfg.get("cover_3x4") and not (c_3x4 and os.path.exists(c_3x4)):
                errors.append(f"抖音 3:4 竖封面不存在：{c_3x4}")
            if enable_handle:
                if not dy_cfg.get("game_keyword") or not dy_cfg.get("expected_game_title"):
                    errors.append("已开启抖音游戏手柄挂载，但缺少 douyin.game_keyword 或 douyin.expected_game_title。")

    if "bilibili" in platforms:
        if not bi_cfg:
            errors.append("任务单缺少 bilibili 配置段。")
        else:
            if bi_cfg.get("cover_4x3") and not (bi_4x3 and os.path.exists(bi_4x3)):
                errors.append(f"B站 4:3 首页推荐封面不存在：{bi_4x3}")
            if bi_cfg.get("cover_16x9") and not (bi_16x9 and os.path.exists(bi_16x9)):
                errors.append(f"B站 16:9 个人空间封面不存在：{bi_16x9}")

    log_dir = log_dir_override or _resolve_path(job.get("log_dir"), base_dir) or os.path.join(base_dir, "publish_logs")

    resolved = {
        "job_path": job_path,
        "job_id": job.get("job_id") or os.path.splitext(os.path.basename(job_path))[0],
        "account": account,
        "platforms": list(platforms),
        "mode": mode,
        "video_path": video_path,
        "log_dir": log_dir,
        "douyin": {
            **dy_cfg,
            "cover_4x3": c_4x3,
            "cover_3x4": c_3x4,
            "enable_game_handle": enable_handle,
        },
        "bilibili": {
            **bi_cfg,
            "cover_4x3": bi_4x3,
            "cover_16x9": bi_16x9,
        },
    }
    return {
        "passed": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "resolved": resolved,
    }


def publish_job(
    job_json_path,
    account_override=None,
    accounts_config=None,
    platforms=("douyin", "bilibili"),
    mode="draft",
    confirm_publish=False,
    game_handle_override=None,
    reuse_existing_draft=None,
    log_dir_override=None,
    dry_run=False,
):
    check = validate_job(
        job_json_path,
        account_override=account_override,
        accounts_config=accounts_config,
        platforms=platforms,
        mode=mode,
        confirm_publish=confirm_publish,
        game_handle_override=game_handle_override,
        log_dir_override=log_dir_override,
        check_account_config=not dry_run,
    )
    if dry_run:
        print("=== Dry-Run 任务单预检结果 ===")
        print(json.dumps(check, ensure_ascii=False, indent=2))
        if not check["passed"]:
            sys.exit(2)
        return check

    if not check["passed"]:
        print("=== 发布前校验拦截 ===")
        print(json.dumps({"errors": check["errors"], "warnings": check["warnings"]}, ensure_ascii=False, indent=2))
        sys.exit(2)

    for w in check["warnings"]:
        print(f"[警告] {w}")

    cfg = check["resolved"]
    dy_cfg = cfg["douyin"]
    bi_cfg = cfg["bilibili"]
    log_dir = cfg["log_dir"]
    os.makedirs(log_dir, exist_ok=True)

    reuse_draft = dy_cfg.get("reuse_existing_draft", False) if reuse_existing_draft is None else reuse_existing_draft
    results = {"job_id": cfg["job_id"], "account": cfg["account"], "mode": mode, "platforms": {}}

    with AccountBrowserSession(cfg["account"], headless=False, accounts_config=accounts_config) as sess:
        if "douyin" in platforms:
            results["platforms"]["douyin"] = upload_to_douyin(
                session=sess,
                video_path=cfg["video_path"],
                title=dy_cfg.get("title", ""),
                desc=dy_cfg.get("desc", ""),
                topics=dy_cfg.get("topics", []),
                cover_4x3=dy_cfg.get("cover_4x3"),
                cover_3x4=dy_cfg.get("cover_3x4"),
                enable_game_handle=dy_cfg["enable_game_handle"],
                game_keyword=dy_cfg.get("game_keyword"),
                expected_game_title=dy_cfg.get("expected_game_title"),
                game_match_substring=dy_cfg.get("game_match_substring"),
                mode=mode,
                confirm_publish=confirm_publish,
                log_dir=log_dir,
                reuse_existing_draft=reuse_draft,
            )

        if "bilibili" in platforms:
            results["platforms"]["bilibili"] = upload_to_bilibili(
                session=sess,
                video_path=cfg["video_path"],
                title=bi_cfg.get("title", ""),
                desc=bi_cfg.get("desc", ""),
                main_topic=bi_cfg.get("main_topic"),
                topic_fallback_keywords=bi_cfg.get("topic_fallback_keywords"),
                tags=bi_cfg.get("tags", []),
                cover_16x9=bi_cfg.get("cover_16x9"),
                cover_4x3=bi_cfg.get("cover_4x3"),
                declaration=bi_cfg.get("declaration", "内容无需标注"),
                mode=mode,
                confirm_publish=confirm_publish,
                log_dir=log_dir,
            )

    result_path = os.path.join(log_dir, "publish_result.json")
    with open(result_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print("=== 双平台上传结果 ===")
    print(json.dumps(results, ensure_ascii=False, indent=2))
    return results


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Dual-platform (Douyin + Bilibili) isolated sync uploader")
    ap.add_argument("job_json", help="Path to publish_job.json")
    ap.add_argument("--account", default=None, help="Override account name in accounts.json")
    ap.add_argument("--accounts-config", default=None, help="Path to accounts.json")
    ap.add_argument("--platforms", default="douyin,bilibili", help="Comma-separated: douyin,bilibili")
    ap.add_argument("--mode", choices=["draft", "publish"], default="draft", help="Default: draft (safe)")
    ap.add_argument("--confirm-publish", action="store_true", help="Explicit guard required for --mode publish")
    ap.add_argument("--game-handle", choices=["on", "off"], default=None, help="Override Douyin game handle toggle")
    ap.add_argument("--reuse-existing-draft", action="store_true", default=None, help="Click 继续编辑 if draft banner exists")
    ap.add_argument("--log-dir", default=None, help="Override screenshot/result log directory")
    ap.add_argument("--dry-run", action="store_true", help="Validate job schema & paths without opening Chrome")
    args = ap.parse_args()

    plats = tuple(p.strip() for p in args.platforms.split(",") if p.strip())
    publish_job(
        args.job_json,
        account_override=args.account,
        accounts_config=args.accounts_config,
        platforms=plats,
        mode=args.mode,
        confirm_publish=args.confirm_publish,
        game_handle_override=args.game_handle,
        reuse_existing_draft=args.reuse_existing_draft,
        log_dir_override=args.log_dir,
        dry_run=args.dry_run,
    )
