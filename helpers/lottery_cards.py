"""赏视频模板 CLI：连接商品清单、选品、前端工程与渲染流程。"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import subprocess
import sys
import uuid

try:
    from .lottery_common import edit_path, prepare_edit, write_json
    from .lottery_templates import DEFAULT_TEMPLATE, list_templates, load_template
    from .lottery_scene import prepare_scene, select_prizes
    from .lottery_remotion import browser_arguments, prepare_font, prepare_project, remotion_command, resolve_font, verify_video
except ImportError:
    from lottery_common import edit_path, prepare_edit, write_json
    from lottery_templates import DEFAULT_TEMPLATE, list_templates, load_template
    from lottery_scene import prepare_scene, select_prizes
    from lottery_remotion import browser_arguments, prepare_font, prepare_project, remotion_command, resolve_font, verify_video


# 功能：使用所选模板原子渲染镜头；输入：奖池、ID、时长、输出、字体、模板 ID；返回：预览 PNG。
def render_card(goods_path: Path, ids: list[str], duration: float, output: Path,
                font_path: Path | None = None, preview_only: bool = False,
                template_id: str = DEFAULT_TEMPLATE) -> Path:
    template = load_template(template_id)
    output = edit_path(output)
    if output.suffix != ".mp4" or not math.isfinite(duration) or duration <= 0:
        raise ValueError("输出须为 .mp4，镜头时长必须为正有限数")
    root = next(parent for parent in output.parents if parent.name == "edit")
    prepare_edit(root)
    goods = json.loads(goods_path.read_text(encoding="utf-8"))
    prizes = select_prizes(goods, ids)
    config = template.config
    project = prepare_project(root, template)
    prepare_font(resolve_font(font_path), project)
    scene, report = prepare_scene(goods, prizes, project / "public", config, duration)
    folder = output.parent / f"{output.stem}-scene"
    folder.mkdir(parents=True, exist_ok=True)
    props = folder / "props.json"
    write_json(props, scene)
    write_json(project / "src" / "scene.json", scene)
    write_json(folder / "template.json", config)
    command = remotion_command(project)
    browser = browser_arguments(project)
    preview = folder / "preview.png"
    frame = min(36, scene["durationInFrames"] - 1)
    subprocess.run(command + ["still", "src/index.ts", "PrizeCard", str(preview), f"--props={props}",
                   f"--frame={frame}", "--log=error"] + browser, cwd=project, check=True)
    report.update({"goods_path": str(goods_path.resolve()), "item_id": goods["item_id"], "prize_ids": ids,
        "requested_duration": duration, "probability_display": False, "project_path": str(project), "props_path": str(props)})
    if not preview_only:
        temporary = output.with_name(f".{output.stem}-{uuid.uuid4().hex}.partial.mp4")
        try:
            subprocess.run(command + ["render", "src/index.ts", "PrizeCard", str(temporary), f"--props={props}",
                "--codec=h264", "--crf=18", "--concurrency=2", "--log=error"] + browser, cwd=project, check=True)
            report["video"] = verify_video(temporary, scene["durationInFrames"], config)
            temporary.replace(output)
        finally:
            temporary.unlink(missing_ok=True)
    write_json(folder / "render_report.json", report)
    print(f"模板：{template.id}；前端工程：{project}（可运行 npm run studio -- --props {props}）")
    return preview


# 功能：解析赏舞台渲染命令；输入：CLI 参数；返回：进程状态。
def main() -> int:
    parser = argparse.ArgumentParser(description="用 Remotion / React 渲染赏品主题舞台")
    parser.add_argument("goods", type=Path, nargs="?")
    parser.add_argument("--prize-id", action="append")
    parser.add_argument("--duration", type=float)
    parser.add_argument("-o", "--output", type=Path)
    parser.add_argument("--template", default=DEFAULT_TEMPLATE, help="模板 ID，默认 default")
    parser.add_argument("--list-templates", action="store_true", help="列出已安装模板，不采集或渲染")
    parser.add_argument("--font", type=Path)
    parser.add_argument("--preview-only", action="store_true", help="仅渲染前端审阅帧，不编码视频")
    args = parser.parse_args()
    try:
        if args.list_templates:
            for template in list_templates():
                label = "（默认）" if template.id == DEFAULT_TEMPLATE else ""
                print(f"{template.id}{label}\t{template.config['name']}\t{template.config.get('description', '')}")
            return 0
        if not args.goods or not args.prize_id or args.duration is None or not args.output:
            parser.error("渲染须提供 goods、--prize-id、--duration 和 --output")
        print(f"预览：{render_card(args.goods, args.prize_id, args.duration, args.output, args.font, args.preview_only, args.template)}")
        return 0
    except (ValueError, OSError, KeyError, subprocess.CalledProcessError) as exc:
        print(f"渲染失败：{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
