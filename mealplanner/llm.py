"""Text generation through an outside model. Only used for recipe ideas; numbers are always
recomputed by our own code.

The default provider shells out to the opencode CLI (works with an opencode subscription, e.g.
DeepSeek through opencode-go). It runs in an empty temporary folder so the agent has nothing to
touch, and the prompt goes in as an attached file to avoid shell quoting problems.
"""
import json
import os
import shutil
import subprocess
import tempfile

from flask import current_app

DEFAULT_MODEL = "opencode-go/deepseek-v4-flash"
DEFAULT_VISION_MODEL = "opencode-go/deepseek-v4-flash-vision-exp"
DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"


class LLMError(Exception):
    pass


class OpencodeProvider:
    name = "opencode"

    def __init__(self, model=None, timeout=120, binary=None):
        self.model = model or DEFAULT_MODEL
        self.timeout = timeout
        self.binary = binary or shutil.which("opencode")

    def available(self):
        return bool(self.binary)

    def complete(self, prompt, images=(), model=None):
        """images: paths of pictures to attach (needs a vision model)."""
        if not self.binary:
            raise LLMError("opencode is not installed or not on PATH")
        with tempfile.TemporaryDirectory(prefix="mealplanner-llm-") as work:
            prompt_file = os.path.join(work, "request.md")
            with open(prompt_file, "w", encoding="utf-8") as f:
                f.write(prompt)
            attached = ["-f", prompt_file]
            for i, src in enumerate(images):
                dest = os.path.join(work, f"image{i}{os.path.splitext(src)[1].lower() or '.jpg'}")
                shutil.copyfile(src, dest)
                attached += ["-f", dest]
            cmd = [self.binary, "run", "--pure", "--format", "json", "-m", model or self.model, *attached,
                   "--", "Follow the instructions in the attached request.md. Do not use any tools."]
            try:
                proc = subprocess.run(cmd, cwd=work, capture_output=True, text=True, encoding="utf-8",
                                      timeout=self.timeout, stdin=subprocess.DEVNULL)
            except subprocess.TimeoutExpired:
                raise LLMError(f"the model took longer than {self.timeout} seconds")
        text = parse_events(proc.stdout)
        if not text:
            raise LLMError(event_error(proc.stdout) or "no reply from the model")
        return text


def parse_events(stdout):
    """Join the text parts of opencode's JSON event stream."""
    parts = []
    for line in stdout.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("type") == "text":
            parts.append(event.get("part", {}).get("text", ""))
    return "".join(parts).strip()


def event_error(stdout):
    """The error message from opencode's event stream, if it reported one."""
    for line in stdout.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("type") == "error":
            err = event.get("error") or {}
            msg = (err.get("data") or {}).get("message") or err.get("name") or "unknown error"
            if "subscription" in msg.lower():
                return "your OpenCode Go subscription isn't active, so the model refused"
            return msg[:200]
    return None


def extract_json(text):
    """Pull the first JSON object out of a reply that may have code fences or chatter around it."""
    start = text.find("{")
    if start == -1:
        raise LLMError("the reply did not contain JSON")
    depth = 0
    in_string = escaped = False
    for i, ch in enumerate(text[start:], start):
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
        elif ch == '"':
            in_string = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[start:i + 1])
                except json.JSONDecodeError as e:
                    raise LLMError(f"the reply had broken JSON ({e.msg})")
    raise LLMError("the reply's JSON was cut off")


class GeminiProvider:
    """Google's Gemini API over plain HTTPS. Reads text and photos."""
    name = "gemini"
    API = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

    def __init__(self, key, model=None, timeout=90):
        self.key = key
        self.model = model or DEFAULT_GEMINI_MODEL
        self.timeout = timeout

    def complete(self, prompt, images=(), model=None):
        import base64
        import mimetypes
        from urllib.error import HTTPError, URLError
        from urllib.request import Request, urlopen

        parts = [{"text": prompt}]
        for path in images:
            mime = mimetypes.guess_type(path)[0] or "image/jpeg"
            with open(path, "rb") as f:
                parts.append({"inline_data": {"mime_type": mime, "data": base64.b64encode(f.read()).decode()}})
        # "vision" model names belong to opencode; Gemini reads images with the same model
        use = model if model and model.startswith("gemini") else self.model
        body = json.dumps({"contents": [{"parts": parts}],
                           "generationConfig": {"responseMimeType": "application/json", "temperature": 0.4}})
        req = Request(self.API.format(model=use), data=body.encode(), method="POST",
                      headers={"Content-Type": "application/json", "x-goog-api-key": self.key})
        try:
            with urlopen(req, timeout=self.timeout) as resp:
                data = json.loads(resp.read().decode())
        except HTTPError as e:
            detail = e.read().decode(errors="replace")[:300]
            if e.code in (400, 403) and "API key" in detail:
                raise LLMError("the Gemini key was rejected. Check it in Settings")
            if e.code == 429:
                raise LLMError("Gemini's free limit is used up for now. Try again in a minute")
            raise LLMError(f"Gemini error {e.code}")
        except (URLError, TimeoutError) as e:
            raise LLMError(f"couldn't reach Gemini ({e.__class__.__name__})")
        try:
            return "".join(p.get("text", "") for p in data["candidates"][0]["content"]["parts"]).strip()
        except (KeyError, IndexError):
            raise LLMError("Gemini sent an empty answer")


def gemini_key():
    key = os.environ.get("GEMINI_API_KEY")
    if key:
        return key
    try:
        from .store import settings
        return settings().get("gemini_key") or None
    except Exception:
        return None


def provider():
    """The configured provider: Gemini when a key is set, otherwise opencode.

    Tests put a fake one in app.config["LLM_PROVIDER"]; MEALPLANNER_LLM=none turns models off.
    """
    injected = current_app.config.get("LLM_PROVIDER")
    if injected is not None:
        return injected
    choice = os.environ.get("MEALPLANNER_LLM", "auto")
    if choice == "none":
        return None
    key = gemini_key()
    if key and choice in ("auto", "gemini"):
        return GeminiProvider(key, model=os.environ.get("MEALPLANNER_GEMINI_MODEL"))
    if choice == "gemini":
        return None
    p = OpencodeProvider(model=os.environ.get("MEALPLANNER_LLM_MODEL"))
    return p if p.available() else None
