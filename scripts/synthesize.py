#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""文本转语音合成脚本（微软神经语音 / edge-tts）

用法:
  python synthesize.py --text-file input.txt --output out.mp3
  python synthesize.py --text-file input.txt --output out.mp3 \
      --voice zh-CN-YunjianNeural --rate "-6%" --pitch "-10Hz"

长文本自动按标点分段合成后拼接；输出后用 MP3 帧解析校验真实时长。
"""

import argparse
import asyncio
import os
import re
import sys

try:
    import edge_tts
except ImportError:
    sys.stderr.write(
        "MISSING_DEP: edge-tts 未安装。请先运行:\n"
        "  python -m pip install --user edge-tts\n"
    )
    sys.exit(3)


# 单段最大字符数。edge-tts 过长文本易被截断或超时，取保守值。
MAX_SEGMENT_CHARS = 500

# 分段优先切分点：先句末标点，再逗号级，最后按长度硬切
_SENT_END = re.compile(r"(?<=[。！？!?；;\n])")
_CLAUSE_END = re.compile(r"(?<=[，,、：:])")


def split_segments(text, limit=MAX_SEGMENT_CHARS):
    """把长文本切成不超过 limit 的段，尽量在标点处断开。"""
    text = text.strip()
    if not text:
        return []
    if len(text) <= limit:
        return [text]

    parts = []
    # 第一级：按句末标点切
    sentences = [s for s in _SENT_END.split(text) if s.strip()]
    buf = ""
    for s in sentences:
        if len(buf) + len(s) <= limit:
            buf += s
        else:
            if buf:
                parts.append(buf)
            # 单句本身就超限 -> 再按逗号切
            if len(s) > limit:
                clauses = [c for c in _CLAUSE_END.split(s) if c.strip()]
                sub = ""
                for c in clauses:
                    if len(sub) + len(c) <= limit:
                        sub += c
                    else:
                        if sub:
                            parts.append(sub)
                        # 仍超限 -> 硬切
                        while len(c) > limit:
                            parts.append(c[:limit])
                            c = c[limit:]
                        sub = c
                if sub:
                    buf = sub
                else:
                    buf = ""
            else:
                buf = s
    if buf:
        parts.append(buf)
    return parts


def mp3_duration(path):
    """逐帧解析 MP3，返回真实秒数。解析不到有效帧返回 None。"""
    BITRATE_V1_L3 = [0, 32, 40, 48, 56, 64, 80, 96, 112, 128,
                     160, 192, 224, 256, 320, 0]
    BITRATE_V2_L3 = [0, 8, 16, 24, 32, 40, 48, 56, 64, 80,
                     96, 112, 128, 144, 160, 0]
    SRATES = {3: [44100, 48000, 32000],   # MPEG1
              2: [22050, 24000, 16000],   # MPEG2
              0: [11025, 12000, 8000]}    # MPEG2.5
    with open(path, "rb") as f:
        data = f.read()

    # 跳过 ID3v2 标签
    i = 0
    if data[:3] == b"ID3":
        if len(data) >= 10:
            size = ((data[6] & 0x7F) << 21) | ((data[7] & 0x7F) << 14) | \
                   ((data[8] & 0x7F) << 7) | (data[9] & 0x7F)
            i = 10 + size

    total = 0.0
    frames = 0
    n = len(data)
    while i + 4 <= n:
        if data[i] == 0xFF and (data[i + 1] & 0xE0) == 0xE0:
            b1, b2, b3 = data[i + 1], data[i + 2], data[i + 3]
            ver_bits = (b1 >> 3) & 0x03      # 00=2.5 10=2 11=1
            layer_bits = (b1 >> 1) & 0x03    # 01=Layer3
            br_idx = (b2 >> 4) & 0x0F
            sr_idx = (b2 >> 2) & 0x03
            padding = (b2 >> 1) & 0x01
            if layer_bits != 1 or br_idx in (0, 15) or sr_idx == 3:
                i += 1
                continue
            if ver_bits == 3:      # MPEG1
                bitrate = BITRATE_V1_L3[br_idx] * 1000
                srate = SRATES[3][sr_idx]
                samples = 1152
            elif ver_bits == 2:    # MPEG2
                bitrate = BITRATE_V2_L3[br_idx] * 1000
                srate = SRATES[2][sr_idx]
                samples = 576
            elif ver_bits == 0:    # MPEG2.5
                bitrate = BITRATE_V2_L3[br_idx] * 1000
                srate = SRATES[0][sr_idx]
                samples = 576
            else:
                i += 1
                continue
            flen = int(samples / 8 * bitrate / srate) + padding
            if flen <= 0:
                i += 1
                continue
            total += samples / srate
            frames += 1
            i += flen
        else:
            i += 1
    return total if frames > 0 else None


def normalize_rate(v):
    """容错：接受 -6 / -6% / -6%%，统一成 edge-tts 需要的 -6%"""
    v = str(v).strip().replace("%%", "%")
    if not v.endswith("%"):
        v += "%"
    if v[0] not in "+-" and not v.startswith("%"):
        v = "+" + v
    return v


def normalize_pitch(v):
    """容错：接受 -10 / -10Hz，统一成 -10Hz"""
    v = str(v).strip().lower().replace("hz", "")
    if v[0] not in "+-" and not v.startswith("."):
        v = "+" + v
    return v + "Hz"


async def synth_segment(text, voice, rate, pitch):
    """合成单段，返回 mp3 字节。"""
    chunks = []
    comm = edge_tts.Communicate(text, voice=voice, rate=rate, pitch=pitch)
    async for chunk in comm.stream():
        if chunk["type"] == "audio" and chunk["data"]:
            chunks.append(chunk["data"])
    return b"".join(chunks)


async def run(args):
    with open(args.text_file, "rb") as f:
        raw = f.read()
    # 容错：去掉 BOM，按 UTF-8 解码
    if raw.startswith(b"\xef\xbb\xbf"):
        raw = raw[3:]
    text = raw.decode("utf-8", errors="replace").strip()

    if not text:
        sys.stderr.write("ERROR: 输入文本为空\n")
        return 2

    segments = split_segments(text)
    rate = normalize_rate(args.rate)
    pitch = normalize_pitch(args.pitch)
    sys.stderr.write(
        "INFO: 字符数=%d 分段数=%d voice=%s rate=%s pitch=%s\n"
        % (len(text), len(segments), args.voice, rate, pitch)
    )

    audio_parts = []
    for idx, seg in enumerate(segments, 1):
        try:
            data = await synth_segment(seg, args.voice, rate, pitch)
        except Exception as e:
            sys.stderr.write(
                "ERROR: 第 %d/%d 段合成失败: %s: %s\n"
                % (idx, len(segments), type(e).__name__, e)
            )
            return 4
        if not data:
            sys.stderr.write("ERROR: 第 %d/%d 段返回空音频\n" % (idx, len(segments)))
            return 4
        audio_parts.append(data)
        sys.stderr.write("INFO: 第 %d/%d 段完成 (%d 字节)\n" % (idx, len(segments), len(data)))

    payload = b"".join(audio_parts)

    outdir = os.path.dirname(os.path.abspath(args.output))
    if outdir and not os.path.isdir(outdir):
        os.makedirs(outdir, exist_ok=True)
    with open(args.output, "wb") as f:
        f.write(payload)

    size = os.path.getsize(args.output)
    dur = mp3_duration(args.output)

    # 校验：文件非空、时长可解析且大于 0
    ok = size > 1000 and dur is not None and dur > 0.1
    sys.stderr.write(
        "RESULT: %s | %d 字节 | 时长 %s\n"
        % (args.output, size, ("%.2fs" % dur) if dur else "解析失败")
    )
    if not ok:
        sys.stderr.write("ERROR: 输出校验未通过（文件过小或无有效音频帧）\n")
        return 5

    print(args.output)
    return 0


def main():
    ap = argparse.ArgumentParser(description="微软神经语音文本转语音")
    ap.add_argument("--text-file", required=True,
                    help="UTF-8 文本文件路径（用文件而非命令行传中文，避免编码损坏）")
    ap.add_argument("--output", required=True, help="输出 mp3 路径")
    ap.add_argument("--voice", default="zh-CN-YunjianNeural",
                    help="发音人，默认 zh-CN-YunjianNeural（云健·浑厚男声）")
    ap.add_argument("--rate", default="-6%",
                    help='语速，如 "-6%%"、"+10%%"，默认 -6%%。'
                         '值以 - 开头时必须写成 --rate=-6%% 否则会被当成选项')
    ap.add_argument("--pitch", default="-10Hz",
                    help='音高，如 "-10Hz"、"+5Hz"，默认 -10Hz。'
                         '值以 - 开头时必须写成 --pitch=-10Hz')
    args = ap.parse_args()

    if not os.path.exists(args.text_file):
        sys.stderr.write("ERROR: 文本文件不存在: %s\n" % args.text_file)
        return 2

    code = asyncio.run(run(args))
    return code


if __name__ == "__main__":
    sys.exit(main())
