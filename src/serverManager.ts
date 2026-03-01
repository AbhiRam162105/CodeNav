/**
 * Server lifecycle management for CodeNav FastAPI backend.
 */
import * as vscode from 'vscode';
import * as cp from 'child_process';
import * as path from 'path';
import * as fs from 'fs';

export enum ServerStatus {
    Stopped = 'stopped',
    Starting = 'starting',
    Running = 'running',
    Error = 'error'
}

export class ServerManager {
    private serverProcess: cp.ChildProcess | null = null;
    private status: ServerStatus = ServerStatus.Stopped;
    private outputChannel: vscode.OutputChannel;
    private statusChangeEmitter = new vscode.EventEmitter<ServerStatus>();
    public readonly onStatusChange = this.statusChangeEmitter.event;

    constructor(
        private context: vscode.ExtensionContext,
        outputChannel: vscode.OutputChannel
    ) {
        this.outputChannel = outputChannel;
    }

    /**
     * Start the FastAPI server.
     */
    public async start(): Promise<boolean> {
        if (this.status === ServerStatus.Running) {
            this.outputChannel.appendLine('Server is already running');
            return true;
        }

        if (this.status === ServerStatus.Starting) {
            this.outputChannel.appendLine('Server is already starting');
            return false;
        }

        this.setStatus(ServerStatus.Starting);
        this.outputChannel.appendLine('Starting CodeNav server...');

        try {
            // Get server configuration
            const config = vscode.workspace.getConfiguration('codenav');
            const serverPath = config.get<string>('serverPath');
            const pythonPath = config.get<string>('pythonPath', 'python');
            const serverPort = config.get<number>('serverPort', 8765);

            // Determine server directory
            let serverDir: string;
            if (serverPath && fs.existsSync(serverPath)) {
                serverDir = serverPath;
            } else {
                // Default: server directory inside extension root
                serverDir = path.join(this.context.extensionPath, 'server');
            }

            if (!fs.existsSync(serverDir)) {
                throw new Error(`Server directory not found: ${serverDir}`);
            }

            const mainPy = path.join(serverDir, 'main.py');
            if (!fs.existsSync(mainPy)) {
                throw new Error(`Server main.py not found: ${mainPy}`);
            }

            this.outputChannel.appendLine(`Server directory: ${serverDir}`);
            this.outputChannel.appendLine(`Python path: ${pythonPath}`);
            this.outputChannel.appendLine(`Server port: ${serverPort}`);

            // Set environment variables
            const env = {
                ...process.env,
                SERVER_PORT: serverPort.toString(),
                PYTHONUNBUFFERED: '1'
            };

            // Start server process
            this.serverProcess = cp.spawn(
                pythonPath,
                ['main.py'],
                {
                    cwd: serverDir,
                    env: env,
                    shell: true
                }
            );

            // Handle stdout
            this.serverProcess.stdout?.on('data', (data) => {
                const output = data.toString();
                this.outputChannel.append(output);

                // Check if server is ready
                if (output.includes('Uvicorn running') || output.includes('Application startup complete')) {
                    this.setStatus(ServerStatus.Running);
                    this.outputChannel.appendLine('✅ Server started successfully');
                    vscode.window.showInformationMessage('CodeNav server started');
                }
            });

            // Handle stderr
            this.serverProcess.stderr?.on('data', (data) => {
                const output = data.toString();
                this.outputChannel.append(`[stderr] ${output}`);
            });

            // Handle process exit
            this.serverProcess.on('exit', (code) => {
                this.outputChannel.appendLine(`Server process exited with code ${code}`);
                this.setStatus(ServerStatus.Stopped);
                this.serverProcess = null;

                if (code !== 0 && code !== null) {
                    vscode.window.showErrorMessage(`CodeNav server exited with code ${code}`);
                }
            });

            // Handle process errors
            this.serverProcess.on('error', (error) => {
                this.outputChannel.appendLine(`Server process error: ${error.message}`);
                this.setStatus(ServerStatus.Error);
                vscode.window.showErrorMessage(`Failed to start server: ${error.message}`);
            });

            // Wait a bit for server to start
            await new Promise(resolve => setTimeout(resolve, 2000));

            // Check if process is still running
            if (this.serverProcess && !this.serverProcess.killed) {
                // If the stdout handler hasn't already detected the server is running,
                // we'll assume it's running after the timeout
                const currentStatus = this.getStatus();
                if (currentStatus === ServerStatus.Starting) {
                    this.setStatus(ServerStatus.Running);
                }
                return true;
            } else {
                this.setStatus(ServerStatus.Error);
                return false;
            }

        } catch (error) {
            const message = error instanceof Error ? error.message : String(error);
            this.outputChannel.appendLine(`Failed to start server: ${message}`);
            this.setStatus(ServerStatus.Error);
            vscode.window.showErrorMessage(`Failed to start CodeNav server: ${message}`);
            return false;
        }
    }

    /**
     * Stop the FastAPI server.
     */
    public async stop(): Promise<void> {
        if (!this.serverProcess) {
            this.outputChannel.appendLine('Server is not running');
            return;
        }

        this.outputChannel.appendLine('Stopping CodeNav server...');

        return new Promise((resolve) => {
            if (!this.serverProcess) {
                resolve();
                return;
            }

            // Set timeout to force kill if needed
            const timeout = setTimeout(() => {
                if (this.serverProcess && !this.serverProcess.killed) {
                    this.outputChannel.appendLine('Force killing server process');
                    this.serverProcess.kill('SIGKILL');
                }
            }, 5000);

            this.serverProcess.once('exit', () => {
                clearTimeout(timeout);
                this.outputChannel.appendLine('✅ Server stopped');
                this.setStatus(ServerStatus.Stopped);
                this.serverProcess = null;
                resolve();
            });

            // Try graceful shutdown first
            this.serverProcess.kill('SIGTERM');
        });
    }

    /**
     * Restart the server.
     */
    public async restart(): Promise<boolean> {
        this.outputChannel.appendLine('Restarting CodeNav server...');
        await this.stop();
        await new Promise(resolve => setTimeout(resolve, 1000));
        return await this.start();
    }

    /**
     * Get current server status.
     */
    public getStatus(): ServerStatus {
        return this.status;
    }

    /**
     * Check if server is running.
     */
    public isRunning(): boolean {
        return this.status === ServerStatus.Running;
    }

    /**
     * Get server base URL.
     */
    public getServerUrl(): string {
        const config = vscode.workspace.getConfiguration('codenav');
        const port = config.get<number>('serverPort', 8765);
        return `http://localhost:${port}`;
    }

    /**
     * Set server status and emit event.
     */
    private setStatus(status: ServerStatus): void {
        this.status = status;
        this.statusChangeEmitter.fire(status);
    }

    /**
     * Dispose resources.
     */
    public dispose(): void {
        if (this.serverProcess) {
            this.serverProcess.kill();
            this.serverProcess = null;
        }
        this.statusChangeEmitter.dispose();
    }
}
