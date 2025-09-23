<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import {
  GraphBuilder,
  GraphComponent,
  GraphItemTypes,
  GraphViewerInputMode,
  IEdge,
  INode,
  License,
  Point,
  ShapeNodeStyle,
  Size
} from '@yfiles/yfiles'

import licenseData from '../license.json'
import manifestJson from '../../yfiles_graphs/manifest.json'

License.value = licenseData

type NodeData = {
  id: string
  label?: string
  properties?: string[]
  key?: string
  color?: string
  [key: string]: unknown
}

type EdgeData = {
  from?: string
  to?: string
  source?: string
  target?: string
  label?: string
  relationship?: string
  source_column?: string
  target_column?: string
  [key: string]: unknown
}

type GraphPayload = {
  id?: string
  nodes?: NodeData[]
  edges?: EdgeData[]
}

type ManifestEntry = {
  id: string
  file: string
  nodes: number
  edges: number
}

type ManifestFile = {
  graphs?: ManifestEntry[]
}

type GraphStats = {
  nodeCount: number
  edgeCount: number
  nodeLabels: Record<string, number>
  relationshipTypes: Record<string, number>
  nodeNames: string[]
}

const graphModules = import.meta.glob('../../yfiles_graphs/*_yfiles.json', {
  eager: true,
  import: 'default'
}) as Record<string, GraphPayload>

const palette = [
  '#f97316',
  '#f472b6',
  '#38bdf8',
  '#a855f7',
  '#10b981',
  '#ef4444',
  '#facc15',
  '#22d3ee',
  '#818cf8',
  '#f87171'
]
const nodeColorMap = new Map<string, string>()
let paletteIndex = 0

function resetNodeColors() {
  nodeColorMap.clear()
  paletteIndex = 0
}

function getColorForIdentifier(identifier: string): string {
  const key = identifier.trim().toLowerCase() || 'default'
  if (nodeColorMap.has(key)) {
    return nodeColorMap.get(key) as string
  }
  const color = palette[paletteIndex % palette.length]
  paletteIndex += 1
  nodeColorMap.set(key, color)
  return color
}

function extractFileName(moduleKey: string): string {
  const parts = moduleKey.split('/')
  return parts[parts.length - 1] ?? moduleKey
}

function buildManifestEntries(manifestEntries: ManifestEntry[] = []): ManifestEntry[] {
  const entries = new Map<string, ManifestEntry>()

  for (const entry of manifestEntries) {
    entries.set(entry.file, { ...entry })
  }

  for (const [key, payload] of Object.entries(graphModules)) {
    const file = extractFileName(key)
    const existing = entries.get(file)
    const nodesCount = payload?.nodes?.length ?? existing?.nodes ?? 0
    const edgesCount = payload?.edges?.length ?? existing?.edges ?? 0
    const id = payload?.id ?? existing?.id ?? file
    entries.set(file, {
      id,
      file,
      nodes: nodesCount,
      edges: edgesCount
    })
  }

  return Array.from(entries.values()).sort((a, b) => a.id.localeCompare(b.id))
}

function computeGraphStats(nodes: NodeData[], edges: EdgeData[]): GraphStats {
  const nodeLabels: Record<string, number> = {}
  const relationshipTypes: Record<string, number> = {}
  const nodeNames: string[] = []

  for (const node of nodes) {
    const displayLabel = (node.label ?? node.id).trim() || node.id
    nodeLabels[displayLabel] = (nodeLabels[displayLabel] ?? 0) + 1
    node.color = getColorForIdentifier(displayLabel)
    nodeNames.push(displayLabel)
  }

  nodeNames.sort((a, b) => a.localeCompare(b))

  for (const edge of edges) {
    const type = (edge.relationship ?? edge.label ?? 'RELATIONSHIP').trim()
    relationshipTypes[type] = (relationshipTypes[type] ?? 0) + 1
  }

  return {
    nodeCount: nodes.length,
    edgeCount: edges.length,
    nodeLabels,
    relationshipTypes,
    nodeNames
  }
}

