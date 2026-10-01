"""
Headless CLI for the video pipeline. stdout carries ONE JSON document, nothing else
(all logging, including from imported modules, is routed to stderr).

  python cli.py create --source <url|file> [--title T] [--body B] [--caption C] [--layout lower|standard]
  python cli.py status <job_id>
  python cli.py list [--limit N]
  python cli.py request-approval <job_id>
  python cli.py publish <job_id> [--code 123456]
"""
import argparse
import json
import sys

_real_stdout = sys.stdout
_real_stdout.reconfigure(encoding="utf-8")  # Hebrew in the JSON; Windows defaults to cp1252
sys.stdout = sys.stderr  # import-time prints (config.py etc.) must not corrupt the JSON output

import pipeline  # noqa: E402
import publisher  # noqa: E402
from config import Config  # noqa: E402


def emit(obj, code: int = 0):
    _real_stdout.write(json.dumps(obj, ensure_ascii=False, indent=2) + "\n")
    _real_stdout.flush()
    sys.exit(code)


def main():
    parser = argparse.ArgumentParser(prog="video-creator")
    sub = parser.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("create", help="Download + render a video")
    c.add_argument("--source", required=True, help="URL (TikTok/Instagram/YouTube) or local file path")
    c.add_argument("--title")
    c.add_argument("--body")
    c.add_argument("--caption")
    c.add_argument("--layout", default="lower", choices=pipeline.LAYOUTS)

    s = sub.add_parser("status"); s.add_argument("job_id")
    l = sub.add_parser("list"); l.add_argument("--limit", type=int, default=10)
    r = sub.add_parser("request-approval", help="Send the owner an approval code on Telegram (instagram mode)"); r.add_argument("job_id"); r.add_argument("--account", default="main", choices=["main", "test"])
    p = sub.add_parser("publish"); p.add_argument("job_id"); p.add_argument("--code", help="Approval code from Telegram")

    args = parser.parse_args()
    Config.ensure_dirs()

    try:
        if args.cmd == "create":
            job_id = pipeline.submit_job(
                args.source, args.title, args.body, args.caption, args.layout,
                trusted=True,  # CLI runs as the local user
                background=False,
            )
            job = pipeline.get_job(job_id)
            emit(pipeline.summary(job) | {"video_path": job.get("video_path")},
                 0 if job["status"] != "failed" else 1)
        elif args.cmd == "status":
            job = pipeline.get_job(args.job_id)
            emit(pipeline.summary(job) | {"video_path": job.get("video_path")})
        elif args.cmd == "list":
            emit(pipeline.list_jobs(args.limit))
        elif args.cmd == "publish":
            emit(publisher.publish(args.job_id, args.code))
        elif args.cmd == "request-approval":
            emit(publisher.request_publish(args.job_id, args.account))
    except (ValueError, KeyError, RuntimeError, NotImplementedError) as e:
        emit({"error": str(e)}, 1)


if __name__ == "__main__":
    main()
