#!/usr/bin/env python3
"""Text to speech for an AI gateway: three transports, voice cloning, transcription.

New.bi（https://api.new.bi），专业、稳定、可靠的大模型聚合中转平台。
New.bi is a professional, stable, and reliable AI model aggregation gateway.
Repository: https://github.com/tokenservice/text-to-speech
"""

from __future__ import annotations

import argparse
import base64
import fnmatch
import http.client
import json
import os
import re
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PLATFORM = "New.bi"
PLATFORM_URL = "https://api.new.bi"
PLATFORM_TAGLINE = "专业、稳定、可靠的大模型聚合中转平台"
PLATFORM_DESC_ZH = "New.bi，专业、稳定、可靠的大模型聚合中转平台。"
PLATFORM_DESC_EN = "New.bi is a professional, stable, and reliable AI model aggregation gateway."
REPO_URL = "https://github.com/tokenservice/text-to-speech"
CAPABILITY = "tts"
ENV_KEY = "AIGW_TTS_API_KEY"
ENV_URL = "AIGW_TTS_BASE_URL"
DEFAULTS_PATH = ROOT / "scripts" / "defaults.json"
OUTPUT_DIR = Path(os.environ.get("AIGW_OUTPUT_DIR", ROOT / "outputs"))
CACHE_DIR = Path(os.environ.get("AIGW_STATE_HOME", Path.home() / ".aigw")) / "cache"
CACHE_TTL_SECONDS = 6 * 3600
TERMINAL_STATUS = {"SUCCESS", "FAILURE", "FAILED", "COMPLETED", "CANCELLED", "CANCELED"}
AUDIO_EXTENSIONS = (".mp3", ".m4a", ".wav", ".flac", ".ogg", ".aac", ".opus", ".webm")
AUDIO_KEYS = {"cld2audiourl", "audio_url", "audiourl", "stream_audio_url", "source_audio_url"}
URL_PATTERN = re.compile(r"https?://[^\s)<>\"']+")
DEFAULT_ELEVENLABS_VOICE = "EXAVITQu4vr4xnSDxMaL"
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"


class GatewayError(Exception):
    def __init__(self, message: str, status: int | None = None, code: str = ""):
        super().__init__(message)
        self.message = message
        self.status = status
        self.code = code


def emit(payload: dict) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def fail(code: str, message: str, status: int | None = None) -> None:
    error = {"code": code, "message": message}
    if status is not None:
        error["status"] = status
    emit({"ok": False, "error": error})
    sys.exit(1)