function formatValue(value: unknown): string {
  if (value === null || value === undefined) {
    return ''
  }
  if (Array.isArray(value)) {
    const formatted = value
      .map(entry => formatValue(entry))
      .filter((entry): entry is string => entry.length > 0)
    return formatted.join(', ')
  }
  if (typeof value === 'object') {
    try {
      return JSON.stringify(value, null, 2)
    } catch (error) {
      console.warn('Failed to stringify value', error)
      return String(value)
    }
  }
  return String(value)
}

function extractAdditionalFields(
  item: Record<string, unknown> | null | undefined,
  excludedKeys: string[]
): DetailEntry[] {
  if (!item) {
    return []
  }
  return Object.entries(item)
    .filter(([key]) => !excludedKeys.includes(key))
    .map(([key, value]) => ({ key, value: formatValue(value) }))
    .filter(entry => entry.value.length > 0)
}

interface DetailEntry {
  key: string
  value: string
}

const manifestEntries = ref<ManifestEntry[]>(
  buildManifestEntries((manifestJson as ManifestFile).graphs ?? [])
)
const selectedFile = ref<string>(manifestEntries.value[0]?.file ?? '')
const statusMessage = ref('Ready')

const selectedNode = ref<NodeData | null>(null)
const selectedEdge = ref<EdgeData | null>(null)
const graphStats = ref<GraphStats>({
  nodeCount: 0,
  edgeCount: 0,
  nodeLabels: {},
  relationshipTypes: {},
  nodeNames: []
})

const nodeTitle = computed(() => selectedNode.value?.label ?? selectedNode.value?.id ?? '')
const edgeTitle = computed(() => selectedEdge.value?.relationship ?? selectedEdge.value?.label ?? '')

const nodeAdditionalFields = computed(() =>
  extractAdditionalFields(selectedNode.value, ['id', 'label', 'properties', 'key', 'color'])
)
const edgeAdditionalFields = computed(() =>
  extractAdditionalFields(selectedEdge.value, [
    'from',
    'to',
    'source',
    'target',
    'label',
    'relationship',
    'source_column',
    'target_column'
  ])
)

const nodeLabelEntries = computed(() =>
  Object.entries(graphStats.value.nodeLabels)
    .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
    .map(([label, count]) => ({ label, count, color: getColorForIdentifier(label) }))
)

const relationshipEntries = computed(() =>
  Object.entries(graphStats.value.relationshipTypes)
    .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
    .map(([label, count]) => ({ label, count }))
)

const nodeNameList = computed(() => graphStats.value.nodeNames)

const nodeLabelDisplay = computed(() => nodeLabelEntries.value.slice(0, 6))
const nodeLabelOverflow = computed(() =>
  Math.max(nodeLabelEntries.value.length - nodeLabelDisplay.value.length, 0)
)
const relationshipDisplay = computed(() => relationshipEntries.value.slice(0, 6))
const relationshipOverflow = computed(() =>
  Math.max(relationshipEntries.value.length - relationshipDisplay.value.length, 0)
)
const nodeNamePreview = computed(() => nodeNameList.value.slice(0, 12))
const nodeNameOverflow = computed(() =>
  Math.max(nodeNameList.value.length - nodeNamePreview.value.length, 0)
)

const edgeSourceDisplay = computed(() =>
  selectedEdge.value ? resolveEdgeSource(selectedEdge.value) ?? '' : ''
)
const edgeTargetDisplay = computed(() =>
  selectedEdge.value ? resolveEdgeTarget(selectedEdge.value) ?? '' : ''
)

const currentDatabaseLabel = computed(() => {
  const match = manifestEntries.value.find(entry => entry.file === selectedFile.value)
  return match?.id ?? selectedFile.value
})

const containerRef = ref<HTMLDivElement | null>(null)
let graphComponent: GraphComponent | null = null

