/**
 * Socket authentication module for cmux-win.
 *
 * 5-stage authentication matching cmux:
 *  - off:        Socket API disabled, reject all connections
 *  - cmux-only:  Only cmux CLI (validated by shared secret token)
 *  - automation:  cmux CLI + automation API (browser.*, agent.* allowed)
 *  - password:   Require password in first message ({"auth":"<password>"})
 *  - allow-all:  No authentication required
 */

export type AuthMode = 'off' | 'cmux-only' | 'automation' | 'password' | 'allow-all';

export interface AuthResult {
  allowed: boolean;
  reason?: string;
}

export class SocketAuth {
  private mode: AuthMode;
  private token: string;
  private password: string;
  private authenticatedSockets = new WeakSet<object>();

  constructor(mode: AuthMode = 'cmux-only', password?: string) {
    this.mode = mode;
    this.token = crypto.randomUUID();
    this.password = password || '';
  }

  /** Get the shared secret token for cmux-only / automation modes. */
  getToken(): string {
    return this.token;
  }

  /** Get the current auth mode. */
  getMode(): AuthMode {
    return this.mode;
  }

  /** Change the auth mode at runtime. */
  setMode(mode: AuthMode): void {
    this.mode = mode;
  }

  /**
   * Check if a connection is allowed.
   *
   * For token-based modes (cmux-only, automation), the first message must
   * contain `{"token":"<token>"}`. For password mode, `{"auth":"<password>"}`.
   *
   * Once authenticated, the socketId object is remembered in a WeakSet so
   * subsequent calls for the same socket do not require re-authentication.
   */
  authenticate(socketId: object, firstMessage?: string): AuthResult {
    if (this.mode === 'off') {
      return { allowed: false, reason: 'Socket API is disabled' };
    }

    if (this.mode === 'allow-all') {
      return { allowed: true };
    }

    if (this.mode === 'password') {
      if (this.authenticatedSockets.has(socketId)) {
        return { allowed: true };
      }
      try {
        const parsed = JSON.parse(firstMessage || '') as Record<string, unknown>;
        if (parsed.auth === this.password) {
          this.authenticatedSockets.add(socketId);
          return { allowed: true };
        }
      } catch {
        /* invalid JSON */
      }
      return { allowed: false, reason: 'Invalid password' };
    }

    // cmux-only and automation modes: check token
    if (this.authenticatedSockets.has(socketId)) {
      return { allowed: true };
    }
    try {
      const parsed = JSON.parse(firstMessage || '') as Record<string, unknown>;
      // Token can be at top level {"token":"xxx"} or in params {"params":{"token":"xxx"}}
      const params = parsed.params as Record<string, unknown> | undefined;
      const extractedToken = parsed.token ?? params?.token;
      if (extractedToken === this.token) {
        this.authenticatedSockets.add(socketId);
        return { allowed: true };
      }
    } catch {
      /* invalid JSON */
    }
    return { allowed: false, reason: 'Invalid token' };
  }

  /**
   * Check if a specific JSON-RPC method is allowed for the current auth mode.
   *
   * - off:       no methods allowed
   * - cmux-only: system.*, workspace.*, surface.*, panel.*, window.*, notification.*, agent.*
   * - automation: all methods (including browser.*)
   * - password:  all methods
   * - allow-all: all methods
   */
  isMethodAllowed(method: string): boolean {
    if (this.mode === 'off') {
      return false;
    }

    if (this.mode === 'allow-all') {
      return true;
    }

    if (this.mode === 'cmux-only') {
      return (
        method.startsWith('system.') ||
        method.startsWith('workspace.') ||
        method.startsWith('surface.') ||
        method.startsWith('panel.') ||
        method.startsWith('window.') ||
        method.startsWith('notification.') ||
        method.startsWith('agent.') ||
        method.startsWith('workflow.')
      );
    }

    // automation and password modes: all methods allowed
    return true;
  }
}
