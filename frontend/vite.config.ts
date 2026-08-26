import { fileURLToPath, URL } from 'node:url';
import { defineConfig, loadEnv } from 'vite';
import vue from '@vitejs/plugin-vue';
import tailwindcss from '@tailwindcss/vite';

export default defineConfig(({ mode }) => {
  // The backend reads ANCHOR_PORT from the repo-root .env; point the dev
  // proxy at the same port so dev and deploy worktrees can run side by side.
  const env = loadEnv(mode, fileURLToPath(new URL('..', import.meta.url)), 'ANCHOR_');
  const backendTarget = `http://127.0.0.1:${env.ANCHOR_PORT || '23119'}`;

  return {
    plugins: [vue(), tailwindcss()],
    resolve: {
      alias: {
        '@': fileURLToPath(new URL('./src', import.meta.url)),
      },
    },
    server: {
      port: 5173,
      proxy: {
        // Forward API calls to the Anchor backend.
        '/api': {
          target: backendTarget,
          changeOrigin: true,
        },
      },
    },
  };
});
