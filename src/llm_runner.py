#!/usr/bin/env python
"""
llm_runner.py — run a single Open Interpreter chat in an isolated subprocess.

WHY THIS EXISTS
---------------
Open Interpreter drives code execution through a Jupyter/`ipykernel` subprocess
managed by `jupyter_client` + `asyncio` + POSIX/Windows signal handlers. Those
machineries are only reliable on a process's MAIN thread.

dobd.py processes drives on a background worker thread. Running Open Interpreter
on that worker thread caused intermittent, PERMANENT hangs: every so often the
Jupyter kernel would connect its ZMQ channels but never execute the submitted
code, and because Open Interpreter's own ">15s, should I send Ctrl-C?" watchdog
fails (it dispatches a recovery completion with the provider prefix stripped, so
LiteLLM raises "LLM Provider NOT provided"), nothing ever recovered. The drive
build would sit on "Matching Specific Files" forever.

Running each chat in its own subprocess gives Open Interpreter a real MAIN
thread (eliminating the kernel deadlock), full isolation (its own working
directory and kernel), and a clean boundary the parent process can enforce a
hard timeout on — killing the whole tree if it ever exceeds it.

USAGE
-----
    python llm_runner.py <config.json>

config.json keys:
    ip_address, port, model, context_window, api_key, max_tokens,
    working_directory, prompt

Exit codes:
    0  -> chat completed
    2  -> bad/missing config path
    3  -> invalid working_directory
    4  -> failed to import Open Interpreter
    5  -> exception during the chat
"""

import json
import os
import sys

# Sentinel line llm_runner prints (and dobd.py's LLM class parses) to record how
# much of the model's context window a finished run consumed. Kept in sync with
# CONTEXT_SENTINEL in dobd.py.
CONTEXT_SENTINEL = "__DOB_CONTEXT_USAGE__"


def _force_utf8_stdio():
    """Force stdout/stderr to UTF-8 so Open Interpreter's streaming prints can
    NEVER crash the run on a non-Latin-1 character.

    On Windows a child process's piped stdout defaults to the legacy ANSI code
    page (cp1252). Open Interpreter streams the model's reply straight to stdout,
    so the moment a model emitted a perfectly ordinary character like "→" (U+2192)
    or "•" (U+2022) — which happens constantly when an agent narrates
    "source → destination" mappings — print() raised UnicodeEncodeError and the
    whole chat aborted (exit 5), silently throwing away the matchFiles / judge /
    fix work mid-run. Reconfiguring to UTF-8 with errors="replace" makes that
    impossible.
    """
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def _report_context_usage(interpreter, cfg):
    """Print a CONTEXT_SENTINEL line describing how full the context window got.

    Estimates the tokens in the full conversation (system + user + assistant +
    tool output) at the end of the run — a good proxy for the peak request size
    against the model's context window — and reports it as a percentage. The
    parent (dobd.py) parses the sentinel and writes it to logs/contextLog.log.
    Never raises: any failure falls back to a rough char/4 estimate, then to 0.
    """
    model = cfg.get("model", "") or ""
    try:
        window = int(cfg.get("context_window", 0) or 0)
    except Exception:
        window = 0

    messages = []
    try:
        for m in (getattr(interpreter, "messages", None) or []):
            content = m.get("content", "")
            if not isinstance(content, str):
                content = str(content)
            messages.append({"role": m.get("role", "user") or "user", "content": content})
    except Exception:
        messages = []

    tokens = None
    try:
        import litellm
        # Strip the litellm provider prefix ("openai/") so the tokenizer lookup
        # sees the real model id; unknown models fall back to a default encoder.
        token_model = model.split("openai/", 1)[-1]
        tokens = litellm.token_counter(model=token_model, messages=messages)
    except Exception:
        tokens = None
    if not tokens:
        tokens = sum(len(m["content"]) for m in messages) // 4  # ~4 chars/token

    percent = (tokens / window * 100.0) if window > 0 else 0.0
    payload = {
        "model": model,
        "context_window": window,
        "tokens": int(tokens),
        "percent": round(percent, 2),
    }
    print(CONTEXT_SENTINEL + json.dumps(payload), flush=True)


def _load_open_interpreter():
    """Import OpenInterpreter, falling back to the common pipx install path."""
    try:
        from interpreter import OpenInterpreter
        return OpenInterpreter
    except ImportError:
        pipx_path = os.path.expanduser(r"~\pipx\venvs\open-interpreter\Lib\site-packages")
        if os.path.exists(pipx_path) and pipx_path not in sys.path:
            sys.path.append(pipx_path)
        from interpreter import OpenInterpreter
        return OpenInterpreter


def main():
    # Must run before anything streams to stdout (Open Interpreter prints the
    # model's reply live), or a single non-cp1252 character will crash the chat.
    _force_utf8_stdio()

    if len(sys.argv) < 2:
        print("llm_runner: missing config path argument", file=sys.stderr)
        return 2

    try:
        with open(sys.argv[1], "r", encoding="utf-8") as f:
            cfg = json.load(f)
    except Exception as e:
        print(f"llm_runner: could not read config {sys.argv[1]!r}: {e}", file=sys.stderr)
        return 2

    # Isolate to the target directory. Because this is a fresh process, this
    # chdir cannot race with dobd.py's main polling thread.
    wd = cfg.get("working_directory")
    if not (wd and os.path.isdir(wd)):
        print(f"llm_runner: invalid working_directory: {wd!r}", file=sys.stderr)
        return 3
    os.chdir(wd)

    try:
        OpenInterpreter = _load_open_interpreter()
    except Exception as e:
        print(f"llm_runner: failed to import Open Interpreter: {e}", file=sys.stderr)
        return 4

    interpreter = OpenInterpreter()
    interpreter.llm.api_base = f"http://{cfg['ip_address']}:{cfg['port']}/v1"
    interpreter.llm.model = cfg["model"]
    interpreter.llm.api_key = cfg.get("api_key", "fake_key")
    interpreter.llm.context_window = cfg.get("context_window", 40000)
    interpreter.llm.max_tokens = cfg.get("max_tokens", 8192)
    interpreter.auto_run = True  # never prompt for confirmation (like -y)
    if hasattr(interpreter.llm, "temperature"):
        interpreter.llm.temperature = 0

    print(f"llm_runner: starting chat (model={cfg['model']}, dir={wd})", flush=True)
    try:
        interpreter.chat(cfg["prompt"])
    except Exception as e:
        print(f"llm_runner: exception during chat: {e}", file=sys.stderr)
        # Still try to report context usage for the partial run before exiting.
        _report_context_usage(interpreter, cfg)
        return 5

    # Report how much of the context window this run consumed (-> contextLog.log).
    _report_context_usage(interpreter, cfg)
    print("llm_runner: chat completed", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