onMounted(async () => {
  graphComponent = new GraphComponent()
  graphComponent.htmlElement.style.width = '100%'
  graphComponent.htmlElement.style.height = '100%'
  graphComponent.htmlElement.style.flex = '1 1 auto'
  configureGraph()
  configureInteraction()

  if (containerRef.value) {
    containerRef.value.appendChild(graphComponent.htmlElement)
  }

  if (selectedFile.value) {
    await loadGraph(selectedFile.value)
  }
})

watch(selectedFile, file => {
  if (file) {
    void loadGraph(file)
  }
})

function configureGraph() {
  if (!graphComponent) {
    return
  }
  const graph = graphComponent.graph
  graph.undoEngineEnabled = false
  graph.nodeDefaults.style = new ShapeNodeStyle({
    shape: 'ellipse',
    fill: '#bfdbfe',
    stroke: '3px #ffffff'
  })
  graph.nodeDefaults.size = new Size(200, 160)
}

function configureInteraction() {
  if (!graphComponent) {
    return
  }
  const inputMode = new GraphViewerInputMode()
  inputMode.clickableItems = GraphItemTypes.NODE | GraphItemTypes.EDGE
  inputMode.selectableItems = GraphItemTypes.NODE | GraphItemTypes.EDGE
  inputMode.addEventListener('item-clicked', event => {
    applySelection(event.item ?? null)
  })
  inputMode.addEventListener('canvas-clicked', () => {
    applySelection(null)
  })
  graphComponent.inputMode = inputMode
}

function normalizeText(text: string | undefined): string {
  if (!text) {
    return ''
  }
  return text.replace(/\\n/g, '\\n')
}

function getNodeDisplayLabel(item: NodeData): string {
  const normalized = normalizeText(item.label ?? item.id)
  const firstLine = normalized.split('\\n')[0]?.trim() ?? normalized
  const truncated = firstLine.length > 24 ? firstLine.slice(0, 24) + '...' : firstLine
  return truncated || item.id
}

function resolveEdgeSource(item: EdgeData): string | null {
  return item.from ?? item.source ?? null
}

function resolveEdgeTarget(item: EdgeData): string | null {
  return item.to ?? item.target ?? null
}

function isNodeItem(item: unknown): item is INode {
  return !!item && typeof item === 'object' && 'ports' in (item as Record<string, unknown>)
}

function isEdgeItem(item: unknown): item is IEdge {
  return (
    !!item &&
    typeof item === 'object' &&
    'sourceNode' in (item as Record<string, unknown>) &&
    'targetNode' in (item as Record<string, unknown>)
  )
}

function applySelection(item: unknown | null) {
  selectedNode.value = null
  selectedEdge.value = null
  if (!item) {
    return
  }
  if (isNodeItem(item)) {
    selectedNode.value = (item.tag as NodeData) ?? null
    return
  }
  if (isEdgeItem(item)) {
    selectedEdge.value = (item.tag as EdgeData) ?? null
  }
}

function cloneNodeData(item: NodeData): NodeData {
  return {
    ...item,
    properties: Array.isArray(item.properties) ? [...item.properties] : item.properties
  }
}

function cloneEdgeData(item: EdgeData): EdgeData {
  return {
    ...item
  }
}

function createNodeStyle(item: NodeData): ShapeNodeStyle {
  const label = (item.label ?? item.id).trim() || item.id
  const fill = getColorForIdentifier(label)
  return new ShapeNodeStyle({
    shape: 'ellipse',
    fill,
    stroke: '3px #ffffff'
  })
}

