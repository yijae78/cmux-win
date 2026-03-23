import { JsonRpcRouter } from '../router';
import type { AppStateStore } from '../../sot/store';

export function registerSystemHandlers(router: JsonRpcRouter, _store: AppStateStore): void {
  router.register('system.ping', () => {
    return { pong: true, timestamp: Date.now() };
  });

  router.register('system.identify', () => {
    return {
      name: 'cmux-win',
      version: '0.1.0',
      platform: 'win32',
    };
  });

  router.register('system.capabilities', () => {
    return {
      methods: router.getMethods(),
    };
  });
}