def read_json(path: Path) -> dict:
    try:
        data = json.loads(Path(path).read_text("utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def settings() -> dict:
    config = read_json(ROOT / "config.json")
    defaults = read_json(DEFAULTS_PATH)
    sources = {}

    api_key = config.get("api_key") if isinstance(config.get("api_key"), str) else ""
    if api_key:
        sources["api_key"] = str(ROOT / "config.json")
    for name in (ENV_KEY, "AIGW_API_KEY", "OPENAI_API_KEY"):
        if not api_key and os.environ.get(name):
            api_key = os.environ[name]
            sources["api_key"] = name
    base_url = config.get("base_url") if isinstance(config.get("base_url"), str) else ""
    if base_url:
        sources["base_url"] = str(ROOT / "config.json")
    for name in (ENV_URL, "AIGW_BASE_URL"):
        if not base_url and os.environ.get(name):
            base_url = os.environ[name]
            sources["base_url"] = name
    if not base_url and isinstance(defaults.get("base_url"), str) and defaults["base_url"]:
        base_url = defaults["base_url"]
        sources["base_url"] = str(DEFAULTS_PATH)

    timeout = defaults.get("request_timeout_seconds")
    return {
        "api_key": api_key,
        "base_url": (base_url or "").rstrip("/"),
        "group": config.get("group") if isinstance(config.get("group"), str) else "",
        "default_model": config.get("model") if isinstance(config.get("model"), str) else "",
        "timeout": int(timeout) if isinstance(timeout, (int, float)) and timeout > 0 else 180,
        "sources": sources,
    }


def mask_secret(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 8:
        return "*" * len(value)
    return f"{value[:4]}...{value[-4:]}"


def parse_error(body: bytes, status: int) -> tuple[str, str]:
    try:
        payload = json.loads(body.decode("utf-8", "replace"))
    except ValueError:
        return body.decode("utf-8", "replace")[:500] or f"HTTP {status}", ""
    if isinstance(payload, dict):
        error = payload.get("error")
        if isinstance(error, dict):
            return str(error.get("message") or error), str(error.get("code") or "")
        if isinstance(error, str) and error:
            return error, str(payload.get("code") or "")
        for key in ("message", "msg", "detail"):
            if payload.get(key):
                return str(payload[key]), str(payload.get("code") or "")
    return json.dumps(payload, ensure_ascii=False)[:500], ""


def read_body(resp) -> bytes:
    chunks = []
    while True:
        try:
            chunk = resp.read(65536)
        except ssl.SSLEOFError:
            break
        except http.client.IncompleteRead as err:
            if err.partial:
                chunks.append(err.partial)
            break
        if not chunk:
            break
        chunks.append(chunk)
    return b"".join(chunks)


def encode_multipart(fields: list, files: list) -> tuple[bytes, str]:
    boundary = f"----aigw{int(time.time() * 1000)}{os.getpid()}"
    chunk = []
    for name, value in fields:
        chunk.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"\r\n\r\n{value}\r\n".encode("utf-8"))
    for name, filename, payload, content_type in files:
        header = (
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"; filename=\"{filename}\"\r\n"
            f"Content-Type: {content_type or 'application/octet-stream'}\r\n\r\n"
        )
        chunk.append(header.encode("utf-8"))
        chunk.append(payload)
        chunk.append(b"\r\n")
    chunk.append(f"--{boundary}--\r\n".encode("utf-8"))
    return b"".join(chunk), f"multipart/form-data; boundary={boundary}"


def request(settings: dict, method: str, path: str, body: dict | None = None, query: dict | None = None,
            fields: list | None = None, files: list | None = None, timeout: int | None = None) -> tuple[int, dict, bytes]:
    if not settings.get("base_url"):
        raise GatewayError("base_url is not configured: run `login --base-url`, set AIGW_BASE_URL, or edit scripts/defaults.json")
    url = settings["base_url"] + path
    if query:
        url += ("&" if "?" in url else "?") + urllib.parse.urlencode(query)

    headers = {"Accept": "application/json", "Connection": "close", "User-Agent": USER_AGENT}
    data = None
    if files is not None:
        data, content_type = encode_multipart(fields or [], files)
        headers["Content-Type"] = content_type
    elif body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if settings.get("api_key"):
        headers["Authorization"] = f"Bearer {settings['api_key']}"

    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout or settings.get("timeout", 180)) as resp:
            return resp.status, dict(resp.headers), read_body(resp)
    except urllib.error.HTTPError as err:
        message, code = parse_error(read_body(err), err.code)
        raise GatewayError(message, err.code, code) from None
    except urllib.error.URLError as err:
        raise GatewayError(f"{url}: {err.reason}") from None


def request_json(settings: dict, method: str, path: str, body: dict | None = None, query: dict | None = None) -> dict:
    _, _, raw = request(settings, method, path, body=body, query=query)
    try:
        payload = json.loads(raw.decode("utf-8", "replace"))
    except ValueError:
        raise GatewayError("upstream returned a non-JSON body") from None
    if not isinstance(payload, dict):
        raise GatewayError("upstream returned an unexpected JSON payload")
    return payload


def belongs(model_id: str, patterns: list) -> bool:
    name = model_id.lower()
    if any(keyword in name for keyword in ("speech-to-text", "voice-changer", "speech-to-speech", "suno_uploads", "suno_lyrics")):
        return False
    return any(fnmatch.fnmatch(name, pattern.lower()) for pattern in patterns)


def load_models(settings: dict, refresh: bool = False) -> list:
    key = re.sub(r"[^a-z0-9]+", "-", (settings.get("base_url") or "unconfigured").lower()).strip("-")
    cache = CACHE_DIR / f"{CAPABILITY}-{key}.json"
    cached = read_json(cache)
    if not refresh and cached.get("fetched_at", 0) + CACHE_TTL_SECONDS > time.time():
        return cached.get("models", [])

    patterns = read_json(ROOT / "scripts" / "models.json").get("patterns", {}).get(CAPABILITY, [])
    models: list = []
    try:
        payload = request_json(settings, "GET", "/api/pricing")
        for item in payload.get("data") or []:
            if not isinstance(item, dict) or not item.get("model_name"):
                continue
            if not belongs(item["model_name"], patterns):
                continue
            models.append({
                "id": item["model_name"],
                "quota_type": item.get("quota_type"),
                "price": item.get("model_price"),
                "ratio": item.get("model_ratio"),
                "billing_mode": item.get("billing_mode"),
                "billing_expr": item.get("billing_expr"),
                "groups": item.get("enable_groups") or [],
            })
    except GatewayError:
        models = []

    known = {model["id"] for model in models}
    try:
        payload = request_json(settings, "GET", "/v1/models")
        for item in payload.get("data") or []:
            model_id = item.get("id") if isinstance(item, dict) else ""
            if model_id and model_id not in known and belongs(model_id, patterns):
                models.append({"id": model_id, "groups": []})
                known.add(model_id)
    except GatewayError:
        if not models:
            raise

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps({"fetched_at": int(time.time()), "models": models}, ensure_ascii=False), "utf-8")
    return models


