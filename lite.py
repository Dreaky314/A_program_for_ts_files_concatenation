# cli.py —— 演示 core 的复用性
import sys
import core
from core import MergerRunner

def main():
    files = core.list_ts_files(sys.argv[1])   # 从目录里挑出所有 ts
    output = sys.argv[2]
    cmd, list_path = core.build_ffmpeg_cmd(files, output, reencode=False)

    # 简单的日志回调：直接 print
    runner = MergerRunner(
        on_log=lambda line, is_err: print(line),
        on_done=lambda ok, msg: print("OK" if ok else "FAIL", msg),
    )
    runner.start(cmd, cleanup_path=list_path)

    # 等它跑完
    import time
    while runner.is_running():
        time.sleep(0.2)

if __name__ == "__main__":
    main()