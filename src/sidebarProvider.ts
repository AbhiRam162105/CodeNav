/**
 * Sidebar WebView Provider for CodeNav chat interface.
 */
import * as vscode from 'vscode';
import { ApiClient } from './apiClient';

export class CodeNavSidebarProvider implements vscode.WebviewViewProvider {
    public static readonly viewType = 'codenav.chatView';
    private _view?: vscode.WebviewView;
    private outputChannel: vscode.OutputChannel;
    private indexStatusInterval?: NodeJS.Timeout;

    constructor(
        private readonly _extensionUri: vscode.Uri,
        private apiClient: ApiClient,
        outputChannel: vscode.OutputChannel
    ) {
        this.outputChannel = outputChannel;
    }

    public resolveWebviewView(
        webviewView: vscode.WebviewView,
        context: vscode.WebviewViewResolveContext,
        _token: vscode.CancellationToken,
    ) {
        this._view = webviewView;

        webviewView.webview.options = {
            enableScripts: true,
            localResourceRoots: [this._extensionUri]
        };

        webviewView.webview.html = this._getHtmlForWebview(webviewView.webview);

        // Handle messages from the webview
        webviewView.webview.onDidReceiveMessage(async (data) => {
            switch (data.type) {
                case 'askAgent':
                    await this.handleAskAgent(data.message);
                    break;
                case 'loadSessions':
                    await this.loadSessions();
                    break;
                case 'loadSession':
                    await this.loadSession(data.sessionId);
                    break;
                case 'deleteSession':
                    await this.deleteSession(data.sessionId);
                    break;
                case 'clearSessions':
                    await this.clearAllSessions();
                    break;
                case 'getIndexStatus':
                    await this.updateIndexStatus();
                    break;
                case 'startPolling':
                    this.startIndexStatusPolling();
                    break;
                case 'stopPolling':
                    this.stopIndexStatusPolling();
                    break;
            }
        });

        // Start polling for index status
        this.startIndexStatusPolling();
    }

    private startIndexStatusPolling() {
        // Stop existing interval if any
        this.stopIndexStatusPolling();

        // Update immediately
        this.updateIndexStatus();

        // Poll every 2 seconds
        this.indexStatusInterval = setInterval(() => {
            this.updateIndexStatus();
        }, 2000);
    }
    private stopIndexStatusPolling() {
        if (this.indexStatusInterval) {
            clearInterval(this.indexStatusInterval);
            this.indexStatusInterval = undefined;
        }
    }

    private async updateIndexStatus() {
        try {
            const status = await this.apiClient.getIndexStatus();
            this._view?.webview.postMessage({
                type: 'indexStatus',
                status: status.status,
                progress: status.progress,
                functionCount: status.function_count,
                fileCount: status.file_count
            });

            // Stop polling if indexing is complete or errored
            if (status.status === 'ready' || status.status === 'error') {
                this.stopIndexStatusPolling();
            }
        } catch (error) {
            // Silently fail - server might not be ready yet
        }
    }

    public dispose() {
        this.stopIndexStatusPolling();
    }

    private async handleAskAgent(message: string) {
        if (!message.trim()) {
            return;
        }

        // Show loading in webview
        this._view?.webview.postMessage({
            type: 'agentThinking',
            message: 'Thinking...'
        });

        try {
            const config = vscode.workspace.getConfiguration('codenav');
            const maxIterations = config.get<number>('maxIterations', 10);
            const maxTokens = config.get<number>('maxTokens', 2048);

            const response = await this.apiClient.agentQuery(message, maxIterations, maxTokens);

            // Send response to webview
            this._view?.webview.postMessage({
                type: 'agentResponse',
                response: response.response,
                status: response.status,
                tokensUsed: response.tokens_used,
                toolCalls: response.tool_calls_made.length,
                iterations: response.iterations || []
            });

            // Also log to output
            this.outputChannel.appendLine('\n━━━ Agent Response ━━━');
            this.outputChannel.appendLine(`Task: ${message}`);
            this.outputChannel.appendLine(`Status: ${response.status}`);
            this.outputChannel.appendLine(`Tokens: ${response.tokens_used}`);
            this.outputChannel.appendLine(`\nResponse:\n${response.response}`);

        } catch (error) {
            const errorMessage = error instanceof Error ? error.message : String(error);
            this._view?.webview.postMessage({
                type: 'agentError',
                error: errorMessage
            });
            vscode.window.showErrorMessage(`Agent error: ${errorMessage}`);
        }
    }

