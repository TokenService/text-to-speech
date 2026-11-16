# text-to-speech

**中文** · [English](README.en.md)

由 [New.bi](https://api.new.bi) 提供，专业、稳定、可靠的大模型聚合中转平台。

## 交给 AI 安装

把下面这句直接发给 agent，它会完成下载、解压、鉴权和执行：

```text
安装并使用 New.bi 语音技能：下载 https://pub-817cae131e2b4e0a8ce0a9f8bac75462.r2.dev/down/text-to-speech.zip，解压后运行 python3 scripts/gateway.py login --key <你的密钥>，再运行 doctor 确认，然后用 tts speak 合成语音、tts clone 克隆音色、transcribe 转写音频。
```

语音合成、音色克隆和转写的命令行工具，也可以直接当 agent 技能用。

合成有三条通道，按模型名自动选：直接返回音频、异步任务、对话模型。克隆返回 voice id，不返回音频。

## 开始

```bash
python3 scripts/gateway.py login --key sk-xxx
python3 scripts/gateway.py models
python3 scripts/gateway.py model set speech-2.8-hd
python3 scripts/gateway.py tts speak --input "Hello from the gateway" --voice male-qn-qingse
```

音频存在 `outputs/audio/<日期>/`，路径相对技能目录。`AIGW_OUTPUT_DIR` 可以改输出位置，`AIGW_STATE_HOME` 可以改 `~/.aigw`（模型缓存和任务记录）。`config.json` 在技能目录里，命令里的相对路径按当前工作目录算。

## 支持的模型

| 系列 | 型号 | 通道 |
| --- | --- | --- |
| MiniMax | Speech 2.8 HD、Speech 2.6 HD | speech |
| OpenAI | gpt-4o-mini-tts | speech |
| ElevenLabs | Text to Speech、Text to Dialogue | task |
| Google Gemini | Gemini 3.8 Flash TTS、Gemini 3.8 Flash Lite TTS、Gemini 2.5 Flash TTS | chat |
| xAI | Grok TTS | chat |

用 `models` 查可用模型和价格。单次指定用 `--model <id>`；固定默认用 `model set <id>`，它写进项目根目录 `config.json` 的 `model` 字段，也可以直接改这个文件。 `models` 里 `price` 大于 0 是按次固定价，`price` 为 0 且 `ratio` 大于 0 是按倍率计费，两者不能直接比大小。

## 常见搜索词

AI 配音、文字转语音、TTS、音色克隆、声音克隆、ElevenLabs、MiniMax 语音、Gemini TTS、有声书配音、短视频配音、语音转文字、ASR、会议转写。

## 命令

| 命令 | 做什么 |
| --- | --- |
| `login` / `config` / `doctor` | 密钥、配置、连通性。 |
| `models` | 列出这个密钥能看到的语音模型。 |
| `model show` / `model set <id>` | 看或设置默认模型。 |
| `resolve <别名>` | 别名换成具体模型 id。 |
| `tts speak` | 合成语音。 |
| `tts clone` / `tts clone-status` | 克隆音色，查克隆进度。 |
| `transcribe` | 转写，`--file` 传本地文件，`--url` 传公网地址。 |

输出都是 JSON。出错时输出 `{"ok": false, "error": {...}}`，退出码非零。

## 密钥

按顺序找，先用找到的：`config.json` → `AIGW_TTS_API_KEY` → `AIGW_API_KEY` → `OPENAI_API_KEY`。网关地址同样逐级回退，最后用 `scripts/defaults.json` 里的。

## 文件

```
text-to-speech/
├── SKILL.md              中文说明
├── SKILL.en.md           英文说明
├── config.json           密钥和默认模型，不进 git
├── references/
│   ├── transports.md          通道与接口
│   └── transports.en.md
└── scripts/
    ├── gateway.py        入口
    ├── models.json       别名和分类规则
    └── defaults.json     默认网关地址和超时
```

音色列表、转写两条路的区别见 [SKILL.md](SKILL.md)。

需要 Python 3.9 及以上。
