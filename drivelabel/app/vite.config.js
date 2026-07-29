import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// The built site is COMMITTED to the repo at drivelabel/site so the office PC
// never needs Node installed — the Dobinator's git update drops the finished
// files in place and IIS serves them directly. `npm run build` here is a
// developer step only.
//
// base: './' keeps every asset reference relative, so the same build works
// whether IIS serves it at the root of drivelabel.c-nav.com or from a subpath.
export default defineConfig({
  plugins: [react()],
  base: './',
  build: {
    outDir: '../site',
    emptyOutDir: true,   // outDir is outside the Vite root, so this must be explicit
    assetsDir: 'assets',
    sourcemap: false,
  },
  server: {
    port: 5173,
    host: true,
  },
});
