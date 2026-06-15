/**
 * cmux-win unified build script.
 *
 * Builds main, preload, and renderer bundles using the vite API.
 * Properly externalizes Node.js builtins for the main/preload (CJS) builds
 * so that fs/path/os are NOT replaced with empty browser shims.
 *
 * Usage:
 *   node scripts/build.js            # build all
 *   node scripts/build.js renderer   # build renderer only
 *   node scripts/build.js main       # build main only
 */
const { build } = require('vite');
const path = require('path');
const builtinModules = require('module').builtinModules;

const ROOT = path.resolve(__dirname, '..');

// Node.js builtins: both bare (fs) and prefixed (node:fs)
const nodeExternals = [
  ...builtinModules,
  ...builtinModules.map((m) => `node:${m}`),
];

// Native / optional packages that must stay external
const nativeExternals = [
  'better-sqlite3',
  'node-pty',
  'grammy',
  '@anthropic-ai/sdk',
];

async function buildMain() {
  console.log('\n=== Building main ===');
  await build({
    configFile: false,
    root: ROOT,
    build: {
      outDir: 'out/main',
      lib: {
        entry: path.join(ROOT, 'src/main/index.ts'),
        formats: ['cjs'],
        fileName: () => 'index.js',
      },
      rollupOptions: {
        external: [
          /^electron/,
          ...nodeExternals,
          ...nativeExternals,
        ],
      },
      minify: false,
      emptyOutDir: true,
      sourcemap: false,
      commonjsOptions: { ignoreDynamicRequires: true },
    },
    resolve: {
      alias: { '@shared': path.join(ROOT, 'src/shared') },
    },
  });
  console.log('=== main OK ===');
}

async function buildPreload() {
  console.log('\n=== Building preload ===');
  await build({
    configFile: false,
    root: ROOT,
    build: {
      outDir: 'out/preload',
      lib: {
        entry: path.join(ROOT, 'src/preload/index.ts'),
        formats: ['cjs'],
        fileName: () => 'index.js',
      },
      rollupOptions: {
        external: [/^electron/, ...nodeExternals],
      },
      minify: false,
      emptyOutDir: true,
      sourcemap: false,
    },
    resolve: {
      alias: { '@shared': path.join(ROOT, 'src/shared') },
    },
  });
  console.log('=== preload OK ===');
}

async function buildRenderer() {
  console.log('\n=== Building renderer ===');
  await build({
    configFile: false,
    root: path.join(ROOT, 'src/renderer'),
    base: './',
    build: {
      outDir: path.join(ROOT, 'out/renderer'),
      rollupOptions: {
        input: path.join(ROOT, 'src/renderer/index.html'),
        external: [/^electron/],
      },
      minify: false,
      emptyOutDir: true,
      sourcemap: false,
    },
    resolve: {
      alias: { '@shared': path.join(ROOT, 'src/shared') },
    },
  });
  console.log('=== renderer OK ===');
}

async function main() {
  const target = process.argv[2]; // optional: main, preload, renderer

  try {
    if (!target || target === 'main') await buildMain();
    if (!target || target === 'preload') await buildPreload();
    if (!target || target === 'renderer') await buildRenderer();
    console.log('\n*** All builds completed successfully ***');
  } catch (err) {
    console.error('\n*** BUILD FAILED ***');
    console.error(err.message || err);
    process.exit(1);
  }
}

main();