function applySimpleLayout() {
  if (!graphComponent) {
    return
  }
  const graph = graphComponent.graph
  const nodes = Array.from(graph.nodes)
  const edges = Array.from(graph.edges)
  if (!nodes.length) {
    return
  }

  const positions = new Map(
    nodes.map((node, index) => {
      const angle = (index / nodes.length) * 2 * Math.PI
      return [node, { x: Math.cos(angle) * 320, y: Math.sin(angle) * 320 }]
    })
  )

  const width = Math.max(1200, nodes.length * 280)
  const area = width * width
  const k = Math.sqrt(area / nodes.length)
  let temperature = width / 8

  const repulsiveForce = (distance: number) => (k * k) / distance
  const attractiveForce = (distance: number) => (distance * distance) / k

  for (let iteration = 0; iteration < 120; iteration++) {
    const displacements = new Map(
      nodes.map(node => [node, { x: 0, y: 0 }])
    )

    for (let i = 0; i < nodes.length; i++) {
      const nodeA = nodes[i]
      const posA = positions.get(nodeA)!
      for (let j = i + 1; j < nodes.length; j++) {
        const nodeB = nodes[j]
        const posB = positions.get(nodeB)!
        let dx = posA.x - posB.x
        let dy = posA.y - posB.y
        let distance = Math.sqrt(dx * dx + dy * dy) + 0.01
        const force = repulsiveForce(distance)
        dx = (dx / distance) * force
        dy = (dy / distance) * force
        displacements.get(nodeA)!.x += dx
        displacements.get(nodeA)!.y += dy
        displacements.get(nodeB)!.x -= dx
        displacements.get(nodeB)!.y -= dy
      }
    }

    for (const edge of edges) {
      const source = edge.sourceNode
      const target = edge.targetNode
      const posSource = positions.get(source)!
      const posTarget = positions.get(target)!
      let dx = posSource.x - posTarget.x
      let dy = posSource.y - posTarget.y
      let distance = Math.sqrt(dx * dx + dy * dy) + 0.01
      const force = attractiveForce(distance)
      dx = (dx / distance) * force
      dy = (dy / distance) * force
      displacements.get(source)!.x -= dx
      displacements.get(source)!.y -= dy
      displacements.get(target)!.x += dx
      displacements.get(target)!.y += dy
    }

    for (const node of nodes) {
      const displacement = displacements.get(node)!
      let dx = displacement.x
      let dy = displacement.y
      const distance = Math.sqrt(dx * dx + dy * dy)
      if (distance > 0) {
        const limit = Math.min(distance, temperature)
        dx = (dx / distance) * limit
        dy = (dy / distance) * limit
      }
      const pos = positions.get(node)!
      pos.x += dx
      pos.y += dy
    }

    temperature *= 0.92
  }

  let minX = Infinity
  let minY = Infinity
  for (const pos of positions.values()) {
    if (pos.x < minX) {
      minX = pos.x
    }
    if (pos.y < minY) {
      minY = pos.y
    }
  }

  const offsetX = isFinite(minX) ? -minX + 250 : 250
  const offsetY = isFinite(minY) ? -minY + 250 : 250

  for (const node of nodes) {
    const pos = positions.get(node)!
    graph.setNodeCenter(node, new Point(pos.x + offsetX, pos.y + offsetY))
  }
}

async function loadGraph(file: string) {
  if (!graphComponent) {
    return
  }
  statusMessage.value = `Loading ${file} ...`

  const data = await resolveGraphData(file)
  if (!data) {
    statusMessage.value = `Unable to load ${file}`
    return
  }

  const graph = graphComponent.graph
  graph.clear()
  graphComponent.selection.clear()
  applySelection(null)
  resetNodeColors()

  const nodes = (data.nodes ?? []).filter(item => !!item?.id)
  const edges = (data.edges ?? []).filter(
    item => resolveEdgeSource(item) && resolveEdgeTarget(item)
  )

  graphStats.value = computeGraphStats(nodes, edges)

  const builder = new GraphBuilder(graph)
  const nodesSource = builder.createNodesSource(nodes, item => item.id)
  nodesSource.nodeCreator.createLabelBinding(item => getNodeDisplayLabel(item))
  nodesSource.nodeCreator.tagProvider = item => cloneNodeData(item)
  nodesSource.nodeCreator.styleProvider = item => createNodeStyle(item)

  const edgesSource = builder.createEdgesSource(
    edges,
    item => resolveEdgeSource(item)!,
    item => resolveEdgeTarget(item)!
  )
  edgesSource.edgeCreator.createLabelBinding(item => normalizeText(item.relationship ?? item.label ?? ''))
  edgesSource.edgeCreator.tagProvider = item => cloneEdgeData(item)

  builder.buildGraph()

  applySimpleLayout()
  graphComponent.fitGraphBounds()
  const identifier = data.id ? `Loaded ${data.id}` : `Loaded ${file}`
  statusMessage.value = `${identifier} (${nodes.length} nodes, ${edges.length} edges)`
}

