import { fileURLToPath, URL } from 'node:url'
import path from 'node:path'

import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

const projectRoot = fileURLToPath(new URL('.', import.meta.url))
const workspaceRoot = path.resolve(projectRoot, '..')
const extractedOutputDir = path.resolve(workspaceRoot, 'extracted_output')
const evaluationSummaryDir = path.resolve(workspaceRoot, 'evaluation_summary')

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
      '@extracted': extractedOutputDir,
      '@evaluation': evaluationSummaryDir
    }
  },
  server: {
    fs: {
      allow: [projectRoot, extractedOutputDir, evaluationSummaryDir, workspaceRoot]
    }
  }
})
