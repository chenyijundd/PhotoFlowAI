#!/usr/bin/env python3
"""
PhotoFlow AI - License Key Generator

Run this script on your own machine to generate license keys for users.
You MUST change SECRET_KEY in backend/api/license_service.py before
generating keys — both sides must use the same secret.

Usage:
    python scripts/generate_license.py "张三"
    python scripts/generate_license.py "张三" --expiry 2026-12-31
    python scripts/generate_license.py --batch users.txt

The output is a 16-character uppercase key that the user enters together
with their name in the activation dialog.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

# Allow importing from the backend package (project root)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# ── Must match the SECRET_KEY in backend/env.py ───────────────────────────
from backend.env import SECRET_KEY  # noqa: E402  (import after sys.path setup)


def generate_license(user_name: str, expiry: str = "permanent") -> str:
    """Generate a 16-character uppercase license key."""
    payload = f"{user_name}|{expiry}|{SECRET_KEY}"
    return hashlib.sha256(payload.encode()).hexdigest()[:16].upper()


def main() -> None:
    # Work around Windows cp932 terminal encoding — force UTF-8 output
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(
        description="PhotoFlow AI — 激活码生成器",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python scripts/generate_license.py "张三"
  python scripts/generate_license.py "张三" --expiry 2026-12-31
  python scripts/generate_license.py --batch users.txt
        """,
    )
    parser.add_argument(
        "user_name",
        nargs="?",
        help="用户名称",
    )
    parser.add_argument(
        "--expiry",
        default="permanent",
        help="过期时间（默认: permanent）",
    )
    parser.add_argument(
        "--batch",
        metavar="FILE",
        help="从文件批量生成（每行一个用户名）",
    )
    args = parser.parse_args()

    if args.batch:
        path = Path(args.batch)
        if not path.is_file():
            print(f"错误：文件不存在 — {args.batch}", file=sys.stderr)
            sys.exit(1)
        lines = path.read_text(encoding="utf-8").strip().splitlines()
        print(f"{'用户名':<20} {'过期':<16} {'激活码'}")
        print("-" * 56)
        for line in lines:
            name = line.strip()
            if not name or name.startswith("#"):
                continue
            key = generate_license(name, args.expiry)
            print(f"{name:<20} {args.expiry:<16} {key}")
    elif args.user_name:
        key = generate_license(args.user_name, args.expiry)
        print(f"用户名: {args.user_name}")
        print(f"过期:   {args.expiry}")
        print(f"激活码: {key}")
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