def resolve_alias(alias: str, models: list) -> list:
    key = alias.lower().strip()
    for model in models:
        if model["id"].lower() == key:
            return [model]
    patterns = read_json(ROOT / "scripts" / "models.json").get("aliases", {}).get(key, [])
    matches = []
    for pattern in patterns:
        for model in models:
            if fnmatch.fnmatch(model["id"].lower(), pattern.lower()) and model not in matches:
                matches.append(model)
    return matches


def price_rank(model: dict) -> tuple:
    price = model.get("price")
    if isinstance(price, (int, float)) and price > 0:
        return (0, float(price))
    ratio = model.get("ratio")
    if isinstance(ratio, (int, float)) and ratio > 0:
        return (1, float(ratio))
    return (2, 0.0)


def pick_model(args, models: list, alias: str = "", default: str = "") -> str:
    if getattr(args, "model", ""):
        return args.model
    if default:
        return default
    if alias:
        matches = resolve_alias(alias, models)
        if len(matches) == 1:
            return matches[0]["id"]
        if matches:
            return min(matches, key=price_rank)["id"]
    if len(models) == 1:
        return models[0]["id"]
    hint = f", alias '{alias}'" if alias else ""
    raise GatewayError(f"model is required: pass --model or set a default with `model set` ({CAPABILITY}{hint})")


def slug(text: str, limit: int = 40) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fa5]+", "-", text or "").strip("-")
    return (cleaned[:limit] or "output").lower()


def save_bytes(stem: str, payload: bytes, extension: str = "") -> Path:
    target = OUTPUT_DIR / CAPABILITY / date.today().isoformat()
    target.mkdir(parents=True, exist_ok=True)
    suffix = (extension or "").strip(".").lower()
    if not suffix:
        suffix = "mp3"
        if payload[:3] == b"ID3" or payload[:2] in (b"\xff\xfb", b"\xff\xf3"):
            suffix = "mp3"
        elif payload[:4] == b"fLaC":
            suffix = "flac"
        elif payload[:4] == b"RIFF":
            suffix = "wav"
        elif payload[4:8] == b"ftyp":
            suffix = "m4a"
    path = target / f"{stem}-{time.strftime('%H%M%S')}.{suffix}"
    path.write_bytes(payload)
    return path


def download(settings: dict, url: str, timeout: int = 120) -> bytes:
    headers = {"User-Agent": USER_AGENT, "Accept": "*/*"}
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return read_body(resp)
    except urllib.error.HTTPError as err:
        message, code = parse_error(read_body(err), err.code)
        raise GatewayError(f"download failed: {message}", err.code, code) from None
    except urllib.error.URLError as err:
        raise GatewayError(f"download failed: {url}: {err.reason}") from None


def audio_transport(model_id: str) -> str:
    name = model_id.lower()
    if name.startswith("speech-"):
        return "speech"
    if "elevenlabs" in name or "dialogue" in name:
        return "task"
    if ("gpt-4o" in name or name.startswith("tts-")) and "audio" not in name:
        return "speech"
    return "chat"


def audio_content_type(filename: str) -> str:
    extension = Path(filename).suffix.lower()
    return {
        ".mp3": "audio/mpeg",
        ".m4a": "audio/mp4",
        ".wav": "audio/wav",
        ".flac": "audio/flac",
        ".ogg": "audio/ogg",
        ".aac": "audio/aac",
        ".webm": "audio/webm",
        ".mp4": "video/mp4",
    }.get(extension, "application/octet-stream")


