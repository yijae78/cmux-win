// scripts/create-module.ts
/**
 * TDD Module Scaffolding Script
 * Usage: npx tsx scripts/create-module.ts --name <name> --path <path>
 * Example: npx tsx scripts/create-module.ts --name "MyModule" --path "src/main/feature"
 */
import fs from 'node:fs';
import path from 'node:path';

const args = process.argv.slice(2);
const nameIdx = args.indexOf('--name');
const pathIdx = args.indexOf('--path');

if (nameIdx === -1 || pathIdx === -1) {
  console.error('Usage: npx tsx scripts/create-module.ts --name <name> --path <path>');
  process.exit(1);
}

const moduleName = args[nameIdx + 1];
const modulePath = args[pathIdx + 1];
const kebabName = moduleName.replace(/([a-z])([A-Z])/g, '$1-$2').toLowerCase();

// Create source file
const srcDir = path.resolve(modulePath);
const srcFile = path.join(srcDir, `${kebabName}.ts`);
fs.mkdirSync(srcDir, { recursive: true });
fs.writeFileSync(
  srcFile,
  `/**\n * ${moduleName}\n */\n\nexport class ${moduleName} {\n  // TODO: implement\n}\n`,
);

// Create test file
const testRelative = modulePath.replace(/^src\//, '');
const testDir = path.resolve('tests/unit', testRelative);
const testFile = path.join(testDir, `${kebabName}.test.ts`);
fs.mkdirSync(testDir, { recursive: true });
fs.writeFileSync(
  testFile,
  `import { describe, it, expect } from 'vitest';\nimport { ${moduleName} } from '${path.relative(testDir, srcDir).replace(/\\/g, '/')}/${kebabName}';\n\ndescribe('${moduleName}', () => {\n  it('should exist', () => {\n    expect(${moduleName}).toBeDefined();\n  });\n});\n`,
);

console.warn(`Created: ${srcFile}`);
console.warn(`Created: ${testFile}`);
