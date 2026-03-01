"""
File system watcher for automatic codemap updates.
"""
import os
import time
import threading
from collections import defaultdict
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import logging

logger = logging.getLogger(__name__)


class CodeFileHandler(FileSystemEventHandler):
    """Handler for code file changes."""

    def __init__(self, root_dir: str, on_files_changed):
        """
        Initialize the handler.

        Args:
            root_dir: Project root directory
            on_files_changed: Callback(changed_files: list) called after debounce
        """
        self.root_dir = root_dir
        self.on_files_changed = on_files_changed
        self.pending_changes = set()
        self.debounce_timer = None
        self.debounce_delay = 2.0  # seconds
        self.lock = threading.Lock()

        # Supported extensions
        self.supported_exts = {'.py', '.js', '.jsx', '.ts', '.tsx'}

    def on_modified(self, event):
        """Handle file modification events."""
        if event.is_directory:
            return

        self._handle_change(event.src_path)

    def on_created(self, event):
        """Handle file creation events."""
        if event.is_directory:
            return

        self._handle_change(event.src_path)

    def _handle_change(self, file_path: str):
        """Handle a file change with debouncing."""
        # Check if it's a supported file type
        ext = os.path.splitext(file_path)[1].lower()
        if ext not in self.supported_exts:
            return

        # Get relative path
        try:
            rel_path = os.path.relpath(file_path, self.root_dir)
        except ValueError:
            # File is outside project root
            return

        with self.lock:
            # Add to pending changes
            self.pending_changes.add(rel_path)

            # Cancel existing timer
            if self.debounce_timer:
                self.debounce_timer.cancel()

            # Start new timer
            self.debounce_timer = threading.Timer(
                self.debounce_delay,
                self._process_changes
            )
            self.debounce_timer.start()

    def _process_changes(self):
        """Process accumulated changes after debounce period."""
        with self.lock:
            if not self.pending_changes:
                return

            changed_files = list(self.pending_changes)
            self.pending_changes.clear()

        logger.info(f"Processing {len(changed_files)} changed files")

        # Call the callback
        try:
            self.on_files_changed(changed_files)
        except Exception as e:
            logger.error(f"Error processing file changes: {e}")


class FileWatcher:
    """File system watcher for code changes."""

    def __init__(self, root_dir: str, on_files_changed):
        """
        Initialize the watcher.

        Args:
            root_dir: Project root directory to watch
            on_files_changed: Callback(changed_files: list) for updates
        """
        self.root_dir = root_dir
        self.on_files_changed = on_files_changed
        self.observer = None
        self.handler = None

    def start(self):
        """Start watching the directory."""
        if self.observer:
            # Already running
            return

        logger.info(f"Starting file watcher for {self.root_dir}")

        # Create handler
        self.handler = CodeFileHandler(self.root_dir, self.on_files_changed)

        # Create and start observer
        self.observer = Observer()
        self.observer.schedule(self.handler, self.root_dir, recursive=True)
        self.observer.start()

    def stop(self):
        """Stop watching the directory."""
        if not self.observer:
            return

        logger.info("Stopping file watcher")

        self.observer.stop()
        self.observer.join(timeout=5)
        self.observer = None
        self.handler = None

    def is_running(self) -> bool:
        """Check if watcher is running."""
        return self.observer is not None and self.observer.is_alive()
