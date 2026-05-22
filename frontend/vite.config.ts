import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const apiTarget = env.VITE_API_TARGET || 'http://localhost:8000'
  const isProd = mode === 'production'

  return {
    plugins: [react()],
    server: {
      port: 5173,
      proxy: {
        '/models':        { target: apiTarget, changeOrigin: true },
        '/health':        { target: apiTarget, changeOrigin: true },
        '/generate':      { target: apiTarget, changeOrigin: true },
        '/evaluate':      { target: apiTarget, changeOrigin: true },
        '/rag':           { target: apiTarget, changeOrigin: true },
        '/model-status':  { target: apiTarget, changeOrigin: true },
        '/pull-model':    { target: apiTarget, changeOrigin: true },
        '/regenerate-tc': { target: apiTarget, changeOrigin: true },
      },
    },
    build: {
      outDir: 'dist',
      // No sourcemaps in production — avoids exposing source to end users
      sourcemap: isProd ? false : 'inline',
      target: 'es2020',
      rollupOptions: {
        output: {
          manualChunks: {
            'vendor-react':   ['react', 'react-dom'],
            'vendor-motion':  ['framer-motion'],
            'vendor-zustand': ['zustand'],
            // xlsx is ~600 KB — keep it in its own lazy chunk
            'vendor-xlsx':    ['xlsx'],
          },
        },
      },
    },
  }
})
