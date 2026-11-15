# 通道与接口

## 接口

合成返回二进制：

```
POST /v1/audio/speech
Content-Type: audio/mpeg
<二进制>
```

命令行把字节写进 `outputs/audio/<日期>/`。如果返回的是 JSON，会从里面找音频地址再下载。

chat 形态：

```
POST /v1/chat/completions
{ "model": "gemini-3.8-flash-tts", "voice": "Kore", "messages": [{ "role": "user", "content": "..." }] }
```

音频可能在 `data[]`、`message.content` 的 Markdown 链接，或 `message.audio` 的 base64，都能处理。

音色克隆：

```
POST /kling/v1/general/custom-voices
{ "code": 0, "message": "SUCCEED", "data": { "task_id": "task_xxxx", "task_status": "submitted" } }

GET /kling/v1/general/custom-voices/{task_id}
{ "code": 0, "message": "SUCCEED", "data": { "task_id": "task_xxxx", "task_status": "succeed", "task_result": { "voices": [{ "voice_id": "voice_xxxx", "voice_name": "my-voice", "trial_url": "https://..." }] } } }
```

`task_status` 是 `submitted`、`processing`、`succeed` 或 `failed`。

## 任务通道的形态

ElevenLabs 和对话模型不接受 `/v1/audio/speech`，走任务，模型名匹配时自动切换：

```
POST /v1/tasks
{ "model": "elevenlabs/text-to-speech", "input": { "text": "...", "voice": "EXAVITQu4vr4xnSDxMaL" } }

GET /v1/tasks/{task_id}
{ "code": 200, "success": true, "data": { "task_id": "task_...", "status": "completed", "output": { "audio_url": "https://..." } } }
```

多人对话的输入不一样：

```
{ "model": "elevenlabs/text-to-dialogue",
  "input": { "dialogue": [{ "text": "Hello", "voice": "EXAVITQu4vr4xnSDxMaL" }] } }
```

`status` 是 `processing`、`completed` 或 `failed`。ElevenLabs 必须给 `voice`，不给时命令行用 `EXAVITQu4vr4xnSDxMaL`（Sarah），免得上游报 422。其他预设还有 `JBFqnCBsd6RMkjVDRZzb`（George）、`pNInz6obpgDQGcFmaJgB`（Adam）。

转写的任务形态：

```
POST /v1/tasks
{ "model": "<model>", "input": { "audio_url": "https://...", "language_code": "en" } }

GET /v1/tasks/{task_id}
{ "code": 200, "success": true, "data": { "task_id": "task_...", "status": "completed", "output": { "text": "..." } } }
```
