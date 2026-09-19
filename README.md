
## 简介

一个用来把下载到本地的 **TS 分片** 或 **m3u8 播放列表** 合并成完整视频的小工具。

因为发现下载的视频全是 `.ts` 切片，懒得敲ffmpeg指令，叫ai写的程序（我的天哪是ds大人）。

---

## 功能

- **合并 TS 分片**：手动添加文件、添加整个目录，自动按文件名里的数字自然排序
- **从 m3u8 导入**：直接选本地 `.m3u8` 文件，自动解析出所有分片路径并填入列表
- **三种编码模式**：
  - `直接拼接`：`-c copy`，不重编码，速度最快，码率与原文件一致（但实际测试会偏小不知道为什么）
  - `高质量重编码`：libx264 CRF 18，接近无损，但慢
  - `指定码率`：libx264 固定码率（如 4M / 8M / 2000k）
- **多种输出格式**：mp4 / ts / mkv
- **ts文件手动排序**：上移、下移、删除选中、清空列表
- **ffmpeg 路径可配置**：支持浏览选择、自动检测、一键测试
- **实时日志**：ffmpeg 输出实时滚动，错误行标红
- **查看命令**：合并前可以先看一眼实际执行的 ffmpeg 命令(~~ffmpeg:你盯着我干嘛~~)

---

## 环境要求

- [ffmpeg](https://ffmpeg.org/download.html)（必须，且需要 `ffmpeg.exe` 和 `ffprobe.exe`）
- 可以把ffmpeg加到环境里，但是程序识别好像有问题（~~绝对不是我不会改~~），但是程序里也提供了手动选择ffmpeg位置的方案

---

## 运行

直接运行exe文件即可

---

## 其他

有 bug 或者想要的功能，提 Issue，我尽量改（虽然我也是让 AI 搓）

---

## Introduction

A small tool for merging locally downloaded **TS segments** or **m3u8 playlists** into a complete video.

Because I found that the downloaded videos were all `.ts` chunks, and I was too lazy to type ffmpeg commands, I had an AI write the program (OMG, with the help of an AI assistant).

---

## Features

- **Merge TS segments**: Manually add files, add an entire directory, automatically natural-sort by the numbers in filenames
- **Import from m3u8**: Select a local `.m3u8` file directly, automatically parse all segment paths and fill them into the list
- **Three encoding modes**:
  - `Direct concatenation`: `-c copy`, no re-encoding, fastest, bitrate same as the original files (but in actual tests it comes out smaller for some reason)
  - `High-quality re-encoding`: libx264 CRF 18, nearly lossless, but slow
  - `Specified bitrate`: libx264 fixed bitrate (e.g. 4M / 8M / 2000k)
- **Multiple output formats**: mp4 / ts / mkv
- **Manual TS file sorting**: Move up, move down, delete selected, clear list
- **Configurable ffmpeg path**: Supports browse selection, auto-detection, one-click test
- **Real-time logs**: ffmpeg output scrolls in real time, error lines are marked in red
- **View command**: Before merging, you can take a look at the ffmpeg command that will actually be executed (~~ffmpeg: why are you staring at me~~)

---

## Requirements

- [ffmpeg](https://ffmpeg.org/download.html) (required, and requires `ffmpeg.exe` and `ffprobe.exe`)
- You can add ffmpeg to the environment, but the program seems to have trouble recognizing it (~~definitely not because I don't know how to fix it~~), but the program also provides an option to manually select the ffmpeg location

---

## Run

Just run the exe file directly.

## Finally, most of the README was also written by Deepseek. Deepseek is godlike.
## README大部分也是ds老师写的，ds老师超神了
<img width="850" height="936" alt="61a66efde3f31fbf10ac5bc59c56c729" src="https://github.com/user-attachments/assets/114ee98c-bd40-4459-b486-c83be4b1c8d6" />