    private async loadSessions() {
        try {
            const sessions = await this.apiClient.listSessions();
            this._view?.webview.postMessage({
                type: 'sessionsLoaded',
                sessions: sessions.sessions
            });
        } catch (error) {
            const errorMessage = error instanceof Error ? error.message : String(error);
            vscode.window.showErrorMessage(`Failed to load sessions: ${errorMessage}`);
        }
    }

    private async loadSession(sessionId: string) {
        try {
            const session = await this.apiClient.getSession(sessionId);
            this._view?.webview.postMessage({
                type: 'sessionLoaded',
                session: session
            });
        } catch (error) {
            const errorMessage = error instanceof Error ? error.message : String(error);
            vscode.window.showErrorMessage(`Failed to load session: ${errorMessage}`);
        }
    }

    private async deleteSession(sessionId: string) {
        try {
            await this.apiClient.deleteSession(sessionId);
            await this.loadSessions(); // Refresh list
            vscode.window.showInformationMessage('Session deleted');
        } catch (error) {
            const errorMessage = error instanceof Error ? error.message : String(error);
            vscode.window.showErrorMessage(`Failed to delete session: ${errorMessage}`);
        }
    }

    private async clearAllSessions() {
        try {
            await this.apiClient.clearSessions();
            this._view?.webview.postMessage({
                type: 'sessionsCleared'
            });
            vscode.window.showInformationMessage('All sessions cleared');
        } catch (error) {
            const errorMessage = error instanceof Error ? error.message : String(error);
            vscode.window.showErrorMessage(`Failed to clear sessions: ${errorMessage}`);
        }
    }

