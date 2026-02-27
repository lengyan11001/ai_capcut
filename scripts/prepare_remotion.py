#!/usr/bin/env python3
"""Prepare assets for Remotion LottieExplainer composition.

Subcommands:
  search-lottie  segments.json → download Lottie JSON files to public/<project>/lottie/
  build-config   audio durations → public/<project>/config.json with frame counts
"""

import argparse
import io
import json
import math
import subprocess
import sys
import time
import zipfile
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

# ── LottieFiles Search ──────────────────────────────────────────

GRAPHQL_URL = "https://graphql.lottiefiles.com/2022-08"

SEARCH_QUERY = """
query Search($query: String!, $first: Int) {
  searchPublicAnimations(query: $query, first: $first) {
    totalCount
    edges {
      node { id name lottieUrl jsonUrl imageUrl downloads likesCount }
    }
  }
}
"""

HTTP_HEADERS = {
    "Content-Type": "application/json",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Origin": "https://lottiefiles.com",
    "Referer": "https://lottiefiles.com/",
}


def search_lottie(keyword, limit=8):
    payload = json.dumps({
        "query": SEARCH_QUERY,
        "variables": {"query": keyword, "first": limit},
    }).encode()
    req = Request(GRAPHQL_URL, data=payload, headers=HTTP_HEADERS)
    try:
        with urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
        edges = data.get("data", {}).get("searchPublicAnimations", {}).get("edges", [])
        return [e["node"] for e in edges]
    except (URLError, KeyError, json.JSONDecodeError) as exc:
        print(f"  [warn] search '{keyword}' failed: {exc}", file=sys.stderr)
        return []


def pick_best(results):  # type: (list) -> dict
    if not results:
        return None
    scored = sorted(
        results,
        key=lambda r: (r.get("downloads", 0) or 0) + (r.get("likesCount", 0) or 0) * 2,
        reverse=True,
    )
    for r in scored:
        if r.get("lottieUrl") or r.get("jsonUrl"):
            return r
    return scored[0] if scored else None


def download_lottie_json(url):  # type: (str) -> dict
    """Download a Lottie animation as JSON. Handles both .json and .lottie (zip) formats."""
    req = Request(url, headers={"User-Agent": HTTP_HEADERS["User-Agent"]})
    with urlopen(req, timeout=30) as resp:
        raw = resp.read()

    if url.endswith(".lottie"):
        try:
            with zipfile.ZipFile(io.BytesIO(raw)) as zf:
                for name in zf.namelist():
                    if name.endswith(".json") and "manifest" not in name.lower():
                        return json.loads(zf.read(name))
                manifest = json.loads(zf.read("manifest.json"))
                anim_path = manifest.get("animations", [{}])[0].get("id", "")
                if anim_path:
                    for candidate in [f"animations/{anim_path}.json", f"{anim_path}.json"]:
                        if candidate in zf.namelist():
                            return json.loads(zf.read(candidate))
                for name in zf.namelist():
                    if name.endswith(".json"):
                        return json.loads(zf.read(name))
        except Exception as e:
            print(f"    [warn] dotlottie extract failed: {e}", file=sys.stderr)
    else:
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass
    return None


# ── Subcommand: search-lottie ───────────────────────────────────

