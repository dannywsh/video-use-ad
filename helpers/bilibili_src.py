#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Bilibili source helper for video-use / video-use-ad.

Why Bilibili: it is a strong ACG/game/anime stock source (OST audio and short
clips) and a good complement to YouTube for Chinese-language material.

Three commands:
  search         query Bilibili search API, list candidate videos
  probe-frames   download a short low-res probe and dump PNG frames for
                 multimodal watermark inspection by the agent
  download       pull audio (BGM) and/or video via yt-dlp

Usage:
  python bilibili_src.py search "<keyword>" [--n 5]
  python bilibili_src.py probe-frames <BVid> --frames-out <edit>/verify/bili_wm/<BVid> [--probe-sec 5] [--cookies-from-browser chrome]
  python bilibili_src.py download <BVid> --audio-out edit/downloads/x.mp3 [--video-out edit/downloads/x.mp4] [--cookies-from-browser chrome]

Cookie acquisition (for video streams): Bilibili serves only AUDIO anonymously,
so BGM works with no login. Video formats need a logged-in cookie, obtained via
`--cookies-from-browser <chrome|firefox|edge|safari|brave>` — yt-dlp reads the
already-logged-in Bilibili cookie straight from the user's local browser (no manual
export). Works when that browser is installed and logged in. If a probe/download
reports "format not available", that is the cookie signal.

WATERMARK POLICY (mandatory BEFORE using a Bilibili-sourced VIDEO as stock):
  Run `probe-frames <BVid> --frames-out <dir>` first, then visually inspect the
  dumped PNGs with a multimodal model (Read the images). Look especially at
  corners (Bilibili watermarks often sit top-right: UP name + logo). If any
  burned-in watermark/logo/UP overlay is visible, DO NOT use that video as
  material. This check applies ONLY to Bilibili videos; videos from
  YouTube/other platforms are NOT subject to it. Audio-only downloads (BGM)
  are exempt — there is no visual watermark in an audio stream.
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
# 2. probe-frames (screenshots for multimodal watermark inspection)
# --------------------------------------------------------------------------
def probe_frames(bvid, frames_out, probe_sec=5, cookie_args=None):
    """Download a short low-res probe and dump PNGs for the agent to Read.

    Does NOT judge watermarks — the multimodal model must inspect the frames.
    """
    url = f"https://www.bilibili.com/video/{bvid}"
    frames_out = os.path.abspath(frames_out)
    os.makedirs(frames_out, exist_ok=True)
    tmp = tempfile.mkdtemp(prefix="bili_probe_")
    probe = os.path.join(tmp, "probe.mp4")
    cookie_args = cookie_args or []
    try:
        # Low-res probe (small). ffmpeg then reads only the first probe_sec.
        # NOTE: Bilibili video formats need a logged-in cookie. Without one,
        # only audio is downloadable and this probe fails.
        r = _yt_dlp([
            "-f", "bv[height<=480]+ba/bestvideo+bestaudio",
            "-o", probe, url,
        ] + cookie_args)
        if not os.path.exists(probe):
            return {"ok": False, "bvid": bvid,
                    "error": "download failed: " + (r.stderr.strip()[:200])}

        subprocess.run([
            "ffmpeg", "-y", "-ss", "0", "-t", str(probe_sec), "-i", probe,
            "-vf", "fps=1",
            os.path.join(frames_out, "f%03d.png"),
        ], capture_output=True, text=True, check=True)

        frames = sorted(
            os.path.join(frames_out, f)
            for f in os.listdir(frames_out)
            if f.endswith(".png")
        )
        if not frames:
            return {"ok": False, "bvid": bvid, "error": "no frames extracted",
                    "frames_out": frames_out}
        return {
            "ok": True,
            "bvid": bvid,
            "frames_out": frames_out,
            "frames": frames,
            "count": len(frames),
            "hint": ("Read each PNG with multimodal vision. Discard the clip "
                     "if any burned-in watermark/logo/UP overlay is visible "
                     "(often top-right on Bilibili)."),
        }
    except subprocess.CalledProcessError as e:
        return {"ok": False, "bvid": bvid,
                "error": "ffmpeg failed: " + ((e.stderr or "")[:200])}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# --------------------------------------------------------------------------
# 3. download
# --------------------------------------------------------------------------
def download(bvid, audio_out=None, video_out=None, cookie_args=None):
    url = f"https://www.bilibili.com/video/{bvid}"
    cookie_args = cookie_args or []
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

    p = sub.add_parser("probe-frames")
    p.add_argument("bvid")
    p.add_argument("--frames-out", required=True,
                   help="directory to write PNG probe frames")
    p.add_argument("--probe-sec", type=int, default=5)
    p.add_argument("--cookies-from-browser", help="e.g. chrome / firefox")

    p = sub.add_parser("download")
    p.add_argument("bvid")
    p.add_argument("--audio-out")
    p.add_argument("--video-out")
    p.add_argument("--cookies-from-browser", help="e.g. chrome / firefox")

    args = ap.parse_args()
    cookie_args = []
    if getattr(args, "cookies_from_browser", None):
        cookie_args += ["--cookies-from-browser", args.cookies_from_browser]
    if args.cmd == "search":
        print(json.dumps(search(args.keyword, args.n), ensure_ascii=False, indent=2))
    elif args.cmd == "probe-frames":
        print(json.dumps(
            probe_frames(args.bvid, args.frames_out, args.probe_sec, cookie_args),
            ensure_ascii=False, indent=2))
    elif args.cmd == "download":
        if not args.audio_out and not args.video_out:
            ap.error("specify --audio-out and/or --video-out")
        print(json.dumps(download(args.bvid, args.audio_out, args.video_out, cookie_args),
                         ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
