/**
 * Project management for CodeNav.
 */
import * as vscode from 'vscode';
import { ApiClient, IndexStatusResponse } from './apiClient';

export class ProjectManager {
    private currentProject: string | null = null;
    private indexStatusInterval: NodeJS.Timeout | null = null;
    private indexStatusEmitter = new vscode.EventEmitter<IndexStatusResponse>();
    public readonly onIndexStatusChange = this.indexStatusEmitter.event;

    constructor(
        private apiClient: ApiClient,
        private outputChannel: vscode.OutputChannel
    ) {}

    /**
     * Open a project with retry logic.
     */
    public async openProject(projectPath?: string, retries: number = 3): Promise<boolean> {
        // If no path provided, use workspace folder
        if (!projectPath) {
            const workspaceFolders = vscode.workspace.workspaceFolders;
            if (!workspaceFolders || workspaceFolders.length === 0) {
                vscode.window.showErrorMessage('No workspace folder open');
                return false;
            }

            projectPath = workspaceFolders[0].uri.fsPath;
        }

        this.outputChannel.appendLine(`Opening project: ${projectPath}`);

        for (let attempt = 1; attempt <= retries; attempt++) {
            try {
                const response = await this.apiClient.openProject(projectPath);

                if (response.success) {
                    this.currentProject = response.path;
                    this.outputChannel.appendLine(`✅ Project opened: ${response.name}`);
                    vscode.window.showInformationMessage(`CodeNav: Opened project "${response.name}"`);
                    return true;
                } else {
                    vscode.window.showErrorMessage('Failed to open project');
                    return false;
                }

            } catch (error) {
                const message = error instanceof Error ? error.message : String(error);

                if (attempt < retries) {
                    this.outputChannel.appendLine(`⚠️ Failed to open project (attempt ${attempt}/${retries}), retrying...`);
                    await new Promise(resolve => setTimeout(resolve, 2000));
                } else {
                    this.outputChannel.appendLine(`❌ Failed to open project after ${retries} attempts: ${message}`);
                    vscode.window.showErrorMessage(`Failed to open project: ${message}`);
                    return false;
                }
            }
        }

        return false;
    }

    /**
     * Start indexing the project.
     */
    public async startIndexing(): Promise<boolean> {
        if (!this.currentProject) {
            vscode.window.showWarningMessage('No project opened');
            return false;
        }

        this.outputChannel.appendLine('Starting indexing...');

        try {
            await this.apiClient.startIndexing();
            this.outputChannel.appendLine('✅ Indexing started');

            // Start polling index status
            this.startIndexStatusPolling();

            return true;

        } catch (error) {
            const message = error instanceof Error ? error.message : String(error);
            this.outputChannel.appendLine(`❌ Failed to start indexing: ${message}`);
            vscode.window.showErrorMessage(`Failed to start indexing: ${message}`);
            return false;
        }
    }

    /**
     * Get current index status.
     */
    public async getIndexStatus(): Promise<IndexStatusResponse | null> {
        try {
            return await this.apiClient.getIndexStatus();
        } catch (error) {
            const message = error instanceof Error ? error.message : String(error);
            this.outputChannel.appendLine(`Failed to get index status: ${message}`);
            return null;
        }
    }

    /**
     * Start polling index status.
     */
    private startIndexStatusPolling(): void {
        // Stop existing polling if any
        this.stopIndexStatusPolling();

        // Poll every 2 seconds
        this.indexStatusInterval = setInterval(async () => {
            const status = await this.getIndexStatus();

            if (status) {
                this.indexStatusEmitter.fire(status);

                // Stop polling if indexing is complete or error
                if (status.status === 'ready' || status.status === 'error') {
                    this.stopIndexStatusPolling();

                    if (status.status === 'ready') {
                        this.outputChannel.appendLine(
                            `✅ Indexing complete: ${status.function_count} functions in ${status.file_count} files`
                        );
                        vscode.window.showInformationMessage(
                            `CodeNav: Indexed ${status.function_count} functions`
                        );
                    } else {
                        this.outputChannel.appendLine('❌ Indexing failed');
                        vscode.window.showErrorMessage('CodeNav: Indexing failed');
                    }
                }
            }
        }, 2000);
    }

    /**
     * Stop polling index status.
     */
    private stopIndexStatusPolling(): void {
        if (this.indexStatusInterval) {
            clearInterval(this.indexStatusInterval);
            this.indexStatusInterval = null;
        }
    }

    /**
     * Open current project and start indexing.
     */
    public async openAndIndex(): Promise<boolean> {
        const opened = await this.openProject();
        if (!opened) {
            return false;
        }

        return await this.startIndexing();
    }

    /**
     * Get current project path.
     */
    public getCurrentProject(): string | null {
        return this.currentProject;
    }

    /**
     * Dispose resources.
     */
    public dispose(): void {
        this.stopIndexStatusPolling();
        this.indexStatusEmitter.dispose();
    }
}
