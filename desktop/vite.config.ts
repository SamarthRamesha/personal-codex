import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

const host = '127.0.0.1';
const port = 1420;
const developmentOrigin = `http://${host}:${port}`;
const backendOrigin = `http://${host}:8787`;

export default defineConfig({
  plugins: [react()],
  clearScreen: false,
  server: {
    host,
    port,
    strictPort: true,
    proxy: {
      '/api': {
        target: backendOrigin,
        changeOrigin: true,
        configure(proxy) {
          proxy.on('proxyReq', (upstream, request) => {
            if (request.socket.remoteAddress === host &&
                request.headers.host === `${host}:${port}` &&
                request.headers.origin === developmentOrigin) {
              upstream.setHeader('Origin', backendOrigin);
            }
          });
        },
      },
    },
  },
  build: {target: 'safari15'},
});
