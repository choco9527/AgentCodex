import sys
import os
from pathlib import Path

# Add project root to path to allow importing codex_client
project_root = Path(os.path.abspath(__file__)).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from codex_client import CodexClient, normalize_sessions, get_codex_home

class SessionExtractor:
    """Utility class to extract and parse Codex App session data using CodexClient."""

    def __init__(self):
        self.codex_home = get_codex_home()

    def list_sessions(self, limit=10):
        """List recent sessions by reusing CodexClient logic."""
        try:
            with CodexClient() as client:
                summaries = client.list_sessions()
                return normalize_sessions(summaries)[:limit]
        except Exception as e:
            print(f"Error listing sessions: {e}")
            return []

    def get_session_content(self, thread_id):
        """Get detailed content of a session by its thread ID."""
        try:
            with CodexClient() as client:
                data = client.get_session(thread_id)
                # Return a simplified representation or raw data keys
                if isinstance(data, dict):
                    return f"Session {thread_id} retrieved. Data keys: {list(data.keys())}"
                return f"Session {thread_id} retrieved."
        except Exception as e:
            return f"Error reading session {thread_id}: {str(e)}"

if __name__ == "__main__":
    extractor = SessionExtractor()
    sessions = extractor.list_sessions(limit=5)
    print(f"Found {len(sessions)} sessions:")
    for s in sessions:
        # Handle both dict and SessionSummary object formats
        if isinstance(s, dict):
            tid = s.get('thread_id') or s.get('uuid', 'N/A')
            print(f"- {s.get('title', 'Untitled')} (ID: {tid[:8]}...)")
        else:
            tid = getattr(s, 'thread_id', None) or getattr(s, 'uuid', 'N/A')
            print(f"- {getattr(s, 'title', 'Untitled')} (ID: {str(tid)[:8]}...)")
