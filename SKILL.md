---
name: text-to-speech
description: 通过统一网关合成语音、克隆音色、转写音频，可选 MiniMax、Gemini、OpenAI、ElevenLabs、Grok 的模型。 平台：New.bi（https://api.new.bi），专业、稳定、可靠的大模型聚合中转平台。
metadata:
  version: 1.1.0
---

**中文** · [English](SKILL.en.md)

# 语音合成

三条通道，按模型名自动选：

| 通道 | 模型 | 路径 |
| --- | --- | --- |
| speech | `speech-*`（MiniMax）、`tts-1`、`gpt-4o-mini-tts` | `POST /v1/audio/speech`，直接返回音频字节 |
| task | `elevenlabs/*`、`*-text-to-dialogue` | `POST /v1/tasks`，再查 `GET /v1/tasks/{id}` |
| chat | Gemini `*-tts`、`xai/grok-tts`、`gpt-4o-*-audio-preview` | `POST /v1/chat/completions`，`voice` 放顶层 |

音色克隆返回的是 voice id，不是音频。

## 什么时候用

- 用指定音色把文字读出来。
- 从厂商预设里挑一个音色。
- 用 5 到 30 秒干净的单人录音，生成一个能重复用的音色。
- 把音频转成文字。

## 什么时候不用

- 音乐或歌曲，这里不做。
- 实时语音对话，这里不做。

## 准备

密钥按顺序查找，先用找到的：

1. 项目根目录 `config.json` 里的 `api_key`
2. `AIGW_TTS_API_KEY`
3. `AIGW_API_KEY`
4. `OPENAI_API_KEY`

```bash
python3 scripts/gateway.py login --key sk-xxx
python3 scripts/gateway.py models
```

## 能用哪些模型

| 系列 | 型号 | 通道 |
| --- | --- | --- |
| MiniMax | Speech 2.8 HD、Speech 2.6 HD | speech |
| OpenAI | gpt-4o-mini-tts | speech |
| ElevenLabs | Text to Speech、Text to Dialogue | task |
| Google Gemini | Gemini 3.8 Flash TTS、Gemini 3.8 Flash Lite TTS、Gemini 2.5 Flash TTS | chat |
| xAI | Grok TTS | chat |

用 `models` 查可用模型和价格。单次指定用 `--model <id>`；固定默认用 `model set <id>`，它写进项目根目录 `config.json` 的 `model` 字段，也可以直接改这个文件。 `models` 里 `price` 大于 0 是按次固定价，`price` 为 0 且 `ratio` 大于 0 是按倍率计费，两者不能直接比大小。

## 固定默认模型

```bash
python3 scripts/gateway.py model set speech-2.8-hd
python3 scripts/gateway.py model show
```

设置后合成和转写不带 `--model` 都用它，`--model` 仍可临时覆盖。值写在项目根目录 `config.json` 的 `model` 字段，手改这个文件也一样。

## 合成

```bash
# 同步语音，MiniMax
python3 scripts/gateway.py tts speak --input "The weather is lovely today, let's walk in the park." \
  --model speech-2.8-hd --voice male-qn-qingse --format mp3 --speed 1.1

# chat 通道，Gemini / Grok
python3 scripts/gateway.py tts speak --input "Hello from the gateway" \
  --model gemini-3.8-flash-tts --voice Kore

# task 通道，ElevenLabs；不给 --voice 时用默认音色
python3 scripts/gateway.py tts speak --input "Hello from the gateway" \
  --model elevenlabs/text-to-speech --voice EXAVITQu4vr4xnSDxMaL
```

文本里不要描述音色。Gemini 那类模型会把描述原样念出来。

## 音色克隆

```bash
python3 scripts/gateway.py tts clone --name my-voice --audio-url https://example.com/sample.mp3
python3 scripts/gateway.py tts clone-status <task_id>
```

`--audio-url` 和 `--video-id` 二选一。克隆按次计费，产出一个 voice id。

task id 必须放在路径里，用查询参数会打到 Web 端返回 HTML。

## 转写

两条路，看模型怎么服务，别只看名字。

```bash
# 本地文件，走同步接口
python3 scripts/gateway.py transcribe --file ./audio.mp3 --model <同步模型>

# 公网地址，走任务接口
python3 scripts/gateway.py transcribe --url https://cdn.example.com/audio.mp3 --model <任务模型> --language en
```

拿任务型模型去打 `/v1/audio/transcriptions` 会返回 404。看到 404 就是模型只走任务形式，需要公网地址。任务转写按音频小时计费，不足一小时按一小时算。

## 参数

### 合成

| 参数 | 必填 | 说明 |
| --- | --- | --- |
| `--input` | 是 | 要读的文字。 |
| `--model` | 否 | 语音模型。默认用配置文件里的；没配置又有多模型时必填。 |
| `--voice` | 否 | 音色 id。MiniMax 默认 `male-qn-qingse`，ElevenLabs 默认 `EXAVITQu4vr4xnSDxMaL`（Sarah）。 |
| `--format` | 否 | `mp3`（默认）、`wav`、`opus`、`aac`、`flac`、`pcm`。只对 speech 通道有效。 |
| `--speed` | 否 | 只对 speech 通道有效。MiniMax 支持 0.5 到 2，其他 0.25 到 4。 |
| `--instructions` | 否 | 只对 speech 通道有效。自然语言风格提示，OpenAI TTS 会照做，其他厂商忽略。 |
| `--group` | 否 | 指定计费分组。 |

音色名：MiniMax 有 `male-qn-qingse`、`female-shaonv`、`male-qn-jingying` 等二十多个；Gemini 用 `Kore`、`Puck`、`Charon`、`Aoede`；OpenAI 用 `alloy`、`echo`、`fable`、`onyx`、`nova`、`shimmer`。传错名字返回 400。

`grok-voice-latest` 不接受 `voice` 字段，这个模型不要传。

### 克隆

| 参数 | 必填 | 说明 |
| --- | --- | --- |
| `--name` | 是 | 音色名称。 |
| `--audio-url` | 二选一 | 公网地址，5 到 30 秒干净单人音频或视频。 |
| `--video-id` | 二选一 | 账号里已有的视频 id。 |

三条通道的接口与返回形态见 [references/transports.md](references/transports.md)。

## 计费

MiniMax 语音按每 1000 个计费字符算：一个汉字算 2，一个拉丁字符算 1。

## 错误

| 状态 | 原因 | 怎么办 |
| --- | --- | --- |
| 400 | 音色不支持或输入不合法 | 换厂商列表里的音色。 |
| 401 | 密钥缺失或无效 | 重新 `login`，跑 `doctor`。 |
| 402 | 余额不足 | 充值。 |
| 429 | 并发到顶 | 等一会重试。 |
| 503 | 这个分组用不了该模型 | 换模型或换密钥。 |
