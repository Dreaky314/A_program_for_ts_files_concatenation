import os
import re
import sys
import json
import shutil
import subprocess
import threading
import tempfile
from pathlib import Path

__all__ = [
    "natural_key",
    "list_ts_files",
    "parse_m3u8",
    "resolve_segments",
    "build_concat_list",
    "build_ffmpeg_cmd",
    "MergerRunner",
    "get_ffmpeg_path",
    "get_ffprobe_path",
    "set_ffmpeg_path",
    "load_config",
    "save_config",
    "test_ffmpeg",
    "M3U8Error",
]


# ============================================================
# 程序所在目录 & 配置文件
# ============================================================
def _get_app_dir() -> Path:
    """
    程序真正所在目录，用于放配置文件。
    - 开发环境：core.py 所在目录
    - 打包后：exe 所在目录
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def _get_config_path() -> Path:
    return _get_app_dir() / "config.json"


def load_config() -> dict:
    path = _get_config_path()
    if not path.is_file():
        return {}
    try:
        with open(path, "r", encoding="utf-8") as fp:
            data = json.load(fp)
            if isinstance(data, dict):
                return data
    except Exception:
        pass
    return {}


def save_config(cfg: dict):
    path = _get_config_path()
    try:
        with open(path, "w", encoding="utf-8") as fp:
            json.dump(cfg, fp, indent=2, ensure_ascii=False)
    except Exception:
        pass


def set_ffmpeg_path(path: str):
    cfg = load_config()
    cfg["ffmpeg_path"] = path
    save_config(cfg)


# ============================================================
# ffmpeg / ffprobe 路径查找
# ============================================================
def _check_exe(path: str) -> bool:
    if not path:
        return False
    p = Path(path)
    if not p.is_file():
        return False
    if sys.platform == "win32" and p.suffix.lower() not in (".exe", ".bat", ".cmd"):
        return False
    return True


def get_ffmpeg_path() -> str:
    """
    按优先级返回 ffmpeg 路径：
      1. 用户配置文件里保存的路径
      2. 程序所在目录的 ffmpeg(.exe)
      3. 系统 PATH
    """
    # 1. 用户配置
    cfg = load_config()
    user_path = cfg.get("ffmpeg_path", "")
    if _check_exe(user_path):
        return user_path

    # 2. 程序同目录
    base = _get_app_dir()
    for name in ("ffmpeg.exe", "ffmpeg"):
        p = base / name
        q = base / "ffmpeg/bin" / name
        if p.is_file():
            return str(p)
        elif q.is_file():
            return str(q)

    # 3. 系统 PATH
    found = shutil.which("ffmpeg")
    if found:
        return found

    return "ffmpeg"


def get_ffprobe_path() -> str:
    """
    找 ffprobe，逻辑和 ffmpeg 一样：
      1. 用户配置的 ffmpeg 同目录
      2. 程序同目录
      3. 系统 PATH
    """
    # 1. 用户配置的 ffmpeg 同目录
    cfg = load_config()
    user_path = cfg.get("ffmpeg_path", "")
    if _check_exe(user_path):
        same_dir = Path(user_path).parent
        for name in ("ffprobe.exe", "ffprobe"):
            p = same_dir / name
            if p.is_file():
                return str(p)

    # 2. 程序同目录
    base = _get_app_dir()
    for name in ("ffprobe.exe", "ffprobe"):
        p = base / name
        q = base / "ffmpeg/bin" / name
        if p.is_file():
            return str(p)
        elif q.is_file():
            return str(q)

    # 3. 系统 PATH
    found = shutil.which("ffprobe")
    if found:
        return found

    return "ffprobe"


def test_ffmpeg(path: str | None = None) -> tuple[bool, str]:
    exe = path or get_ffmpeg_path()
    try:
        r = subprocess.run(
            [exe, "-version"],
            capture_output=True, text=True, timeout=8,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )
        if r.returncode == 0:
            first = (r.stdout or "").splitlines()[0] if r.stdout else ""
            return True, first
        return False, f"退出码 {r.returncode}"
    except FileNotFoundError:
        return False, "找不到该文件"
    except subprocess.TimeoutExpired:
        return False, "执行超时"
    except Exception as e:
        return False, str(e)


# ============================================================
# 工具函数
# ============================================================
def natural_key(s: str):
    parts = re.split(r"(\d+)", os.path.basename(s))
    return [int(t) if t.isdigit() else t.lower() for t in parts]


def list_ts_files(directory: str) -> list[str]:
    files = [
        os.path.join(directory, f)
        for f in os.listdir(directory)
        if f.lower().endswith(".ts")
    ]
    return sorted(files, key=natural_key)


# ============================================================
# m3u8 解析
# ============================================================
class M3U8Error(Exception):
    pass


def parse_m3u8(m3u8_path: str) -> dict:
    if not os.path.isfile(m3u8_path):
        raise M3U8Error(f"文件不存在: {m3u8_path}")

    with open(m3u8_path, "r", encoding="utf-8", errors="ignore") as fp:
        content = fp.read()

    if not content.lstrip("\ufeff \t\r\n").startswith("#EXTM3U"):
        raise M3U8Error("不是合法的 m3u8 文件（缺少 #EXTM3U 头）")

    segments, encrypted, is_master, has_endlist = [], False, False, False

    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("#"):
            if line.startswith("#EXT-X-KEY") and "METHOD=NONE" not in line.upper():
                encrypted = True
            elif line.startswith("#EXT-X-STREAM-INF"):
                is_master = True
            elif line.startswith("#EXT-X-ENDLIST"):
                has_endlist = True
            continue
        segments.append(line)

    return {
        "path": os.path.abspath(m3u8_path),
        "dir": os.path.dirname(os.path.abspath(m3u8_path)),
        "segments": segments,
        "encrypted": encrypted,
        "is_master": is_master,
        "has_endlist": has_endlist,
    }


def resolve_segments(info: dict, must_exist: bool = True) -> list[str]:
    base_dir = info["dir"]
    result = []
    for seg in info["segments"]:
        if seg.startswith(("http://", "https://")):
            result.append(seg)
            continue
        full = os.path.normpath(
            seg if os.path.isabs(seg) else os.path.join(base_dir, seg)
        )
        if must_exist and not os.path.isfile(full):
            raise M3U8Error(f"m3u8 引用的分片不存在: {full}")
        result.append(full)

    if not result:
        raise M3U8Error("m3u8 中没有解析到任何分片")
    return result


# ============================================================
# 构建命令
# ============================================================
def build_concat_list(files: list[str], list_path: str | None = None) -> str:
    if list_path is None:
        list_path = os.path.join(tempfile.gettempdir(), "ts_concat_list.txt")
    with open(list_path, "w", encoding="utf-8") as fp:
        for f in files:
            safe = os.path.abspath(f).replace("\\", "/").replace("'", "'\\''")
            fp.write(f"file '{safe}'\n")
    return list_path


def build_ffmpeg_cmd(
    files: list[str],
    output: str,
    mode: str = "copy",           # "copy" / "crf" / "bitrate"
    crf: int = 18,
    video_bitrate: str = "8M",
    audio_bitrate: str = "192k",
    list_path: str | None = None,
) -> tuple[list[str], str]:
    """
    拼 ffmpeg 命令。

    mode:
      "copy"    直接复制流，不重编码，码率与源一致
      "crf"     质量优先重编码，CRF 越小越清晰
      "bitrate" 固定码率重编码
    """
    if not files:
        raise ValueError("文件列表为空")
    for f in files:
        if not os.path.isfile(f):
            raise ValueError(f"文件不存在: {f}")
    if not output:
        raise ValueError("输出文件名不能为空")

    list_path = build_concat_list(files, list_path)

    cmd = [
        get_ffmpeg_path(),
        "-y",
        "-f", "concat", "-safe", "0",
        "-i", list_path,
    ]

    if mode == "copy":
        cmd += ["-c", "copy"]

    elif mode == "crf":
        cmd += [
            "-c:v", "libx264",
            "-crf", str(crf),
            "-preset", "medium",
            "-c:a", "aac",
            "-b:a", audio_bitrate,
        ]

    elif mode == "bitrate":
        cmd += [
            "-c:v", "libx264",
            "-b:v", video_bitrate,
            "-maxrate", video_bitrate,
            "-bufsize", video_bitrate,
            "-preset", "medium",
            "-c:a", "aac",
            "-b:a", audio_bitrate,
        ]

    else:
        raise ValueError(f"未知的 mode: {mode}")

    if output.lower().endswith(".mp4"):
        cmd += ["-bsf:a", "aac_adtstoasc", "-movflags", "+faststart"]

    cmd += [output]
    return cmd, list_path

# ============================================================
# 运行器
# ============================================================
class MergerRunner:
    """
    在后台线程里运行 ffmpeg，通过回调通知调用者。
    回调：
        on_log(line, is_error)        每读一行 ffmpeg 输出
        on_done(success, message)     任务结束
    """

    def __init__(self, on_log=None, on_done=None):
        self.on_log = on_log or (lambda line, is_error: None)
        self.on_done = on_done or (lambda success, message: None)
        self._process: subprocess.Popen | None = None
        self._thread: threading.Thread | None = None

    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self, cmd: list[str], cleanup_path: str | None = None):
        if self.is_running():
            raise RuntimeError("已有任务在执行")
        self._thread = threading.Thread(
            target=self._run,
            args=(cmd, cleanup_path),
            daemon=True,
        )
        self._thread.start()

    def _run(self, cmd: list[str], cleanup_path: str | None):
        success, message = False, ""
        try:
            creationflags = 0
            if sys.platform.startswith("win"):
                creationflags = subprocess.CREATE_NO_WINDOW

            self._process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                encoding="utf-8",
                errors="ignore",
                creationflags=creationflags,
            )

            assert self._process.stdout is not None
            for line in self._process.stdout:
                line = line.rstrip()
                if not line:
                    continue
                low = line.lower()
                is_err = "error" in low or "failed" in low or "invalid" in low
                self.on_log(line, is_err)

            code = self._process.wait()
            success = (code == 0)
            message = "完成" if success else f"ffmpeg 退出码 {code}"

        except FileNotFoundError:
            exe = cmd[0] if cmd else "ffmpeg"
            message = f"找不到 ffmpeg：{exe}\n请点击界面上的『浏览』选择 ffmpeg 路径"
        except Exception as e:
            message = f"异常：{e}"
        finally:
            if cleanup_path:
                try:
                    if os.path.exists(cleanup_path):
                        os.remove(cleanup_path)
                except OSError:
                    pass
            self._process = None
            self.on_done(success, message)

    def stop(self):
        if self._process and self._process.poll() is None:
            try:
                self._process.terminate()
            except Exception:
                pass