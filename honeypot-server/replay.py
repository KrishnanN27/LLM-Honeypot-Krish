import json
import time
import argparse
from datetime import datetime

def load_events(filename, session_id=None):
    events = []

    with open(filename, "r") as f:
        for line in f:
            try:
                entry = json.loads(line)
            except:
                continue

            if session_id and entry.get("session") != session_id:
                continue

            events.append(entry)

    # Sort by timestamp just in case
    events.sort(key=lambda e: e["ts"])
    return events


def replay(events, realtime=True):
    if not events:
        print("No events to replay.")
        return

    print("\n--- REPLAY START ---\n")

    prev_time = None

    for e in events:
        ts = e["ts"]
        cmd = e["cmd"]
        resp = e["resp"]
        delta_ms = e.get("delta_ms", 0)
        session = e.get("session")

        # Real-time timing simulation
        if realtime and delta_ms > 0:
            time.sleep(delta_ms / 1000.0)

        prompt = f"{session}@honeypot$ "
        print(prompt + cmd)
        print(resp)

    print("\n--- REPLAY END ---\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Replay honeypot session logs.")
    parser.add_argument("logfile", help="Path to JSONL honeypot log file")
    parser.add_argument("--session", help="Replay only this session ID", default=None)
    parser.add_argument("--fast", action="store_true", help="Skip real-time delays")

    args = parser.parse_args()
    events = load_events(args.logfile, args.session)

    replay(events, realtime=not args.fast)
