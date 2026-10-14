"""管理隔离的 Remotion 工程、中文字体与渲染产物校验。"""

from __future__ import annotations

import hashlib
import json
import os
import platform
from pathlib import Path
import shutil
import subprocess
import sys

from fontTools.ttLib import TTFont

try:
    from .lottery_common import write_json
    from .lottery_templates import ASSETS_ROOT, LotteryTemplate
except ImportError:
    from lottery_common import write_json
    from lottery_templates import ASSETS_ROOT, LotteryTemplate


# 功能：选择中文字体；输入：可选字体路径；返回：存在的字体文件，否则阻塞。
def resolve_font(explicit: Path | None) -> Path:
    windows_fonts = Path(os.environ.get("WINDIR") or os.environ.get("SystemRoot") or "C:/Windows") / "Fonts"
    candidates = [explicit.expanduser()] if explicit else ([
        windows_fonts / "msyhbd.ttc", windows_fonts / "msyh.ttc",
    ] if sys.platform == "win32" else [
        Path("/System/Library/Fonts/Hiragino Sans GB.ttc"),
        Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"),
        Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
    ])
    for path in candidates:
        if path and path.is_file():
            return path.resolve()
    raise FileNotFoundError("未找到中文字体，请用 --font 指定微软雅黑/Noto Sans CJK/冬青黑体字体文件")


# 功能：查找可直接执行的 Node；输入：无；返回：Node 可执行文件绝对路径。
def node_executable() -> str:
    binary = shutil.which("node")
    if not binary:
        raise FileNotFoundError("未找到 Node.js，请安装并将 node 加入 PATH")
    return binary


# 功能：解析跨平台 npm 入口，避免执行 Windows 批处理；输入：无；返回：安装命令前缀。
def npm_command() -> list[str]:
    binary = shutil.which("npm")
    if not binary:
        raise FileNotFoundError("未找到 npm，请安装 Node.js/npm 并加入 PATH")
    resolved = Path(binary).resolve()
    if resolved.suffix.lower() == ".cmd":
        entry = resolved.parent / "node_modules" / "npm" / "bin" / "npm-cli.js"
        if not entry.is_file():
            raise FileNotFoundError(f"npm 的 JavaScript 入口不存在，请检查 Node.js/npm 安装：{entry}")
        return [node_executable(), str(entry)]
    if resolved.suffix.lower() == ".js":
        return [node_executable(), str(resolved)]
    return [binary]


# 功能：从包清单定位 Remotion CLI；输入：运行工程；返回：跨平台 Node 命令前缀。
def remotion_command(project: Path) -> list[str]:
    package_root = project / "node_modules" / "@remotion" / "cli"
    package = json.loads((package_root / "package.json").read_text())
    entry = (package_root / package["bin"]["remotion"]).resolve()
    if not entry.is_file() or package_root.resolve() not in entry.parents:
        raise FileNotFoundError("Remotion CLI 入口无效，请检查运行工程依赖")
    return [node_executable(), str(entry)]


# 功能：复用同任务内同版本、同平台的已安装浏览器；输入：模板工程；返回：Remotion 浏览器参数或空列表。
def browser_arguments(project: Path) -> list[str]:
    manifest = project / "node_modules/@remotion/cli/package.json"
    version = json.loads(manifest.read_text())["version"]
    if sys.platform == "win32":
        target_platform, executable = "win64", "chrome-headless-shell.exe"
    elif sys.platform == "darwin":
        target_platform = "mac-arm64" if platform.machine().lower() in {"arm64", "aarch64"} else "mac-x64"
        executable = "chrome-headless-shell"
    else:
        target_platform = "linux-arm64" if platform.machine().lower() in {"arm64", "aarch64"} else "linux64"
        executable = "chrome-headless-shell"
    for peer in sorted(project.parent.iterdir()):
        if peer == project or not peer.is_dir():
            continue
        peer_manifest = peer / "node_modules/@remotion/cli/package.json"
        if not peer_manifest.is_file():
            continue
        try:
            if json.loads(peer_manifest.read_text())["version"] != version:
                continue
        except (OSError, ValueError, KeyError):
            continue
        cache = peer / "node_modules/.remotion/chrome-headless-shell" / target_platform
        for name in ("headless_shell", executable):
            for binary in sorted(cache.glob(f"*/{name}")):
                if binary.is_file() and binary.stat().st_size > 0:
                    return [f"--browser-executable={binary.resolve()}"]
    return []


