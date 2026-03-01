/**
 * HTTP client for communicating with CodeNav FastAPI server.
 */
import * as vscode from 'vscode';

export interface HealthResponse {
    status: string;
    version: string;
    project_root: string | null;
    index_status: string;
}

export interface ProjectOpenResponse {
    success: boolean;
    path: string;
    name: string;
}

export interface IndexStatusResponse {
    status: string;
    progress: number;
    function_count: number;
    file_count: number;
}

export interface SearchResult {
    qualified_name: string;
    file: string;
    name: string;
    line_start: number;
    line_end: number;
    score: number;
}

export interface SearchResponse {
    results: SearchResult[];
    count: number;
}

export interface AgentIteration {
    iteration: number;
    max_iterations: number;
    thinking: string | null;
    tool_call: {
        name: string;
        params: any;
    } | null;
    tool_result: string | null;
}

export interface AgentQueryResponse {
    status: string;
    response?: string;
    question?: string;
    tool_calls_made: Array<{
        tool: string;
        params: any;
        result: string;
    }>;
    tokens_used: number;
    iterations?: AgentIteration[];
}

export interface Session {
    session_id: string;
    task: string;
    project_root: string;
    status: string;
    created_at: string;
    updated_at: string;
    message_count: number;
    tool_call_count: number;
}

export interface SessionListResponse {
    sessions: Session[];
    count: number;
}

export interface AgentTask {
    task_id: string;
    description: string;
    session_id?: string;
    status: string;
    progress: number;
    current_step?: string;
    created_at: string;
    started_at?: string;
    completed_at?: string;
    result?: any;
    error?: string;
}

export interface TaskListResponse {
    tasks: AgentTask[];
    count: number;
}

export class ApiClient {
    private baseUrl: string;
    private timeout: number = 30000; // 30 seconds

    constructor(baseUrl: string) {
        this.baseUrl = baseUrl;
    }

