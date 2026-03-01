/**
 * Status bar manager for CodeNav extension.
 */
import * as vscode from 'vscode';
import { ServerStatus } from './serverManager';

export class StatusBarManager {
    private statusBarItem: vscode.StatusBarItem;
    private indexStatusItem: vscode.StatusBarItem;

    constructor() {
        // Server status item (left side)
        this.statusBarItem = vscode.window.createStatusBarItem(
            vscode.StatusBarAlignment.Left,
            100
        );
        this.statusBarItem.command = 'codenav.toggleServer';
        this.statusBarItem.show();

        // Index status item (left side, next to server)
        this.indexStatusItem = vscode.window.createStatusBarItem(
            vscode.StatusBarAlignment.Left,
            99
        );
        this.indexStatusItem.command = 'codenav.showIndexStatus';
        this.indexStatusItem.hide();
    }

    /**
     * Update server status display.
     */
    public updateServerStatus(status: ServerStatus): void {
        switch (status) {
            case ServerStatus.Stopped:
                this.statusBarItem.text = '$(debug-stop) CodeNav: Stopped';
                this.statusBarItem.tooltip = 'Click to start CodeNav server';
                this.statusBarItem.backgroundColor = undefined;
                this.indexStatusItem.hide();
                break;

            case ServerStatus.Starting:
                this.statusBarItem.text = '$(loading~spin) CodeNav: Starting...';
                this.statusBarItem.tooltip = 'CodeNav server is starting';
                this.statusBarItem.backgroundColor = new vscode.ThemeColor(
                    'statusBarItem.warningBackground'
                );
                this.indexStatusItem.hide();
                break;

            case ServerStatus.Running:
                this.statusBarItem.text = '$(check) CodeNav: Running';
                this.statusBarItem.tooltip = 'CodeNav server is running (click to stop)';
                this.statusBarItem.backgroundColor = new vscode.ThemeColor(
                    'statusBarItem.successBackground'
                );
                break;

            case ServerStatus.Error:
                this.statusBarItem.text = '$(error) CodeNav: Error';
                this.statusBarItem.tooltip = 'CodeNav server encountered an error (click to restart)';
                this.statusBarItem.backgroundColor = new vscode.ThemeColor(
                    'statusBarItem.errorBackground'
                );
                this.indexStatusItem.hide();
                break;
        }
    }

    /**
     * Update index status display.
     */
    public updateIndexStatus(status: string, progress: number, functionCount: number): void {
        switch (status) {
            case 'idle':
                this.indexStatusItem.hide();
                break;

            case 'indexing':
                this.indexStatusItem.text = `$(sync~spin) Indexing: ${progress}%`;
                this.indexStatusItem.tooltip = `Indexing codebase (${progress}% complete)`;
                this.indexStatusItem.backgroundColor = new vscode.ThemeColor(
                    'statusBarItem.warningBackground'
                );
                this.indexStatusItem.show();
                break;

            case 'ready':
                this.indexStatusItem.text = `$(database) ${functionCount} functions`;
                this.indexStatusItem.tooltip = `Index ready (${functionCount} functions indexed)`;
                this.indexStatusItem.backgroundColor = undefined;
                this.indexStatusItem.show();
                break;

            case 'error':
                this.indexStatusItem.text = '$(error) Index Error';
                this.indexStatusItem.tooltip = 'Indexing failed';
                this.indexStatusItem.backgroundColor = new vscode.ThemeColor(
                    'statusBarItem.errorBackground'
                );
                this.indexStatusItem.show();
                break;

            default:
                this.indexStatusItem.hide();
        }
    }

    /**
     * Show temporary message.
     */
    public showMessage(message: string, timeout: number = 3000): void {
        const originalText = this.statusBarItem.text;
        this.statusBarItem.text = message;

        setTimeout(() => {
            // Only restore if not changed by something else
            if (this.statusBarItem.text === message) {
                this.statusBarItem.text = originalText;
            }
        }, timeout);
    }

    /**
     * Dispose status bar items.
     */
    public dispose(): void {
        this.statusBarItem.dispose();
        this.indexStatusItem.dispose();
    }
}
