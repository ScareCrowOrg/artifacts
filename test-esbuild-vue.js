import * as esbuild from 'esbuild';

try {
  const result = esbuild.buildSync({
    entryPoints: ['canonical/viewers/dynamic-workspace/main.ts'],
    bundle: true,
    format: 'esm',
    outfile: '/dev/null',
    external: ['vue', 'pinia', 'vue-i18n'],
    loader: {
      '.vue': 'text',  // Treat Vue as text
    },
    logLevel: 'silent',
  });
  console.log('✅ Bundle succeeded with .vue loader');
} catch (err) {
  console.log('❌ Bundle failed even with .vue loader');
  console.log('Error:', err.message);
  if (err.errors) {
    console.log('Details:', err.errors);
  }
}
