import * as esbuild from 'esbuild';

try {
  const result = esbuild.buildSync({
    entryPoints: ['canonical/viewers/dynamic-workspace/main.ts'],
    bundle: true,
    format: 'esm',
    outfile: '/dev/null',
    external: ['vue', 'pinia', 'vue-i18n'],
    logLevel: 'silent',
  });
  console.log('✅ Bundle succeeded');
} catch (err) {
  console.log('❌ Bundle failed');
  console.log('Error message:', err.message);
  console.log('Error text:', err.text);
  console.log('Error location:', err.location);
}
