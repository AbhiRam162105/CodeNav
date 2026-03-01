/**
 * CodeNav VS Code Extension
 * Main entry point for the extension.
 */
import * as vscode from 'vscode';
import { ServerManager, ServerStatus } from './serverManager';
import { ApiClient } from './apiClient';
import { StatusBarManager } from './statusBar';
import { ProjectManager } from './projectManager';
import { CodeNavSidebarProvider } from './sidebarProvider';

let serverManager: ServerManager;
let apiClient: ApiClient;
let statusBarManager: StatusBarManager;
let projectManager: ProjectManager;
let sidebarProvider: CodeNavSidebarProvider;
let outputChannel: vscode.OutputChannel;

export function activate(context: vscode.ExtensionContext) {
    console.log('CodeNav extension is now active');

    // Create output channel
    outputChannel = vscode.window.createOutputChannel('CodeNav');
    context.subscriptions.push(outputChannel);

    // Create managers
    serverManager = new ServerManager(context, outputChannel);
    context.subscriptions.push(serverManager);

    apiClient = new ApiClient('http://localhost:8765');
    statusBarManager = new StatusBarManager();
    context.subscriptions.push(statusBarManager);

    projectManager = new ProjectManager(apiClient, outputChannel);
    context.subscriptions.push(projectManager);

    // Register sidebar provider
    sidebarProvider = new CodeNavSidebarProvider(context.extensionUri, apiClient, outputChannel);
    context.subscriptions.push(
        vscode.window.registerWebviewViewProvider(
            CodeNavSidebarProvider.viewType,
            sidebarProvider
        )
    );

    // Listen to server status changes
    serverManager.onStatusChange((status) => {
        statusBarManager.updateServerStatus(status);

        // Update API client URL when server starts
        if (status === ServerStatus.Running) {
            apiClient.setBaseUrl(serverManager.getServerUrl());
        }
    });

    // Listen to index status changes
    projectManager.onIndexStatusChange((status) => {
        statusBarManager.updateIndexStatus(
            status.status,
            status.progress,
            status.function_count
        );
    });

    // Initialize status bar
    statusBarManager.updateServerStatus(ServerStatus.Stopped);

    // Register commands
    registerCommands(context);

    // Auto-start server on activation if enabled
    const config = vscode.workspace.getConfiguration('codenav');
    if (config.get<boolean>('autoStartServer', true)) {
        setTimeout(() => startServer(), 1000);
    }

    outputChannel.appendLine('CodeNav extension activated');
}

function registerCommands(context: vscode.ExtensionContext) {
    // Server management commands
    context.subscriptions.push(
        vscode.commands.registerCommand('codenav.startServer', startServer)
    );

    context.subscriptions.push(
        vscode.commands.registerCommand('codenav.stopServer', stopServer)
    );

    context.subscriptions.push(
        vscode.commands.registerCommand('codenav.restartServer', restartServer)
    );

    context.subscriptions.push(
        vscode.commands.registerCommand('codenav.toggleServer', toggleServer)
    );

    // Project management commands
    context.subscriptions.push(
        vscode.commands.registerCommand('codenav.openProject', openProject)
    );

    context.subscriptions.push(
        vscode.commands.registerCommand('codenav.startIndexing', startIndexing)
    );

    context.subscriptions.push(
        vscode.commands.registerCommand('codenav.showIndexStatus', showIndexStatus)
    );

    // Agent commands
    context.subscriptions.push(
        vscode.commands.registerCommand('codenav.askAgent', askAgent)
    );

    context.subscriptions.push(
        vscode.commands.registerCommand('codenav.searchCode', searchCode)
    );

    // Utility commands
    context.subscriptions.push(
        vscode.commands.registerCommand('codenav.showOutput', showOutput)
    );

    context.subscriptions.push(
        vscode.commands.registerCommand('codenav.checkHealth', checkHealth)
    );
}

async function startServer() {
    outputChannel.show(true);
    const started = await serverManager.start();

    if (started) {
        // Wait for server to be fully ready with health check
        const serverReady = await waitForServerReady();

        if (serverReady) {
            // Auto-open project if workspace is available
            const config = vscode.workspace.getConfiguration('codenav');
            if (config.get<boolean>('autoOpenProject', true)) {
                await projectManager.openAndIndex();
            }
        } else {
            outputChannel.appendLine('⚠️ Server started but health check failed');
        }
    }
}

async function waitForServerReady(maxAttempts: number = 10): Promise<boolean> {
    for (let i = 0; i < maxAttempts; i++) {
        try {
            await apiClient.healthCheck();
            outputChannel.appendLine('✅ Server health check passed');
            return true;
        } catch (error) {
            outputChannel.appendLine(`Waiting for server... (attempt ${i + 1}/${maxAttempts})`);
            await new Promise(resolve => setTimeout(resolve, 1000));
        }
    }
    return false;
}

async function stopServer() {
    await serverManager.stop();
}

async function restartServer() {
    outputChannel.show(true);
    await serverManager.restart();
}

async function toggleServer() {
    if (serverManager.isRunning()) {
        await stopServer();
    } else {
        await startServer();
    }
}

async function openProject() {
    if (!serverManager.isRunning()) {
        vscode.window.showWarningMessage('Please start the CodeNav server first');
        return;
    }

    const opened = await projectManager.openProject();
    if (opened) {
        // Ask if user wants to start indexing
        const answer = await vscode.window.showQuickPick(
            ['Yes', 'No'],
            { placeHolder: 'Start indexing the project?' }
        );

        if (answer === 'Yes') {
            await startIndexing();
        }
    }
}

