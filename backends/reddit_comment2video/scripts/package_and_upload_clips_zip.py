#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import zipfile
from pathlib import Path

import tos

def _load_tos_config(root: Path) -> dict:
    """Load TOS_CONFIG from project-root upload_latest_clips_to_tos.py."""
    cfg_path = root / "upload_latest_clips_to_tos.py"
    if not cfg_path.exists():
        raise FileNotFoundError(f"missing {cfg_path}")
    scope: dict = {}
    code = cfg_path.read_text(encoding="utf-8")
    exec(code, scope, scope)
    cfg = scope.get("TOS_CONFIG")
    if not isinstance(cfg, dict):
        raise RuntimeError("TOS_CONFIG not found or invalid in upload_latest_clips_to_tos.py")
    return cfg


DEFAULT_SOURCES = [
    ("prog", Path("out/reddit-3s-clips-prog/clips")),
    ("roses", Path("out/reddit-3s-clips-roses/clips")),
    ("meirl", Path("out/reddit-3s-clips-meirl/clips")),
]


def _zip_dir(src_root: Path, zip_path: Path) -> None:
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for p in sorted(src_root.rglob("*")):
            if not p.is_file():
                continue
            zf.write(p, arcname=str(p.relative_to(src_root)))


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Collect generated clips into creator subdirs, zip, upload to TOS, print URL."
    )
    ap.add_argument(
        "--out-root",
        default="out/reddit-3s-bundle",
        help="Where to assemble clips before zipping (default: out/reddit-3s-bundle)",
    )
    ap.add_argument(
        "--zip-out",
        default="",
        help="Zip file output path (default: <out-root>/reddit-3s-YYYYmmdd-HHMMSS.zip)",
    )
    ap.add_argument(
        "--tos-prefix",
        default="reddit-3s/bundles",
        help="TOS key prefix for the zip file (default: reddit-3s/bundles)",
    )
    ap.add_argument(
        "--glob",
        default="clip-*.mp4",
        help="Which files to include from each clips dir (default: clip-*.mp4)",
    )
    args = ap.parse_args()

    root = Path(__file__).resolve().parent.parent
    TOS_CONFIG = _load_tos_config(root)
    out_root = (root / args.out_root).resolve()
    out_root.mkdir(parents=True, exist_ok=True)

    # Assemble: <out_root>/<creator>/clip-xx.mp4
    total = 0
    for creator, rel_dir in DEFAULT_SOURCES:
        src_dir = (root / rel_dir).resolve()
        if not src_dir.exists():
            continue
        files = sorted(p for p in src_dir.glob(args.glob) if p.is_file())
        if not files:
            continue
        dst_dir = out_root / creator
        dst_dir.mkdir(parents=True, exist_ok=True)
        for p in files:
            dst = dst_dir / p.name
            dst.write_bytes(p.read_bytes())
            total += 1

    if total == 0:
        print("No clips found to package.")
        return 1

    if args.zip_out:
        zip_path = Path(args.zip_out).expanduser().resolve()
    else:
        ts = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
        zip_path = out_root / f"reddit-3s-{ts}.zip"

    _zip_dir(out_root, zip_path)

    client = tos.TosClientV2(
        ak=TOS_CONFIG["access_key"],
        sk=TOS_CONFIG["secret_key"],
        endpoint=TOS_CONFIG["endpoint"],
        region=TOS_CONFIG["region"],
        enable_verify_ssl=False,
    )

    prefix = args.tos_prefix.strip().strip("/")
    key = f"{prefix}/{zip_path.name}" if prefix else zip_path.name
    with zip_path.open("rb") as f:
        client.put_object(
            bucket=TOS_CONFIG["bucket_name"],
            key=key,
            content=f,
            content_length=zip_path.stat().st_size,
        )

    url = f"{TOS_CONFIG['public_domain'].rstrip('/')}/{key}"
    print(url)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

