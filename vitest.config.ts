import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    globals: true,
    environment: 'node',
    include: ['tests/**/*.test.ts'],
    coverage: {
      provider: 'v8',
      reporter: ['text', 'json', 'html'],
      include: ['src/main/**/*.ts', 'src/shared/**/*.ts'],
      exclude: ['src/renderer/**', 'src/preload/**'],
      thresholds: {
        lines: 60,
        branches: 50,
        functions: 60,
      },
    },
  },
});