# 功能：将本地合法字体转换成浏览器可加载的 TTF；输入：字体与工程；返回：缓存字体文件。
def prepare_font(source: Path, project: Path) -> Path:
    target = project / "public" / "fonts" / "prize.ttf"
    marker = target.with_suffix(".sha256")
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    if target.exists() and marker.exists() and marker.read_text() == digest:
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    # 冬青 GB TTC 包含 W3、界面 W3、W6、界面 W6，选择明确的粗体 W6。
    font_number = 2 if source.name == "Hiragino Sans GB.ttc" else 0
    with TTFont(str(source), fontNumber=font_number) as font:
        font.flavor = None
        font.save(target)
    marker.write_text(digest)
    return target


# 功能：复制受管理工程文件并保留用户修改；输入：工程、相对文件→内容；返回：无。
def sync_project_files(project: Path, sources: dict[str, bytes]) -> None:
    marker = project / ".template-hashes.json"
    previous = json.loads(marker.read_text()) if marker.exists() else {}
    hashes = {}
    for relative, content in sources.items():
        destination = project / relative
        digest = hashlib.sha256(content).hexdigest()
        if destination.exists():
            existing = hashlib.sha256(destination.read_bytes()).hexdigest()
            if existing != digest and existing != previous.get(relative):
                if relative not in previous:
                    raise ValueError(f"已有工程并非技能创建，保留原文件，请更换素材 edit 目录：{destination}")
                print(f"保留已编辑的前端组件：{destination}")
                hashes[relative] = previous[relative]
                continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(content)
        hashes[relative] = digest
    # 仅清理技能之前生成且未被用户修改的过期文件。
    for relative, digest in previous.items():
        obsolete = project / relative
        if relative not in sources and obsolete.is_file() and hashlib.sha256(obsolete.read_bytes()).hexdigest() == digest:
            obsolete.unlink()
    write_json(marker, hashes)


# 功能：校验并安装前端依赖；输入：工程路径；返回：无，安装失败则阻塞。
def ensure_dependencies(project: Path) -> None:
    package = json.loads((project / "package.json").read_text())
    for name, version in {**package.get("dependencies", {}), **package.get("devDependencies", {})}.items():
        installed = project / "node_modules" / name / "package.json"
        if not installed.is_file() or json.loads(installed.read_text())["version"] != version:
            # 不执行安装脚本，不改变用户 npm 发布等待期或全局安全设置。
            subprocess.run(npm_command() + ["install", "--ignore-scripts", "--no-audit", "--no-fund"], cwd=project, check=True)
            return


# 功能：为所选模板建立独立前端工程；输入：edit 根、模板定义、共用资源根；返回：工程目录。
def prepare_project(root: Path, template: LotteryTemplate, assets_root: Path = ASSETS_ROOT) -> Path:
    project = root / "remotion" / "lottery" / template.id
    sources = {}
    shared = assets_root / "shared"
    for source in shared.rglob("*"):
        if source.is_file() and source.name != "scene.json":
            sources[source.relative_to(shared).as_posix()] = source.read_bytes()
    for source in template.directory.rglob("*"):
        if source.is_file():
            relative = source.relative_to(template.directory).as_posix()
            destination = (f"public/templates/{template.id}/{relative[7:]}" if relative.startswith("public/")
                           else f"src/templates/{template.id}/{relative}")
            sources[destination] = source.read_bytes()
    entry = Path(template.config["entrypoint"]).with_suffix("").as_posix()
    module = json.dumps(f"./templates/{template.id}/{entry}")
    sources["src/SelectedTemplate.ts"] = (
        f"export {{PrizeStage as TemplateStage}} from {module};\n"
        f"export const TEMPLATE_ID = {json.dumps(template.id)};\n"
    ).encode()
    sync_project_files(project, sources)
    ensure_dependencies(project)
    return project


# 功能：验证渲染规格与解码完整性；输入：视频、预期帧数、模板；返回：FFprobe 视频信息。
def verify_video(path: Path, frames: int, config: dict) -> dict:
    result = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
        "stream=width,height,avg_frame_rate,nb_frames,duration,sample_aspect_ratio", "-of", "json", str(path)],
        capture_output=True, text=True, check=True)
    stream = json.loads(result.stdout)["streams"][0]
    if (stream["width"], stream["height"], stream["avg_frame_rate"]) != (1080, 1920, "30/1"):
        raise ValueError("渲染视频不是 1080×1920、30fps")
    if int(stream["nb_frames"]) != frames or abs(float(stream["duration"]) - frames / config["fps"]) > 0.001:
        raise ValueError("视频帧数/时长与口播时间窗不符")
    subprocess.run(["ffmpeg", "-v", "error", "-xerror", "-i", str(path), "-f", "null", "-"],
        stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, check=True)
    return stream