def collect_audio_urls(node) -> list:
    found = []

    def walk(value, key=""):
        if isinstance(value, dict):
            for child_key, child in value.items():
                walk(child, child_key)
        elif isinstance(value, list):
            for child in value:
                walk(child, key)
        elif isinstance(value, str) and value.startswith(("http://", "https://")):
            lowered = key.lower()
            bare = value.lower().split("?", 1)[0]
            if lowered in AUDIO_KEYS or bare.endswith(AUDIO_EXTENSIONS):
                if value not in found:
                    found.append(value)

    walk(node)
    return found


def collect_chat_audio(payload: dict) -> tuple[list, list]:
    urls, inline = [], []
    for item in payload.get("data") or []:
        if not isinstance(item, dict):
            continue
        url = str(item.get("url") or "")
        mime = str(item.get("mime_type") or "")
        if url and (mime.startswith("audio/") or url.lower().split("?", 1)[0].endswith(AUDIO_EXTENSIONS)):
            if url not in urls:
                urls.append(url)

    choices = payload.get("choices") if isinstance(payload.get("choices"), list) else []
    message = choices[0].get("message") if choices and isinstance(choices[0], dict) else {}
    if not isinstance(message, dict):
        message = {}

    audio = message.get("audio")
    if isinstance(audio, dict) and isinstance(audio.get("data"), str) and audio["data"]:
        inline.append((base64.b64decode(audio["data"]), str(audio.get("format") or "mp3")))

    content = message.get("content")
    if isinstance(content, list):
        content = "\n".join(str(part.get("text") or "") for part in content if isinstance(part, dict))
    if isinstance(content, str):
        for url in URL_PATTERN.findall(content):
            if url.lower().split("?", 1)[0].endswith(AUDIO_EXTENSIONS) and url not in urls:
                urls.append(url)
    return urls, inline


def request_chat_audio(settings: dict, model: str, prompt: str, voice: str = "", group: str = "") -> tuple[list, list]:
    body = {"model": model, "messages": [{"role": "user", "content": prompt}], "stream": False}
    if voice:
        body["voice"] = voice
    if group:
        body["group"] = group
    payload = request_json(settings, "POST", "/v1/chat/completions", body=body)
    urls, inline = collect_chat_audio(payload)
    if not urls and not inline:
        raise GatewayError(f"response contained no audio data: {json.dumps(payload, ensure_ascii=False)[:300]}")
    return urls, inline


def save_chat_audio(stem: str, urls: list, inline: list, settings: dict) -> tuple[list, list]:
    files = []
    for index, (payload, extension) in enumerate(inline):
        files.append(str(save_bytes(f"{stem}-{index + 1}", payload, extension)))
    for index, url in enumerate(urls):
        files.append(str(save_bytes(f"{stem}-{len(inline) + index + 1}", download(settings, url))))
    return files, urls


def normalize_audio_task(payload: dict) -> dict:
    data = payload.get("data")
    if not isinstance(data, dict):
        return {"status": "", "urls": [], "reason": ""}
    reason = data.get("error") or data.get("message") or ""
    return {"status": str(data.get("status") or "").upper(), "urls": collect_audio_urls(data), "reason": str(reason)}


def normalize_transcript(payload: dict) -> dict:
    data = payload.get("data")
    if not isinstance(data, dict):
        return {"status": "", "text": "", "reason": ""}
    output = data.get("output") if isinstance(data.get("output"), dict) else {}
    text = data.get("text") or output.get("text") or ""
    reason = data.get("error") or data.get("message") or ""
    return {"status": str(data.get("status") or "").upper(), "text": str(text), "reason": str(reason)}


def poll(settings: dict, path: str, normalize, timeout: int, interval: int) -> dict:
    deadline = time.time() + max(timeout, 1)
    interval = max(interval, 1)
    while True:
        state = normalize(request_json(settings, "GET", path))
        if state["status"] in TERMINAL_STATUS or time.time() >= deadline:
            return state
        time.sleep(interval)


def submit_task_id(payload: dict) -> str:
    data = payload.get("data")
    if isinstance(data, str):
        return data
    if isinstance(data, dict):
        return str(data.get("task_id") or "")
    return ""


