/**
 * Auto-update manager using electron-updater.
 * In dev mode, electron-updater is not available — failures are caught silently.
 */

// ---------------------------------------------------------------------------
// Config types
// ---------------------------------------------------------------------------
export interface UpdateManagerConfig {
  channel: 'stable' | 'nightly';
  autoCheck: boolean;
}

export interface UpdateGithubConfig {
  provider: 'github';
  owner: string;
  repo: string;
}

export function createUpdateConfig(
  channel: 'stable' | 'nightly',
  autoCheck: boolean,
): UpdateManagerConfig {
  return { channel, autoCheck };
}

export function shouldCheckForUpdates(config: UpdateManagerConfig): boolean {
  return config.autoCheck;
}

/**
 * Return the GitHub publish configuration for electron-updater.
 */
export function getUpdateConfig(): UpdateGithubConfig {
  return { provider: 'github', owner: 'cmux-win', repo: 'cmux-win' };
}

// ---------------------------------------------------------------------------
// Updater reference (set after init)
// ---------------------------------------------------------------------------
let autoUpdaterInstance: {
  checkForUpdatesAndNotify: () => Promise<unknown>;
} | null = null;

/**
 * Check for updates manually. Safe to call at any time.
 * Returns true if check was initiated, false if updater is unavailable.
 */
export async function checkForUpdates(): Promise<boolean> {
  if (!autoUpdaterInstance) {
    console.warn('[cmux-win] Auto-updater not initialized — cannot check for updates');
    return false;
  }
  try {
    await autoUpdaterInstance.checkForUpdatesAndNotify();
    return true;
  } catch (err) {
    console.error(
      '[cmux-win] Update check failed:',
      err instanceof Error ? err.message : err,
    );
    return false;
  }
}

/**
 * Initialize the auto-updater using electron-updater.
 * Only works in a packaged app; dev environment failures are caught silently.
 */
export async function initAutoUpdater(config: UpdateManagerConfig): Promise<void> {
  try {
    // Conditional import — electron-updater may not be available in dev
    const { autoUpdater } = await import('electron-updater');
    autoUpdaterInstance = autoUpdater;

    autoUpdater.autoDownload = true;
    autoUpdater.channel = config.channel;

    // Apply GitHub publish config
    const ghConfig = getUpdateConfig();
    autoUpdater.setFeedURL({
      provider: ghConfig.provider,
      owner: ghConfig.owner,
      repo: ghConfig.repo,
    });

    autoUpdater.on('update-available', (info: { version: string }) => {
      console.warn(`[cmux-win] Update available: ${info.version}`);
    });
    autoUpdater.on('update-downloaded', () => {
      console.warn('[cmux-win] Update downloaded. Will install on quit.');
    });
    autoUpdater.on('error', (err: Error) => {
      console.error('[cmux-win] Auto-update error:', err.message);
    });

    if (config.autoCheck) {
      autoUpdater.checkForUpdatesAndNotify().catch((_err: Error) => {
        // Expected to fail in dev environment
        console.warn('[cmux-win] Update check skipped (dev mode or no publish config)');
      });
    }
  } catch {
    // electron-updater not available or dev environment
    autoUpdaterInstance = null;
    console.warn('[cmux-win] Auto-updater not available');
  }
}
