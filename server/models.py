"""
Pydantic models for request/response validation.
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any


class ProjectOpenRequest(BaseModel):
    """Request to open a project."""
    path: str = Field(..., description="Absolute path to project directory")


class ProjectOpenResponse(BaseModel):
    """Response after opening a project."""
    success: bool
    path: Optional[str] = None
    name: Optional[str] = None
    error: Optional[str] = None


class FileNode(BaseModel):
    """A node in the file tree."""
    name: str
    path: str  # Relative to project root
    type: str  # "file" or "dir"
    children: List['FileNode'] = Field(default_factory=list)


class FileReadResponse(BaseModel):
    """Response from reading a file."""
    content: str
    language: str
    line_count: int
    size_bytes: int


class FileWriteRequest(BaseModel):
    """Request to write a file."""
    path: str
    content: str


class FileWriteResponse(BaseModel):
    """Response after writing a file."""
    success: bool
    line_count: int
    error: Optional[str] = None


class ApplyDiffRequest(BaseModel):
    """Request to apply a diff to a file."""
    path: str
    original: str
    modified: str


class ApplyDiffResponse(BaseModel):
    """Response after applying a diff."""
    success: bool
    diff: Optional[str] = None
    error: Optional[str] = None


class AgentQueryRequest(BaseModel):
    """Request to execute agent for a task."""
    task: str = Field(..., description="User's task description")
    max_iterations: int = Field(default=10, description="Maximum agent turns")
    max_tokens: int = Field(default=2048, description="Maximum tokens per LLM call")


class ToolCallRecord(BaseModel):
    """Record of a tool call made by the agent."""
    tool: str
    params: Dict[str, Any]
    result: str


class AgentQueryResponse(BaseModel):
    """Response from agent execution."""
    status: str = Field(..., description="Status: complete, needs_input, max_iterations, error")
    response: Optional[str] = None
    question: Optional[str] = None  # For needs_input status
    tool_calls_made: List[ToolCallRecord] = Field(default_factory=list)
    tokens_used: int = 0


# Enable forward references for recursive models
FileNode.model_rebuild()