def handle_login(args, settings: dict) -> None:
    if not args.key:
        raise GatewayError("--key is required")
    if args.base_url and not args.base_url.startswith(("http://", "https://")):
        raise GatewayError("--base-url must start with http:// or https://")
    target = ROOT / "config.json"
    data = read_json(target)
    data["api_key"] = args.key
    if args.base_url:
        data["base_url"] = args.base_url.rstrip("/")
    if args.group:
        data["group"] = args.group
    target.write_text(json.dumps(data, ensure_ascii=False, indent=2), "utf-8")
    os.chmod(target, 0o600)
    emit({"ok": True, "config": str(target), "base_url": data.get("base_url") or settings["base_url"]})


def handle_model(args, settings: dict) -> None:
    if args.action == "set":
        target = ROOT / "config.json"
        data = read_json(target)
        data["model"] = args.model_id
        target.write_text(json.dumps(data, ensure_ascii=False, indent=2), "utf-8")
        os.chmod(target, 0o600)
        emit({"ok": True, "model": args.model_id, "config": str(target)})
        return
    configured = settings["default_model"]
    available = None
    if configured:
        try:
            available = configured in {model["id"] for model in load_models(settings)}
        except GatewayError:
            available = None
    emit({"ok": True, "model": configured, "configured": bool(configured), "available": available,
          "source": str(ROOT / "config.json") if configured else "none"})


def handle_config(args, settings: dict) -> None:
    emit({
        "ok": True,
        "capability": CAPABILITY,
        "platform": {"name": PLATFORM, "url": PLATFORM_URL, "tagline": PLATFORM_TAGLINE,
                     "description_zh": PLATFORM_DESC_ZH, "description_en": PLATFORM_DESC_EN,
                     "repository": REPO_URL},
        "config": str(ROOT / "config.json"),
        "base_url": settings["base_url"],
        "group": settings["group"],
        "model": settings["default_model"],
        "api_key": mask_secret(settings["api_key"]),
        "sources": settings["sources"],
        "defaults": str(DEFAULTS_PATH),
    })


def handle_models(args, settings: dict) -> None:
    models = load_models(settings, refresh=args.refresh)
    key = re.sub(r"[^a-z0-9]+", "-", (settings.get("base_url") or "unconfigured").lower()).strip("-")
    cached = read_json(CACHE_DIR / f"{CAPABILITY}-{key}.json")
    fetched_at = cached.get("fetched_at") or 0
    emit({"ok": True, "base_url": settings["base_url"], "count": len(models),
          "cached_at": fetched_at or None,
          "cache_age_seconds": int(time.time() - fetched_at) if fetched_at else None,
          "models": models})


def handle_resolve(args, settings: dict) -> None:
    matches = resolve_alias(args.alias, load_models(settings))
    if not matches:
        raise GatewayError(f"no model matches alias '{args.alias}'")
    emit({"ok": True, "alias": args.alias, "matches": matches})


def handle_doctor(args, settings: dict) -> None:
    report = {"ok": False, "base_url": settings["base_url"], "sources": settings["sources"],
              "api_key": mask_secret(settings["api_key"]), "api_key_configured": bool(settings["api_key"])}
    if not settings["api_key"]:
        report["error"] = {"message": "no API key configured"}
        emit(report)
        return
    try:
        payload = request_json(settings, "GET", "/v1/models")
        report["auth_ok"] = True
        report["models"] = len(payload.get("data") or [])
        report["ok"] = True
    except GatewayError as err:
        report["auth_ok"] = False
        report["error"] = {"message": err.message, "status": err.status}
    emit(report)


