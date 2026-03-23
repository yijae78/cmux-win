/**
 * Telemetry manager — opt-out via settings.telemetry.enabled.
 * Stub implementation: actual Sentry/PostHog SDKs require API keys
 * configured at build time.
 */

export interface TelemetryConfig {
  enabled: boolean;
  sentryDsn?: string;
  posthogApiKey?: string;
}

export function createTelemetryConfig(enabled: boolean): TelemetryConfig {
  return {
    enabled,
    sentryDsn: process.env.SENTRY_DSN,
    posthogApiKey: process.env.POSTHOG_API_KEY,
  };
}

export function shouldSendTelemetry(config: TelemetryConfig): boolean {
  return config.enabled && (!!config.sentryDsn || !!config.posthogApiKey);
}

export function trackEvent(
  config: TelemetryConfig,
  _event: string,
  _properties?: Record<string, unknown>,
): void {
  if (!shouldSendTelemetry(config)) return;
  // Stub: actual PostHog capture would go here
  // posthog.capture(event, properties);
}

export function trackError(config: TelemetryConfig, _error: Error): void {
  if (!shouldSendTelemetry(config)) return;
  // Stub: actual Sentry captureException would go here
  // Sentry.captureException(error);
}
