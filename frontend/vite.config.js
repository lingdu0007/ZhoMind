import { defineConfig } from 'vite';
import vue from '@vitejs/plugin-vue';

const proxyOptions = {
  target: 'http://127.0.0.1:8000',
  changeOrigin: true,
  secure: false,
  proxyTimeout: 0,
  ws: false
};

export default defineConfig({
  plugins: [vue()],
  server: {
    host: '0.0.0.0',
    port: 5173,
    proxy: {
      '/chat': {
        ...proxyOptions,
        configure: (proxy) => {
          proxy.on('proxyRes', (proxyRes) => {
            proxyRes.headers['Cache-Control'] = 'no-cache';
          });
        }
      },
      '/sessions': proxyOptions,
      '/documents': proxyOptions,
      '/auth': proxyOptions
    }
  }
});
