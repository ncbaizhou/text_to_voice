# 中文发音人清单与选型

来源：`python -m edge_tts --list-voices`（2026-09 实测）。
`Style`/`角色定位` 列来自微软官方标注，是选型的主要依据。

## 普通话男声

| Voice ID | 官方定位 | 风格标注 | 适用场景 |
|---|---|---|---|
| `zh-CN-YunjianNeural` | Sports, Novel | Passion | 力量感最强、音色最浑厚。**默认推荐**，体育解说、励志、主持 |
| `zh-CN-YunyangNeural` | News | Professional, Reliable | 新闻播报，专业稳重、字正腔圆。正式稿件首选 |
| `zh-CN-YunxiNeural` | Novel | Lively, Sunshine | 年轻阳光，适合解说、Vlog、有声书旁白 |
| `zh-CN-YunxiaNeural` | Cartoon, Novel | Cute | 童声感，儿童故事、卡通 |

## 普通话女声

| Voice ID | 官方定位 | 风格标注 | 适用场景 |
|---|---|---|---|
| `zh-CN-XiaoxiaoNeural` | News, Novel | Warm | 温暖自然，通用度最高 |
| `zh-CN-XiaoyiNeural` | Cartoon, Novel | Lively | 活泼，动画、轻松内容 |

## 方言

| Voice ID | 方言 | 标注 |
|---|---|---|
| `zh-CN-liaoning-XiaobeiNeural` | 辽宁话 | Humorous |
| `zh-CN-shaanxi-XiaoniNeural` | 陕西话 | Bright |

## 其他中文区

| Voice ID | 区域 | 性别 |
|---|---|---|
| `zh-HK-WanLungNeural` | 粤语（港） | 男 |
| `zh-HK-HiuGaaiNeural` / `zh-HK-HiuMaanNeural` | 粤语（港） | 女 |
| `zh-TW-YunJheNeural` | 台湾 | 男 |
| `zh-TW-HsiaoChenNeural` / `zh-TW-HsiaoYuNeural` | 台湾 | 女 |

英文等外语清单用 `python -m edge_tts --list-voices` 现查，不要凭记忆写 Voice ID。

## 参数调节经验值

`--rate` 与 `--pitch` 都是相对原始音色的偏移，不是绝对值。

| 目标 | rate | pitch |
|---|---|---|
| 浑厚沉稳（默认） | `-6%` | `-10Hz` |
| 更慢更庄重 | `-12%` | `-12Hz` |
| 标准播报 | `+0%` | `+0Hz` |
| 轻快活泼 | `+10%` | `+5Hz` |

实测注意事项：

- **神经语音底子已经够厚，不要再叠加 EQ 补低频**，否则发闷。这一点和老式 SAPI 引擎（如康康）相反。
- pitch 降幅超过约 `-15Hz` 后开始出现失真和机械感，不建议再往下压。
- rate 超过 `+20%` 时中文咬字会含糊。
- 主持感主要靠**停顿节奏**而不是音色：中文句末用 `。` `，` 自然断句，需要更长停顿时另起一行或在句中加逗号。edge-tts 不支持 SSML `<break>` 标签，不要尝试插入。
