#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Bilibili source helper for video-use / video-use-ad.

Why Bilibili: it is a strong ACG/game/anime stock source (OST audio and short
clips) and a good complement to YouTube for Chinese-language material.

Three commands:
  search            query Bilibili search API, list candidate videos
  check-watermark   probe a video and heuristically detect a burned-in watermark
  download          pull audio (BGM) and/or video via yt-dlp

Usage:
  python bilibili_src.py search "<keyword>" [--n 5]
  python bilibili_src.py check-watermark <BVid> [--probe-sec 5] [--cookies-from-browser chrome]
  python bilibili_src.py download <BVid> --audio-out edit/downloads/x.mp3 [--video-out edit/downloads/x.mp4] [--cookies-from-browser chrome]

Cookie acquisition (for video streams): Bilibili serves only AUDIO anonymously,
so BGM works with no login. Video formats need a logged-in cookie, obtained via
`--cookies-from-browser <chrome|firefox|edge|safari|brave>` — yt-dlp reads the
already-logged-in Bilibili cookie straight from the user's local browser (no manual
export). Works when that browser is installed and logged in. If a probe/download
reports "format not available", that is the cookie signal.

WATERMARK POLICY (mandatory BEFORE using a Bilibili-sourced VIDEO as stock):
  Run `check-watermark <BVid>` first. If it reports watermark=true, DO NOT use
  that video as material. This check applies ONLY to Bilibili videos; videos
  from YouTube/other platforms are NOT subject to it. Audio-only downloads
  (BGM) are exempt — there is no visual watermark in an audio stream. Pass
  --force to override only when the user has manually confirmed the clip is
  clean.

The watermark check is a best-effort pixel heuristic (corner edge-busyness
vs. center), not a guarantee. Borderline/uncertain results should be treated
as watermarked unless the user confirms otherwise.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.parse
import urllib.request

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120 Safari/537.36")

SEARCH_API = "https://api.bilibili.com/x/web-interface/wbi/search/all/v2"
VIEW_API = "https://api.bilibili.com/x/web-interface/view"


def _http_get(url, params=None, timeout=20):
    if params:
        url = url + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Referer": "https://www.bilibili.com",
    })
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def _yt_dlp(args):
    cmd = ["yt-dlp"] + args
    return subprocess.run(cmd, capture_output=True, text=True)


# --------------------------------------------------------------------------
# 1. search
# --------------------------------------------------------------------------
def search(keyword, n=5):
    data = _http_get(SEARCH_API, {"keyword": keyword})
    out = []
    for grp in data.get("data", {}).get("result", []):
        if grp.get("result_type") != "video":
            continue
        for v in grp.get("data", [])[: n]:
            out.append({
                "bvid": v.get("bvid"),
                "title": _strip_tags(v.get("title", "")),
                "author": v.get("author"),
                "duration": v.get("duration"),
                "play": v.get("play"),
                "url": f"https://www.bilibili.com/video/{v.get('bvid')}",
            })
        if out:
            break
    return out[:n]


def _strip_tags(s):
    import re
    return re.sub(r"<[^>]+>", "", s or "")


# --------------------------------------------------------------------------
# 2. check-watermark (heuristic)
# --------------------------------------------------------------------------
def _edge_busyness(png_path):
    """Return variance of edge-enhanced pixels as a 'detail' proxy.

    Bilibili watermarks most often sit in the top-right corner (UP name +
    bilibili logo), but can also appear in any corner. We check all four
    corners and the center, then let the caller pick the busiest corner.
    """
    from PIL import Image, ImageFilter
    im = Image.open(png_path).convert("L")
    w, h = im.size
    edges = im.filter(ImageFilter.FIND_EDGES)
    # center reference (middle 25% x 25%)
    center = edges.crop((int(w * 0.375), int(h * 0.375),
                         int(w * 0.625), int(h * 0.625)))
    # four 25%x25% corner crops
    corners = {
        "top_left":     edges.crop((0, 0, int(w * 0.25), int(h * 0.25))),
        "top_right":    edges.crop((int(w * 0.75), 0, w, int(h * 0.25))),
        "bottom_left":  edges.crop((0, int(h * 0.75), int(w * 0.25), h)),
        "bottom_right": edges.crop((int(w * 0.75), int(h * 0.75), w, h)),
    }
    return {name: _variance(crop) for name, crop in corners.items()}, _variance(center)


def _variance(img):
    px = list(img.getdata())
    if not px:
        return 0.0
    m = sum(px) / len(px)
    return sum((p - m) ** 2 for p in px) / len(px)