    private _getHtmlForWebview(webview: vscode.Webview) {
        const styleResetUri = webview.asWebviewUri(
            vscode.Uri.joinPath(this._extensionUri, 'media', 'reset.css')
        );
        const styleVSCodeUri = webview.asWebviewUri(
            vscode.Uri.joinPath(this._extensionUri, 'media', 'vscode.css')
        );
        const styleMainUri = webview.asWebviewUri(
            vscode.Uri.joinPath(this._extensionUri, 'media', 'main.css')
        );

        const nonce = getNonce();

        return `<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src ${webview.cspSource} 'unsafe-inline' https://cdn.jsdelivr.net; script-src 'nonce-${nonce}' 'unsafe-eval' https://cdn.jsdelivr.net; img-src ${webview.cspSource} data: https:; connect-src https:;">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link href="${styleResetUri}" rel="stylesheet">
    <link href="${styleVSCodeUri}" rel="stylesheet">
    <link href="${styleMainUri}" rel="stylesheet">
    <title>CodeNav Chat</title>
    <!-- Markdown and Mermaid support -->
    <script nonce="${nonce}" src="https://cdn.jsdelivr.net/npm/marked@11.1.0/marked.min.js"></script>
    <script nonce="${nonce}" src="https://cdn.jsdelivr.net/npm/mermaid@10.6.1/dist/mermaid.min.js"></script>
</head>
<body>
    <div class="container">
        <div class="header">
            <h2>CodeNav Agent</h2>
            <div class="header-actions">
                <button id="sessionsBtn" class="icon-button" title="Sessions">📋</button>
                <button id="clearBtn" class="icon-button" title="Clear chat">🗑️</button>
            </div>
        </div>

        <div id="indexStatus" class="index-status hidden">
            <div class="status-icon">⚙️</div>
            <div class="status-text">
                <div id="statusMessage">Checking status...</div>
                <div id="statusDetails"></div>
            </div>
        </div>

        <div id="fileEditsPanel" class="file-edits-panel hidden">
            <div class="file-edits-header">
                <span>📝 Files Modified</span>
                <button id="closeFileEditsBtn">✕</button>
            </div>
            <div id="fileEditsList" class="file-edits-list"></div>
        </div>

        <div id="chatContainer" class="chat-container"></div>

        <div class="input-container">
            <textarea id="messageInput" placeholder="Ask CodeNav..." rows="3"></textarea>
            <button id="sendBtn" class="send-button">Send</button>
        </div>

        <div id="sessionsPanel" class="sessions-panel hidden">
            <div class="sessions-header">
                <h3>Sessions</h3>
                <button id="closeSessionsBtn">✕</button>
            </div>
            <div id="sessionsList" class="sessions-list"></div>
        </div>
    </div>

    <script nonce="${nonce}">
        const vscode = acquireVsCodeApi();
        const chatContainer = document.getElementById('chatContainer');
        const messageInput = document.getElementById('messageInput');
        const sendBtn = document.getElementById('sendBtn');
        const sessionsBtn = document.getElementById('sessionsBtn');
        const clearBtn = document.getElementById('clearBtn');
        const sessionsPanel = document.getElementById('sessionsPanel');
        const closeSessionsBtn = document.getElementById('closeSessionsBtn');
        const sessionsList = document.getElementById('sessionsList');
        const indexStatus = document.getElementById('indexStatus');
        const statusMessage = document.getElementById('statusMessage');
        const statusDetails = document.getElementById('statusDetails');

        let messages = [];
        let currentIndexStatus = 'idle';
        let editedFiles = new Set();
        let liveThinkingDiv = null;
        let mermaidReady = false;
        let markedReady = false;

        // Wait for libraries to load and initialize
        function initializeLibraries() {
            // Initialize Mermaid
            if (typeof mermaid !== 'undefined' && !mermaidReady) {
                try {
                    mermaid.initialize({
                        startOnLoad: false,
                        theme: 'dark',
                        securityLevel: 'loose',
                        fontFamily: 'var(--vscode-font-family)'
                    });
                    mermaidReady = true;
                    console.log('Mermaid initialized');
                } catch (e) {
                    console.error('Mermaid init error:', e);
                }
            }

            // Configure marked
            if (typeof marked !== 'undefined' && !markedReady) {
                try {
                    marked.setOptions({
                        breaks: true,
                        gfm: true,
                        highlight: function(code, lang) {
                            return code; // Basic highlighting
                        }
                    });
                    markedReady = true;
                    console.log('Marked initialized');
                } catch (e) {
                    console.error('Marked init error:', e);
                }
            }
        }

        // Try to initialize immediately and retry if needed
        initializeLibraries();
        setTimeout(initializeLibraries, 500);
        setTimeout(initializeLibraries, 1000);

        // Render markdown with Mermaid support
        function renderMarkdown(text) {
            if (!markedReady || typeof marked === 'undefined') {
                console.log('Marked not ready, returning plain text');
                // Convert line breaks at least
                return text.replace(/\n/g, '<br>');
            }

            try {
                // Convert markdown to HTML
                let html = marked.parse(text);
                return html;
            } catch (e) {
                console.error('Markdown parsing error:', e);
                return text.replace(/\n/g, '<br>');
            }
        }

        // Process Mermaid diagrams after rendering
        function processMermaidDiagrams(element) {
            if (typeof mermaid === 'undefined') {
                console.log('Mermaid not loaded yet');
                return;
            }

            // Find all code blocks that might contain mermaid
            const codeBlocks = element.querySelectorAll('pre code');
            codeBlocks.forEach((block, index) => {
                const code = block.textContent || '';
                // Check if it's a mermaid diagram (starts with graph, sequenceDiagram, etc.)
                if (code.trim().match(/^(graph|sequenceDiagram|classDiagram|stateDiagram|erDiagram|gantt|pie|flowchart|gitGraph)/)) {
                    const id = 'mermaid-' + Date.now() + '-' + index;
                    const div = document.createElement('div');
                    div.className = 'mermaid';
                    div.id = id;
                    div.textContent = code;

                    // Replace the pre element
                    const pre = block.closest('pre');
                    if (pre) {
                        pre.replaceWith(div);
                    }
                }
            });

            // Render all mermaid diagrams
            try {
                mermaid.run({
                    querySelector: '.mermaid:not([data-processed])',
                    suppressErrors: false
                }).then(() => {
                    // Mark as processed
                    element.querySelectorAll('.mermaid').forEach(el => {
                        el.setAttribute('data-processed', 'true');
                    });
                }).catch(err => {
                    console.error('Mermaid rendering error:', err);
                });
            } catch (err) {
                console.error('Mermaid error:', err);
            }
        }

        // Send message
        function sendMessage() {
            const message = messageInput.value.trim();
            if (!message) return;

            // Add user message to chat
            addMessage('user', message);
            messageInput.value = '';

            // Send to extension
            vscode.postMessage({
                type: 'askAgent',
                message: message
            });
        }

        sendBtn.addEventListener('click', sendMessage);
        messageInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                sendMessage();
            }
        });

        // Clear chat
        clearBtn.addEventListener('click', () => {
            messages = [];
            chatContainer.innerHTML = '';
        });

        // Sessions panel
        sessionsBtn.addEventListener('click', () => {
            sessionsPanel.classList.toggle('hidden');
            if (!sessionsPanel.classList.contains('hidden')) {
                vscode.postMessage({ type: 'loadSessions' });
            }
        });

        closeSessionsBtn.addEventListener('click', () => {
            sessionsPanel.classList.add('hidden');
        });

        // Add message to chat
        function addMessage(role, content, metadata = {}) {
            const messageDiv = document.createElement('div');
            messageDiv.className = \`message \${role}-message\`;

            const roleLabel = document.createElement('div');
            roleLabel.className = 'message-role';
            roleLabel.textContent = role === 'user' ? 'You' : 'CodeNav';

            const contentDiv = document.createElement('div');
            contentDiv.className = 'message-content';

            // Use markdown rendering for assistant messages
            if (role === 'assistant' || role === 'system') {
                contentDiv.innerHTML = renderMarkdown(content);
                // Process Mermaid diagrams
                setTimeout(() => processMermaidDiagrams(contentDiv), 100);
            } else {
                contentDiv.textContent = content;
            }

            messageDiv.appendChild(roleLabel);
            messageDiv.appendChild(contentDiv);

            if (metadata.tokensUsed) {
                const metaDiv = document.createElement('div');
                metaDiv.className = 'message-meta';
                metaDiv.textContent = \`Tokens: \${metadata.tokensUsed} | Tools: \${metadata.toolCalls || 0}\`;
                messageDiv.appendChild(metaDiv);
            }

            chatContainer.appendChild(messageDiv);
            chatContainer.scrollTop = chatContainer.scrollHeight;

            messages.push({ role, content, metadata });
        }

        // Add message with thinking iterations
        function addMessageWithThinking(response, iterations, metadata = {}) {
            const messageDiv = document.createElement('div');
            messageDiv.className = 'message assistant-message';

            const roleLabel = document.createElement('div');
            roleLabel.className = 'message-role';
            roleLabel.textContent = 'CodeNav';

            messageDiv.appendChild(roleLabel);

            // Add thinking section (collapsible)
            const thinkingSection = document.createElement('details');
            thinkingSection.className = 'thinking-section';
            const thinkingSummary = document.createElement('summary');
            thinkingSummary.className = 'thinking-summary';
            thinkingSummary.textContent = \`🧠 Thinking (\${iterations.length} iteration\${iterations.length > 1 ? 's' : ''})\`;
            thinkingSection.appendChild(thinkingSummary);

            const thinkingContent = document.createElement('div');
            thinkingContent.className = 'thinking-content';

            iterations.forEach(iter => {
                const iterDiv = document.createElement('div');
                iterDiv.className = 'iteration';

                const iterHeader = document.createElement('div');
                iterHeader.className = 'iteration-header';
                iterHeader.textContent = \`Iteration \${iter.iteration}/\${iter.max_iterations}\`;
                iterDiv.appendChild(iterHeader);

                if (iter.thinking) {
                    const thinkingText = document.createElement('div');
                    thinkingText.className = 'iteration-thinking';
                    thinkingText.textContent = iter.thinking;
                    iterDiv.appendChild(thinkingText);
                }

                if (iter.tool_call) {
                    const toolDiv = document.createElement('div');
                    toolDiv.className = 'iteration-tool';
                    toolDiv.textContent = \`🔧 \${iter.tool_call.name}\`;
                    iterDiv.appendChild(toolDiv);

                    if (iter.tool_result) {
                        const resultDiv = document.createElement('div');
                        resultDiv.className = 'iteration-result';
                        resultDiv.textContent = iter.tool_result;
                        iterDiv.appendChild(resultDiv);
                    }
                }

                thinkingContent.appendChild(iterDiv);
            });

            thinkingSection.appendChild(thinkingContent);
            messageDiv.appendChild(thinkingSection);

            // Add final response with markdown rendering
            const contentDiv = document.createElement('div');
            contentDiv.className = 'message-content';
            if (response) {
                contentDiv.innerHTML = renderMarkdown(response);
                // Process Mermaid diagrams
                setTimeout(() => processMermaidDiagrams(contentDiv), 100);
            } else {
                contentDiv.textContent = '(Completed)';
            }
            messageDiv.appendChild(contentDiv);

            if (metadata.tokensUsed) {
                const metaDiv = document.createElement('div');
                metaDiv.className = 'message-meta';
                metaDiv.textContent = \`Tokens: \${metadata.tokensUsed} | Tools: \${metadata.toolCalls || 0}\`;
                messageDiv.appendChild(metaDiv);
            }

            chatContainer.appendChild(messageDiv);
            chatContainer.scrollTop = chatContainer.scrollHeight;

            messages.push({ role: 'assistant', content: response, metadata, iterations });
        }

        // Handle messages from extension
        window.addEventListener('message', event => {
            const message = event.data;

            switch (message.type) {
                case 'agentThinking':
                    addMessage('assistant', message.message);
                    break;

                case 'agentResponse':
                    // Remove thinking message
                    const lastMessage = chatContainer.lastElementChild;
                    if (lastMessage && lastMessage.textContent.includes('Thinking')) {
                        lastMessage.remove();
                        messages.pop();
                    }

                    // Add message with iterations if available
                    if (message.iterations && message.iterations.length > 0) {
                        addMessageWithThinking(message.response, message.iterations, {
                            tokensUsed: message.tokensUsed,
                            toolCalls: message.toolCalls
                        });
                    } else {
                        addMessage('assistant', message.response, {
                            tokensUsed: message.tokensUsed,
                            toolCalls: message.toolCalls
                        });
                    }
                    break;

                case 'agentError':
                    addMessage('system', \`Error: \${message.error}\`);
                    break;

                case 'sessionsLoaded':
                    renderSessions(message.sessions);
                    break;

                case 'sessionLoaded':
                    loadSessionMessages(message.session);
                    sessionsPanel.classList.add('hidden');
                    break;

                case 'sessionsCleared':
                    messages = [];
                    chatContainer.innerHTML = '';
                    sessionsList.innerHTML = '<p>No sessions</p>';
                    break;

                case 'indexStatus':
                    updateIndexStatus(message.status, message.progress, message.functionCount, message.fileCount);
                    break;

                case 'fileEdited':
                    addFileEdit(message.file, message.operation);
                    break;

                case 'liveThinking':
                    updateLiveThinking(message.iteration, message.thinking, message.toolCall);
                    break;

                case 'thinkingComplete':
                    if (liveThinkingDiv) {
                        liveThinkingDiv.remove();
                        liveThinkingDiv = null;
                    }
                    break;
            }
        });

        function updateIndexStatus(status, progress, functionCount, fileCount) {
            currentIndexStatus = status;

            if (status === 'idle') {
                indexStatus.classList.add('hidden');
                return;
            }

            indexStatus.classList.remove('hidden');

            if (status === 'indexing') {
                indexStatus.className = 'index-status indexing';
                statusMessage.textContent = \`Indexing project... \${progress}%\`;
                statusDetails.textContent = \`Found \${functionCount} functions in \${fileCount} files\`;
            } else if (status === 'ready') {
                indexStatus.className = 'index-status ready';
                statusMessage.textContent = 'Index ready';
                statusDetails.textContent = \`\${functionCount} functions in \${fileCount} files\`;

                // Hide after 3 seconds
                setTimeout(() => {
                    indexStatus.classList.add('hidden');
                }, 3000);
            } else if (status === 'error') {
                indexStatus.className = 'index-status error';
                statusMessage.textContent = 'Indexing failed';
                statusDetails.textContent = 'Check output panel for details';
            }
        }

        // File edit tracking
        function addFileEdit(file, operation) {
            editedFiles.add(file);
            updateFileEditsPanel();
        }

        function updateFileEditsPanel() {
            const fileEditsPanel = document.getElementById('fileEditsPanel');
            const fileEditsList = document.getElementById('fileEditsList');

            if (editedFiles.size === 0) {
                fileEditsPanel.classList.add('hidden');
                return;
            }

            fileEditsPanel.classList.remove('hidden');
            fileEditsList.innerHTML = Array.from(editedFiles).map(file => \`
                <div class="file-edit-item">
                    <span class="file-edit-icon">✏️</span>
                    <span class="file-edit-path">\${file}</span>
                </div>
            \`).join('');
        }

        const closeFileEditsBtn = document.getElementById('closeFileEditsBtn');
        closeFileEditsBtn?.addEventListener('click', () => {
            document.getElementById('fileEditsPanel').classList.add('hidden');
        });

        // Live thinking updates
        function updateLiveThinking(iteration, thinking, toolCall) {
            if (!liveThinkingDiv) {
                // Create live thinking container
                liveThinkingDiv = document.createElement('div');
                liveThinkingDiv.className = 'message assistant-message live-thinking';
                liveThinkingDiv.innerHTML = \`
                    <div class="message-role">CodeNav</div>
                    <div class="thinking-live-header">🧠 Thinking...</div>
                    <div class="thinking-live-content"></div>
                \`;
                chatContainer.appendChild(liveThinkingDiv);
            }

            const content = liveThinkingDiv.querySelector('.thinking-live-content');
            const iterDiv = document.createElement('div');
            iterDiv.className = 'iteration-live';
            iterDiv.innerHTML = \`
                <div class="iteration-header">Iteration \${iteration}</div>
                \${thinking ? \`<div class="iteration-thinking">\${thinking}</div>\` : ''}
                \${toolCall ? \`<div class="iteration-tool">🔧 \${toolCall}</div>\` : ''}
            \`;
            content.appendChild(iterDiv);

            // Auto-scroll
            chatContainer.scrollTop = chatContainer.scrollHeight;
        }

        // Request initial status
        vscode.postMessage({ type: 'getIndexStatus' });
        vscode.postMessage({ type: 'startPolling' });

        function renderSessions(sessions) {
            if (sessions.length === 0) {
                sessionsList.innerHTML = '<p>No sessions yet</p>';
                return;
            }

            sessionsList.innerHTML = sessions.map(session => \`
                <div class="session-item">
                    <div class="session-task">\${session.task}</div>
                    <div class="session-meta">
                        <span>\${new Date(session.created_at).toLocaleDateString()}</span>
                        <button onclick="loadSession('\${session.session_id}')">Load</button>
                        <button onclick="deleteSession('\${session.session_id}')">Delete</button>
                    </div>
                </div>
            \`).join('');
        }

        function loadSession(sessionId) {
            vscode.postMessage({
                type: 'loadSession',
                sessionId: sessionId
            });
        }

        function deleteSession(sessionId) {
            if (confirm('Delete this session?')) {
                vscode.postMessage({
                    type: 'deleteSession',
                    sessionId: sessionId
                });
            }
        }

        function loadSessionMessages(session) {
            messages = [];
            chatContainer.innerHTML = '';

            // Load history
            if (session.history && session.history.length > 0) {
                session.history.forEach(msg => {
                    addMessage(msg.role || 'assistant', msg.content || msg.text || '');
                });
            }
        }
    </script>
</body>
</html>`;
    }
}

function getNonce() {
    let text = '';
    const possible = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';
    for (let i = 0; i < 32; i++) {
        text += possible.charAt(Math.floor(Math.random() * possible.length));
    }
    return text;
}
