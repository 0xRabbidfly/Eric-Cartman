"""
Minimal test client for Anthropic Managed Agents API.

Creates a session, streams events, sends a user message, and
prints agent responses as they arrive.

Usage:
    set ANTHROPIC_API_KEY=sk-ant-...
    python test_managed_agent.py
    python test_managed_agent.py "What can you help me with?"
"""

import sys
import os
import threading
from pathlib import Path

from dotenv import load_dotenv
import anthropic

# Load .env from repo root
load_dotenv(Path(__file__).resolve().parents[2] / ".env")

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
AGENT_ID = "agent_011CZxGWACDQfTpzVc7L3ZgC"
ENVIRONMENT_ID = "env_01MF357PP3PYeFAgbUY9hQBk"

USER_MESSAGE = sys.argv[1] if len(sys.argv) > 1 else "Hello! What can you do?"


def main():
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("Error: ANTHROPIC_API_KEY environment variable is not set.", file=sys.stderr)
        sys.exit(1)

    client = anthropic.Anthropic(api_key=api_key)

    # 1. Create a session
    print(f"Creating session (agent={AGENT_ID})...")
    session = client.beta.sessions.create(
        agent=AGENT_ID,
        environment_id=ENVIRONMENT_ID,
    )
    session_id = session.id
    print(f"Session created: {session_id}")

    # 2. Open the event stream in a background thread
    done = threading.Event()
    error_holder = [None]

    def stream_events():
        try:
            with client.beta.sessions.events.stream(session_id) as stream:
                for event in stream:
                    handle_event(event, done)
                    if done.is_set():
                        break
        except Exception as exc:
            error_holder[0] = exc
            done.set()

    stream_thread = threading.Thread(target=stream_events, daemon=True)
    stream_thread.start()

    # 3. Send a user message
    print(f"\n> {USER_MESSAGE}\n")
    client.beta.sessions.events.send(
        session_id,
        events=[
            {
                "type": "user.message",
                "content": [{"type": "text", "text": USER_MESSAGE}],
            }
        ],
    )

    # 4. Wait for the agent to finish (idle) or error out
    done.wait(timeout=120)

    if error_holder[0]:
        print(f"\nStream error: {error_holder[0]}", file=sys.stderr)
        sys.exit(1)

    print("\n--- Session complete ---")


def handle_event(event, done_event: threading.Event):
    """Route each streamed event to the right handler."""
    etype = getattr(event, "type", None)

    if etype == "agent.message":
        # Print each text block as it arrives
        for block in event.content:
            if getattr(block, "type", None) == "text":
                print(block.text, end="", flush=True)
        print()  # newline after full message

    elif etype == "agent.thinking":
        # Optional: show thinking indicator
        pass

    elif etype == "agent.tool_use":
        tool_name = getattr(event, "name", "unknown")
        print(f"  [tool call: {tool_name}]")

    elif etype == "agent.tool_result":
        pass  # tool results handled internally

    elif etype == "session.status_idle":
        done_event.set()

    elif etype == "session.error":
        error_msg = getattr(event, "error", "unknown error")
        print(f"\nAgent error: {error_msg}", file=sys.stderr)
        done_event.set()

    elif etype == "session.status_terminated":
        print("\nSession terminated.", file=sys.stderr)
        done_event.set()

    else:
        # Uncomment for debugging unknown events:
        # print(f"  [{etype}]", file=sys.stderr)
        pass


if __name__ == "__main__":
    main()
