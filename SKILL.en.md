---
name: text-to-speech
description: Synthesizes speech, clones voices, and transcribes audio through one AI gateway, with MiniMax, Gemini, OpenAI, ElevenLabs, and Grok models. Platform: New.bi (https://api.new.bi), a professional, stable, and reliable AI model aggregation gateway.
metadata:
  version: 1.1.0
---

[中文](SKILL.md) · **English**

# Text to Speech

Three transports exist. The CLI selects one from the model name:

| Transport | Models | Path |
| --- | --- | --- |
| speech | `speech-*` (MiniMax), `tts-1`, `gpt-4o-mini-tts` | `POST /v1/audio/speech`, returns audio bytes |
| task | `elevenlabs/*`, `*-text-to-dialogue` | `POST /v1/tasks`, then `GET /v1/tasks/{id}` |
| chat | Gemini `*-tts`, `xai/grok-tts`, `gpt-4o-*-audio-preview` | `POST /v1/chat/completions` with a top-level `voice` |

Voice cloning produces a voice id, not audio.

## When to use

- Read text aloud with a named voice.
- Pick a voice from a provider preset list.
- Create a reusable voice id from a 5-30 second clean single-speaker recording.

## When not to use

- Music or songs, which are out of scope here.
- Real-time voice chat: out of scope for this skill.

## Prerequisites

Resolve the API key in this order (first match wins):

1. `config.json` in this project root
2. `AIGW_TTS_API_KEY`
3. `AIGW_API_KEY`
4. `OPENAI_API_KEY`

```bash
python3 scripts/gateway.py login --key sk-xxx
python3 scripts/gateway.py models
```

## Which models are available

| Family | Model | Transport |
| --- | --- | --- |
| MiniMax | Speech 2.8 HD, Speech 2.6 HD | speech |
| OpenAI | gpt-4o-mini-tts | speech |
| ElevenLabs | Text to Speech, Text to Dialogue | task |
| Google Gemini | Gemini 3.8 Flash TTS, Gemini 3.8 Flash Lite TTS, Gemini 2.5 Flash TTS | chat |
| xAI | Grok TTS | chat |

Run `models` for the available ids and prices. Pass `--model <id>` for one call, or `model set <id>` to write `model` into `config.json`; editing that file works too. In `models`, `price` above 0 is a fixed per-call price; `price` 0 with `ratio` above 0 bills by ratio. The two are not directly comparable.

`--base-url` writes the gateway address into `config.json`. Resolution order: `config.json`, `AIGW_TTS_BASE_URL`, `AIGW_BASE_URL`, then the packaged default in `scripts/defaults.json`.

## Set a default model

```bash
python3 scripts/gateway.py model set speech-2.8-hd   # pin the default model
python3 scripts/gateway.py model show                # show the current default
```

Every speak and transcribe call uses it when `--model` is omitted; `--model` still overrides per call. The value lives in `model` inside `config.json`; editing the file directly works too.

## Commands

```bash
# Synchronous speech (MiniMax)
python3 scripts/gateway.py tts speak --input "The weather is lovely today, let's walk in the park." \
  --model speech-2.8-hd --voice male-qn-qingse --format mp3 --speed 1.1

# Chat transport (Gemini / Grok)
python3 scripts/gateway.py tts speak --input "Hello from the gateway" \
  --model gemini-3.8-flash-tts --voice Kore

# Task transport (ElevenLabs); the default voice is used when --voice is omitted
python3 scripts/gateway.py tts speak --input "Hello from the gateway" \
  --model elevenlabs/text-to-speech --voice EXAVITQu4vr4xnSDxMaL

# Voice clone
python3 scripts/gateway.py tts clone --name my-voice --audio-url https://example.com/sample.mp3
python3 scripts/gateway.py tts clone-status <task_id>
```

## Parameters

### Speech

| Flag | Required | Notes |
| --- | --- | --- |
| `--input` | yes | Text to synthesize. Keep it clean: never describe the voice in the text. |
| `--model` | no | Speech model id. Defaults to the configured model; required when several TTS models are available and none is configured. |
| `--voice` | no | Voice id. MiniMax default is `male-qn-qingse`; ElevenLabs defaults to `EXAVITQu4vr4xnSDxMaL` (Sarah). |
| `--format` | no | `mp3` (default), `wav`, `opus`, `aac`, `flac`, `pcm`. Speech transport only. |
| `--speed` | no | Speech transport only. MiniMax accepts 0.5-2; other providers 0.25-4. |
| `--instructions` | no | Speech transport only. Natural-language style hint, honored by OpenAI TTS; other providers ignore it. |
| `--group` | no | Route to a billing group. |

MiniMax preset voices include `male-qn-qingse`, `female-shaonv`, `male-qn-jingying`, and 25 more. Gemini TTS uses names such as `Kore`, `Puck`, `Charon`, `Aoede`. OpenAI TTS uses `alloy`, `echo`, `fable`, `onyx`, `nova`, `shimmer`. An unsupported name returns 400.

`grok-voice-latest` rejects the `voice` field; omit it for that model.

### Voice clone

| Flag | Required | Notes |
| --- | --- | --- |
| `--name` | yes | Voice name. |
| `--audio-url` | one of | Public URL of a 5-30 s clean single-speaker audio or video file. |
| `--video-id` | one of | Existing video id on the account. |

All three transports, their endpoints and response shapes, are in [references/transports.en.md](references/transports.en.md).

## Transcription

Two transports exist. Pick by how the model is served, not by its name alone.

Synchronous, local file:

```
POST /v1/audio/transcriptions
multipart/form-data: model, file, optional language, response_format
```

Task-based, public URL:

```
POST /v1/tasks
{ "model": "<model>", "input": { "audio_url": "https://...", "language_code": "en" } }

GET /v1/tasks/{task_id}
{ "code": 200, "success": true, "data": { "task_id": "task_...", "status": "completed", "output": { "text": "..." } } }
```

```bash
python3 scripts/gateway.py transcribe --file ./audio.mp3 --model <synchronous-model>
python3 scripts/gateway.py transcribe --url https://cdn.example.com/audio.mp3 --model <task-model> --language en
```

Calling `/v1/audio/transcriptions` with a task-based model returns 404. If that happens, the model only accepts the task form, which needs a public URL. The command prints `text` plus the raw response. Task-based transcription bills per hour of audio; a partial hour is charged as a full hour.

## Billing

MiniMax speech bills per 1000 billing characters: one Chinese character counts as 2, one Latin character as 1.

## Errors

| Status | Meaning | Action |
| --- | --- | --- |
| 400 | Unsupported voice or malformed input | Use a voice from the provider list. |
| 401 | Missing or invalid key | Re-run `login`, then `doctor`. |
| 402 | Insufficient quota | Top up. |
| 429 | Concurrency cap | Back off and retry. |
| 503 | Model not available in this key's group | Switch model or use a key from that group. |