def cmd_search_lottie(args):
    seg_path = Path(args.segments_json)
    data = json.loads(seg_path.read_text("utf-8"))
    segments = data.get("segments", [])

    project = args.project
    public_dir = Path("public") / project / "lottie"
    public_dir.mkdir(parents=True, exist_ok=True)

    total = len(segments)
    results_log = []

    for idx, seg in enumerate(segments):
        num = idx + 1
        kw_en = seg.get("lottie_keywords_en", "")
        kw_list = seg.get("lottie_keywords", [])

        print(f"\n[{num}/{total}] {seg.get('narration', '')[:30]}...")
        print(f"  keywords: {kw_en} | {kw_list}")

        best = None
        if kw_en:
            results = search_lottie(kw_en, limit=8)
            best = pick_best(results)
            if best:
                print(f"  found (en): {best['name']} (downloads={best.get('downloads', 0)})")

        if not best:
            for kw in kw_list:
                results = search_lottie(kw, limit=8)
                best = pick_best(results)
                if best:
                    print(f"  found (kw={kw}): {best['name']}")
                    break
                time.sleep(0.3)

        if not best:
            print("  [warn] no animation found, using fallback")
            best = {
                "name": "fallback",
                "lottieUrl": "https://assets-v2.lottiefiles.com/a/0e5f9e62-1153-11ee-8c46-4f56030c6b3d/QUKZrZTXlp.lottie",
                "jsonUrl": "",
            }

        json_url = best.get("jsonUrl")
        lottie_url = best.get("lottieUrl")
        url = json_url or lottie_url or ""

        saved = False
        if url:
            print(f"  downloading: {url[:70]}...")
            anim_data = download_lottie_json(url)
            if anim_data:
                out_path = public_dir / f"segment-{num:02d}.json"
                out_path.write_text(json.dumps(anim_data), encoding="utf-8")
                size_kb = out_path.stat().st_size / 1024
                print(f"  -> {out_path} ({size_kb:.0f}KB)")
                saved = True

        if not saved:
            print(f"  [warn] no animation saved for segment {num}")

        results_log.append({
            "segment": num,
            "narration": seg.get("narration", "")[:40],
            "keyword_used": kw_en or (kw_list[0] if kw_list else ""),
            "lottie_name": best.get("name", ""),
            "lottie_url": url,
            "saved": saved,
        })
        time.sleep(0.5)

    log_path = Path("public") / project / "lottie_search_log.json"
    log_path.write_text(json.dumps(results_log, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n  {total} segments processed -> {public_dir}")
    print(f"  search log -> {log_path}")


# ── Subcommand: build-config ───────────────────────────────────

def _get_audio_duration(path: Path) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(path)],
        capture_output=True, text=True,
    )
    return float(result.stdout.strip())


def cmd_build_config(args):
    seg_path = Path(args.segments_json)
    data = json.loads(seg_path.read_text("utf-8"))
    segments = data.get("segments", [])

    project = args.project
    fps = int(args.fps)
    padding = int(args.padding_frames)

    audio_dir = Path("public") / project / "audio"
    lottie_dir = Path("public") / project / "lottie"

    config_segments = []
    total_frames = 0

    for idx, seg in enumerate(segments):
        num = idx + 1
        audio_file = f"segment-{num:02d}.mp3"
        lottie_file = f"segment-{num:02d}.json"
        audio_path = audio_dir / audio_file

        if audio_path.exists():
            duration_sec = _get_audio_duration(audio_path)
            duration_frames = math.ceil(duration_sec * fps) + padding
        else:
            duration_frames = 4 * fps
            print(f"  [warn] {audio_file} not found, using default {duration_frames} frames")

        if not (lottie_dir / lottie_file).exists():
            print(f"  [warn] {lottie_file} not found")

        seg_config = {
            "id": seg.get("id", f"seg-{num}"),
            "narration": seg.get("narration", ""),
            "lottieFile": lottie_file,
            "audioFile": audio_file,
            "durationFrames": duration_frames,
        }
        config_segments.append(seg_config)
        total_frames += duration_frames
        print(f"  [{num:02d}] {duration_frames} frames ({duration_frames / fps:.1f}s) - {seg.get('narration', '')[:30]}...")

    config = {
        "title": data.get("title", "Lottie Explainer"),
        "fps": fps,
        "totalFrames": total_frames,
        "segments": config_segments,
    }

    config_path = Path("public") / project / "config.json"
    config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")

    duration_sec = total_frames / fps
    print(f"\n  config -> {config_path}")
    print(f"  total: {total_frames} frames ({duration_sec:.1f}s) @ {fps}fps")
    print(f"  segments: {len(config_segments)}")


# ── CLI ─────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        prog="prepare_remotion",
        description="Prepare Lottie assets and config for Remotion LottieExplainer",
    )
    sub = parser.add_subparsers(dest="cmd")

    p = sub.add_parser("search-lottie", help="Search LottieFiles and download JSON animations")
    p.add_argument("segments_json", help="Path to segments.json")
    p.add_argument("project", help="Project name (used as public/<project>/ subfolder)")

    p = sub.add_parser("build-config", help="Build config.json from audio durations")
    p.add_argument("segments_json", help="Path to segments.json")
    p.add_argument("project", help="Project name (used as public/<project>/ subfolder)")
    p.add_argument("--fps", default="30", help="Frames per second (default: 30)")
    p.add_argument("--padding-frames", default="15", help="Extra frames after audio ends (default: 15)")

    args = parser.parse_args()
    if args.cmd == "search-lottie":
        cmd_search_lottie(args)
    elif args.cmd == "build-config":
        cmd_build_config(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
