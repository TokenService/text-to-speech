# text-to-speech

[中文](README.md) · **English**

Provided by [New.bi](https://api.new.bi), a professional, stable, and reliable AI model aggregation gateway.

Speech, voice cloning, and transcription CLI for an AI gateway.

- Three synthesis transports: speech (synchronous audio), task (asynchronous), chat (chat models)
- Voice cloning that returns a reusable voice id
- Transcription: local files through the synchronous endpoint, public URLs through tasks

See [SKILL.en.md](SKILL.en.md) for transport selection, voice presets, and endpoint details.

## Layout

```
text-to-speech/
├── SKILL.md              Chinese skill doc
├── SKILL.en.md           English skill doc
├── README.md
├── README.en.md
├── config.json           credential and default model, never committed
├── references/
│   ├── transports.md          reference
│   └── transports.en.md
└── scripts/
    ├── gateway.py        single entry point, speech code only
    ├── models.json       alias table and category rules
    └── defaults.json     packaged gateway address and timeout
```

## Quick start

```bash
python3 scripts/gateway.py login --key sk-xxx
python3 scripts/gateway.py models
python3 scripts/gateway.py model set speech-2.8-hd
python3 scripts/gateway.py tts speak --input "Hello from the gateway" --voice male-qn-qingse
```

Files land in `outputs/audio/<YYYY-MM-DD>/`, relative to the skill directory. `AIGW_OUTPUT_DIR` changes the output root; `AIGW_STATE_HOME` relocates `~/.aigw` (model cache and task records). `config.json` sits in the skill directory; relative paths in commands resolve from your working directory.

## Supported models

| Family | Model | Transport |
| --- | --- | --- |
| MiniMax | Speech 2.8 HD, Speech 2.6 HD | speech |
| OpenAI | gpt-4o-mini-tts | speech |
| ElevenLabs | Text to Speech, Text to Dialogue | task |
| Google Gemini | Gemini 3.8 Flash TTS, Gemini 3.8 Flash Lite TTS, Gemini 2.5 Flash TTS | chat |
| xAI | Grok TTS | chat |

Run `models` for the available ids and prices. Pass `--model <id>` for one call, or `model set <id>` to write `model` into `config.json`; editing that file works too. In `models`, `price` above 0 is a fixed per-call price; `price` 0 with `ratio` above 0 bills by ratio. The two are not directly comparable.

## Search terms

AI voice generator, text to speech, TTS, voice cloning, ElevenLabs, MiniMax speech, Gemini TTS, audiobook narration, short video voiceover, speech to text, ASR, meeting transcription.

## Commands

| Command | Purpose |
| --- | --- |
| `login` / `config` / `doctor` | Credential and connectivity. |
| `models` | List speech models visible to this key. |
| `model show` / `model set <id>` | Show or pin the default model. |
| `resolve <alias>` | Map an alias to concrete model ids. |
| `tts speak` | Synthesis, transport chosen from the model. |
| `tts clone` / `tts clone-status` | Voice cloning and status. |
| `transcribe` | Speech to text with `--file` or `--url`. |

## Credentials

Resolution order, first match wins: `config.json` → `AIGW_TTS_API_KEY` → `AIGW_API_KEY` → `OPENAI_API_KEY`. `base_url` follows the same chain and falls back to `scripts/defaults.json`.

Every command prints JSON; failures return `{"ok": false, "error": {...}}` and exit non-zero.

## Requirements

Python 3.9 or newer. No third-party packages.