    /**
     * Make HTTP request with timeout.
     */
    private async request<T>(
        endpoint: string,
        options: RequestInit = {}
    ): Promise<T> {
        const url = `${this.baseUrl}${endpoint}`;

        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), this.timeout);

        try {
            const response = await fetch(url, {
                ...options,
                signal: controller.signal,
                headers: {
                    'Content-Type': 'application/json',
                    ...options.headers
                }
            });

            clearTimeout(timeoutId);

            if (!response.ok) {
                const error = await response.text();
                throw new Error(`HTTP ${response.status}: ${error}`);
            }

            return await response.json() as T;

        } catch (error) {
            clearTimeout(timeoutId);

            if (error instanceof Error) {
                if (error.name === 'AbortError') {
                    throw new Error('Request timed out');
                }
                throw error;
            }
            throw new Error(String(error));
        }
    }

    /**
     * Check server health.
     */
    public async health(): Promise<HealthResponse> {
        return this.request<HealthResponse>('/health');
    }

    /**
     * Open a project.
     */
    public async openProject(path: string): Promise<ProjectOpenResponse> {
        return this.request<ProjectOpenResponse>('/project/open', {
            method: 'POST',
            body: JSON.stringify({ path })
        });
    }

    /**
     * Start indexing the project.
     */
    public async startIndexing(): Promise<{ status: string; message: string }> {
        return this.request('/index/start', { method: 'POST' });
    }

    /**
     * Get indexing status.
     */
    public async getIndexStatus(): Promise<IndexStatusResponse> {
        return this.request<IndexStatusResponse>('/index/status');
    }

    /**
     * Search for functions.
     */
    public async search(query: string, topK: number = 5): Promise<SearchResponse> {
        const params = new URLSearchParams({
            query,
            top_k: topK.toString()
        });
        return this.request<SearchResponse>(`/search?${params}`);
    }

    /**
     * Retrieve context for a task.
     */
    public async retrieveContext(
        task: string,
        depth: number = 2,
        maxTokens: number = 2000
    ): Promise<any> {
        const params = new URLSearchParams({
            task,
            depth: depth.toString(),
            max_tokens: maxTokens.toString()
        });
        return this.request(`/context/retrieve?${params}`, { method: 'POST' });
    }

    /**
     * Execute agent query.
     */
    public async agentQuery(
        task: string,
        maxIterations: number = 10,
        maxTokens: number = 2048
    ): Promise<AgentQueryResponse> {
        const params = new URLSearchParams({
            task,
            max_iterations: maxIterations.toString(),
            max_tokens: maxTokens.toString()
        });
        return this.request<AgentQueryResponse>(`/agent/query?${params}`, {
            method: 'POST'
        });
    }

    /**
     * Health check endpoint.
     */
    public async healthCheck(): Promise<any> {
        return this.request('/health');
    }

    /**
     * Create a task plan for complex requests.
     */
    public async createTaskPlan(task: string): Promise<any> {
        const params = new URLSearchParams({ task });
        return this.request(`/agent/plan?${params}`, {
            method: 'POST'
        });
    }

    /**
     * List sessions.
     */
    public async listSessions(): Promise<SessionListResponse> {
        return this.request<SessionListResponse>('/sessions');
    }

    /**
     * Get session details.
     */
    public async getSession(sessionId: string): Promise<any> {
        return this.request(`/sessions/${sessionId}`);
    }

    /**
     * Delete session.
     */
    public async deleteSession(sessionId: string): Promise<{ success: boolean }> {
        return this.request(`/sessions/${sessionId}`, { method: 'DELETE' });
    }

    /**
     * Clear all sessions.
     */
    public async clearSessions(): Promise<{ success: boolean; deleted_count: number }> {
        return this.request('/sessions', { method: 'DELETE' });
    }

    /**
     * Submit background task.
     */
    public async submitTask(
        task: string,
        maxIterations: number = 10,
        maxTokens: number = 2048
    ): Promise<{ task_id: string; session_id: string; status: string }> {
        const params = new URLSearchParams({
            task,
            max_iterations: maxIterations.toString(),
            max_tokens: maxTokens.toString()
        });
        return this.request(`/tasks/submit?${params}`, { method: 'POST' });
    }

    /**
     * Get task status.
     */
    public async getTask(taskId: string): Promise<AgentTask> {
        return this.request<AgentTask>(`/tasks/${taskId}`);
    }

    /**
     * List tasks.
     */
    public async listTasks(
        status?: string,
        sessionId?: string
    ): Promise<TaskListResponse> {
        const params = new URLSearchParams();
        if (status) {
            params.append('status', status);
        }
        if (sessionId) {
            params.append('session_id', sessionId);
        }

        const query = params.toString();
        return this.request<TaskListResponse>(`/tasks${query ? '?' + query : ''}`);
    }

    /**
     * Cancel task.
     */
    public async cancelTask(taskId: string): Promise<{ success: boolean }> {
        return this.request(`/tasks/${taskId}`, { method: 'DELETE' });
    }

    /**
     * Read file.
     */
    public async readFile(path: string): Promise<{
        content: string;
        language: string;
        line_count: number;
        size_bytes: number;
    }> {
        const params = new URLSearchParams({ path });
        return this.request(`/files/read?${params}`);
    }

    /**
     * Write file.
     */
    public async writeFile(
        path: string,
        content: string
    ): Promise<{ success: boolean; line_count: number }> {
        return this.request('/files/write', {
            method: 'POST',
            body: JSON.stringify({ path, content })
        });
    }

    /**
     * Apply diff to file.
     */
    public async applyDiff(
        path: string,
        original: string,
        modified: string
    ): Promise<{ success: boolean; diff: string }> {
        return this.request('/files/apply_diff', {
            method: 'POST',
            body: JSON.stringify({ path, original, modified })
        });
    }

    /**
     * Update base URL.
     */
    public setBaseUrl(baseUrl: string): void {
        this.baseUrl = baseUrl;
    }

    /**
     * Set request timeout.
     */
    public setTimeout(timeout: number): void {
        this.timeout = timeout;
    }
}
