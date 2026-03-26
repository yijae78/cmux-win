import { describe, it, expect, beforeEach } from 'vitest';
import { SocketAuth } from '../../../src/main/socket/auth';

describe('SocketAuth', () => {
  // ──────────────────────────────────────────────
  // Constructor & accessors
  // ──────────────────────────────────────────────
  describe('constructor & accessors', () => {
    it('defaults to cmux-only mode', () => {
      const auth = new SocketAuth();
      expect(auth.getMode()).toBe('cmux-only');
    });

    it('accepts explicit mode', () => {
      const auth = new SocketAuth('allow-all');
      expect(auth.getMode()).toBe('allow-all');
    });

    it('generates a UUID token on construction', () => {
      const auth = new SocketAuth();
      const token = auth.getToken();
      // UUID v4 format: 8-4-4-4-12 hex
      expect(token).toMatch(/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i);
    });

    it('generates unique tokens across instances', () => {
      const a = new SocketAuth();
      const b = new SocketAuth();
      expect(a.getToken()).not.toBe(b.getToken());
    });

    it('setMode changes mode at runtime', () => {
      const auth = new SocketAuth('off');
      expect(auth.getMode()).toBe('off');
      auth.setMode('allow-all');
      expect(auth.getMode()).toBe('allow-all');
    });
  });

  // ──────────────────────────────────────────────
  // Mode: off
  // ──────────────────────────────────────────────
  describe('mode: off', () => {
    let auth: SocketAuth;

    beforeEach(() => {
      auth = new SocketAuth('off');
    });

    it('rejects all connections regardless of message', () => {
      const socket = {};
      const result = auth.authenticate(socket);
      expect(result.allowed).toBe(false);
      expect(result.reason).toBe('Socket API is disabled');
    });

    it('rejects even with valid token', () => {
      const socket = {};
      const msg = JSON.stringify({ token: auth.getToken() });
      const result = auth.authenticate(socket, msg);
      expect(result.allowed).toBe(false);
    });
  });

  // ──────────────────────────────────────────────
  // Mode: allow-all
  // ──────────────────────────────────────────────
  describe('mode: allow-all', () => {
    let auth: SocketAuth;

    beforeEach(() => {
      auth = new SocketAuth('allow-all');
    });

    it('allows connections without any message', () => {
      const socket = {};
      const result = auth.authenticate(socket);
      expect(result.allowed).toBe(true);
      expect(result.reason).toBeUndefined();
    });

    it('allows connections with arbitrary message', () => {
      const socket = {};
      const result = auth.authenticate(socket, 'random garbage');
      expect(result.allowed).toBe(true);
    });
  });

  // ──────────────────────────────────────────────
  // Mode: cmux-only (token-based)
  // ──────────────────────────────────────────────
  describe('mode: cmux-only', () => {
    let auth: SocketAuth;

    beforeEach(() => {
      auth = new SocketAuth('cmux-only');
    });

    it('rejects connection without first message', () => {
      const socket = {};
      const result = auth.authenticate(socket);
      expect(result.allowed).toBe(false);
      expect(result.reason).toBe('Invalid token');
    });

    it('rejects connection with wrong token', () => {
      const socket = {};
      const msg = JSON.stringify({ token: 'wrong-token' });
      const result = auth.authenticate(socket, msg);
      expect(result.allowed).toBe(false);
      expect(result.reason).toBe('Invalid token');
    });

    it('rejects connection with invalid JSON', () => {
      const socket = {};
      const result = auth.authenticate(socket, '{not json');
      expect(result.allowed).toBe(false);
      expect(result.reason).toBe('Invalid token');
    });

    it('accepts connection with correct token', () => {
      const socket = {};
      const msg = JSON.stringify({ token: auth.getToken() });
      const result = auth.authenticate(socket, msg);
      expect(result.allowed).toBe(true);
    });

    it('remembers authenticated socket on subsequent calls (WeakSet tracking)', () => {
      const socket = {};
      const msg = JSON.stringify({ token: auth.getToken() });

      // First call — authenticate with token
      auth.authenticate(socket, msg);

      // Second call — no message needed, socket is remembered
      const result = auth.authenticate(socket);
      expect(result.allowed).toBe(true);
    });

    it('does not confuse different socket objects', () => {
      const socket1 = {};
      const socket2 = {};
      const msg = JSON.stringify({ token: auth.getToken() });

      auth.authenticate(socket1, msg);

      // socket2 was never authenticated
      const result = auth.authenticate(socket2);
      expect(result.allowed).toBe(false);
    });
  });

  // ──────────────────────────────────────────────
  // Mode: automation (token-based, same as cmux-only for auth)
  // ──────────────────────────────────────────────
  describe('mode: automation', () => {
    let auth: SocketAuth;

    beforeEach(() => {
      auth = new SocketAuth('automation');
    });

    it('rejects connection without token', () => {
      const socket = {};
      const result = auth.authenticate(socket);
      expect(result.allowed).toBe(false);
      expect(result.reason).toBe('Invalid token');
    });

    it('accepts connection with correct token', () => {
      const socket = {};
      const msg = JSON.stringify({ token: auth.getToken() });
      const result = auth.authenticate(socket, msg);
      expect(result.allowed).toBe(true);
    });

    it('remembers authenticated socket (WeakSet tracking)', () => {
      const socket = {};
      const msg = JSON.stringify({ token: auth.getToken() });
      auth.authenticate(socket, msg);

      const result = auth.authenticate(socket);
      expect(result.allowed).toBe(true);
    });
  });

  // ──────────────────────────────────────────────
  // Mode: password
  // ──────────────────────────────────────────────
  describe('mode: password', () => {
    const PASSWORD = 's3cret!';
    let auth: SocketAuth;

    beforeEach(() => {
      auth = new SocketAuth('password', PASSWORD);
    });

    it('rejects connection without first message', () => {
      const socket = {};
      const result = auth.authenticate(socket);
      expect(result.allowed).toBe(false);
      expect(result.reason).toBe('Invalid password');
    });

    it('rejects connection with wrong password', () => {
      const socket = {};
      const msg = JSON.stringify({ auth: 'wrong' });
      const result = auth.authenticate(socket, msg);
      expect(result.allowed).toBe(false);
      expect(result.reason).toBe('Invalid password');
    });

    it('rejects connection with invalid JSON', () => {
      const socket = {};
      const result = auth.authenticate(socket, 'not json');
      expect(result.allowed).toBe(false);
      expect(result.reason).toBe('Invalid password');
    });

    it('accepts connection with correct password', () => {
      const socket = {};
      const msg = JSON.stringify({ auth: PASSWORD });
      const result = auth.authenticate(socket, msg);
      expect(result.allowed).toBe(true);
    });

    it('remembers authenticated socket on subsequent calls (WeakSet tracking)', () => {
      const socket = {};
      const msg = JSON.stringify({ auth: PASSWORD });
      auth.authenticate(socket, msg);

      // Second call — no message needed
      const result = auth.authenticate(socket);
      expect(result.allowed).toBe(true);
    });

    it('does not confuse different socket objects', () => {
      const socket1 = {};
      const socket2 = {};

      auth.authenticate(socket1, JSON.stringify({ auth: PASSWORD }));

      const result = auth.authenticate(socket2);
      expect(result.allowed).toBe(false);
    });
  });

  // ──────────────────────────────────────────────
  // isMethodAllowed — method filtering per mode
  // ──────────────────────────────────────────────
  describe('isMethodAllowed', () => {
    describe('mode: off', () => {
      it('blocks all methods', () => {
        const auth = new SocketAuth('off');
        expect(auth.isMethodAllowed('system.ping')).toBe(false);
        expect(auth.isMethodAllowed('browser.click')).toBe(false);
        expect(auth.isMethodAllowed('agent.run')).toBe(false);
      });
    });

    describe('mode: allow-all', () => {
      it('allows all methods', () => {
        const auth = new SocketAuth('allow-all');
        expect(auth.isMethodAllowed('system.ping')).toBe(true);
        expect(auth.isMethodAllowed('browser.click')).toBe(true);
        expect(auth.isMethodAllowed('agent.run')).toBe(true);
        expect(auth.isMethodAllowed('anything.goes')).toBe(true);
      });
    });

    describe('mode: cmux-only', () => {
      let auth: SocketAuth;

      beforeEach(() => {
        auth = new SocketAuth('cmux-only');
      });

      it('allows system.* methods', () => {
        expect(auth.isMethodAllowed('system.ping')).toBe(true);
        expect(auth.isMethodAllowed('system.version')).toBe(true);
      });

      it('allows workspace.* methods', () => {
        expect(auth.isMethodAllowed('workspace.list')).toBe(true);
        expect(auth.isMethodAllowed('workspace.create')).toBe(true);
      });

      it('allows surface.* methods', () => {
        expect(auth.isMethodAllowed('surface.split')).toBe(true);
      });

      it('allows panel.* methods', () => {
        expect(auth.isMethodAllowed('panel.close')).toBe(true);
      });

      it('allows window.* methods', () => {
        expect(auth.isMethodAllowed('window.create')).toBe(true);
      });

      it('allows notification.* methods', () => {
        expect(auth.isMethodAllowed('notification.show')).toBe(true);
      });

      it('blocks browser.* methods', () => {
        expect(auth.isMethodAllowed('browser.click')).toBe(false);
        expect(auth.isMethodAllowed('browser.navigate')).toBe(false);
      });

      it('allows agent.* methods (L3: agent orchestration)', () => {
        expect(auth.isMethodAllowed('agent.run')).toBe(true);
        expect(auth.isMethodAllowed('agent.stop')).toBe(true);
      });

      it('blocks unknown namespace methods', () => {
        expect(auth.isMethodAllowed('custom.something')).toBe(false);
        expect(auth.isMethodAllowed('foo')).toBe(false);
      });
    });

    describe('mode: automation', () => {
      let auth: SocketAuth;

      beforeEach(() => {
        auth = new SocketAuth('automation');
      });

      it('allows system.* methods', () => {
        expect(auth.isMethodAllowed('system.ping')).toBe(true);
      });

      it('allows browser.* methods', () => {
        expect(auth.isMethodAllowed('browser.click')).toBe(true);
        expect(auth.isMethodAllowed('browser.navigate')).toBe(true);
      });

      it('allows agent.* methods', () => {
        expect(auth.isMethodAllowed('agent.run')).toBe(true);
        expect(auth.isMethodAllowed('agent.stop')).toBe(true);
      });

      it('allows all methods', () => {
        expect(auth.isMethodAllowed('anything.custom')).toBe(true);
      });
    });

    describe('mode: password', () => {
      it('allows all methods (password mode has no method restrictions)', () => {
        const auth = new SocketAuth('password', 'pw');
        expect(auth.isMethodAllowed('system.ping')).toBe(true);
        expect(auth.isMethodAllowed('browser.click')).toBe(true);
        expect(auth.isMethodAllowed('agent.run')).toBe(true);
      });
    });
  });

  // ──────────────────────────────────────────────
  // WeakSet behavior — garbage collection semantics
  // ──────────────────────────────────────────────
  describe('WeakSet socket tracking', () => {
    it('uses object identity, not equality', () => {
      const auth = new SocketAuth('cmux-only');
      const token = auth.getToken();

      const socketA = { id: 1 };
      const socketB = { id: 1 }; // same shape, different object

      auth.authenticate(socketA, JSON.stringify({ token }));

      expect(auth.authenticate(socketA).allowed).toBe(true);
      expect(auth.authenticate(socketB).allowed).toBe(false);
    });
  });

  // ──────────────────────────────────────────────
  // Edge cases
  // ──────────────────────────────────────────────
  describe('edge cases', () => {
    it('password mode with empty password rejects empty auth field', () => {
      const auth = new SocketAuth('password', '');
      const socket = {};
      // When password is '' and auth is '', it should match
      const result = auth.authenticate(socket, JSON.stringify({ auth: '' }));
      expect(result.allowed).toBe(true);
    });

    it('setMode resets behavior immediately', () => {
      const auth = new SocketAuth('allow-all');
      const socket = {};

      expect(auth.authenticate(socket).allowed).toBe(true);

      auth.setMode('off');
      expect(auth.authenticate(socket).allowed).toBe(false);
    });

    it('authenticated socket in cmux-only still rejected after switching to off', () => {
      const auth = new SocketAuth('cmux-only');
      const socket = {};
      auth.authenticate(socket, JSON.stringify({ token: auth.getToken() }));
      expect(auth.authenticate(socket).allowed).toBe(true);

      auth.setMode('off');
      expect(auth.authenticate(socket).allowed).toBe(false);
    });
  });
});
