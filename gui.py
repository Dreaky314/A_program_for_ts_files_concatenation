# gui.py
# ============================================================
# TS 文件合并 GUI
# ============================================================

import os
import sys
import shlex
import queue
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path

import core


APP_TITLE = "TS 文件合并工具"


class TSMergeGUI:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title(APP_TITLE)
        self.root.geometry("880x740")
        self.root.minsize(780, 560)

        self.log_queue: queue.Queue = queue.Queue()

        # 只保留 on_log 和 on_done，没有进度回调
        self.runner = core.MergerRunner(
            on_log=self._on_log_from_thread,
            on_done=self._on_done_from_thread,
        )

        self._build_ui()
        self._poll_log()
        self._refresh_ffmpeg_display()

    # ================================================================
    # 界面
    # ================================================================
    def _build_ui(self):
        pad = {"padx": 8, "pady": 4}

        # ---------- 0. ffmpeg 设置区 ----------
        frm_ff = ttk.LabelFrame(self.root, text="ffmpeg 位置")
        frm_ff.pack(fill="x", **pad)

        ttk.Label(frm_ff, text="当前路径:").grid(row=0, column=0, sticky="w", padx=6, pady=4)
        self.var_ffmpeg = tk.StringVar()
        ent = ttk.Entry(frm_ff, textvariable=self.var_ffmpeg, state="readonly")
        ent.grid(row=0, column=1, sticky="ew", padx=6)

        ttk.Button(frm_ff, text="浏览…", command=self.pick_ffmpeg).grid(row=0, column=2, padx=4)
        ttk.Button(frm_ff, text="自动检测", command=self.auto_detect_ffmpeg).grid(row=0, column=3, padx=4)
        ttk.Button(frm_ff, text="测试", command=self.test_current_ffmpeg).grid(row=0, column=4, padx=4)

        self.var_ff_status = tk.StringVar(value="")
        self.lbl_ff_status = ttk.Label(
            frm_ff, textvariable=self.var_ff_status, foreground="gray")
        self.lbl_ff_status.grid(row=1, column=0, columnspan=5, sticky="w", padx=6, pady=(0, 4))

        frm_ff.columnconfigure(1, weight=1)

        # ---------- 1. 文件列表区 ----------
        frm_files = ttk.LabelFrame(
            self.root, text="待合并的分片（可直接选 ts 文件，或从 m3u8 自动导入）")
        frm_files.pack(fill="both", expand=True, **pad)

        list_frame = ttk.Frame(frm_files)
        list_frame.pack(side="left", fill="both", expand=True, padx=6, pady=6)

        self.listbox = tk.Listbox(list_frame, selectmode="extended", height=12)
        self.listbox.pack(side="left", fill="both", expand=True)

        sb = ttk.Scrollbar(list_frame, orient="vertical", command=self.listbox.yview)
        sb.pack(side="right", fill="y")
        self.listbox.config(yscrollcommand=sb.set)

        btn_frame = ttk.Frame(frm_files)
        btn_frame.pack(side="right", fill="y", padx=6, pady=6)

        ttk.Button(btn_frame, text="从 m3u8 导入", command=self.import_m3u8, width=14).pack(pady=3)
        ttk.Separator(btn_frame, orient="horizontal").pack(fill="x", pady=4)
        ttk.Button(btn_frame, text="添加文件", command=self.add_files,       width=14).pack(pady=3)
        ttk.Button(btn_frame, text="添加目录", command=self.add_dir,         width=14).pack(pady=3)
        ttk.Separator(btn_frame, orient="horizontal").pack(fill="x", pady=4)
        ttk.Button(btn_frame, text="上移",     command=self.move_up,         width=14).pack(pady=3)
        ttk.Button(btn_frame, text="下移",     command=self.move_down,       width=14).pack(pady=3)
        ttk.Button(btn_frame, text="删除选中", command=self.remove_selected, width=14).pack(pady=3)
        ttk.Button(btn_frame, text="清空列表", command=self.clear_list,      width=14).pack(pady=3)

        # ---------- 2. 输出设置区 ----------
        frm_out = ttk.LabelFrame(self.root, text="输出")
        frm_out.pack(fill="x", **pad)

        ttk.Label(frm_out, text="输出文件:").grid(row=0, column=0, sticky="w", padx=6, pady=4)
        self.var_output = tk.StringVar()
        ttk.Entry(frm_out, textvariable=self.var_output).grid(row=0, column=1, sticky="ew", padx=6)
        ttk.Button(frm_out, text="另存为", command=self.pick_output).grid(row=0, column=2, padx=6)

        ttk.Label(frm_out, text="输出格式:").grid(row=1, column=0, sticky="w", padx=6, pady=4)
        self.var_fmt = tk.StringVar(value="mp4")
        fmt_frame = ttk.Frame(frm_out)
        fmt_frame.grid(row=1, column=1, sticky="w", padx=6)
        for fmt in ["mp4", "ts", "mkv"]:
            ttk.Radiobutton(
                fmt_frame, text=fmt.upper(), value=fmt,
                variable=self.var_fmt, command=self._on_fmt_change,
            ).pack(side="left", padx=6)

        # ---------- 编码方式 ----------
        ttk.Label(frm_out, text="编码方式:").grid(row=2, column=0, sticky="w", padx=6, pady=4)
        self.var_mode = tk.StringVar(value="copy")  # 默认直接复制

        mode_frame = ttk.Frame(frm_out)
        mode_frame.grid(row=2, column=1, columnspan=2, sticky="w", padx=6, pady=4)

        ttk.Radiobutton(
            mode_frame, text="直接拼接（最快，码率不变）",
            value="copy", variable=self.var_mode,
            command=self._on_mode_change,
        ).pack(anchor="w")

        ttk.Radiobutton(
            mode_frame, text="高质量重编码（接近无损，但是慢）",
            value="crf", variable=self.var_mode,
            command=self._on_mode_change,
        ).pack(anchor="w")

        # "指定码率" 单选项 + 输入框放在同一行
        row_bitrate = ttk.Frame(mode_frame)
        row_bitrate.pack(anchor="w")

        ttk.Radiobutton(
            row_bitrate, text="指定码率：",
            value="bitrate", variable=self.var_mode,
            command=self._on_mode_change,
        ).pack(side="left")

        self.var_bitrate = tk.StringVar(value="8M")
        self.ent_bitrate = ttk.Entry(
            row_bitrate, textvariable=self.var_bitrate, width=8)
        self.ent_bitrate.pack(side="left", padx=6)

        ttk.Label(
            row_bitrate, text="如 4M / 8M / 2000k", foreground="gray"
        ).pack(side="left")

        frm_out.columnconfigure(1, weight=1)

        # ---------- 3. 操作按钮区 ----------
        frm_btn = ttk.Frame(self.root)
        frm_btn.pack(fill="x", **pad)

        self.btn_start = ttk.Button(frm_btn, text="开始合并", command=self.start)
        self.btn_start.pack(side="left", padx=6)

        self.btn_stop = ttk.Button(frm_btn, text="停止", command=self.stop, state="disabled")
        self.btn_stop.pack(side="left", padx=6)

        ttk.Button(frm_btn, text="查看命令", command=self.show_cmd).pack(side="left", padx=6)
        ttk.Button(frm_btn, text="清空日志", command=self.clear_log).pack(side="right", padx=6)

        # ---------- 4. 日志区 ----------
        frm_log = ttk.LabelFrame(self.root, text="日志")
        frm_log.pack(fill="both", expand=True, **pad)

        self.txt_log = tk.Text(frm_log, wrap="word", height=12)
        self.txt_log.pack(side="left", fill="both", expand=True)

        sb2 = ttk.Scrollbar(frm_log, orient="vertical", command=self.txt_log.yview)
        sb2.pack(side="right", fill="y")
        self.txt_log.config(yscrollcommand=sb2.set)
        self.txt_log.tag_config("err",  foreground="red")
        self.txt_log.tag_config("ok",   foreground="green")
        self.txt_log.tag_config("warn", foreground="#c07000")

        # 让输入框初始状态跟默认模式一致（copy 模式下禁用）
        self._on_mode_change()

    # ================================================================
    # ffmpeg 位置
    # ================================================================
    def _refresh_ffmpeg_display(self):
        path = core.get_ffmpeg_path()
        self.var_ffmpeg.set(path)
        ok, info = core.test_ffmpeg(path)
        if ok:
            self.var_ff_status.set(f"✔ 可用 · {info}")
            self.lbl_ff_status.config(foreground="green")
        else:
            self.var_ff_status.set(f"✘ 不可用 · {info}")
            self.lbl_ff_status.config(foreground="red")

    def pick_ffmpeg(self):
        if os.name == "nt":
            filetypes = [("可执行文件", "*.exe"), ("所有文件", "*.*")]
        else:
            filetypes = [("所有文件", "*.*")]

        path = filedialog.askopenfilename(
            title="选择 ffmpeg 可执行文件",
            filetypes=filetypes,
        )
        if not path:
            return

        ok, info = core.test_ffmpeg(path)
        if not ok:
            resp = messagebox.askyesno(
                "测试失败",
                f"该文件似乎不是可用的 ffmpeg：\n{info}\n\n仍然保存吗？",
            )
            if not resp:
                return

        core.set_ffmpeg_path(path)
        self._refresh_ffmpeg_display()
        self.log(f"已设置 ffmpeg 路径: {path}")

    def auto_detect_ffmpeg(self):
        cfg = core.load_config()
        cfg.pop("ffmpeg_path", None)
        core.save_config(cfg)
        self._refresh_ffmpeg_display()
        path = core.get_ffmpeg_path()
        self.log(f"已恢复自动检测，当前路径: {path}")

    def test_current_ffmpeg(self):
        path = self.var_ffmpeg.get()
        ok, info = core.test_ffmpeg(path)
        if ok:
            messagebox.showinfo("测试通过", f"ffmpeg 可用：\n{info}")
        else:
            messagebox.showerror("测试失败", f"ffmpeg 不可用：\n{info}")

    # ================================================================
    # m3u8 导入
    # ================================================================
    def import_m3u8(self):
        path = filedialog.askopenfilename(
            title="选择本地 m3u8 文件",
            filetypes=[("M3U8 播放列表", "*.m3u8"), ("所有文件", "*.*")],
        )
        if not path:
            return

        try:
            info = core.parse_m3u8(path)
        except core.M3U8Error as e:
            messagebox.showerror("解析失败", str(e))
            return

        if info["is_master"]:
            messagebox.showwarning(
                "注意",
                "这是一个 master 列表（多码率），它引用的是子 m3u8 而不是 ts。\n"
                "请选择具体的子 m3u8 文件。",
            )
            return

        if info["encrypted"]:
            self.log("⚠ 检测到加密标签（#EXT-X-KEY），本工具不解密，可能合并失败。", "warn")
        if not info["has_endlist"]:
            self.log("⚠ m3u8 中无 #EXT-X-ENDLIST，可能是直播列表，可能不完整。", "warn")

        try:
            segments = core.resolve_segments(info, must_exist=True)
        except core.M3U8Error as e:
            resp = messagebox.askyesno(
                "有分片缺失",
                f"{e}\n\n是否仍然导入现有分片？（合并时可能失败）",
            )
            if not resp:
                return
            segments = core.resolve_segments(info, must_exist=False)

        self.listbox.delete(0, "end")
        for seg in segments:
            self.listbox.insert("end", seg)

        base_dir = info["dir"]
        fmt = self.var_fmt.get()
        default_name = os.path.splitext(os.path.basename(info["path"]))[0]
        self.var_output.set(os.path.join(base_dir, f"{default_name}.{fmt}"))

        self.log("=" * 60)
        self.log(f"已从 m3u8 导入 {len(segments)} 个分片")
        self.log(f"m3u8 路径: {info['path']}")
        self.log(f"分片目录 : {info['dir']}")

    # ================================================================
    # 文件列表操作
    # ================================================================
    def add_files(self):
        paths = filedialog.askopenfilenames(
            title="选择 TS 文件",
            filetypes=[("TS 文件", "*.ts"), ("所有文件", "*.*")],
        )
        for p in paths:
            self.listbox.insert("end", p)
        if paths and not self.var_output.get():
            self._auto_output_name()

    def add_dir(self):
        d = filedialog.askdirectory(title="选择包含 TS 的目录")
        if not d:
            return
        files = core.list_ts_files(d)
        if not files:
            messagebox.showinfo("提示", "该目录下没有 .ts 文件")
            return
        for f in files:
            self.listbox.insert("end", f)
        if not self.var_output.get():
            self._auto_output_name()

    def _auto_output_name(self):
        items = self.listbox.get(0, "end")
        if not items:
            return
        base_dir = os.path.dirname(items[0])
        fmt = self.var_fmt.get()
        self.var_output.set(os.path.join(base_dir, f"merged.{fmt}"))

    def remove_selected(self):
        for i in reversed(self.listbox.curselection()):
            self.listbox.delete(i)

    def clear_list(self):
        self.listbox.delete(0, "end")

    def move_up(self):
        sel = self.listbox.curselection()
        if not sel or sel[0] == 0:
            return
        for i in sel:
            if i == 0:
                continue
            text = self.listbox.get(i)
            self.listbox.delete(i)
            self.listbox.insert(i - 1, text)
        self.listbox.selection_clear(0, "end")
        for i in sel:
            self.listbox.selection_set(max(0, i - 1))

    def move_down(self):
        sel = list(self.listbox.curselection())
        if not sel:
            return
        last = self.listbox.size() - 1
        for i in reversed(sel):
            if i >= last:
                continue
            text = self.listbox.get(i)
            self.listbox.delete(i)
            self.listbox.insert(i + 1, text)
        self.listbox.selection_clear(0, "end")
        for i in sel:
            self.listbox.selection_set(min(last, i + 1))

    def _on_fmt_change(self):
        out = self.var_output.get()
        if out:
            base, _ = os.path.splitext(out)
            self.var_output.set(base + "." + self.var_fmt.get())

    def _on_mode_change(self):
        """码率输入框只在'指定码率'模式下可编辑"""
        state = "normal" if self.var_mode.get() == "bitrate" else "disabled"
        self.ent_bitrate.config(state=state)

    def _build_ffmpeg_kwargs(self) -> dict:
        """
        根据界面上的编码模式，组装传给 core.build_ffmpeg_cmd 的参数。
        """
        mode = self.var_mode.get()

        if mode == "copy":
            return {"mode": "copy"}

        if mode == "crf":
            return {"mode": "crf", "crf": 18}

        if mode == "bitrate":
            return {
                "mode": "bitrate",
                "video_bitrate": self.var_bitrate.get().strip() or "8M",
                "audio_bitrate": "192k",
            }

        return {"mode": "copy"}  # 兜底

    def pick_output(self):
        fmt = self.var_fmt.get()
        path = filedialog.asksaveasfilename(
            title="保存为",
            defaultextension=f".{fmt}",
            filetypes=[(fmt.upper(), f"*.{fmt}"), ("所有文件", "*.*")],
        )
        if path:
            self.var_output.set(path)
            ext = os.path.splitext(path)[1].lstrip(".").lower()
            if ext in ("mp4", "ts", "mkv"):
                self.var_fmt.set(ext)

    # ================================================================
    # 日志
    # ================================================================
    def log(self, msg: str, tag: str | None = None):
        self.log_queue.put(("log", msg, tag))

    def _on_log_from_thread(self, line: str, is_error: bool):
        self.log_queue.put(("log", line, "err" if is_error else None))

    def _on_done_from_thread(self, success: bool, message: str):
        self.log_queue.put(("done", success, message))

    def _poll_log(self):
        try:
            while True:
                item = self.log_queue.get_nowait()
                if item[0] == "log":
                    _, line, tag = item
                    if tag:
                        self.txt_log.insert("end", line + "\n", tag)
                    else:
                        self.txt_log.insert("end", line + "\n")
                    self.txt_log.see("end")
                elif item[0] == "done":
                    _, success, message = item
                    self._on_task_finished(success, message)
        except queue.Empty:
            pass
        self.root.after(100, self._poll_log)

    def _on_task_finished(self, success: bool, message: str):
        if success:
            self.log(f"✅ 完成：{self.var_output.get()}", "ok")
        else:
            self.log(f"❌ {message}", "err")
        self.btn_start.config(state="normal")
        self.btn_stop.config(state="disabled")

    def clear_log(self):
        self.txt_log.delete("1.0", "end")

    # ================================================================
    # 执行
    # ================================================================
    def _collect_files(self) -> list[str]:
        return list(self.listbox.get(0, "end"))

    def show_cmd(self):
        try:
            files = self._collect_files()
            output = self.var_output.get().strip()
            cmd, list_path = core.build_ffmpeg_cmd(
                files, output, **self._build_ffmpeg_kwargs()
            )
            try:
                os.remove(list_path)
            except OSError:
                pass
            self._show_cmd_dialog(cmd)
        except Exception as e:
            messagebox.showerror("错误", str(e))

    def _show_cmd_dialog(self, cmd):
        win = tk.Toplevel(self.root)
        win.title("ffmpeg 命令")
        win.geometry("760x240")
        txt = tk.Text(win, wrap="word")
        txt.pack(fill="both", expand=True)
        display = " ".join(shlex.quote(c) for c in cmd)
        txt.insert("1.0", display)
        txt.config(state="disabled")

        def copy():
            self.root.clipboard_clear()
            self.root.clipboard_append(display)
            messagebox.showinfo("提示", "已复制到剪贴板")

        ttk.Button(win, text="复制", command=copy).pack(pady=6)

    def start(self):
        if self.runner.is_running():
            messagebox.showinfo("提示", "已有任务在执行")
            return

        ok, info = core.test_ffmpeg(core.get_ffmpeg_path())
        if not ok:
            resp = messagebox.askyesno(
                "ffmpeg 不可用",
                f"当前 ffmpeg 无法执行：\n{info}\n\n是否现在选择 ffmpeg 路径？",
            )
            if resp:
                self.pick_ffmpeg()
            return

        files = self._collect_files()
        output = self.var_output.get().strip()
        try:
            cmd, list_path = core.build_ffmpeg_cmd(
                files, output, **self._build_ffmpeg_kwargs()
            )
        except Exception as e:
            messagebox.showerror("错误", str(e))
            return

        self.log("=" * 60)
        self.log(f"使用 ffmpeg: {cmd[0]}")
        self.log("执行命令：")
        self.log(" ".join(shlex.quote(c) for c in cmd))
        self.log("-" * 60)
        self.log("正在合并，请稍候…")

        self.btn_start.config(state="disabled")
        self.btn_stop.config(state="normal")

        self.runner.start(cmd, cleanup_path=list_path)

    def stop(self):
        if self.runner.is_running():
            self.log("正在停止…", "err")
            self.runner.stop()