def handle_tts_speak(args, settings: dict) -> None:
    model = pick_model(args, load_models(settings), "minimax-tts", settings["default_model"])
    transport = audio_transport(model)

    if transport == "chat":
        urls, inline = request_chat_audio(settings, model, args.input, voice=args.voice, group=args.group)
        files, urls = save_chat_audio(slug(args.input), urls, inline, settings)
        emit({"ok": True, "model": model, "files": files, "urls": urls})
        return

    if transport == "task":
        voice = args.voice
        if "elevenlabs" in model.lower() and not voice:
            voice = DEFAULT_ELEVENLABS_VOICE
        if "text-to-dialogue" in model.lower():
            task_input = {"dialogue": [{"text": args.input, "voice": voice or DEFAULT_ELEVENLABS_VOICE}]}
        else:
            task_input = {"text": args.input}
            if voice:
                task_input["voice"] = voice
        payload = request_json(settings, "POST", "/v1/tasks", body={"model": model, "input": task_input})
        task_id = submit_task_id(payload)
        if not task_id:
            raise GatewayError(f"missing task id in response: {json.dumps(payload, ensure_ascii=False)[:300]}")
        state = poll(settings, f"/v1/tasks/{urllib.parse.quote(task_id, safe='')}", normalize_audio_task, 300, 5)
        if state["status"] != "COMPLETED" or not state["urls"]:
            raise GatewayError(f"task {task_id} ended with status {state['status']}: {state['reason']}")
        files = [str(save_bytes(f"{slug(args.input)}-{index + 1}", download(settings, url)))
                 for index, url in enumerate(state["urls"])]
        emit({"ok": True, "model": model, "task_id": task_id, "files": files, "urls": state["urls"]})
        return

    body = {"model": model, "input": args.input}
    if args.voice:
        body["voice"] = args.voice
    if args.format:
        body["response_format"] = args.format
    if args.speed is not None:
        body["speed"] = args.speed
    if args.instructions:
        body["instructions"] = args.instructions
    if args.group:
        body["group"] = args.group
    _, headers, raw = request(settings, "POST", "/v1/audio/speech", body=body)
    content_type = headers.get("Content-Type", "")
    looks_like_json = raw.lstrip()[:1] in (b"{", b"[")

    if "application/json" in content_type or looks_like_json:
        payload = json.loads(raw.decode("utf-8", "replace"))
        urls = collect_audio_urls(payload)
        if not urls:
            raise GatewayError(f"response contained no audio data: {json.dumps(payload, ensure_ascii=False)[:300]}")
        files = [str(save_bytes(f"{slug(args.input)}-{index + 1}", download(settings, url)))
                 for index, url in enumerate(urls)]
        emit({"ok": True, "model": model, "files": files, "urls": urls})
        return

    emit({"ok": True, "model": model, "files": [str(save_bytes(slug(args.input), raw, args.format or ""))],
          "content_type": content_type})


def handle_tts_clone(args, settings: dict) -> None:
    if not args.audio_url and not args.video_id:
        raise GatewayError("--audio-url or --video-id is required")
    body = {"model": "kling-custom-voices", "voice_name": args.name}
    if args.audio_url:
        body["voice_url"] = args.audio_url
    if args.video_id:
        body["video_id"] = args.video_id
    emit({"ok": True, "response": request_json(settings, "POST", "/kling/v1/general/custom-voices", body=body)})


def handle_tts_clone_status(args, settings: dict) -> None:
    task_id = urllib.parse.quote(args.task_id, safe="")
    emit({"ok": True, "response": request_json(settings, "GET", f"/kling/v1/general/custom-voices/{task_id}")})


