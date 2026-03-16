import * as esbuild from 'esbuild';
import * as fs from 'fs';
import * as path from 'path';

const filePath = path.resolve('canonical/viewers/dynamic-workspace/main.ts');
const code = fs.readFileSync(filePath, 'utf-8');

try {
  const result = esbuild.transformSync(code, {
    loader: 'ts',
    target: 'esnext',
    format: 'esm',
    jsx: 'automatic',
  });
  console.log('✅ Transform succeeded');
  console.log('Output length:', result.code.length);
} catch (err) {
  console.log('❌ Transform failed');
  console.log('Error message:', err.message);
  console.log('Error text:', err.text);
  console.log('Error location:', err.location);
  console.log('Full error:', err);
}
