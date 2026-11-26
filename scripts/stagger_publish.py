"""
Randomized Staggered Batch Publisher for Douyin + Bilibili.

Prevents burst-upload risk by validating ALL jobs upfront and inserting randomized
minute-scale intervals between consecutive jobs, opening a fresh session per job
so Douyin game handles are cleanly attached and strictly verified every time.

Usage:
  python -X utf8 scripts/stagger_publish.py --batch-file examples/batch_jobs.example.json --dry-run
  python -X utf8 scripts/stagger_publish.py job1.json job2.json --min-delay 210 --max-delay 540 --mode publish --confirm-publish
"""
import argparse
import datetime
import json
import os
import random
import sys
import time

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from publish_dual import publish_job, validate_job


def _format_duration(seconds):
    mins, secs = divmod(int(seconds), 60)
    return f"{mins}分{secs:02d}秒"


def run_staggered_batch(
    job_paths,
    min_delay_sec=180,
    max_delay_sec=600,
    account_override=None,
    accounts_config=None,
    platforms=("douyin", "bilibili"),
    mode="draft",
    confirm_publish=False,
    game_handle_override=None,
    dry_run=False,
    seed=None,
):
    if not job_paths:
        raise ValueError("任务列表为空，请通过 --batch-file 或位置参数传入至少一个 job.json。")
    if min_delay_sec < 0 or max_delay_sec < min_delay_sec:
        raise ValueError(f"延迟区间非法：min_delay_sec={min_delay_sec}, max_delay_sec={max_delay_sec}")
    if mode == "publish" and not confirm_publish and not dry_run:
        raise ValueError("安全拦截：批量正式发布必须同时传入 --mode publish --confirm-publish！")

    # Pre-validate ALL jobs before starting the schedule
    all_checks = []
    all_passed = True
    for jp in job_paths:
        chk = validate_job(
            jp,
            account_override=account_override,
            accounts_config=accounts_config,
            platforms=platforms,
            mode=mode,
            confirm_publish=confirm_publish,
            game_handle_override=game_handle_override,
            check_account_config=not dry_run,
        )
        all_checks.append(chk)
        if not chk["passed"]:
            all_passed = False

    rng = random.Random(seed)
    planned_delays = [
        rng.randint(min_delay_sec, max_delay_sec) if idx < len(job_paths) - 1 else 0
        for idx in range(len(job_paths))
    ]

    if dry_run:
        summary = {
            "dry_run": True,
            "total_jobs": len(job_paths),
            "all_passed": all_passed,
            "delay_range_sec": [min_delay_sec, max_delay_sec],
            "planned_delays_after_each_sec": planned_delays,
            "checks": all_checks,
        }
        print("=== 错峰批量发布 Dry-Run 预检 ===")
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        if not all_passed:
            sys.exit(2)
        return summary

    if not all_passed:
        print("=== 批量发布前校验拦截（存在未通过任务单）===")
        for jp, chk in zip(job_paths, all_checks):
            if not chk["passed"]:
                print(f"  [FAIL] {jp}: {chk['errors']}")
        sys.exit(2)

    results = []
    total = len(job_paths)
    for idx, jp in enumerate(job_paths):
        now_str = datetime.datetime.now().strftime("%H:%M:%S")
        print(f"\n[{now_str}] >>> 开始执行第 {idx + 1}/{total} 条：{jp} (mode={mode})")
        res = publish_job(
            jp,
            account_override=account_override,
            accounts_config=accounts_config,
            platforms=platforms,
            mode=mode,
            confirm_publish=confirm_publish,
            game_handle_override=game_handle_override,
            dry_run=False,
        )
        results.append(res)

        wait_sec = planned_delays[idx]
        if wait_sec > 0:
            next_dt = datetime.datetime.now() + datetime.timedelta(seconds=wait_sec)
            print(
                f"[错峰等待] 本条完成，随机等待 {_format_duration(wait_sec)} ({wait_sec}s)，"
                f"预计 {next_dt.strftime('%H:%M:%S')} 启动下一条..."
            )
            time.sleep(wait_sec)

    print(f"\n=== 全部 {total} 条错峰任务执行完成 ===")
    return results


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Randomized staggered batch publisher for Douyin + Bilibili")
    ap.add_argument("jobs", nargs="*", help="One or more publish_job.json paths")
    ap.add_argument("--batch-file", default=None, help="JSON file containing jobs[], min_delay_sec, max_delay_sec, platforms")
    ap.add_argument("--min-delay", type=int, default=None, help="Minimum random delay seconds between jobs (default 180)")
    ap.add_argument("--max-delay", type=int, default=None, help="Maximum random delay seconds between jobs (default 600)")
    ap.add_argument("--account", default=None, help="Override account name for all jobs")
    ap.add_argument("--accounts-config", default=None, help="Path to accounts.json")
    ap.add_argument("--platforms", default=None, help="Comma-separated: douyin,bilibili")
    ap.add_argument("--mode", choices=["draft", "publish"], default="draft", help="Default: draft (safe)")
    ap.add_argument("--confirm-publish", action="store_true", help="Explicit guard required for --mode publish")
    ap.add_argument("--game-handle", choices=["on", "off"], default=None, help="Override Douyin game handle toggle")
    ap.add_argument("--seed", type=int, default=None, help="Optional RNG seed for reproducible intervals")
    ap.add_argument("--dry-run", action="store_true", help="Validate all jobs and preview randomized delays")
    args = ap.parse_args()

    job_list = list(args.jobs)
    min_d = 180
    max_d = 600
    plats = ("douyin", "bilibili")

    if args.batch_file:
        batch_abs = os.path.abspath(args.batch_file)
        batch_dir = os.path.dirname(batch_abs)
        with open(batch_abs, "r", encoding="utf-8-sig") as f:
            bcfg = json.load(f)
        min_d = bcfg.get("min_delay_sec", min_d)
        max_d = bcfg.get("max_delay_sec", max_d)
        if bcfg.get("platforms"):
            plats = tuple(bcfg["platforms"])
        for raw_jp in bcfg.get("jobs", []):
            jp = raw_jp if os.path.isabs(raw_jp) else (
                os.path.abspath(raw_jp) if os.path.exists(raw_jp) else os.path.abspath(os.path.join(batch_dir, raw_jp))
            )
            job_list.append(jp)

    if args.min_delay is not None:
        min_d = args.min_delay
    if args.max_delay is not None:
        max_d = args.max_delay
    if args.platforms:
        plats = tuple(p.strip() for p in args.platforms.split(",") if p.strip())

    run_staggered_batch(
        job_paths=job_list,
        min_delay_sec=min_d,
        max_delay_sec=max_d,
        account_override=args.account,
        accounts_config=args.accounts_config,
        platforms=plats,
        mode=args.mode,
        confirm_publish=args.confirm_publish,
        game_handle_override=args.game_handle,
        dry_run=args.dry_run,
        seed=args.seed,
    )
