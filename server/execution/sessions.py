"""
Session persistence for agent conversations.
"""
import os
import json
import logging
from typing import Optional, Dict, List
from datetime import datetime
import uuid

logger = logging.getLogger(__name__)


class AgentSession:
    """Represents a persistent agent session."""

    def __init__(
        self,
        session_id: str,
        task: str,
        project_root: str,
        created_at: Optional[str] = None
    ):
        """
        Initialize agent session.

        Args:
            session_id: Unique session ID
            task: Original task description
            project_root: Project root directory
            created_at: ISO timestamp of creation
        """
        self.session_id = session_id
        self.task = task
        self.project_root = project_root
        self.created_at = created_at or datetime.utcnow().isoformat()
        self.updated_at = datetime.utcnow().isoformat()
        self.status = "active"  # active, complete, error, paused
        self.messages: List[Dict] = []
        self.tool_calls: List[Dict] = []
        self.metadata: Dict = {}

    def add_message(self, role: str, content: str):
        """
        Add a message to the session.

        Args:
            role: Message role (user, assistant, system)
            content: Message content
        """
        self.messages.append({
            "role": role,
            "content": content,
            "timestamp": datetime.utcnow().isoformat()
        })
        self.updated_at = datetime.utcnow().isoformat()

    def add_tool_call(self, tool_name: str, params: Dict, result: str):
        """
        Record a tool call.

        Args:
            tool_name: Name of the tool
            params: Tool parameters
            result: Tool result
        """
        self.tool_calls.append({
            "tool": tool_name,
            "params": params,
            "result": result,
            "timestamp": datetime.utcnow().isoformat()
        })
        self.updated_at = datetime.utcnow().isoformat()

    def set_status(self, status: str):
        """
        Update session status.

        Args:
            status: New status
        """
        self.status = status
        self.updated_at = datetime.utcnow().isoformat()

    def to_dict(self) -> Dict:
        """Convert session to dictionary."""
        return {
            "session_id": self.session_id,
            "task": self.task,
            "project_root": self.project_root,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "status": self.status,
            "messages": self.messages,
            "tool_calls": self.tool_calls,
            "metadata": self.metadata
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "AgentSession":
        """Create session from dictionary."""
        session = cls(
            session_id=data["session_id"],
            task=data["task"],
            project_root=data["project_root"],
            created_at=data.get("created_at")
        )
        session.updated_at = data.get("updated_at", session.updated_at)
        session.status = data.get("status", "active")
        session.messages = data.get("messages", [])
        session.tool_calls = data.get("tool_calls", [])
        session.metadata = data.get("metadata", {})
        return session


class SessionManager:
    """Manages agent sessions with persistence."""

    def __init__(self, sessions_dir: Optional[str] = None):
        """
        Initialize session manager.

        Args:
            sessions_dir: Directory to store sessions (default: ~/.codenav/sessions)
        """
        if sessions_dir is None:
            sessions_dir = os.path.join(
                os.path.expanduser("~"),
                ".codenav",
                "sessions"
            )

        self.sessions_dir = sessions_dir
        os.makedirs(self.sessions_dir, exist_ok=True)

        # In-memory cache
        self.sessions: Dict[str, AgentSession] = {}

        logger.info(f"Session manager initialized: {self.sessions_dir}")

    def create_session(self, task: str, project_root: str) -> AgentSession:
        """
        Create a new session.

        Args:
            task: Task description
            project_root: Project root directory

        Returns:
            AgentSession
        """
        session_id = str(uuid.uuid4())
        session = AgentSession(session_id, task, project_root)

        self.sessions[session_id] = session
        self._save_session(session)

        logger.info(f"Created session {session_id}")

        return session

    def get_session(self, session_id: str) -> Optional[AgentSession]:
        """
        Get a session by ID.

        Args:
            session_id: Session ID

        Returns:
            AgentSession or None
        """
        # Check cache first
        if session_id in self.sessions:
            return self.sessions[session_id]

        # Try to load from disk
        session = self._load_session(session_id)
        if session:
            self.sessions[session_id] = session

        return session

    def update_session(self, session: AgentSession):
        """
        Update a session.

        Args:
            session: Session to update
        """
        self.sessions[session.session_id] = session
        self._save_session(session)

    def delete_session(self, session_id: str):
        """
        Delete a session.

        Args:
            session_id: Session ID
        """
        # Remove from cache
        self.sessions.pop(session_id, None)

        # Remove from disk
        session_file = self._get_session_path(session_id)
        if os.path.exists(session_file):
            os.remove(session_file)
            logger.info(f"Deleted session {session_id}")

    def list_sessions(self, project_root: Optional[str] = None) -> List[Dict]:
        """
        List all sessions.

        Args:
            project_root: Filter by project root (optional)

        Returns:
            List of session summaries
        """
        sessions = []

        # List all session files
        for filename in os.listdir(self.sessions_dir):
            if not filename.endswith(".json"):
                continue

            session_id = filename[:-5]  # Remove .json
            session = self.get_session(session_id)

            if session:
                # Filter by project_root if specified
                if project_root and session.project_root != project_root:
                    continue

                sessions.append({
                    "session_id": session.session_id,
                    "task": session.task,
                    "project_root": session.project_root,
                    "status": session.status,
                    "created_at": session.created_at,
                    "updated_at": session.updated_at,
                    "message_count": len(session.messages),
                    "tool_call_count": len(session.tool_calls)
                })

        # Sort by updated_at (most recent first)
        sessions.sort(key=lambda s: s["updated_at"], reverse=True)

        return sessions

    def get_latest_session(self, project_root: str) -> Optional[AgentSession]:
        """
        Get the most recent session for a project.

        Args:
            project_root: Project root directory

        Returns:
            AgentSession or None
        """
        sessions = self.list_sessions(project_root)

        if sessions:
            return self.get_session(sessions[0]["session_id"])

        return None

    def _get_session_path(self, session_id: str) -> str:
        """Get file path for a session."""
        return os.path.join(self.sessions_dir, f"{session_id}.json")

    def _save_session(self, session: AgentSession):
        """Save session to disk."""
        session_file = self._get_session_path(session.session_id)

        try:
            with open(session_file, 'w', encoding='utf-8') as f:
                json.dump(session.to_dict(), f, indent=2)

            logger.debug(f"Saved session {session.session_id}")

        except Exception as e:
            logger.error(f"Error saving session {session.session_id}: {e}")

    def _load_session(self, session_id: str) -> Optional[AgentSession]:
        """Load session from disk."""
        session_file = self._get_session_path(session_id)

        if not os.path.exists(session_file):
            return None

        try:
            with open(session_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            session = AgentSession.from_dict(data)

            logger.debug(f"Loaded session {session_id}")

            return session

        except Exception as e:
            logger.error(f"Error loading session {session_id}: {e}")
            return None


# Global session manager instance
_session_manager: Optional[SessionManager] = None


def get_session_manager() -> SessionManager:
    """Get the global session manager instance."""
    global _session_manager

    if _session_manager is None:
        _session_manager = SessionManager()

    return _session_manager
