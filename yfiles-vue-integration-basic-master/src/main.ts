import { createApp } from 'vue'
import App from './App.vue'
import { LayoutExecutor } from '@yfiles/yfiles/view-layout-bridge.js'

import './assets/main.css'

const __ensureLayoutBridge = LayoutExecutor
void __ensureLayoutBridge

createApp(App).mount('#app')