async function resolveGraphData(file: string): Promise<GraphPayload | null> {
  const key = `../../yfiles_graphs/${file}`
  const staticData = graphModules[key]
  if (staticData) {
    return staticData
  }
  try {
    const response = await fetch(new URL(key, import.meta.url))
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`)
    }
    return (await response.json()) as GraphPayload
  } catch (error) {
    console.error('Failed to load graph', error)
    return null
  }
}
</script>

<template>
  <div class="neo-shell">
    <aside class="neo-sidebar">
      <h1 class="sidebar-title">Database Information</h1>
      <section class="sidebar-section">
        <label class="sidebar-label" for="database-select">Use database</label>
        <select id="database-select" class="sidebar-select" v-model="selectedFile">
          <option v-for="entry in manifestEntries" :key="entry.file" :value="entry.file">
            {{ entry.id || entry.file }}
          </option>
        </select>
      </section>
      <section v-if="nodeLabelEntries.length" class="sidebar-section">
        <h2 class="sidebar-subtitle">Node Labels</h2>
        <div class="tag-group">
          <span
            v-for="entry in nodeLabelDisplay"
            :key="entry.label"
            class="tag node-tag"
            :style="{ backgroundColor: entry.color }"
          >
            {{ entry.label }}
            <small>({{ entry.count }})</small>
          </span>
        </div>
      </section>
      <section v-if="relationshipEntries.length" class="sidebar-section">
        <h2 class="sidebar-subtitle">Relationship Types</h2>
        <div class="tag-group">
          <span v-for="entry in relationshipDisplay" :key="entry.label" class="tag relationship-tag">
            {{ entry.label }}
            <small>({{ entry.count }})</small>
          </span>
        </div>
      </section>
    </aside>

    <div class="neo-main">
      <header class="neo-header">
        <div class="header-left">
          <span class="header-title">{{ currentDatabaseLabel }}</span>
          <span class="header-status">{{ statusMessage }}</span>
        </div>
        <div class="header-right">
          <span class="stat-chip primary">{{ graphStats.nodeCount }} nodes</span>
          <span class="stat-chip secondary">{{ graphStats.edgeCount }} relationships</span>
        </div>
      </header>

      <div class="neo-body">
        <div class="graph-area">
          <div class="graph-toolbar">
            <span class="graph-toolbar-title">Graph View</span>
          </div>
          <div ref="containerRef" class="graph-canvas"></div>
          <div v-if="selectedNode" class="graph-overlay">
            <div class="overlay-header">
              <span class="detail-dot" :style="{ backgroundColor: selectedNode.color ?? '#6366f1' }"></span>
              <div class="overlay-header-text">
                <h2 class="detail-title">{{ nodeTitle || selectedNode.id }}</h2>
                <p class="detail-subtitle">Node</p>
              </div>
              <button class="overlay-close" type="button" @click="applySelection(null)">x</button>
            </div>
            <div class="overlay-content">
              <div class="detail-line">
                <span class="detail-key">ID</span>
                <span class="detail-value">{{ selectedNode.id }}</span>
              </div>
              <div v-if="selectedNode.key" class="detail-line">
                <span class="detail-key">Key</span>
                <span class="detail-value">{{ selectedNode.key }}</span>
              </div>
              <div v-if="selectedNode.properties?.length" class="detail-section">
                <span class="detail-key">Properties</span>
                <ul class="detail-list">
                  <li v-for="prop in selectedNode.properties" :key="prop">{{ prop }}</li>
                </ul>
              </div>
              <div v-for="entry in nodeAdditionalFields" :key="entry.key" class="detail-line">
                <span class="detail-key">{{ entry.key }}</span>
                <span class="detail-value">{{ entry.value }}</span>
              </div>
            </div>
          </div>
          <div v-else-if="selectedEdge" class="graph-overlay">
            <div class="overlay-header">
              <span class="detail-dot edge"></span>
              <div class="overlay-header-text">
                <h2 class="detail-title">{{ edgeTitle || 'Relationship' }}</h2>
                <p class="detail-subtitle">Edge</p>
              </div>
              <button class="overlay-close" type="button" @click="applySelection(null)">x</button>
            </div>
            <div class="overlay-content">
              <div v-if="edgeSourceDisplay" class="detail-line">
                <span class="detail-key">Source</span>
                <span class="detail-value">{{ edgeSourceDisplay }}</span>
              </div>
              <div v-if="edgeTargetDisplay" class="detail-line">
                <span class="detail-key">Target</span>
                <span class="detail-value">{{ edgeTargetDisplay }}</span>
              </div>
              <div v-if="selectedEdge.relationship" class="detail-line">
                <span class="detail-key">Relationship</span>
                <span class="detail-value">{{ selectedEdge.relationship }}</span>
              </div>
              <div v-if="selectedEdge.label && selectedEdge.label !== selectedEdge.relationship" class="detail-line">
                <span class="detail-key">Label</span>
                <span class="detail-value">{{ selectedEdge.label }}</span>
              </div>
              <div v-if="selectedEdge.source_column" class="detail-line">
                <span class="detail-key">Source Column</span>
                <span class="detail-value">{{ selectedEdge.source_column }}</span>
              </div>
              <div v-if="selectedEdge.target_column" class="detail-line">
                <span class="detail-key">Target Column</span>
                <span class="detail-value">{{ selectedEdge.target_column }}</span>
              </div>
              <div v-for="entry in edgeAdditionalFields" :key="entry.key" class="detail-line">
                <span class="detail-key">{{ entry.key }}</span>
                <span class="detail-value">{{ entry.value }}</span>
              </div>
            </div>
          </div>
        </div>

        <aside class="neo-inspector">
          <div class="overview-card">
            <h3 class="overview-title">Overview</h3>
            <section class="overview-section">
              <h4 class="overview-heading">Node labels</h4>
              <div class="tag-group">
                <span
                  v-for="entry in nodeLabelDisplay"
                  :key="entry.label + '-overview'"
                  class="tag node-tag"
                  :style="{ backgroundColor: entry.color }"
                >
                  {{ entry.label }}
                  <small>({{ entry.count }})</small>
                </span>
              </div>
              <p v-if="nodeLabelOverflow" class="tag-overflow">+{{ nodeLabelOverflow }} more</p>
            </section>
            <section class="overview-section">
              <h4 class="overview-heading">Relationship types</h4>
              <div class="tag-group">
                <span
                  v-for="entry in relationshipDisplay"
                  :key="entry.label + '-overview'"
                  class="tag relationship-tag"
                >
                  {{ entry.label }}
                  <small>({{ entry.count }})</small>
                </span>
              </div>
              <p v-if="relationshipOverflow" class="tag-overflow">+{{ relationshipOverflow }} more</p>
            </section>
            <section class="overview-section">
              <h4 class="overview-heading">Node names</h4>
              <ul class="overview-list">
                <li v-for="name in nodeNamePreview" :key="name">{{ name }}</li>
              </ul>
              <p v-if="nodeNameOverflow" class="tag-overflow">+{{ nodeNameOverflow }} more</p>
            </section>
            <footer class="overview-footnote">
              Displaying {{ graphStats.nodeCount }} nodes and {{ graphStats.edgeCount }} relationships.
            </footer>
          </div>
        </aside>
      </div>
    </div>
  </div>
</template>

<style scoped>
.neo-shell {
  display: flex;
  min-height: 100vh;
  width: 100vw;
  max-width: 100vw;
  overflow: hidden;
  background: #f3f4f6;
  color: #0f172a;
  font-family: 'Inter', 'Helvetica Neue', Arial, sans-serif;
}

.neo-sidebar {
  width: 160px;
  background: #1f2937;
  color: #f8fafc;
  padding: 0.8rem 1rem;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  box-shadow: inset -1px 0 0 rgba(15, 23, 42, 0.4);
}

.sidebar-title {
  margin: 0;
  font-size: 1.25rem;
  font-weight: 600;
}

.sidebar-section {
  display: flex;
  flex-direction: column;
  gap: 0.45rem;
}

.sidebar-label {
  font-size: 0.85rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: #cbd5f5;
}

.sidebar-select {
  background: #111827;
  color: #f8fafc;
  border: 1px solid rgba(148, 163, 184, 0.3);
  border-radius: 6px;
  padding: 0.5rem 0.75rem;
}

.sidebar-subtitle {
  margin: 0;
  font-size: 0.95rem;
  font-weight: 600;
  color: #e2e8f0;
}

.tag-group {
  display: flex;
  flex-wrap: wrap;
  gap: 0.45rem;
}

.tag {
  display: inline-flex;
  align-items: center;
  gap: 0.28rem;
  padding: 0.28rem 0.5rem;
  border-radius: 999px;
  font-size: 0.7rem;
  font-weight: 600;
  letter-spacing: 0.01em;
  background: rgba(255, 255, 255, 0.08);
  color: #0f172a;
}

.tag small {
  font-size: 0.68rem;
  font-weight: 500;
}

.tag-overflow {
  margin: 0;
  font-size: 0.7rem;
  color: #cbd5f5;
}

.node-tag {
  color: #0f172a;
  background: #bfdbfe;
}

.relationship-tag {
  background: rgba(148, 163, 184, 0.25);
  color: #f8fafc;
  border: 1px solid rgba(148, 163, 184, 0.45);
}

.neo-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  padding: 0.5rem 0.75rem;
  width: 100%;
  min-height: 100vh;
  box-sizing: border-box;
}

.neo-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;
  background: #e2e8f0;
  border-radius: 12px;
  padding: 0.85rem 1.1rem;
  box-shadow: 0 8px 20px rgba(15, 23, 42, 0.12);
}

.header-left {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.header-title {
  font-size: 1.1rem;
  font-weight: 600;
  color: #0f172a;
}

.header-status {
  font-size: 0.85rem;
  color: #475569;
}

.header-right {
  display: flex;
  gap: 0.5rem;
}

.stat-chip {
  padding: 0.35rem 0.75rem;
  border-radius: 999px;
  font-size: 0.8rem;
  font-weight: 600;
  letter-spacing: 0.01em;
}

.stat-chip.primary {
  background: #6366f1;
  color: #f8fafc;
}

.stat-chip.secondary {
  background: #0ea5e9;
  color: #f8fafc;
}

.neo-body {
  flex: 1;
  display: flex;
  gap: 0.5rem;
  min-height: 0;
  height: 100%;
  align-items: stretch;
}

.graph-area {
  flex: 1 1 82%;
  min-width: 0;
  min-height: calc(100vh - 160px);
  position: relative;
  display: flex;
  flex-direction: column;
  background: #ffffff;
  border-radius: 16px;
  box-shadow: 0 12px 24px rgba(148, 163, 184, 0.2);
  overflow: hidden;
}

.graph-toolbar {
  display: flex;
  align-items: center;
  padding: 0.65rem 0.9rem;
  border-bottom: 1px solid rgba(148, 163, 184, 0.25);
  background: linear-gradient(90deg, rgba(96, 165, 250, 0.14), rgba(129, 140, 248, 0.1));
}

.graph-toolbar-title {
  font-weight: 600;
  color: #1e293b;
}

.graph-canvas {
  flex: 1;
  min-height: calc(100vh - 240px);
  height: 100%;
  display: flex;
  position: relative;
  background: radial-gradient(circle at 20% 20%, rgba(148, 163, 184, 0.12), transparent),
    radial-gradient(circle at 80% 0%, rgba(96, 165, 250, 0.12), transparent),
    #f8fafc;
}

.graph-overlay {
  position: absolute;
  top: 1rem;
  right: 1rem;
  width: 340px;
  max-width: calc(100% - 2rem);
  max-height: calc(100% - 2rem);
  background: #ffffff;
  border-radius: 18px;
  box-shadow: 0 18px 32px rgba(15, 23, 42, 0.25);
  padding: 1rem 1.1rem;
  display: flex;
  flex-direction: column;
  gap: 0.7rem;
  z-index: 20;
}

.overlay-header {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.overlay-header-text {
  display: flex;
  flex-direction: column;
}

.overlay-close {
  margin-left: auto;
  border: none;
  background: transparent;
  font-size: 1.1rem;
  line-height: 1;
  cursor: pointer;
  color: #475569;
}

.overlay-close:hover {
  color: #1f2937;
}

.overlay-content {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
}

.neo-inspector {
  flex: 0 0 12%;
  max-width: 150px;
  min-width: 135px;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.detail-card {
  flex: 1 1 auto;
  background: #ffffff;
  border-radius: 16px;
  padding: 0.85rem 1rem;
  box-shadow: 0 12px 24px rgba(148, 163, 184, 0.2);
  display: flex;
  flex-direction: column;
  gap: 0.65rem;
}

.overview-card {
  flex: 0 0 auto;
  background: #ffffff;
  border-radius: 16px;
  padding: 0.65rem 0.85rem;
  box-shadow: 0 12px 24px rgba(148, 163, 184, 0.18);
  display: flex;
  flex-direction: column;
  gap: 0.55rem;
}

.detail-header {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.detail-dot {
  width: 14px;
  height: 14px;
  border-radius: 50%;
  background: #6366f1;
  box-shadow: 0 0 0 4px rgba(99, 102, 241, 0.12);
}

.detail-dot.edge {
  background: #fb7185;
  box-shadow: 0 0 0 4px rgba(251, 113, 133, 0.18);
}

.detail-title {
  margin: 0;
  font-size: 1.05rem;
  font-weight: 600;
  color: #0f172a;
}

.detail-subtitle {
  margin: 0;
  font-size: 0.8rem;
  color: #64748b;
}

.detail-content {
  display: flex;
  flex-direction: column;
  gap: 0.55rem;
}

.detail-line {
  display: flex;
  gap: 0.5rem;
  font-size: 0.85rem;
}

.detail-key {
  min-width: 110px;
  font-weight: 600;
  color: #475569;
}

.detail-value {
  flex: 1;
  color: #0f172a;
  white-space: pre-wrap;
  word-break: break-word;
}

.detail-section {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

.detail-list {
  margin: 0;
  padding-left: 1.1rem;
  font-size: 0.85rem;
  color: #1f2937;
}

.detail-placeholder {
  margin: 0;
  color: #94a3b8;
  font-size: 0.9rem;
}

.overview-title {
  margin: 0;
  font-size: 1rem;
  font-weight: 600;
  color: #0f172a;
}

.overview-section {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.overview-heading {
  margin: 0;
  font-size: 0.85rem;
  font-weight: 600;
  color: #64748b;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.overview-list {
  margin: 0;
  padding-left: 0.85rem;
  max-height: 110px;
  overflow-y: auto;
  color: #1f2937;
  font-size: 0.78rem;
  line-height: 1.25;
}

.overview-footnote {
  margin-top: auto;
  font-size: 0.78rem;
  color: #64748b;
}

@media (max-width: 1200px) {
  .neo-shell {
    flex-direction: column;
  }
  .neo-sidebar {
    width: 100%;
    flex-direction: row;
    flex-wrap: wrap;
    gap: 1rem 2rem;
  }
  .neo-main {
    padding: 1rem;
  }
  .neo-body {
  flex: 1;
  display: flex;
  gap: 0.5rem;
  min-height: 0;
  height: 100%;
  align-items: stretch;
}
  .neo-inspector {
  flex: 0 0 12%;
  max-width: 150px;
  min-width: 135px;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}
  .detail-card,
  .overview-card {
    flex: 1 1 320px;
  }
}
</style>









