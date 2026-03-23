import { describe, it, expect } from 'vitest';
import {
  createTelemetryConfig,
  shouldSendTelemetry,
  trackEvent,
  trackError,
} from '../../../src/main/telemetry/telemetry-manager';

describe('telemetry-manager', () => {
  it('creates config from enabled flag', () => {
    const config = createTelemetryConfig(true);
    expect(config.enabled).toBe(true);
  });

  it('shouldSendTelemetry returns false when disabled', () => {
    expect(shouldSendTelemetry({ enabled: false })).toBe(false);
  });

  it('shouldSendTelemetry returns false when enabled but no keys', () => {
    expect(shouldSendTelemetry({ enabled: true })).toBe(false);
  });

  it('shouldSendTelemetry returns true with DSN', () => {
    expect(shouldSendTelemetry({ enabled: true, sentryDsn: 'https://sentry.io/123' })).toBe(true);
  });

  it('trackEvent does not throw when disabled', () => {
    expect(() => trackEvent({ enabled: false }, 'test')).not.toThrow();
  });

  it('trackError does not throw when disabled', () => {
    expect(() => trackError({ enabled: false }, new Error('test'))).not.toThrow();
  });
});
