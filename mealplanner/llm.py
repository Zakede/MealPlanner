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
            raise LLMError("no reply from the model" + (f": {proc.stderr.strip()[:200]}" if proc.stderr else ""))
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


def provider():
    """The configured provider. Tests put a fake one in app.config["LLM_PROVIDER"]."""
    injected = current_app.config.get("LLM_PROVIDER")
    if injected is not None:
        return injected
    if os.environ.get("MEALPLANNER_LLM", "opencode") == "none":
        return None
    p = OpencodeProvider(model=os.environ.get("MEALPLANNER_LLM_MODEL"))
    return p if p.available() else None