def check_watermark(bvid, probe_sec=5, cookie_args=None):
    url = f"https://www.bilibili.com/video/{bvid}"
    tmp = tempfile.mkdtemp(prefix="bili_wm_")
    probe = os.path.join(tmp, "probe.mp4")
    cookie_args = cookie_args or []
    try:
        # Download a low-res copy (small; for long videos this is a few 10s of
        # MB). ffmpeg then reads only the first probe_sec for analysis.
        # (Avoid --download-sections: it can emit a fragment ffmpeg won't parse.)
        # NOTE: Bilibili video formats need a logged-in cookie (premium). Without
        # one, only audio is downloadable and this probe fails -> see reason.
        r = _yt_dlp([
            "-f", "bv[height<=480]+ba/bestvideo+bestaudio",
            "-o", probe, url,
        ] + cookie_args)
        if not os.path.exists(probe):
            return {"bvid": bvid, "watermark": "unknown",
                    "reason": "download failed: " + (r.stderr.strip()[:200])}

        # extract frames from the probe
        frames_dir = os.path.join(tmp, "frames")
        os.makedirs(frames_dir, exist_ok=True)
        subprocess.run([
            "ffmpeg", "-y", "-ss", "0", "-t", str(probe_sec), "-i", probe,
            "-vf", "fps=2",
            os.path.join(frames_dir, "f%03d.png"),
        ], capture_output=True, text=True, check=True)

        corner_var_lists = {name: [] for name in ["top_left", "top_right",
                                                    "bottom_left", "bottom_right"]}
        center_vars = []
        for f in sorted(os.listdir(frames_dir)):
            if not f.endswith(".png"):
                continue
            corners, center = _edge_busyness(os.path.join(frames_dir, f))
            for name, val in corners.items():
                corner_var_lists[name].append(val)
            center_vars.append(center)
        if not center_vars:
            return {"bvid": bvid, "watermark": "unknown",
                    "reason": "no frames extracted"}

        avg_center = sum(center_vars) / len(center_vars)
        # compute per-corner average and ratio vs. center
        corner_stats = {}
        best_corner, best_ratio = None, 0.0
        for name, vals in corner_var_lists.items():
            if not vals:
                continue
            avg_corner = sum(vals) / len(vals)
            ratio = (avg_corner / avg_center) if avg_center > 0 else float("inf")
            corner_stats[name] = {"var": round(avg_corner, 1), "ratio": round(ratio, 2)}
            if ratio > best_ratio:
                best_ratio = ratio
                best_corner = name

        # watermark if any corner is consistently much busier than center
        flagged = best_ratio > 1.6 and corner_stats[best_corner]["var"] > 60
        return {
            "bvid": bvid,
            "watermark": bool(flagged),
            "busiest_corner": best_corner,
            "corner_stats": corner_stats,
            "center_edge_var": round(avg_center, 1),
            "best_ratio": round(best_ratio, 2),
            "reason": (f"{best_corner} corner busier than center"
                       if flagged else f"{best_corner} not significantly busier than center"),
        }
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# --------------------------------------------------------------------------
# 3. download
# --------------------------------------------------------------------------
def download(bvid, audio_out=None, video_out=None, force=False, cookie_args=None):
    url = f"https://www.bilibili.com/video/{bvid}"
    cookie_args = cookie_args or []
    if video_out and not force:
        wm = check_watermark(bvid, cookie_args=cookie_args)
        if wm.get("watermark") is True:
            return {"ok": False, "error": "watermark detected; "
                    "refusing to use as stock. Re-run with --force to override.",
                    "watermark": wm}
    results = {"ok": True}
    if audio_out:
        # audio-only: no visual watermark concern; use best audio format
        r = _yt_dlp(["-x", "--audio-format", "mp3", "--audio-quality", "0",
                     "-o", audio_out, url] + cookie_args)
        results["audio"] = audio_out if os.path.exists(audio_out) else r.stderr.strip()[:200]
    if video_out:
        r = _yt_dlp(["-f", "bv[height<=1080]+ba/best", "-o", video_out, url] + cookie_args)
        results["video"] = video_out if os.path.exists(video_out) else r.stderr.strip()[:200]
    return results


def main():
    ap = argparse.ArgumentParser(description="Bilibili stock-source helper")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("search")
    p.add_argument("keyword")
    p.add_argument("--n", type=int, default=5)

    p = sub.add_parser("check-watermark")
    p.add_argument("bvid")
    p.add_argument("--probe-sec", type=int, default=5)
    p.add_argument("--cookies-from-browser", help="e.g. chrome / firefox")

    p = sub.add_parser("download")
    p.add_argument("bvid")
    p.add_argument("--audio-out")
    p.add_argument("--video-out")
    p.add_argument("--force", action="store_true")
    p.add_argument("--cookies-from-browser", help="e.g. chrome / firefox")

    args = ap.parse_args()
    cookie_args = []
    if getattr(args, "cookies_from_browser", None):
        cookie_args += ["--cookies-from-browser", args.cookies_from_browser]
    if args.cmd == "search":
        print(json.dumps(search(args.keyword, args.n), ensure_ascii=False, indent=2))
    elif args.cmd == "check-watermark":
        print(json.dumps(check_watermark(args.bvid, args.probe_sec, cookie_args), ensure_ascii=False, indent=2))
    elif args.cmd == "download":
        if not args.audio_out and not args.video_out:
            ap.error("specify --audio-out and/or --video-out")
        print(json.dumps(download(args.bvid, args.audio_out, args.video_out, args.force, cookie_args),
                         ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
