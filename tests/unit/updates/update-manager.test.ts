import { describe, it, expect } from 'vitest';
import {
  createUpdateConfig,
  shouldCheckForUpdates,
} from '../../../src/main/updates/update-manager';

describe('update-manager', () => {
  it('creates config with channel and autoCheck', () => {
    const config = createUpdateConfig('stable', true);
    expect(config.channel).toBe('stable');
    expect(config.autoCheck).toBe(true);
  });

  it('shouldCheckForUpdates returns true when autoCheck enabled', () => {
    expect(shouldCheckForUpdates({ channel: 'stable', autoCheck: true })).toBe(true);
  });

  it('shouldCheckForUpdates returns false when autoCheck disabled', () => {
    expect(shouldCheckForUpdates({ channel: 'nightly', autoCheck: false })).toBe(false);
  });
});
