#!/usr/bin/env python3
"""Download Lottie animations as JSON for @remotion/lottie."""
import json, sys, time, zipfile, io
from pathlib import Path
from urllib.request import Request, urlopen

GRAPHQL_URL = "https://graphql.lottiefiles.com/2022-08"
SEARCH_QUERY = """
query Search($query: String!, $first: Int) {
  searchPublicAnimations(query: $query, first: $first) {
    edges {
      node { id name lottieUrl jsonUrl downloads likesCount }
    }
  }
}
"""

HEADERS = {
    "Content-Type": "application/json",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
    "Origin": "https://lottiefiles.com",
    "Referer": "https://lottiefiles.com/",
}

def search(query: str, limit=8) -> list:
    payload = json.dumps({"query": SEARCH_QUERY, "variables": {"query": query, "first": limit}}).encode()
    req = Request(GRAPHQL_URL, data=payload, headers=HEADERS)
    with urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read())
    return [e["node"] for e in data.get("data", {}).get("searchPublicAnimations", {}).get("edges", [])]

def download_json(url: str) -> dict | None:
    req = Request(url, headers={"User-Agent": HEADERS["User-Agent"]})
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

def main():
    segments_path = Path(sys.argv[1])
    out_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else segments_path.parent / "lottie"
    out_dir.mkdir(parents=True, exist_ok=True)

    data = json.loads(segments_path.read_text("utf-8"))
    segments = data.get("segments", [])

    for idx, seg in enumerate(segments):
        num = idx + 1
        kw_en = seg.get("lottie_keywords_en", "")
        kw_list = seg.get("lottie_keywords", [])
        print(f"[{num}/{len(segments)}] {kw_en}")

        results = search(kw_en, limit=8) if kw_en else []
        if not results:
            for kw in kw_list:
                results = search(kw, limit=8)
                if results:
                    break
                time.sleep(0.3)

        scored = sorted(results, key=lambda r: (r.get("downloads", 0) or 0) + (r.get("likesCount", 0) or 0) * 2, reverse=True)

        saved = False
        for r in scored:
            json_url = r.get("jsonUrl")
            lottie_url = r.get("lottieUrl")
            url = json_url or lottie_url
            if not url:
                continue
            print(f"  trying: {r['name']} ({url[:60]}...)")
            anim_data = download_json(url)
            if anim_data:
                out_path = out_dir / f"segment-{num:02d}.json"
                out_path.write_text(json.dumps(anim_data), encoding="utf-8")
                size_kb = out_path.stat().st_size / 1024
                print(f"  → {out_path.name} ({size_kb:.0f}KB)")
                saved = True
                break
        if not saved:
            print(f"  [warn] no animation saved for segment {num}")
        time.sleep(0.5)

    print(f"\nDone → {out_dir}")

if __name__ == "__main__":
    main()
