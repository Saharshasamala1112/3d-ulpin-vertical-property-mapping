/// <reference types="vitest/config" />
import { gzipSync } from 'node:zlib'
import { defineConfig, type Plugin } from 'vitest/config'
import react from '@vitejs/plugin-react'

/**
 * The 3D viewer is deliberately isolated in its own chunk so three.js never
 * lands in the initial bundle for users who do not open the page. Chunking is
 * left to Vite: forcing it via `manualChunks` makes Rolldown emit a
 * `modulepreload` for the chunk in index.html, which would download ~900 kB on
 * every page load and defeat the lazy import.
 *
 * three.js + @react-three/fiber is ~900 kB uncompressed, so the budget sits
 * just above the current size. It exists to catch an accidental heavy extra
 * dependency (e.g. pulling in @react-three/drei), not to micro-manage the
 * three.js version.
 */
const GEOMETRY_VIEWER = /geometry-?viewer/i
const GEOMETRY_VIEWER_BUDGET_BYTES = 1024 * 1024

function formatKb(bytes: number): string {
  return `${(bytes / 1024).toFixed(1)} kB`
}

function isGeometryViewerChunk(chunk: { fileName: string; name: string; facadeModuleId?: string | null }): boolean {
  return GEOMETRY_VIEWER.test(chunk.fileName) || GEOMETRY_VIEWER.test(chunk.name) ||
    (chunk.facadeModuleId ? GEOMETRY_VIEWER.test(chunk.facadeModuleId) : false)
}

function enforceChunkBudget(matcher: (chunk: { fileName: string; name: string; facadeModuleId?: string | null }) => boolean, budget: number, label: string): Plugin {
  return {
    name: 'enforce-chunk-budget',
    apply: 'build',
    enforce: 'post',
    generateBundle(_options, bundle) {
      let found = false
      for (const chunk of Object.values(bundle)) {
        if (chunk.type !== 'chunk' || !matcher(chunk)) continue
        found = true

        const bytes = Buffer.byteLength(chunk.code, 'utf8')
        if (bytes > budget) {
          this.error(
            `${label} chunk ${chunk.fileName} is ${formatKb(bytes)}, over the ${formatKb(budget)} budget.`,
          )
          return
        }
        this.info?.(
          `${label} chunk ${chunk.fileName}: ${formatKb(bytes)} raw / ` +
            `${formatKb(gzipSync(chunk.code, { level: 9 }).length)} gzip ` +
            `(budget ${formatKb(budget)})`,
        )
      }

      if (!found) {
        this.error(
          `Could not find the ${label} chunk in the build output, so its size budget was not enforced.`,
        )
      }
    },
  }
}

export default defineConfig({
  plugins: [react(), enforceChunkBudget(isGeometryViewerChunk, GEOMETRY_VIEWER_BUDGET_BYTES, 'geometry-viewer')],
  build: {
    // The geometry-viewer chunk is checked explicitly below; keep Vite's
    // generic size warning aligned with that budget instead of 500 kB.
    chunkSizeWarningLimit: 1024,
  },
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test/setup.ts'],
    css: false,
  },
})