async function startIndexing() {
    if (!serverManager.isRunning()) {
        vscode.window.showWarningMessage('Please start the CodeNav server first');
        return;
    }

    await projectManager.startIndexing();
}

async function showIndexStatus() {
    if (!serverManager.isRunning()) {
        vscode.window.showWarningMessage('Server not running');
        return;
    }

    const status = await projectManager.getIndexStatus();
    if (status) {
        let message = `Index Status: ${status.status}\n`;
        if (status.status === 'indexing') {
            message += `Progress: ${status.progress}%\n`;
        }
        if (status.function_count > 0) {
            message += `Functions: ${status.function_count}\n`;
            message += `Files: ${status.file_count}`;
        }

        vscode.window.showInformationMessage(message);
    }
}

async function askAgent() {
    if (!serverManager.isRunning()) {
        vscode.window.showWarningMessage('Please start the CodeNav server first');
        return;
    }

    // Check if index is ready
    const indexStatus = await projectManager.getIndexStatus();
    if (!indexStatus || indexStatus.status !== 'ready') {
        vscode.window.showWarningMessage('Please wait for indexing to complete');
        return;
    }

    // Get task from user
    const task = await vscode.window.showInputBox({
        prompt: 'What would you like CodeNav to do?',
        placeHolder: 'e.g., Find all authentication functions',
    });

    if (!task) {
        return;
    }

    outputChannel.show(true);
    outputChannel.appendLine(`\n━━━ Agent Task ━━━`);
    outputChannel.appendLine(`Task: ${task}\n`);

    // Show progress
    await vscode.window.withProgress(
        {
            location: vscode.ProgressLocation.Notification,
            title: 'CodeNav Agent',
            cancellable: false
        },
        async (progress) => {
            progress.report({ message: 'Processing...' });

            try {
                const response = await apiClient.agentQuery(task);

                outputChannel.appendLine(`Status: ${response.status}`);
                outputChannel.appendLine(`Tokens used: ${response.tokens_used}`);
                outputChannel.appendLine(`Tool calls: ${response.tool_calls_made.length}\n`);

                if (response.status === 'complete' && response.response) {
                    outputChannel.appendLine(`Response:\n${response.response}\n`);
                    vscode.window.showInformationMessage('Agent task completed (see output)');
                } else if (response.status === 'needs_input' && response.question) {
                    outputChannel.appendLine(`Question: ${response.question}\n`);
                    vscode.window.showWarningMessage(
                        `Agent needs input: ${response.question}`
                    );
                } else {
                    outputChannel.appendLine(`Status: ${response.status}\n`);
                }

                // Show tool calls
                if (response.tool_calls_made.length > 0) {
                    outputChannel.appendLine('Tool Calls:');
                    response.tool_calls_made.forEach((call, i) => {
                        outputChannel.appendLine(`  ${i + 1}. ${call.tool}`);
                        outputChannel.appendLine(`     Result: ${call.result.substring(0, 100)}...`);
                    });
                }

            } catch (error) {
                const message = error instanceof Error ? error.message : String(error);
                outputChannel.appendLine(`❌ Error: ${message}\n`);
                vscode.window.showErrorMessage(`Agent error: ${message}`);
            }
        }
    );
}

async function searchCode() {
    if (!serverManager.isRunning()) {
        vscode.window.showWarningMessage('Please start the CodeNav server first');
        return;
    }

    // Check if index is ready
    const indexStatus = await projectManager.getIndexStatus();
    if (!indexStatus || indexStatus.status !== 'ready') {
        vscode.window.showWarningMessage('Please wait for indexing to complete');
        return;
    }

    // Get search query
    const query = await vscode.window.showInputBox({
        prompt: 'Search for functions',
        placeHolder: 'e.g., authentication functions',
    });

    if (!query) {
        return;
    }

    try {
        const response = await apiClient.search(query, 10);

        if (response.results.length === 0) {
            vscode.window.showInformationMessage('No results found');
            return;
        }

        // Show results in quick pick
        const items = response.results.map(result => ({
            label: result.name,
            description: `${result.file}:${result.line_start}`,
            detail: `Score: ${result.score.toFixed(2)} | ${result.qualified_name}`,
            result
        }));

        const selected = await vscode.window.showQuickPick(items, {
            placeHolder: `Found ${response.count} results`,
        });

        if (selected) {
            // Open file at location
            const projectRoot = projectManager.getCurrentProject();
            if (projectRoot) {
                const filePath = vscode.Uri.file(`${projectRoot}/${selected.result.file}`);
                const document = await vscode.workspace.openTextDocument(filePath);
                const editor = await vscode.window.showTextDocument(document);

                // Jump to line
                const line = selected.result.line_start - 1;
                const range = new vscode.Range(line, 0, line, 0);
                editor.selection = new vscode.Selection(range.start, range.end);
                editor.revealRange(range, vscode.TextEditorRevealType.InCenter);
            }
        }

    } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        vscode.window.showErrorMessage(`Search error: ${message}`);
    }
}

function showOutput() {
    outputChannel.show();
}

async function checkHealth() {
    if (!serverManager.isRunning()) {
        vscode.window.showWarningMessage('Server not running');
        return;
    }

    try {
        const health = await apiClient.health();
        const message = `Server: ${health.status}\n` +
                       `Version: ${health.version}\n` +
                       `Project: ${health.project_root || 'None'}\n` +
                       `Index: ${health.index_status}`;

        vscode.window.showInformationMessage(message);
    } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        vscode.window.showErrorMessage(`Health check failed: ${message}`);
    }
}

export function deactivate() {
    console.log('CodeNav extension is being deactivated');

    // Stop server on deactivation
    if (serverManager) {
        serverManager.stop();
    }

    outputChannel.appendLine('CodeNav extension deactivated');
}
