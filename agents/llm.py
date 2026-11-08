"""Thin wrapper around the Anthropic Messages API, with run logging.

Set ANTHROPIC_API_KEY (environment variable or Streamlit secret). Without a
key the app runs in baseline mode (no AI calls). Every call is appended to
logs/runs.jsonl so the portfolio's run log and AI-use log can be filled from it.
"""
import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOG = ROOT / "logs" / "runs.jsonl"
PROMPTS = Path(__file__).resolve().parent / "prompts"

DEFAULT_MODEL = os.environ.get("BILL_AGENT_MODEL", "claude-sonnet-5-5")


def api_key():
    """Key order: one pasted by this visitor (session only) > app secret > environment."""
    try:
        import streamlit as st
        k = st.session_state.get("user_api_key")
        if k:
            return k
        try:
            k = st.secrets.get("ANTHROPIC_API_KEY")
        except Exception:
            k = None
        if k:
            return k
    except Exception:
        pass
    return os.environ.get("ANTHROPIC_API_KEY")


def prompt(name):
    return (PROMPTS / f"{name}.md").read_text()


def call(agent, system, user, model=None, max_tokens=4000):
    """Send one request; return (text, meta). Raises RuntimeError without a key."""
    key = api_key()
    if not key:
        raise RuntimeError("No ANTHROPIC_API_KEY set: running in baseline mode.")
    import anthropic
    client = anthropic.Anthropic(api_key=key)
    t0 = time.time()
    msg = client.messages.create(model=model or DEFAULT_MODEL, max_tokens=max_tokens, temperature=0,
                                 system=system, messages=[{"role": "user", "content": user}])
    text = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
    meta = {"time": datetime.now(timezone.utc).isoformat(timespec="seconds"), "agent": agent,
            "model": msg.model, "input_tokens": msg.usage.input_tokens, "output_tokens": msg.usage.output_tokens,
            "seconds": round(time.time() - t0, 1)}
    LOG.parent.mkdir(exist_ok=True)
    with open(LOG, "a") as f:
        f.write(json.dumps({**meta, "user_prompt": user[:4000], "output": text[:8000]}, ensure_ascii=False) + "\n")
    return text, meta


def chat(agent, system, messages, model=None, max_tokens=2000):
    """Multi-turn call (messages = [{"role": "user"|"assistant", "content": str}, ...])."""
    key = api_key()
    if not key:
        raise RuntimeError("No ANTHROPIC_API_KEY set: running in baseline mode.")
    import anthropic
    client = anthropic.Anthropic(api_key=key)
    t0 = time.time()
    msg = client.messages.create(model=model or DEFAULT_MODEL, max_tokens=max_tokens, temperature=0, system=system, messages=messages)
    text = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
    meta = {"time": datetime.now(timezone.utc).isoformat(timespec="seconds"), "agent": agent, "model": msg.model,
            "input_tokens": msg.usage.input_tokens, "output_tokens": msg.usage.output_tokens, "seconds": round(time.time() - t0, 1)}
    LOG.parent.mkdir(exist_ok=True)
    with open(LOG, "a") as f:
        f.write(json.dumps({**meta, "user_prompt": messages[-1]["content"][:4000], "output": text[:8000]}, ensure_ascii=False) + "\n")
    return text, meta


def parse_json(text):
    """Pull the first JSON object out of a model reply."""
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        raise ValueError("No JSON object in model output")
    return json.loads(m.group(0))