def handle_transcribe(args, settings: dict) -> None:
    model = args.model or settings["default_model"] or pick_model(args, load_models(settings))

    if args.url:
        body = {"model": model, "input": {"audio_url": args.url}}
        if args.language:
            body["input"]["language_code"] = args.language
        payload = request_json(settings, "POST", "/v1/tasks", body=body)
        task_id = submit_task_id(payload)
        if not task_id:
            raise GatewayError(f"missing task id in response: {json.dumps(payload, ensure_ascii=False)[:300]}")
        state = poll(settings, f"/v1/tasks/{urllib.parse.quote(task_id, safe='')}", normalize_transcript, 600, 5)
        if state["status"] != "COMPLETED":
            raise GatewayError(f"task {task_id} ended with status {state['status']}: {state['reason']}")
        if args.out:
            Path(args.out).parent.mkdir(parents=True, exist_ok=True)
            Path(args.out).write_text(json.dumps(state, ensure_ascii=False, indent=2), "utf-8")
        emit({"ok": True, "model": model, "task_id": task_id, "text": state["text"]})
        return

    if not args.file:
        raise GatewayError("--file is required for synchronous models; use --url for task-based transcription")

    source = Path(args.file)
    try:
        payload = source.read_bytes()
    except OSError as err:
        raise GatewayError(f"cannot read audio {args.file}: {err.strerror or err}") from None

    fields = [("model", model)]
    if args.language:
        fields.append(("language", args.language))
    if args.format:
        fields.append(("response_format", args.format))
    if args.group:
        fields.append(("group", args.group))
    files = [("file", source.name, payload, audio_content_type(source.name))]
    _, _, raw = request(settings, "POST", "/v1/audio/transcriptions", fields=fields, files=files)
    result = json.loads(raw.decode("utf-8", "replace"))
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(json.dumps(result, ensure_ascii=False, indent=2), "utf-8")
    emit({"ok": True, "model": model, "text": result.get("text", ""), "response": result})


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="gateway.py",
        description=f"Text to speech skill for {PLATFORM} ({PLATFORM_URL})",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            f"{PLATFORM} · {PLATFORM_URL}\n"
            f"{PLATFORM_DESC_ZH}\n"
            f"{PLATFORM_DESC_EN}\n"
            f"Repository: {REPO_URL}"
        ),
    )
    parser.add_argument("--request-timeout", dest="request_timeout", type=int, default=0,
                        help="override the single-request timeout in seconds")
    sub = parser.add_subparsers(dest="command", required=True)

    login = sub.add_parser("login", help="store an API key")
    login.add_argument("--key", required=True)
    login.add_argument("--base-url", default="")
    login.add_argument("--group", default="")

    sub.add_parser("config", help="show resolved settings")

    models = sub.add_parser("models", help="list speech models")
    models.add_argument("--refresh", action="store_true")

    model = sub.add_parser("model", help="show or set the default model")
    model_sub = model.add_subparsers(dest="action", required=True)
    model_sub.add_parser("show", help="show the configured default model")
    model_set = model_sub.add_parser("set", help="pin a default model in config.json")
    model_set.add_argument("model_id")

    resolve = sub.add_parser("resolve", help="map an alias to a model id")
    resolve.add_argument("alias")

    tts = sub.add_parser("tts", help="speech synthesis and voice cloning")
    tts_sub = tts.add_subparsers(dest="action", required=True)

    speak = tts_sub.add_parser("speak")
    speak.add_argument("--input", required=True)
    speak.add_argument("--model", default="")
    speak.add_argument("--voice", default="")
    speak.add_argument("--format", default="")
    speak.add_argument("--speed", type=float, default=None)
    speak.add_argument("--instructions", default="")
    speak.add_argument("--group", default="")

    clone = tts_sub.add_parser("clone")
    clone.add_argument("--name", required=True)
    clone.add_argument("--audio-url", dest="audio_url", default="")
    clone.add_argument("--video-id", dest="video_id", default="")

    clone_status = tts_sub.add_parser("clone-status")
    clone_status.add_argument("task_id")

    transcribe = sub.add_parser("transcribe", help="speech to text")
    transcribe.add_argument("--file", default="", help="local audio or video file for synchronous models")
    transcribe.add_argument("--url", default="", help="public audio URL for task-based models")
    transcribe.add_argument("--model", default="")
    transcribe.add_argument("--language", default="")
    transcribe.add_argument("--format", default="")
    transcribe.add_argument("--group", default="")
    transcribe.add_argument("--out", default="")

    sub.add_parser("doctor", help="verify credentials and connectivity")
    return parser


DISPATCH = {
    ("login", None): handle_login,
    ("config", None): handle_config,
    ("models", None): handle_models,
    ("model", "show"): handle_model,
    ("model", "set"): handle_model,
    ("resolve", None): handle_resolve,
    ("tts", "speak"): handle_tts_speak,
    ("tts", "clone"): handle_tts_clone,
    ("tts", "clone-status"): handle_tts_clone_status,
    ("transcribe", None): handle_transcribe,
    ("doctor", None): handle_doctor,
}


def main(argv: list | None = None) -> None:
    args = build_parser().parse_args(argv)
    current = settings()
    if getattr(args, "request_timeout", 0) > 0:
        current["timeout"] = args.request_timeout
    try:
        DISPATCH[(args.command, getattr(args, "action", None))](args, current)
    except GatewayError as err:
        fail(err.code or "request_failed", err.message, err.status)
    except KeyboardInterrupt:
        fail("interrupted", "cancelled by user")
    except Exception as err:
        fail("internal_error", f"{type(err).__name__}: {err}")


if __name__ == "__main__":
    main()