# ================================================================
# 图标
# ================================================================
def _resource_path(name: str) -> str:
        """
        获取资源文件的绝对路径。
        - 开发环境：脚本所在目录
        - 打包后：PyInstaller 解压出来的临时目录 sys._MEIPASS
        """
        if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
            base = Path(sys._MEIPASS)
        else:
            base = Path(__file__).resolve().parent
        return str(base / name)

def _set_window_icon(root: tk.Tk):
        """设置窗口左上角图标，找不到文件就静默跳过"""
        ico_path = _resource_path("app.ico")
        if not os.path.isfile(ico_path):
            return
        try:
            # iconbitmap 只接受 .ico，Windows 上最稳
            root.iconbitmap(ico_path)
        except Exception:
            # Linux/macOS 可能不支持 iconbitmap，可以试试 PhotoImage
            try:
                img = tk.PhotoImage(file=ico_path)
                root.iconphoto(True, img)
                root._icon_ref = img  # 保存引用，防止被 GC 回收
            except Exception:
                pass

# ================================================================
# 入口
# ================================================================
def main():
    if sys.platform == "win32":
        import ctypes
        # 这个 ID 可以自定义，建议用点分命名，例如 "com.yourname.tsmergetool"
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            "com.yourname.tsmergetool"
        )

    root = tk.Tk()
    root.title(APP_TITLE)

    # 设置窗口图标
    _set_window_icon(root)

    try:
        style = ttk.Style()
        if "vista" in style.theme_names():
            style.theme_use("vista")
        elif "clam" in style.theme_names():
            style.theme_use("clam")
    except Exception:
        pass

    TSMergeGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()