"""
Application State Management
Singleton state object for the CodeNav server.
"""
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class AppState:
    """Application state singleton."""
    project_root: Optional[str] = None
    codemap: Optional[dict] = None
    faiss_index: Optional[object] = None  # faiss.Index
    index_metadata: Optional[list] = None
    index_status: str = "idle"  # idle, indexing, ready, error
    index_progress: int = 0
    conversation_history: list = field(default_factory=list)

    def reset(self):
        """Reset all state."""
        self.project_root = None
        self.codemap = None
        self.faiss_index = None
        self.index_metadata = None
        self.index_status = "idle"
        self.index_progress = 0
        self.conversation_history = []


# Singleton instance
app_state = AppState()
