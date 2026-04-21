"""Minimal client for Anthropic managed agent via the Sessions API (beta).

Creates a session, sends a user message, streams agent responses,
and exits cleanly on session.status_idle or errors.

Usage:
    set ANTHROPIC_API_KEY=sk-ant-...
    python managed_agent_client.py "Your prompt here"
"""

import io
import os
import sys

import keyring
from anthropic import Anthropic

# Force UTF-8 stdout on Windows (agent responses contain emoji)
if sys.stdout.encoding != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

AGENT_ID = "agent_011CZxGWACDQfTpzVc7L3ZgC"
ENVIRONMENT_ID = "env_01MF357PP3PYeFAgbUY9hQBk"


def main() -> None:
    prompt = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "Hello, what can you do?"

    api_key = os.environ.get("ANTHROPIC_API_KEY") or keyring.get_password("automation/anthropic", "api_key")
    if not api_key:
        print("Set ANTHROPIC_API_KEY env var or store in keyring:\n"
              '  python -c "import keyring; keyring.set_password(\'automation/anthropic\', \'api_key\', \'sk-ant-...\')"',
              file=sys.stderr)
        sys.exit(1)
    client = Anthropic(api_key=api_key)

    # 1. Create a session
    print(f"Creating session (agent={AGENT_ID[:20]}…)…")
    session = client.beta.sessions.create(
        agent=AGENT_ID,
        environment_id=ENVIRONMENT_ID,
    )
    print(f"Session created: {session.id}\n")

    # 2. Send user message
    client.beta.sessions.events.send(
        session_id=session.id,
        events=[
            {
                "type": "user.message",
                "content": [{"type": "text", "text": prompt}],
            }
        ],
    )

    # 3. Stream events until idle or error
    with client.beta.sessions.events.stream(session_id=session.id) as stream:
        for event in stream:
            match event.type:
                case "agent.message":
                    for block in event.content:
                        print(block.text, end="", flush=True)
                    print()  # newline after each message event

                case "session.status_idle":
                    print(f"\n[idle — {event.stop_reason.type}]")
                    break

                case "session.error":
                    print(f"\n[error] {event.error.message}", file=sys.stderr)
                    sys.exit(1)

                case "session.status_terminated":
                    print("\n[session terminated]", file=sys.stderr)
                    sys.exit(1)

                case _:
                    pass  # ignore thinking, tool_use, running, etc.


if __name__ == "__main__":
    main()
