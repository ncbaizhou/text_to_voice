---
name: text-to-speech
description: 把文本转成语音文件（mp3），使用微软神经语音，音色接近真人播音。支持中英文、多发音人、语速与音高调节、长文本自动分段。当用户要求文字转语音、语音合成、生成配音、朗读文稿、做播客或视频旁白、生成有声读物、把文章读出来、TTS 时使用。不适用于：语音识别/转写（音频转文字）、音乐生成、音色克隆。
---

# 文本转语音（Text to Speech）

把文本合成语音文件。默认使用微软神经语音（音色接近真人），默认发音人为**云健·低沉浑厚男声**。

## 关键前提

1. **必须联网**。神经语音由远端服务合成，本机无法离线完成。离线降级方案见文末。
2. **文本会离开本机**。合成前必须告知用户「文本内容将发送到语音服务」。如果文本可能含敏感信息（个人隐私、公司机密、未公开稿件），先取得用户确认再执行。
3. **依赖 edge-tts**。缺失时先安装：`python -m pip install --user edge-tts`

## 执行步骤

### 1. 把文本写入 UTF-8 文件

**不要用命令行参数直接传中文文本**——Windows PowerShell 5.1 下会出现编码损坏（曾实测中文被解成乱码导致脚本报语法错误）。一律先写文件：

```
Write 工具 -> <工作目录>/_tts_input.txt   （UTF-8，内容即待合成文本）
```

### 2. 调用合成脚本

```powershell
python "<skill_dir>/scripts/synthesize.py" `
  --text-file "<工作目录>/_tts_input.txt" `
  --output "<输出目录>/<中文文件名>.mp3"
```

常用参数：

| 参数 | 默认值 | 说明 |
|---|---|---|
| `--voice` | `zh-CN-YunjianNeural` | 发音人 ID，清单见 `references/voices.md` |
| `--rate` | `-6%` | 语速偏移 |
| `--pitch` | `-10Hz` | 音高偏移 |

**负值参数必须用等号写法**，否则 argparse 会把 `-6%` 当成选项名而报错：

```powershell
--rate="-12%" --pitch="-10Hz"     # 正确
--rate "-12%"                     # 错误：expected one argument
```

### 3. 校验输出

脚本已在内部逐帧解析 MP3 并校验时长，成功时 stdout 输出文件路径，stderr 输出：

```
RESULT: <path> | <字节数> 字节 | 时长 <秒>s
```

**必须确认时长与文本量匹配**（中文约 4~5 字/秒）。时长异常偏小说明合成被截断。退出码含义：

| 退出码 | 含义 | 处理 |
|---|---|---|
| 0 | 成功 | 交付文件 |
| 2 | 输入文件缺失或文本为空 | 检查路径与文本 |
| 3 | 缺少 edge-tts 依赖 | 执行安装命令 |
| 4 | 合成失败（发音人无效、网络中断） | 核对 Voice ID；确认网络后重试 |
| 5 | 输出校验未通过 | 视为失败，不要交付该文件 |

### 4. 交付

调用 SendUserFile 交付生成的 mp3。文件名用中文、体现内容主题。

## 选型速查

用户没指定音色时的默认决策：

| 用户需求 | 推荐 | 参数 |
|---|---|---|
| 浑厚男声 / 主持 / 有力量感 | `zh-CN-YunjianNeural` | `--rate="-6%" --pitch="-10Hz"` |
| 新闻播报 / 正式稿件 | `zh-CN-YunyangNeural` | `--rate="+0%" --pitch="+0Hz"` |
| 年轻活泼男声 | `zh-CN-YunxiNeural` | 默认即可 |
| 温暖女声 / 通用 | `zh-CN-XiaoxiaoNeural` | `--rate="+0%" --pitch="+0Hz"` |
| 有声书旁白 | `zh-CN-YunxiNeural` 或 `XiaoxiaoNeural` | `--rate="-4%"` |

完整清单与参数经验值见 `references/voices.md`。不确定某语种有哪些发音人时，现查：

```powershell
python -m edge_tts --list-voices | Select-String "zh-CN"
```

不要凭记忆编造 Voice ID——实测传错会直接以退出码 4 失败。

## 重要经验（避免重复踩坑）

- **不要给神经语音叠加 EQ 补低频**。神经语音底子已经够厚，再加低频增强会发闷。这条与老式 SAPI 引擎相反（那种引擎音色单薄才需要补）。
- **pitch 降幅不要超过 `-15Hz`**，超过后出现失真和机械感。
- **rate 不要超过 `+20%`**，中文咬字会含糊。
- **主持感主要靠停顿节奏，不是靠音色**。中文用 `。` `，` 自然断句；需要更长停顿就另起一行。edge-tts **不支持 SSML `<break>` 标签**，不要尝试插入，会被当普通文本处理。
- **长文本会自动分段**（单段上限 500 字符，按句末标点优先切分），分段音频直接拼接，实测 720 字切 2 段合成 160 秒无截断、拼接处无异常。无需自己切分。
- **输出目录不存在会自动创建**，不必预先建目录。

## 离线降级方案

网络不可用且用户接受较差音质时，可退回本机 Windows SAPI 引擎。中文男声只有 `Microsoft Kangkang`（康康），**音色机械感强**，必须明确告知用户这是降级效果。

康康不在常规接口里，需要直接读 OneCore 语音库才能调用：

```powershell
$cat = New-Object -ComObject SAPI.SpObjectTokenCategory
$cat.SetId("HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Speech_OneCore\Voices", $true)
$token = $cat.EnumerateTokens().Item(4)   # Kangkang，索引实测为 4
$v = New-Object -ComObject SAPI.SpVoice
$v.Voice = $token
```

三个已验证的坑：

- `Speak` 的 XML 标志值是 **8**（`SVSFIsXML`），传 16 是 `SVSFIsNotXML`，正好相反，会导致音高标签不生效。
- `<pitch>` 标签必须**包裹**文本，自闭合写法无效：`<pitch middle='-6'>文本</pitch>`
- 必须用**同步**模式（flag `0` 或 `8`）。异步模式下立即关闭流会得到只有 46 字节的空文件。
- 不要强行覆盖音频格式（如指定 44kHz），实测会退化成 8kHz ADPCM，音质明显劣化。用引擎默认格式。

康康的音高调节实测有效但幅度有限：基频仅能从 151Hz 降到 141Hz。
