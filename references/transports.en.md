# Transports and endpoints

## Endpoints and response shapes

```
POST /v1/audio/speech
Content-Type: audio/mpeg
<binary>
```

The CLI writes the bytes to `outputs/audio/<YYYY-MM-DD>/`. If a gateway returns JSON instead, the CLI collects audio URLs from the payload and downloads them.

Chat-based TTS:

```
POST /v1/chat/completions
{ "model": "gemini-3.8-flash-tts", "voice": "Kore", "messages": [{ "role": "user", "content": "..." }] }
```

Audio appears in `data[]`, as a Markdown link in `message.content`, or as base64 in `message.audio`. The CLI wraps this form and writes the result to `outputs/audio/`. Never describe the voice in the content: Gemini reads it verbatim.

Voice clone:

```
POST /kling/v1/general/custom-voices
{ "code": 0, "message": "SUCCEED", "data": { "task_id": "task_xxxx", "task_status": "submitted" } }

GET /kling/v1/general/custom-voices/{task_id}
{ "code": 0, "message": "SUCCEED", "data": { "task_id": "task_xxxx", "task_status": "succeed", "task_result": { "voices": [{ "voice_id": "voice_xxxx", "voice_name": "my-voice", "trial_url": "https://..." }] } } }
```

`task_status` is `submitted`, `processing`, `succeed`, or `failed`. Pass the task id as a path segment; a query parameter hits the web app and returns HTML.

Cloning is billed per call and yields a `voice_id`. It does not synthesize audio.

## Task transport models

ElevenLabs and dialogue models do not accept `/v1/audio/speech`. They run as asynchronous tasks, and the CLI switches automatically when the model matches:

```
POST /v1/tasks
{ "model": "elevenlabs/text-to-speech", "input": { "text": "...", "voice": "EXAVITQu4vr4xnSDxMaL" } }

GET /v1/tasks/{task_id}
{ "code": 200, "success": true, "data": { "task_id": "task_...", "status": "completed", "output": { "audio_url": "https://..." } } }
```

Multi-speaker dialogue uses a different input shape:

```
{ "model": "elevenlabs/text-to-dialogue",
  "input": { "dialogue": [{ "text": "Hello", "voice": "EXAVITQu4vr4xnSDxMaL" }] } }
```

`status` is `processing`, `completed`, or `failed`. `voice` is mandatory for ElevenLabs; the CLI falls back to `EXAVITQu4vr4xnSDxMaL` (Sarah) instead of letting the upstream return 422 `voice: Field required`. Preset voice ids include `EXAVITQu4vr4xnSDxMaL` (Sarah), `JBFqnCBsd6RMkjVDRZzb` (George), and `pNInz6obpgDQGcFmaJgB` (Adam).
