import { fileURLToPath, URL } from 'node:url'
import { defineConfig } from 'vitest/config'
import { loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'
import { previewApiPlugin } from './dev/preview-api.ts'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const previewMode = mode === 'development' && env.FLIGHTLINK_PREVIEW_MODE === 'true'

  return {
    plugins: [
      vue(),
      ...(previewMode
        ? [
            previewApiPlugin({
              username: env.FLIGHTLINK_PREVIEW_USERNAME ?? '',
              password: env.FLIGHTLINK_PREVIEW_PASSWORD ?? '',
            }),
          ]
        : []),
    ],
    define: {
      __FLIGHTLINK_PREVIEW_MODE__: JSON.stringify(previewMode),
    },
    server: {
      host: previewMode ? '127.0.0.1' : undefined,
      proxy: previewMode
        ? undefined
        : {
            '/api': {
              target: env.FLIGHTLINK_API_PROXY_TARGET || 'http://127.0.0.1:8000',
              changeOrigin: true,
            },
          },
    },
    resolve: {
      alias: {
        '@': fileURLToPath(new URL('./src', import.meta.url)),
      },
    },
    test: {
      environment: 'node',
      include: ['src/__tests__/**/*.spec.ts'],
    },
  }
})
