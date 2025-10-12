<script setup lang="ts">
import { computed, onMounted, onBeforeUnmount, ref, watch } from 'vue'
import {
  Arrow,
  Font,
  GraphBuilder,
  GraphComponent,
  GenericLabeling,
  GraphItemTypes,
  GraphEditorInputMode,
  GraphSnapContext,
  OrthogonalEdgeEditingContext,
  IEdge,
  IGraph,
  INode,
  LabelingScope,
  LabelStyle,
  License,
  Point,
  Rect,
  PolylineEdgeStyle,
  ShapeNodeStyle,
  Size,
  EdgeSegmentLabelModel,
  Stroke,
  ComponentLayout,
  OrganicLayout
} from '@yfiles/yfiles'
const layoutBridgePromise = import('@yfiles/yfiles/view-layout-bridge.js')

import licenseData from '../license.json'
import evaluationSummaryCsvRaw from '@evaluation/evaluation_summary.csv?raw'

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
  color?: string
  source_column?: string
  target_column?: string
  [key: string]: unknown
}

type GraphPayload = {
  id?: string
  nodes?: NodeData[]
  edges?: EdgeData[]
}

type DatasetSource = 'data' | 'schema'

const dataModules = import.meta.glob('@extracted/kgs_data/*.json', {
  eager: true,
  import: 'default'
}) as Record<string, GraphPayload>

const schemaModules = import.meta.glob('@extracted/kgs_schema/*.json', {
  eager: true,
  import: 'default'
}) as Record<string, GraphPayload>

const graphModules: Record<string, GraphPayload> = {}
const moduleKinds = new Map<string, DatasetSource>()

type ManifestEntry = {
  id: string
  file: string
  nodes: number
  edges: number
  source: DatasetSource
}

type GraphStats = {
  nodeCount: number
  edgeCount: number
  nodeLabels: Record<string, number>
  relationshipTypes: Record<string, number>
  nodeNames: string[]
}

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

const relationshipPalette = [
  '#2563eb',
  '#db2777',
  '#14b8a6',
  '#f97316',
  '#8b5cf6',
  '#22c55e',
  '#f59e0b',
  '#ef4444',
  '#0ea5e9',
  '#f472b6'
]
const relationshipColorMap = new Map<string, string>()
let relationshipPaletteIndex = 0

const edgeLabelModel = new EdgeSegmentLabelModel(6, 0, 0, true, 'left-of-edge')

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

function resetRelationshipColors() {
  relationshipColorMap.clear()
  relationshipPaletteIndex = 0
}

function getColorForRelationship(identifier: string): string {
  const key = identifier.trim().toLowerCase() || 'relationship'
  if (relationshipColorMap.has(key)) {
    return relationshipColorMap.get(key) as string
  }
  const color =
    relationshipPalette[relationshipPaletteIndex % relationshipPalette.length]
  relationshipPaletteIndex += 1
  relationshipColorMap.set(key, color)
  return color
}

function getReadableTextColor(hexColor: string): string {
  const normalized = hexColor.trim()
  if (!normalized.startsWith('#')) {
    return '#0f172a'
  }
  let hex = normalized.slice(1)
  if (hex.length === 3) {
    hex = hex
      .split('')
      .map(char => char + char)
      .join('')
  }
  const r = parseInt(hex.slice(0, 2), 16)
  const g = parseInt(hex.slice(2, 4), 16)
  const b = parseInt(hex.slice(4, 6), 16)
  const luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255
  return luminance > 0.65 ? '#0f172a' : '#f8fafc'
}

function hexToRgba(hexColor: string, alpha: number): string {
  const normalized = hexColor.trim()
  if (!normalized.startsWith('#')) {
    return normalized
  }
  let hex = normalized.slice(1)
  if (hex.length === 3) {
    hex = hex
      .split('')
      .map(char => char + char)
      .join('')
  }
  const r = parseInt(hex.slice(0, 2), 16)
  const g = parseInt(hex.slice(2, 4), 16)
  const b = parseInt(hex.slice(4, 6), 16)
  return `rgba(${r}, ${g}, ${b}, ${alpha})`
}

function extractFileName(moduleKey: string): string {
  const parts = moduleKey.split('/')
  return parts[parts.length - 1] ?? moduleKey
}

for (const [key, payload] of Object.entries(dataModules)) {
  const file = extractFileName(key)
  graphModules[file] = payload
  moduleKinds.set(file, 'data')
}

for (const [key, payload] of Object.entries(schemaModules)) {
  const file = extractFileName(key)
  graphModules[file] = payload
  moduleKinds.set(file, 'schema')
}

function buildManifestEntries(manifestEntries: ManifestEntry[] = []): ManifestEntry[] {
  const manifestByFile = new Map<string, ManifestEntry>()
  for (const entry of manifestEntries) {
    manifestByFile.set(entry.file, { ...entry })
  }

  const resolvedEntries: ManifestEntry[] = []

  for (const [file, payload] of Object.entries(graphModules)) {
    const manifestEntry = manifestByFile.get(file)
    const typedPayload = payload as GraphPayload
    const nodesCount = Array.isArray(typedPayload?.nodes)
      ? typedPayload.nodes!.length
      : manifestEntry?.nodes ?? 0
    const edgesCount = Array.isArray(typedPayload?.edges)
      ? typedPayload.edges!.length
      : manifestEntry?.edges ?? 0
    const manifestId =
      typeof manifestEntry?.id === 'string' ? manifestEntry.id.trim() : ''
    const payloadId = typeof typedPayload?.id === 'string' ? typedPayload.id.trim() : ''
    const fallbackId = file.replace(/\.json$/i, '').trim()
    const id = manifestId || payloadId || fallbackId

    resolvedEntries.push({
      id,
      file,
      nodes: nodesCount,
      edges: edgesCount,
      source: moduleKinds.get(file) ?? 'data'
    })
  }

  const isSpider = (value: string | undefined): boolean =>
    typeof value === 'string' && value.trim().toLowerCase().startsWith('spider_')

  return resolvedEntries.sort((a, b) => {
    if (a.source !== b.source) {
      return a.source === 'data' ? -1 : 1
    }
    const aSpider = isSpider(a.id)
    const bSpider = isSpider(b.id)
    if (aSpider !== bSpider) {
      return aSpider ? -1 : 1
    }
    return a.id.localeCompare(b.id)
  })
}

function resolveDefaultFile(entries: ManifestEntry[]): string {
  const picker = (predicate: (entry: ManifestEntry) => boolean): string | undefined => {
    const match = entries.find(predicate)
    return match?.file
  }
  return (
    picker(entry => entry.source === 'data' && entry.id?.trim().toLowerCase().startsWith('spider_')) ??
    picker(entry => entry.source === 'data') ??
    entries[0]?.file ??
    ''
  )
}

function formatManifestLabel(entry: ManifestEntry): string {
  const bucket = entry.source === 'schema' ? 'Schema' : 'Data'
  const base = entry.id?.trim().length ? entry.id : entry.file
  return `[${bucket}] ${base}`
}



function computeGraphStats(nodes: NodeData[], edges: EdgeData[]): GraphStats {
  const nodeLabels: Record<string, number> = {}
  const relationshipTypes: Record<string, number> = {}
  const nodeNames: string[] = []

  for (const node of nodes) {
    const group = ((node as any).type ?? node.label ?? node.id).toString().trim() || node.id
    nodeLabels[group] = (nodeLabels[group] ?? 0) + 1
    // Color by group/type rather than individual id/label
    node.color = getColorForIdentifier(group)
    nodeNames.push(group)
  }

  nodeNames.sort((a, b) => a.localeCompare(b))

  for (const edge of edges) {
    const type = (edge.relationship ?? edge.label ?? 'RELATIONSHIP').trim() || 'RELATIONSHIP'
    relationshipTypes[type] = (relationshipTypes[type] ?? 0) + 1
    edge.color = getColorForRelationship(type)
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

function normalizeProperties(properties: unknown): string[] {
  if (!properties) {
    return []
  }
  if (Array.isArray(properties)) {
    return properties
      .map(entry => formatValue(entry))
      .filter((entry): entry is string => entry.length > 0)
  }
  if (typeof properties === 'object') {
    const entries: string[] = []
    for (const [key, value] of Object.entries(properties as Record<string, unknown>)) {
      const formatted = formatValue(value)
      if (formatted.length) {
        entries.push(`${key}: ${formatted}`)
      }
    }
    return entries
  }
  const value = formatValue(properties)
  return value.length ? [value] : []
}

interface DetailEntry {
  key: string
  value: string
}

const manifestEntries = ref<ManifestEntry[]>(buildManifestEntries())
const selectedFile = ref<string>(resolveDefaultFile(manifestEntries.value))
const statusMessage = ref('Ready')

const evaluationSummary = ref<Record<string, EvaluationScores>>({})
let evaluationSummaryLoaded = false

async function ensureEvaluationSummaryLoaded(): Promise<void> {
  if (evaluationSummaryLoaded) {
    return
  }
  try {
    const csv = (evaluationSummaryCsvRaw ?? '').trim()
    if (!csv.length) {
      evaluationSummaryLoaded = true
      return
    }
    const lines = csv
      .split(/\r?\n/)
      .map(line => line.trim())
      .filter(line => line.length > 0)
    if (!lines.length) {
      evaluationSummaryLoaded = true
      return
    }
    const parsed: Record<string, EvaluationScores> = {}
    const headerParts = lines[0].split(',').map(part => part.trim())
    const headerLower = headerParts.map(part => part.toLowerCase())

    const hasHeaderRow = headerLower.some(part =>
      part.includes('schema') || part.includes('relationship') || part.includes('kgs')
    )

    let startIndex = hasHeaderRow ? 1 : 0
    let nameIndex = hasHeaderRow ? headerLower.findIndex(part => part.includes('db_name')) : 0
    if (nameIndex < 0) {
      nameIndex = 0
    }
    let schemaIndex = hasHeaderRow ? headerLower.findIndex(part => part.includes('schema')) : 1
    if (schemaIndex < 0) {
      schemaIndex = 1
    }
    let relationshipIndex = hasHeaderRow ? headerLower.findIndex(part => part.includes('relationship')) : 2
    if (relationshipIndex < 0) {
      relationshipIndex = schemaIndex + 1
    }
    const kgsIndex = hasHeaderRow ? headerLower.findIndex(part => part.includes('kgs')) : -1

    for (let i = startIndex; i < lines.length; i++) {
      const parts = lines[i].split(',').map(part => part.trim())
      const maxIndex = Math.max(nameIndex, schemaIndex, relationshipIndex, kgsIndex)
      if (parts.length <= maxIndex) {
        continue
      }
      const dbName = parts[nameIndex]?.trim()
      if (!dbName) {
        continue
      }
      const schemaRaw = parts[schemaIndex] ?? ''
      const relationshipRaw = parts[relationshipIndex] ?? ''
      const schemaValue = Number.parseFloat(schemaRaw)
      const relationshipValue = Number.parseFloat(relationshipRaw)
      const metrics: EvaluationScores = {
        schemaComp: Number.isFinite(schemaValue) ? schemaValue : null,
        relationshipComp: Number.isFinite(relationshipValue) ? relationshipValue : null
      }

      const keys = new Set<string>()
      keys.add(dbName)
      const derived = `${dbName}_kgs_data`
      keys.add(derived)
      keys.add(`${derived}.json`)
      if (kgsIndex >= 0 && (parts[kgsIndex] ?? '').trim().length) {
        const kgsValue = parts[kgsIndex]!.trim()
        keys.add(kgsValue)
        keys.add(`${kgsValue}.json`)
      }

      for (const key of keys) {
        parsed[key] = { ...metrics }
      }
    }
    evaluationSummary.value = parsed
  } catch (error) {
    console.warn('Failed to load evaluation summary CSV', error)
  } finally {
    evaluationSummaryLoaded = true
  }
}

function applyMetricsFor(file: string): void {
  const entry = manifestEntries.value.find(m => m.file === file)
  const key = entry?.id ?? file
  const data = evaluationSummary.value[key] ?? evaluationSummary.value[file] ?? null
  if (data) {
    metrics.value = { ...data }
  } else {
    metrics.value = { schemaComp: null, relationshipComp: null }
  }
}


const selectedNode = ref<NodeData | null>(null)
const selectedEdge = ref<EdgeData | null>(null)
// Keep reference to the last selected INode/IEdge for actions
let lastSelectedINode: INode | null = null
let lastSelectedIEdge: IEdge | null = null
const graphStats = ref<GraphStats>({
  nodeCount: 0,
  edgeCount: 0,
  nodeLabels: {},
  relationshipTypes: {},
  nodeNames: []
})

const nodeTitle = computed(() => selectedNode.value?.label ?? selectedNode.value?.id ?? '')
const edgeTitle = computed(() => selectedEdge.value?.relationship ?? selectedEdge.value?.label ?? '')

// Simple metrics placeholders (values to be provided later per dataset)
type EvaluationScores = { schemaComp: number | null; relationshipComp: number | null }
const metrics = ref<EvaluationScores>({ schemaComp: null, relationshipComp: null })
function formatEvaluationScore(value: number | null): string {
  if (value == null || !Number.isFinite(value)) {
    return '-'
  }
  if (value >= 0 && value <= 1) {
    return `${(value * 100).toFixed(1)}%`
  }
  return value.toFixed(2)
}
const schemaCompText = computed(() => formatEvaluationScore(metrics.value.schemaComp))
const relationshipCompText = computed(() => formatEvaluationScore(metrics.value.relationshipComp))

const nodeAdditionalFields = computed(() =>
  extractAdditionalFields(selectedNode.value, ['id', 'label', 'properties', 'key', 'color'])
)
const nodePropertyEntries = computed(() => normalizeProperties(selectedNode.value?.properties))
const edgeAdditionalFields = computed(() =>
  extractAdditionalFields(selectedEdge.value, [
    'from',
    'to',
    'source',
    'target',
    'label',
    'relationship',
    'color',
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
    .map(([label, count]) => {
      const color = getColorForRelationship(label)
      const textColor = getReadableTextColor(color)
      return {
        label,
        count,
        color,
        textColor,
        style: {
          backgroundColor: color,
          color: textColor,
          borderColor: hexToRgba(color, 0.55)
        }
      }
    })
)

const nodeNameList = computed(() => graphStats.value.nodeNames)

// Context menu state
const showContextMenu = ref(false)
const contextMenuLeft = ref(0)
const contextMenuTop = ref(0)
let lastContextWorldLocation: Point | null = null

// Edge creation (two-step) state
const edgeCreateActive = ref(false)
let edgeCreateSource: INode | null = null
function resetEdgeCreateState() {
  edgeCreateActive.value = false
  edgeCreateSource = null
}

// Panning state (Left-drag on blank canvas, Space+Left, or Middle button)
let isPanning = false
let panStartWorld: Point | null = null
let panStartCenter: Point | null = null
let spacePressed = false
let lastPressWasCanvas = false

// Filter/Highlight state
const filterMode = ref<'highlight' | 'filter'>('highlight')
const activeNodeLabelFilter = ref<string | null>(null)
const activeRelTypeFilter = ref<string | null>(null)
const searchNodeQuery = ref('')
const searchEdgeQuery = ref('')

// Persist filter state per database/file to avoid leaking filters across datasets
type FilterSettings = { filterMode: 'highlight' | 'filter'; nodeFilter: string | null; relFilter: string | null }
const filterSettingsByFile = new Map<string, FilterSettings>()
let lastLoadedFile: string | null = null
function ensureFilterSettingsFor(file: string) {
  if (!file) return
  const saved = filterSettingsByFile.get(file)
  if (saved) {
    filterMode.value = saved.filterMode
    activeNodeLabelFilter.value = saved.nodeFilter
    activeRelTypeFilter.value = saved.relFilter
  } else {
    filterMode.value = 'highlight'
    activeNodeLabelFilter.value = null
    activeRelTypeFilter.value = null
  }
}
function saveFilterSettingsForCurrent() {
  const file = selectedFile.value
  if (!file) return
  filterSettingsByFile.set(file, {
    filterMode: filterMode.value,
    nodeFilter: activeNodeLabelFilter.value,
    relFilter: activeRelTypeFilter.value
  })
}

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

const selectedEdgeAccent = computed(() => {
  const color = selectedEdge.value?.color
  if (!color || typeof color !== 'string') {
    return {}
  }
  return {
    backgroundColor: color,
    boxShadow: `0 0 0 4px ${hexToRgba(color, 0.2)}`
  }
})

const currentDatabaseLabel = computed(() => {
  const match = manifestEntries.value.find(entry => entry.file === selectedFile.value)
  return match?.id ?? selectedFile.value
})

const containerRef = ref<HTMLDivElement | null>(null)
let graphComponent: GraphComponent | null = null
// Auto (force) layout ideal edge length scale (1=default; <1 shorter; >1 longer)
const edgeLenScale = ref(1.0)
// Inter-cluster gap scale (applies after layout to separate clusters/components)
const clusterGapScale = ref(1.2)
// Node size scale; affects node width/height and node label font
const nodeScale = ref(1.0)
// Per-database view settings so adjustments apply only to the current dataset
type ViewSettings = { nodeScale: number; edgeLenScale: number; clusterGapScale: number }
const settingsByFile = new Map<string, ViewSettings>()
function ensureSettingsFor(file: string) {
  if (!file) return
  if (!settingsByFile.has(file)) {
    settingsByFile.set(file, { nodeScale: 1.0, edgeLenScale: 1.0, clusterGapScale: 1.2 })
  }
  const s = settingsByFile.get(file)!
  nodeScale.value = s.nodeScale
  edgeLenScale.value = s.edgeLenScale
  clusterGapScale.value = s.clusterGapScale
}
function saveSettingsForCurrent() {
  const file = selectedFile.value
  if (!file) return
  settingsByFile.set(file, {
    nodeScale: nodeScale.value,
    edgeLenScale: edgeLenScale.value,
    clusterGapScale: clusterGapScale.value
  })
}
const baseNodeWidth = 260
const baseNodeHeight = 200
const baseNodeFont = 26
const baseEdgeFont = 14
const MIN_READABLE_NODE_PIXEL_WIDTH_NEAR = 110
const MIN_READABLE_NODE_PIXEL_WIDTH_FAR = 68
const MIN_READABLE_NODE_COUNT = 80
const MAX_READABLE_NODE_COUNT = 600

const AUTO_MAXIMUM_ZOOM_CAP = 12
const AUTO_MINIMUM_ZOOM_FLOOR = 0.04

function computeMinReadableNodePixelWidth(count: number): number {
  if (!Number.isFinite(count) || count <= 0) {
    return MIN_READABLE_NODE_PIXEL_WIDTH_NEAR
  }
  if (count <= MIN_READABLE_NODE_COUNT) {
    return MIN_READABLE_NODE_PIXEL_WIDTH_NEAR
  }
  if (count >= MAX_READABLE_NODE_COUNT) {
    return MIN_READABLE_NODE_PIXEL_WIDTH_FAR
  }
  const ratio =
    (count - MIN_READABLE_NODE_COUNT) /
    (MAX_READABLE_NODE_COUNT - MIN_READABLE_NODE_COUNT)
  return (
    MIN_READABLE_NODE_PIXEL_WIDTH_NEAR -
    ratio * (MIN_READABLE_NODE_PIXEL_WIDTH_NEAR - MIN_READABLE_NODE_PIXEL_WIDTH_FAR)
  )
}


function compactLoosen() {
  compactScale.value = Math.min(3, compactScale.value + 0.2)
  if (layoutMode.value === 'compact') {
    applyCompactLayout()
    if (graphComponent) {
      reduceLabelOverlapsAndPlace(graphComponent.graph)
      graphComponent.fitGraphBounds()
      adjustInitialZoomForNodeCount(graphComponent.graph.nodes.size)
    }
  }
}

function compactTighten() {
  compactScale.value = Math.max(0.8, compactScale.value - 0.2)
  if (layoutMode.value === 'compact') {
    applyCompactLayout()
    if (graphComponent) {
      reduceLabelOverlapsAndPlace(graphComponent.graph)
      graphComponent.fitGraphBounds()
      adjustInitialZoomForNodeCount(graphComponent.graph.nodes.size)
    }
  }
}

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
    await ensureEvaluationSummaryLoaded()
    applyMetricsFor(selectedFile.value)
    await loadGraph(selectedFile.value)
  }
})

onBeforeUnmount(() => {
  if (graphComponent && (graphComponent as any)._codexCleanup) {
    try {
      ;(graphComponent as any)._codexCleanup()
    } catch {}
  }
})

watch(selectedFile, file => {
  // Save filters for previous dataset before switching
  if (lastLoadedFile) {
    saveFilterSettingsForCurrent()
  }
  if (file) {
    ensureSettingsFor(file)
    ensureFilterSettingsFor(file)
    void (async () => {
      await ensureEvaluationSummaryLoaded()
      applyMetricsFor(file)
      await loadGraph(file)
    })()
  }
})

function configureGraph() {
  if (!graphComponent) {
    return
  }
  const graph = graphComponent.graph
  graph.undoEngineEnabled = true
  graph.nodeDefaults.style = new ShapeNodeStyle({
    shape: 'ellipse',
    fill: '#bfdbfe',
    stroke: '3px #ffffff'
  })
  graph.nodeDefaults.size = new Size(260, 200)
  graph.nodeDefaults.labels.style = new LabelStyle({
    font: new Font({
      fontFamily: "Inter, 'Helvetica Neue', Arial, sans-serif",
      fontSize: 26,
      fontWeight: '600'
    }),
    textFill: '#0f172a',
    wrapping: 'wrap-word',
    maximumSize: new Size(220, 150),
    horizontalTextAlignment: 'center',
    verticalTextAlignment: 'center',
    padding: 8
  })

  graph.edgeDefaults.labels.style = new LabelStyle({
    font: new Font({
      fontFamily: "Inter, 'Helvetica Neue', Arial, sans-serif",
      fontSize: 14,
      fontWeight: '600'
    }),
    textFill: '#0f172a',
    padding: 4
  })
}

function configureInteraction() {
  if (!graphComponent) {
    return
  }
  const inputMode = new GraphEditorInputMode()
  // Disable implicit create on click; use context menu instead
  inputMode.allowCreateNode = false
  inputMode.allowCreateEdge = false

  // Enable convenient editing behavior
  inputMode.allowEditLabel = true
  inputMode.allowBendCreation = true
  inputMode.snapContext = new GraphSnapContext()
  inputMode.orthogonalEdgeEditingContext = new OrthogonalEdgeEditingContext()
  inputMode.clickableItems = GraphItemTypes.ALL
  inputMode.selectableItems = GraphItemTypes.NODE | GraphItemTypes.EDGE
  // Default: disable marquee to favor panning with left-drag (we implement our own)
  try {
    ;(inputMode as any).marqueeSelectionInputMode && ((inputMode as any).marqueeSelectionInputMode.enabled = false)
  } catch {}
  inputMode.addEventListener('item-clicked', event => {
    // If user is in the middle of Add Edge, consume two node (or node-label) clicks
    if (edgeCreateActive.value && event.item) {
      const node = resolveNodeFromItem(event.item)
      if (!node) {
        // Clicked a non-node while adding edge: cancel edge creation so selection works normally
        resetEdgeCreateState()
        statusMessage.value = 'Edge creation cancelled'
        applySelection(event.item)
        return
      }
      if (!edgeCreateSource) {
        edgeCreateSource = node
        statusMessage.value = 'Edge: select target node'
      } else if (edgeCreateSource !== node) {
        // Create the edge and immediately allow editing the label
        const graph = graphComponent!.graph
        const edgeData: EdgeData = { relationship: '', color: getColorForRelationship('') }
        const newEdge = graph.createEdge(edgeCreateSource, node, createEdgeStyle(edgeData))
        newEdge.tag = edgeData
        // Add empty label and place it on the edge
        const label = graph.addLabel(newEdge, '')
        graph.setLabelLayoutParameter(label, edgeLabelModel.createParameterFromCenter(0.5, 'left-of-edge'))
        // Let user edit the label right away (via input mode)
        const im = graphComponent!.inputMode as GraphEditorInputMode
        if (im && typeof (im as any).editLabel === 'function') {
          void (im as any).editLabel(label)
        }
        // Update stats and finish
        updateStatsFromGraph()
        reduceLabelOverlapsAndPlace(graph)
        statusMessage.value = 'Edge created'
        resetEdgeCreateState()
      }
      return
    }
    applySelection(event.item ?? null)
  })
  inputMode.addEventListener('canvas-clicked', () => {
    if (edgeCreateActive.value) {
      resetEdgeCreateState()
      statusMessage.value = 'Edge creation cancelled'
    }
    applySelection(null)
  })
  graphComponent.inputMode = inputMode

  // Custom context menu via native right-click
  const container = graphComponent.htmlElement
  const onContextMenu = (evt: MouseEvent) => {
    evt.preventDefault()
    // Position menu near cursor
    contextMenuLeft.value = evt.clientX
    contextMenuTop.value = evt.clientY
    // Remember world location for "Add node here"
    try {
      if (typeof (graphComponent as any).toWorldFromPage === 'function') {
        lastContextWorldLocation = (graphComponent as any).toWorldFromPage(
          new Point(evt.pageX, evt.pageY)
        )
      } else if (typeof (graphComponent as any).toWorld === 'function') {
        // Fallback: compute view-relative point, then map
        const rect = graphComponent.htmlElement.getBoundingClientRect()
        const viewX = evt.clientX - rect.left
        const viewY = evt.clientY - rect.top
        lastContextWorldLocation = (graphComponent as any).toWorld(new Point(viewX, viewY))
      } else {
        lastContextWorldLocation = new Point(evt.offsetX, evt.offsetY)
      }
    } catch {
      lastContextWorldLocation = new Point(evt.offsetX, evt.offsetY)
    }
    showContextMenu.value = true
  }
  container.addEventListener('contextmenu', onContextMenu, { capture: true })
  // Recompute selected-edge thickness on zoom (wheel gesture)
  let wheelRafPending = false
  const onWheel = () => {
    if (!selectedEdge.value) return
    if (wheelRafPending) return
    wheelRafPending = true
    requestAnimationFrame(() => {
      wheelRafPending = false
      highlightSelectedEdgeOnTop()
    })
  }
  container.addEventListener('wheel', onWheel, { passive: true })

  const onAnyClick = () => {
    showContextMenu.value = false
  }
  const onKey = (e: KeyboardEvent) => {
    if (e.key === 'Escape') {
      showContextMenu.value = false
      if (edgeCreateActive.value) {
        resetEdgeCreateState()
        statusMessage.value = 'Edge creation cancelled'
      }
    }
  }
  document.addEventListener('click', onAnyClick)
  document.addEventListener('keydown', onKey)
  // No custom panning handlers in this rollback state

  // Cleanup listeners when component is destroyed
  ;(graphComponent as any)._codexCleanup = () => {
    container.removeEventListener('contextmenu', onContextMenu)
    container.removeEventListener('wheel', onWheel)
    document.removeEventListener('click', onAnyClick)
    document.removeEventListener('keydown', onKey)
    // nothing else to clean up
  }
}

function normalizeText(text: string | undefined): string {
  return text ?? ''
}

function getNodeDisplayLabel(item: NodeData): string {
  const props = item.properties as unknown
  const nameCandidate = (() => {
    if (!props) {
      return null
    }
    const sanitize = (value: unknown) => {
      const str = normalizeText(String(value)).trim()
      return str.length ? str : null
    }
    const candidateFromRecord = (record: Record<string, unknown>) => {
      for (const [key, value] of Object.entries(record)) {
        if (!value) continue
        const lower = key.toLowerCase()
        if (lower === 'name' || lower.endsWith('_name')) {
          const sanitized = sanitize(value)
          if (sanitized) {
            return sanitized
          }
        }
      }
      return null
    }
    if (typeof props === 'object' && !Array.isArray(props)) {
      const record = props as Record<string, unknown>
      const direct = candidateFromRecord(record)
      if (direct != null) {
        return direct
      }
    }
    if (Array.isArray(props)) {
      for (const entry of props as unknown[]) {
        if (!entry) continue
        if (typeof entry === 'string') {
          const trimmed = entry.trim()
          const idx = trimmed.indexOf(':')
          if (idx > 0) {
            const keyPart = trimmed.slice(0, idx).trim().toLowerCase()
            if (keyPart === 'name' || keyPart.endsWith('_name')) {
              const sanitized = sanitize(trimmed.slice(idx + 1))
              if (sanitized) {
                return sanitized
              }
            }
          }
        } else if (typeof entry === 'object') {
          const record = entry as Record<string, unknown>
          const candidate = candidateFromRecord(record)
          if (candidate != null) {
            return candidate
          }
        }
      }
    }
    return null
  })()
  if (nameCandidate != null) {
    return nameCandidate.replace(/_/g, ' ')
  }
  const normalized = normalizeText(item.label ?? item.id).trim()
  if (!normalized.length) {
    return item.id
  }
  return normalized.replace(/_/g, ' ')
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

function resolveNodeFromItem(item: unknown): INode | null {
  if (isNodeItem(item)) {
    return item
  }
  if (
    !!item &&
    typeof item === 'object' &&
    'owner' in (item as Record<string, unknown>) &&
    (item as Record<string, unknown>).owner &&
    typeof (item as Record<string, unknown>).owner === 'object' &&
    'ports' in ((item as Record<string, unknown>).owner as Record<string, unknown>)
  ) {
    return ((item as Record<string, unknown>).owner as unknown) as INode
  }
  return null
}

function resolveEdgeFromItem(item: unknown): IEdge | null {
  if (isEdgeItem(item)) {
    return item
  }
  if (
    !!item &&
    typeof item === 'object' &&
    'owner' in (item as Record<string, unknown>) &&
    (item as Record<string, unknown>).owner &&
    typeof (item as Record<string, unknown>).owner === 'object'
  ) {
    const owner = (item as Record<string, unknown>).owner as Record<string, unknown>
    if ('sourceNode' in owner && 'targetNode' in owner) {
      return (owner as unknown) as IEdge
    }
  }
  return null
}

function applySelection(item: unknown | null) {
  selectedNode.value = null
  selectedEdge.value = null
  lastSelectedINode = null
  lastSelectedIEdge = null
  if (!item) {
    applyFilterHighlight()
    return
  }
  const node = resolveNodeFromItem(item)
  if (node) {
    selectedNode.value = (node.tag as NodeData) ?? null
    lastSelectedINode = node
    applyFilterHighlight()
    return
  }
  const edge = resolveEdgeFromItem(item)
  if (edge) {
    selectedEdge.value = (edge.tag as EdgeData) ?? null
    lastSelectedIEdge = edge
    applyFilterHighlight()
    return
  }
  // Fallback: nothing matched, just re-apply styles
  applyFilterHighlight()
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
  const group = ((item as any).type ?? label).toString()
  const fill = (item.color as string) || getColorForIdentifier(group)
  return new ShapeNodeStyle({
    shape: 'ellipse',
    fill,
    stroke: '3px #ffffff'
  })
}

function createEdgeStyle(item: EdgeData): PolylineEdgeStyle {
  const relationshipLabel = (item.relationship ?? item.label ?? '').trim()
  const color = getColorForRelationship(relationshipLabel)
  item.color = color
  return new PolylineEdgeStyle({
    stroke: new Stroke({ fill: color, thickness: 2 }),
    targetArrow: new Arrow({ type: 'triangle', fill: color, stroke: color })
  })
}

function configureEdgeLabelPlacement(graph: IGraph): void {
  for (const edge of graph.edges) {
    if (edge.labels.size === 0) {
      continue
    }
    const label = edge.labels.get(0)
    if (label) {
      graph.setLabelLayoutParameter(
        label,
        edgeLabelModel.createParameterFromCenter(0.5, 'left-of-edge')
      )
    }
  }
}

function reduceLabelOverlapsAndPlace(graph: IGraph): void {
  const labeling = new GenericLabeling({
    scope: LabelingScope.ALL,
    reduceLabelOverlaps: true,
    deterministic: true
  })
  graph.applyLayout(labeling)
}


function graphBoundsTooTight(graph: IGraph): boolean {
  if (!graph) return false
  const nodes = Array.from(graph.nodes)
  if (nodes.length <= 3) {
    return false
  }
  let minX = Infinity
  let minY = Infinity
  let maxX = -Infinity
  let maxY = -Infinity
  for (const node of nodes) {
    const layout = (node as any).layout as Rect
    minX = Math.min(minX, layout.x)
    minY = Math.min(minY, layout.y)
    maxX = Math.max(maxX, layout.x + layout.width)
    maxY = Math.max(maxY, layout.y + layout.height)
  }
  const width = Math.max(maxX - minX, 1)
  const height = Math.max(maxY - minY, 1)
  const scaleFactor = Math.max(1, Math.sqrt(nodes.length) * 0.12)
  const minWidth = baseNodeWidth * 1.4 * scaleFactor
  const minHeight = baseNodeHeight * 1.4 * scaleFactor
  const boundingArea = width * height
  const avgAreaPerNode = boundingArea / nodes.length
  const targetAreaPerNode = baseNodeWidth * baseNodeHeight * 1.2
  return width < minWidth || height < minHeight || avgAreaPerNode < targetAreaPerNode
}

function spreadNodesInGrid(graph: IGraph): void {
  const nodes = Array.from(graph.nodes)
  if (nodes.length <= 1) {
    return
  }
  const cols = Math.ceil(Math.sqrt(nodes.length))
  const rows = Math.ceil(nodes.length / cols)
  const spacingX = baseNodeWidth * 2.3
  const spacingY = baseNodeHeight * 2.0
  const startX = -((cols - 1) * spacingX) / 2
  const startY = -((rows - 1) * spacingY) / 2
  nodes.forEach((node, index) => {
    const col = index % cols
    const row = Math.floor(index / cols)
    const centerX = startX + col * spacingX
    const centerY = startY + row * spacingY
    graph.setNodeCenter(node, new Point(centerX, centerY))
  })
}

function expandGraphExtent(graph: IGraph, minGap: number): void {
  if (!graph) return
  const nodes = Array.from(graph.nodes)
  if (nodes.length <= 1) {
    return
  }
  let minX = Infinity
  let minY = Infinity
  let maxX = -Infinity
  let maxY = -Infinity
  const centers: { node: INode; x: number; y: number }[] = []
  for (const node of nodes) {
    const layout = (node as any).layout as Rect
    const cx = layout.x + layout.width / 2
    const cy = layout.y + layout.height / 2
    centers.push({ node, x: cx, y: cy })
    minX = Math.min(minX, cx)
    minY = Math.min(minY, cy)
    maxX = Math.max(maxX, cx)
    maxY = Math.max(maxY, cy)
  }
  const width = Math.max(maxX - minX, 1)
  const height = Math.max(maxY - minY, 1)
  const sqrtN = Math.sqrt(nodes.length)
  const targetWidth = Math.max((baseNodeWidth + minGap) * sqrtN * 1.25, minGap * (sqrtN + 1.4))
  const targetHeight = Math.max((baseNodeHeight + minGap * 0.5) * sqrtN * 1.25, minGap * 0.7 * (sqrtN + 1.4))
  const factor = Math.max(targetWidth / width, targetHeight / height, 1)
  if (factor <= 1.12) {
    return
  }
  const centerX = (minX + maxX) / 2
  const centerY = (minY + maxY) / 2
  for (const entry of centers) {
    const newX = centerX + (entry.x - centerX) * factor
    const newY = centerY + (entry.y - centerY) * factor
    graph.setNodeCenter(entry.node, new Point(newX, newY))
  }
}

async function applySimpleLayout() {
  if (!graphComponent) {
    return
  }
  const graph = graphComponent.graph
  if (!graph || graph.nodes.size === 0) {
    return
  }

  const preferredLength = Math.max(baseNodeWidth * (nodeScale.value + 0.35), baseNodeHeight * (nodeScale.value + 0.25), 220, 180 * edgeLenScale.value)
  const minimumDistance = Math.max(180, baseNodeWidth * nodeScale.value * 0.9, baseNodeHeight * nodeScale.value * 0.7)
  const componentGap = Math.max(minimumDistance * 2.2, 320 * clusterGapScale.value)

  const organicLayout = new OrganicLayout()
  organicLayout.deterministic = true
  organicLayout.preferredEdgeLength = preferredLength
  organicLayout.minimumNodeDistance = minimumDistance
  organicLayout.nodeOverlapsAllowed = false
  organicLayout.considerNodeSizes = true
  organicLayout.considerNodeLabels = true
  organicLayout.maximumDuration = 5000
  organicLayout.qualityTimeRatio = 0.8

  await graph.applyLayout(organicLayout)

  if (graph.nodes.size > 1) {
    const componentLayout = new ComponentLayout()
    componentLayout.minimumComponentDistance = componentGap
    await graph.applyLayout(componentLayout)
  }

  expandGraphExtent(graph, componentGap)

  if (graphBoundsTooTight(graph)) {
    console.info('Organic layout too tight; applying grid fallback', {
      nodeCount: graph.nodes.size,
      minDistance: minimumDistance,
      componentGap
    })
    spreadNodesInGrid(graph)
  }
}


async function loadGraph(file: string) {
  if (!graphComponent) {
    return
  }
  await layoutBridgePromise
  statusMessage.value = `Loading ${file} ...`

  await ensureEvaluationSummaryLoaded()
  applyMetricsFor(file)


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
  resetRelationshipColors()

  const nodes = (data.nodes ?? []).filter(item => !!item?.id)
  const edges = (data.edges ?? []).filter(
    item => resolveEdgeSource(item) && resolveEdgeTarget(item)
  )

  console.info('loadGraph dataset', file, 'nodes', nodes.length, 'edges', edges.length, 'sampleEdge', edges[0])

  graphStats.value = computeGraphStats(nodes, edges)

  // make sure per-file settings are loaded before laying out
  ensureSettingsFor(file)
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
  edgesSource.edgeCreator.styleProvider = item => createEdgeStyle(item)

  builder.buildGraph()
  console.info('graph edges after build', graph.edges.size)
  configureEdgeLabelPlacement(graph)
  await applySimpleLayout()
  // apply current node scaling to the freshly built graph
  applyNodeScale()
  await adjustClusterSpacing()
  adaptEdgeLabelSizes()
  adaptEdgeLabelSizes()
  reduceLabelOverlapsAndPlace(graph)
  graphComponent.fitGraphBounds()
  adjustInitialZoomForNodeCount(graphComponent.graph.nodes.size)
  const identifier = data.id ? `Loaded ${data.id}` : `Loaded ${file}`
  statusMessage.value = `${identifier} (${nodes.length} nodes, ${edges.length} edges)`
  // Apply any active filters/highlights after loading
  applyFilterHighlight()
  // remember last successful file
  lastLoadedFile = file
}

// Resize nodes and label fonts according to nodeScale
function applyNodeScale() {
  if (!graphComponent) return
  const graph = graphComponent.graph as any
  const w = baseNodeWidth * nodeScale.value
  const h = baseNodeHeight * nodeScale.value
  const fontSize = Math.max(12, Math.round(baseNodeFont * nodeScale.value))
  const maxW = Math.max(60, w - 40)
  const maxH = Math.max(50, h - 50)
  for (const n of graph.nodes) {
    try {
      const l: any = n.layout
      const cx = l.x + l.width / 2
      const cy = l.y + l.height / 2
      const r = new Rect(cx - w / 2, cy - h / 2, w, h)
      graph.setNodeLayout(n, r)
    } catch {}
    // Scale node label style
    if (n.labels && n.labels.size > 0) {
      const label = n.labels.get(0)
      try {
        graph.setStyle(label, new LabelStyle({
          font: new Font({
            fontFamily: "Inter, 'Helvetica Neue', Arial, sans-serif",
            fontSize,
            fontWeight: '600'
          }),
          textFill: '#0f172a',
          wrapping: 'wrap-word',
          maximumSize: new Size(maxW, maxH),
          horizontalTextAlignment: 'center',
          verticalTextAlignment: 'center',
          padding: 8
        }))
        // Ensure label stays centered inside node
        // (defaults are interior center; we keep them)
      } catch {}
    }
  }
  // Update defaults for subsequently created nodes/labels
  try {
    graph.nodeDefaults.size = new Size(w, h)
    graph.nodeDefaults.labels.style = new LabelStyle({
      font: new Font({
        fontFamily: "Inter, 'Helvetica Neue', Arial, sans-serif",
        fontSize,
        fontWeight: '600'
      }),
      textFill: '#0f172a',
      wrapping: 'wrap-word',
      maximumSize: new Size(maxW, maxH),
      horizontalTextAlignment: 'center',
      verticalTextAlignment: 'center',
      padding: 8
    })
  } catch {}
}

// Adjust edge label font size based on current edge length
function adaptEdgeLabelSizes() {
  if (!graphComponent) return
  const graph = graphComponent.graph
  // Reference length around which label size equals baseEdgeFont
  const refLen = 360
  for (const e of graph.edges) {
    if (e.labels.size === 0) {
      continue
    }
    const label = e.labels.get(0)
    // Compute approximate length using source/target centers and bends if available
    let length = 0
    try {
      const pts: Point[] = []
      const sc: any = (e.sourceNode as any).layout.center
      pts.push(new Point(sc.x, sc.y))
      // try to include bends if exposed
      const bends: any = (e as any).bends
      if (bends && typeof bends[Symbol.iterator] === 'function') {
        for (const b of bends as any) {
          const p: any = (b as any).location ?? (b as any)
          if (p && typeof p.x === 'number' && typeof p.y === 'number') {
            pts.push(new Point(p.x, p.y))
          }
        }
      }
      const tc: any = (e.targetNode as any).layout.center
      pts.push(new Point(tc.x, tc.y))
      for (let i = 1; i < pts.length; i++) {
        const dx = pts[i].x - pts[i - 1].x
        const dy = pts[i].y - pts[i - 1].y
        length += Math.sqrt(dx * dx + dy * dy)
      }
    } catch {
      // fallback: straight-line distance
      const s: any = (e.sourceNode as any).layout.center
      const t: any = (e.targetNode as any).layout.center
      const dx = t.x - s.x
      const dy = t.y - s.y
      length = Math.sqrt(dx * dx + dy * dy)
    }
    // Map length to font size factor (clamped)
    const factor = Math.max(0.70, Math.min(1.60, length / refLen))
    const fontSize = Math.max(10, Math.round(baseEdgeFont * factor))
    try {
      graph.setStyle(
        label,
        new LabelStyle({
          font: new Font({
            fontFamily: "Inter, 'Helvetica Neue', Arial, sans-serif",
            fontSize,
            fontWeight: '600'
          }),
          textFill: '#0f172a',
          padding: 4
        })
      )
    } catch {}
  }
}

async function onEdgeLenShorter() {
  edgeLenScale.value = Math.max(0.6, edgeLenScale.value - 0.1)
  saveSettingsForCurrent()
  if (!graphComponent) return
  await applySimpleLayout()
  await adjustClusterSpacing()
  adaptEdgeLabelSizes()
  reduceLabelOverlapsAndPlace(graphComponent.graph)
  graphComponent.fitGraphBounds()
  adjustInitialZoomForNodeCount(graphComponent.graph.nodes.size)
}

async function onEdgeLenLonger() {
  edgeLenScale.value = Math.min(1.6, edgeLenScale.value + 0.1)
  saveSettingsForCurrent()
  if (!graphComponent) return
  await applySimpleLayout()
  await adjustClusterSpacing()
  adaptEdgeLabelSizes()
  reduceLabelOverlapsAndPlace(graphComponent.graph)
  graphComponent.fitGraphBounds()
  adjustInitialZoomForNodeCount(graphComponent.graph.nodes.size)
}

async function onClusterCloser() {
  clusterGapScale.value = Math.max(0.0, clusterGapScale.value - 0.1)
  saveSettingsForCurrent()
  if (!graphComponent) return
  await adjustClusterSpacing()
  adaptEdgeLabelSizes()
  reduceLabelOverlapsAndPlace(graphComponent.graph)
  graphComponent.fitGraphBounds()
  adjustInitialZoomForNodeCount(graphComponent.graph.nodes.size)
}

async function onClusterWider() {
  clusterGapScale.value = Math.min(3.0, clusterGapScale.value + 0.1)
  saveSettingsForCurrent()
  if (!graphComponent) return
  await adjustClusterSpacing()
  adaptEdgeLabelSizes()
  reduceLabelOverlapsAndPlace(graphComponent.graph)
  graphComponent.fitGraphBounds()
  adjustInitialZoomForNodeCount(graphComponent.graph.nodes.size)
}

async function onNodeSmaller() {
  nodeScale.value = Math.max(0.6, nodeScale.value - 0.1)
  saveSettingsForCurrent()
  if (!graphComponent) return
  applyNodeScale()
  await adjustClusterSpacing()
  adaptEdgeLabelSizes()
  reduceLabelOverlapsAndPlace(graphComponent.graph)
  graphComponent.fitGraphBounds()
  adjustInitialZoomForNodeCount(graphComponent.graph.nodes.size)
}

async function onNodeLarger() {
  nodeScale.value = Math.min(2.5, nodeScale.value + 0.1)
  saveSettingsForCurrent()
  if (!graphComponent) return
  applyNodeScale()
  await adjustClusterSpacing()
  adaptEdgeLabelSizes()
  reduceLabelOverlapsAndPlace(graphComponent.graph)
  graphComponent.fitGraphBounds()
  adjustInitialZoomForNodeCount(graphComponent.graph.nodes.size)
}

// Separate clusters/components with extra gap so different groups don't look crowded
async function adjustClusterSpacing() {
  if (!graphComponent) return
  const graph = graphComponent.graph
  if (!graph || graph.nodes.size === 0) return

  const layout = new ComponentLayout()
  layout.minimumComponentDistance = Math.max(80, 240 * clusterGapScale.value)

  await graph.applyLayout(layout)
}


  
function adjustInitialZoomForNodeCount(count: number) {
  if (!graphComponent) {
    return
  }
  const graph = graphComponent.graph
  if (!graph) {
    return
  }
  const gc = graphComponent as any
  const currentZoom: number =
    typeof gc.zoom === 'number' && Number.isFinite(gc.zoom) ? gc.zoom : 1
  const nodeCount = Number.isFinite(count) && count > 0 ? count : graph.nodes.size
  if (!nodeCount) {
    return
  }
  const minimumPixelWidth = computeMinReadableNodePixelWidth(nodeCount)
  const worldNodeWidth = baseNodeWidth * nodeScale.value
  if (!Number.isFinite(worldNodeWidth) || worldNodeWidth <= 0) {
    return
  }
  const minZoom = minimumPixelWidth / worldNodeWidth
  if (!Number.isFinite(minZoom) || minZoom <= 0) {
    return
  }
  const readableMinZoom = Math.max(minZoom * 0.92, AUTO_MINIMUM_ZOOM_FLOOR)
  const targetMinZoom = Math.max(AUTO_MINIMUM_ZOOM_FLOOR, readableMinZoom * 0.25)

  const existingMin =
    typeof gc.minimumZoom === 'number' && Number.isFinite(gc.minimumZoom)
      ? gc.minimumZoom
      : AUTO_MINIMUM_ZOOM_FLOOR
  if (!Number.isFinite(existingMin) || Math.abs(existingMin - targetMinZoom) > 0.002) {
    gc.minimumZoom = targetMinZoom
  }

  const existingMax =
    typeof gc.maximumZoom === 'number' && Number.isFinite(gc.maximumZoom)
      ? gc.maximumZoom
      : 4
  const rawDesiredMax = Math.max(existingMax, readableMinZoom * 4.5, 6)
  const targetMaxZoom = Math.max(
    readableMinZoom + 0.05,
    Math.min(rawDesiredMax, AUTO_MAXIMUM_ZOOM_CAP)
  )
  if (!Number.isFinite(existingMax) || Math.abs(existingMax - targetMaxZoom) > 0.01) {
    gc.maximumZoom = targetMaxZoom
  }

  const comfyUpper = Math.max(targetMinZoom, readableMinZoom * 0.5)
  let desiredZoom = currentZoom
  if (desiredZoom > comfyUpper) {
    desiredZoom = comfyUpper
  }
  if (desiredZoom < targetMinZoom) {
    desiredZoom = targetMinZoom
  }
  if (desiredZoom > targetMaxZoom) {
    desiredZoom = targetMaxZoom
  }

  if (Math.abs(desiredZoom - currentZoom) > 0.005) {
    try {
      gc.zoom = desiredZoom
      console.info('Adjusted graph zoom bounds', {
        nodeCount,
        minimumPixelWidth,
        readableMinZoom,
        targetMinZoom,
        targetMaxZoom,
        previousZoom: currentZoom,
        newZoom: desiredZoom
      })
    } catch (error) {
      console.warn('Failed to enforce readable zoom', error)
    }
  }
}

function dimNodeStyle(nodeData: NodeData): ShapeNodeStyle {
  const group = (((nodeData as any)?.type) ?? nodeData.label ?? nodeData.id).toString()
  const color = (nodeData.color as string) || getColorForIdentifier(group)
  return new ShapeNodeStyle({
    shape: 'ellipse',
    fill: hexToRgba(color, 0.16),
    stroke: '1px rgba(255,255,255,0.6)'
  })
}

function dimEdgeStyle(edgeData: EdgeData): PolylineEdgeStyle {
  const color = (edgeData.color as string) || getColorForRelationship(edgeData.relationship ?? edgeData.label ?? '')
  const dim = hexToRgba(color, 0.18)
  return new PolylineEdgeStyle({
    stroke: new Stroke({ fill: dim, thickness: 1 }),
    targetArrow: new Arrow({ type: 'triangle', fill: dim, stroke: dim })
  })
}

function applyFilterHighlight() {
  if (!graphComponent) {
    return
  }
  const graph = graphComponent.graph
  const nodeFilter = activeNodeLabelFilter.value
  const relFilter = activeRelTypeFilter.value
  const doFilter = filterMode.value === 'filter'
  let nodeMatchesCount = 0
  let edgeMatchesCount = 0
  for (const node of graph.nodes) {
    const tag = (node.tag as NodeData | undefined)
    const group = ((tag as any)?.type ?? tag?.label ?? tag?.id ?? '').toString()
    const matches = nodeFilter ? group === nodeFilter : true
    if (matches) nodeMatchesCount++
    const desiredStyle = matches || (!nodeFilter && !relFilter) ? createNodeStyle(tag ?? { id: 'x', label: group }) : dimNodeStyle(tag ?? { id: 'x', label: group })
    if (doFilter && !(matches || (!nodeFilter && !relFilter))) {
      // nearly invisible in filter mode
      graph.setStyle(node, new ShapeNodeStyle({ shape: 'ellipse', fill: 'rgba(0,0,0,0)', stroke: '1px rgba(0,0,0,0)' }))
    } else {
      graph.setStyle(node, desiredStyle)
    }
  }

  for (const edge of graph.edges) {
    const etag = (edge.tag as EdgeData | undefined)
    const type = (etag?.relationship ?? etag?.label ?? '').trim()
    const matches = relFilter ? type === relFilter : true
    if (matches) edgeMatchesCount++
    const desiredStyle = matches || (!nodeFilter && !relFilter) ? createEdgeStyle(etag ?? {}) : dimEdgeStyle(etag ?? {})
    if (doFilter && !(matches || (!nodeFilter && !relFilter))) {
      const transparent = 'rgba(0,0,0,0)'
      graph.setStyle(edge, new PolylineEdgeStyle({ stroke: new Stroke({ fill: transparent, thickness: 1 }), targetArrow: new Arrow({ type: 'triangle', fill: transparent, stroke: transparent }) }))
    } else {
      graph.setStyle(edge, desiredStyle)
    }
  }

  // Keep label placement stable
  configureEdgeLabelPlacement(graph)
  adaptEdgeLabelSizes()
  reduceLabelOverlapsAndPlace(graph)
  // Re-apply selection emphasis on top
  highlightSelectedEdgeOnTop()

  // If filter hides everything (no matches), auto-clear that filter to avoid blank screen
  if (doFilter || (!doFilter && (nodeFilter || relFilter))) {
    let changed = false
    if (nodeFilter && nodeMatchesCount === 0) {
      activeNodeLabelFilter.value = null
      changed = true
    }
    if (relFilter && edgeMatchesCount === 0) {
      activeRelTypeFilter.value = null
      changed = true
    }
    if (changed) {
      // reapply without invalid filters
      applyFilterHighlight()
    }
  }
}

async function resolveGraphData(file: string): Promise<GraphPayload | null> {
  const staticData = graphModules[file]
  if (staticData) {
    return normalizeGraphPayload(staticData as unknown as Record<string, unknown>)
  }
  console.warn(`Dataset ${file} is not available in the current build output.`)
  return null
}

// Accepts both canonical schema and nested category schema, returns canonical GraphPayload
function normalizeGraphPayload(raw: Record<string, unknown>): GraphPayload {
  // Canonical or flexible schemas
  const nodesRaw = (raw as any).nodes
  const edgesRaw = (raw as any).edges

  const isCanonicalNodeArray =
    Array.isArray(nodesRaw) &&
    (nodesRaw as unknown[]).every(
      item => item !== null && typeof item === 'object' && typeof (item as Record<string, unknown>).id === 'string'
    )
  const isCanonicalEdgeArray =
    Array.isArray(edgesRaw) &&
    (edgesRaw as unknown[]).every(
      item =>
        item !== null &&
        typeof item === 'object' &&
        (typeof (item as Record<string, unknown>).source === 'string' ||
          typeof (item as Record<string, unknown>).from === 'string') &&
        (typeof (item as Record<string, unknown>).target === 'string' ||
          typeof (item as Record<string, unknown>).to === 'string')
    )

  if (isCanonicalNodeArray && isCanonicalEdgeArray) {
    return raw as GraphPayload
  }

  // Helper detectors
  const preferKeys = (o: any, keys: string[]): any => {
    for (const k of keys) {
      if (o && o[k] != null) return o[k]
    }
    return undefined
  }
  const findIdKey = (obj: any, type?: string): { key: string | null; value: any } => {
    if (!obj || typeof obj !== 'object') return { key: null, value: null }
    const lowerType = type ? String(type).toLowerCase() : ''
    const keys = Object.keys(obj)
    // exact matches
    const exact = ['id', 'ID', '_id']
    for (const k of exact) if (k in obj) return { key: k, value: obj[k] }
    // type-specific like Film_ID, FilmId
    if (lowerType) {
      const spec = keys.find(k => k.toLowerCase() === `${lowerType}_id` || k.toLowerCase() === `${lowerType}id`)
      if (spec) return { key: spec, value: obj[spec] }
    }
    // any key that ends with id
    const anyId = keys.find(k => /(^|[_-])id$/i.test(k))
    if (anyId) return { key: anyId, value: obj[anyId] }
    return { key: null, value: null }
  }
  const toStr = (v: any) => (v == null ? '' : String(v))

  // Case A: nodes is an array of arbitrary objects
  if (Array.isArray(nodesRaw)) {
    const nodes: NodeData[] = []
    const idToGlobal = new Map<string, string>()
    const typeToMap = new Map<string, Map<string, string>>()
    const plainMap = new Map<string, string>()
    const hasConflict = new Set<string>()

    let idx = 0
    for (const n of nodesRaw as any[]) {
      idx += 1
      // If no explicit type, fall back to node label as type (common in simple schemas)
      const type = toStr(preferKeys(n, ['type', 'Type', 'nodeType', 'labelType', 'label', 'Label'])) || 'Node'
      const { value: idValRaw } = findIdKey(n, type)
      const idKey = idValRaw != null ? toStr(idValRaw) : String(idx)
      const globalId = `${type}:${idKey}`
      const label = toStr(preferKeys(n, ['name', 'Name', 'title', 'Title', 'label', 'Label'])) || `${type} ${idKey}`
      nodes.push({ ...(n as object), id: globalId, label, type } as NodeData)
      // maps
      if (n.id != null && toStr(n.id) !== idKey) {
        idToGlobal.set(toStr(n.id), globalId)
      }
      if (!typeToMap.has(type)) typeToMap.set(type, new Map())
      typeToMap.get(type)!.set(idKey, globalId)
      if (plainMap.has(idKey) && plainMap.get(idKey) !== globalId) hasConflict.add(idKey)
      else plainMap.set(idKey, globalId)
    }

    // resolver
    const resolveRef = (val: any, t?: any): string | null => {
      if (typeof val === 'string') {
        if (val.includes(':')) return val
        if (t && typeToMap.get(String(t))?.get(val)) return typeToMap.get(String(t))!.get(val)!
        if (!hasConflict.has(val) && plainMap.get(val)) return plainMap.get(val)!
        return null
      }
      if (typeof val === 'number') {
        const s = String(val)
        if (t && typeToMap.get(String(t))?.get(s)) return typeToMap.get(String(t))!.get(s)!
        if (!hasConflict.has(s) && plainMap.get(s)) return plainMap.get(s)!
        return null
      }
      if (val && typeof val === 'object') {
        const tpe = preferKeys(val, ['type', 'Type'])
        const idv = preferKeys(val, ['id', 'ID', '_id', 'value'])
        if (tpe != null && idv != null) return resolveRef(idv, tpe)
      }
      return null
    }

    const edges: EdgeData[] = []
    if (Array.isArray(edgesRaw)) {
      for (const e of edgesRaw as any[]) {
        const rel = toStr(preferKeys(e, ['relationship', 'label', 'type']))
        let from: string | null = null
        let to: string | null = null

        // mappings { source_id, target_id } with types from source/target
        if (e.mappings) {
          const sid = preferKeys(e.mappings, ['source_id', 'sourceId', 'srcId', 'source'])
          const tid = preferKeys(e.mappings, ['target_id', 'targetId', 'dstId', 'target'])
          const st = preferKeys(e, ['source', 'sourceType'])
          const tt = preferKeys(e, ['target', 'targetType'])
          from = resolveRef(sid, st)
          to = resolveRef(tid, tt)
        }
        // direct from/to (string or object)
        if (!from && (e.from != null)) from = resolveRef(e.from, preferKeys(e, ['fromType']))
        if (!to && (e.to != null)) to = resolveRef(e.to, preferKeys(e, ['toType']))
        // classic *_value with source/target types
        if ((!from || !to) && e.source != null && e.target != null && (e.source_value != null || e.target_value != null)) {
          from = from ?? resolveRef(e.source_value, e.source)
          to = to ?? resolveRef(e.target_value, e.target)
        }
        // direct source/target given as id string (or object), without *_value
        if ((!from || !to) && e.source != null && e.target != null) {
          const st = preferKeys(e, ['sourceType', 'source_label', 'sourceLabel', 'sourceCategory'])
          const tt = preferKeys(e, ['targetType', 'target_label', 'targetLabel', 'targetCategory'])
          from = from ?? resolveRef(e.source, st)
          to = to ?? resolveRef(e.target, tt)
        }
        // sourceId/targetId variants with explicit types
        if ((!from || !to) && (e.sourceId != null || e.targetId != null)) {
          from = from ?? resolveRef(e.sourceId, preferKeys(e, ['sourceType', 'source']))
          to = to ?? resolveRef(e.targetId, preferKeys(e, ['targetType', 'target']))
        }
        // fallback: exact match against node.id
        if ((!from || !to) && (typeof e.source === 'string' || typeof e.source === 'number')) {
          const s = toStr(e.source)
          if (!from && idToGlobal.get(s)) from = idToGlobal.get(s)!
          if (!from && plainMap.get(s) && !hasConflict.has(s)) from = plainMap.get(s)!
        }
        if ((!from || !to) && (typeof e.target === 'string' || typeof e.target === 'number')) {
          const t = toStr(e.target)
          if (!to && idToGlobal.get(t)) to = idToGlobal.get(t)!
          if (!to && plainMap.get(t) && !hasConflict.has(t)) to = plainMap.get(t)!
        }

        if (from && to) {
          edges.push({ from, to, relationship: rel, label: rel })
          continue
        }
      }
    }
    return { id: (raw as any).id, nodes, edges }
  }
  // Nested case: nodes is an object { TypeA: [...], TypeB: [...] }
  if (nodesRaw && typeof nodesRaw === 'object') {
    const nodes: NodeData[] = []
    // Map of type -> map(keyUsedInEdges => globalId)
    const refMap = new Map<string, Map<string, string>>()
    // Special composite key map for Schedule (film+cinema[+date] -> globalId)
    const scheduleCompositeMap = new Map<string, string>()
    const typeLower = (s: string) => String(s).toLowerCase()
    for (const [type, arr] of Object.entries(nodesRaw as Record<string, unknown>)) {
      if (!Array.isArray(arr)) continue
      const lower = typeLower(type)
      const mapForType = new Map<string, string>()
      refMap.set(String(type), mapForType)
      let idx = 0
      for (const n of arr as any[]) {
        idx += 1
        // preferred id: type-specific key (e.g., Film_ID) or generic id/ID/_id
        const keys = Object.keys(n)
        const specKey = keys.find(k => k.toLowerCase() === `${lower}_id` || k.toLowerCase() === `${lower}id`)
        let idVal = (specKey ? n[specKey] : (n.id ?? n.ID ?? n._id))
        const edgeKey = idVal != null ? String(idVal) : String(idx) // edges use *_value referencing either id or 1-based index
        const globalId = `${type}:${edgeKey}`
        const label = (n?.name ?? n?.Title ?? n?.label ?? n?.IATA ?? `${type} ${edgeKey}`) as string
        nodes.push({ ...(n as object), id: globalId, label, type } as NodeData)
        mapForType.set(edgeKey, globalId)

        // Build composite key index for Schedule
        if (lower === 'schedule') {
          const filmId = n.Film_ID ?? n.film_id ?? n.FilmId ?? n.filmid
          const cinemaId = n.Cinema_ID ?? n.cinema_id ?? n.CinemaId ?? n.cinemaid
          const dateVal = n.Date ?? n.date
          if (filmId != null && cinemaId != null) {
            const k1 = `film=${String(filmId)}|cinema=${String(cinemaId)}`
            scheduleCompositeMap.set(k1, globalId)
            if (dateVal != null) {
              const k2 = `${k1}|date=${String(dateVal)}`
              scheduleCompositeMap.set(k2, globalId)
            }
          }
        }
      }
    }
    const edges: EdgeData[] = []
    if (Array.isArray(edgesRaw)) {
      for (const e of edgesRaw as any[]) {
        // 1) New format with explicit mappings { source_id, target_id }
        if (e && e.source && e.target && e.mappings && typeof e.mappings === 'object') {
          const sType = String(e.source)
          const tType = String(e.target)
          const sMap = refMap.get(sType)
          const tMap = refMap.get(tType)
          const sid = (e.mappings.source_id ?? e.mappings.sourceId ?? e.mappings.srcId ?? e.mappings.source)
          const tid = (e.mappings.target_id ?? e.mappings.targetId ?? e.mappings.dstId ?? e.mappings.target)
          const fromId = sMap?.get(String(sid))
          const toId = tMap?.get(String(tid))
          const rel = (e.relationship ?? e.label ?? '') as string
          if (fromId && toId) {
            edges.push({ from: fromId, to: toId, relationship: rel, label: rel, ...(e.edge_properties ? { properties: e.edge_properties } : {}) })
            continue
          }
          // fall through to other strategies if mapping failed
        }
        // 2) Classic format with *_value
        if (e && e.source && e.target && e.source_value !== undefined && e.target_value !== undefined) {
          const sType = String(e.source)
          const tType = String(e.target)
          const sMap = refMap.get(sType)
          const tMap = refMap.get(tType)
          let fromId = sMap?.get(String(e.source_value))
          const toId = tMap?.get(String(e.target_value))
          const rel = (e.relationship ?? e.label ?? '') as string
          if (fromId && toId) {
            edges.push({ from: fromId, to: toId, relationship: rel, label: rel, ...(e.edge_properties ? { properties: e.edge_properties } : {}) })
            continue
          }
          // fallback heuristics for special cases
          if (typeLower(sType) === 'schedule' && e.edge_properties) {
            const props = e.edge_properties as any
            // Try composite key lookup to find the correct Schedule node when source_value is ambiguous
            const filmId = props.Film_ID ?? props.film_id ?? props.FilmId ?? props.filmid
            const cinemaId = props.Cinema_ID ?? props.cinema_id ?? props.CinemaId ?? props.cinemaid
            const dateVal = props.Date ?? props.date
            if (filmId != null && cinemaId != null) {
              const k2 = `film=${String(filmId)}|cinema=${String(cinemaId)}|date=${String(dateVal)}`
              const k1 = `film=${String(filmId)}|cinema=${String(cinemaId)}`
              fromId = scheduleCompositeMap.get(k2) ?? scheduleCompositeMap.get(k1) ?? fromId
            }
            if (fromId && toId) {
              edges.push({ from: fromId, to: toId, relationship: rel, label: rel, ...(e.edge_properties ? { properties: e.edge_properties } : {}) })
              continue
            }
          }
        } else if (e && (e.from || e.source) && (e.to || e.target)) {
          edges.push(e as EdgeData)
        }
      }
    }
    return { id: (raw as any).id, nodes, edges }
  }
  // Fallback: return as-is, builder will likely result in empty
  return (raw as unknown) as GraphPayload
}
// Helpers and actions (context menu & editing)
function updateStatsFromGraph() {
  if (!graphComponent) {
    return
  }
  const nodes: NodeData[] = []
  const edges: EdgeData[] = []
  for (const n of graphComponent.graph.nodes) {
    if (n.tag) {
      nodes.push(n.tag as NodeData)
    }
  }
  for (const e of graphComponent.graph.edges) {
    if (e.tag) {
      edges.push(e.tag as EdgeData)
    }
  }
  graphStats.value = computeGraphStats(nodes, edges)
  // Auto-clear invalid filters for the new graph to avoid a blank view
  const labels = graphStats.value.nodeLabels
  const rels = graphStats.value.relationshipTypes
  if (activeNodeLabelFilter.value && !labels[activeNodeLabelFilter.value]) {
    activeNodeLabelFilter.value = null
  }
  if (activeRelTypeFilter.value && !rels[activeRelTypeFilter.value]) {
    activeRelTypeFilter.value = null
  }
}

function generateUniqueNodeId(): string {
  if (!graphComponent) {
    return `new-node-${Date.now()}`
  }
  const used = new Set(
    Array.from(graphComponent.graph.nodes)
      .map(n => (n.tag as NodeData | undefined)?.id)
      .filter(Boolean) as string[]
  )
  let i = 1
  let id = `new-node-${i}`
  while (used.has(id)) {
    i += 1
    id = `new-node-${i}`
  }
  return id
}

function onAddNodeHere() {
  if (!graphComponent) {
    return
  }
  const graph = graphComponent.graph
  const where = lastContextWorldLocation ?? new Point(0, 0)
  const id = generateUniqueNodeId()
  const nodeData: NodeData = { id, label: 'New Node' }
  const node = graph.createNodeAt(where)
  node.tag = nodeData
  graph.setStyle(node, createNodeStyle(nodeData))
  graph.addLabel(node, getNodeDisplayLabel(nodeData))
  updateStatsFromGraph()
  statusMessage.value = `Node ${id} added`
  showContextMenu.value = false
}

function onStartAddEdge() {
  resetEdgeCreateState()
  edgeCreateActive.value = true
  if (lastSelectedINode) {
    edgeCreateSource = lastSelectedINode
    statusMessage.value = 'Edge: select target node'
  } else {
    statusMessage.value = 'Edge: select source node'
  }
  showContextMenu.value = false
}

function getSelectedIEdge(): IEdge | null {
  if (lastSelectedIEdge && graphComponent?.graph.contains(lastSelectedIEdge)) {
    return lastSelectedIEdge
  }
  if (!graphComponent || !selectedEdge.value) {
    return null
  }
  for (const e of graphComponent.graph.edges) {
    if (e.tag === selectedEdge.value) {
      return e
    }
  }
  return null
}

function onEditSelectedEdgeLabel() {
  if (!graphComponent) {
    return
  }
  const edge = getSelectedIEdge()
  if (!edge) {
    return
  }
  const graph = graphComponent.graph
  let label = edge.labels.size > 0 ? edge.labels.get(0) : null
  if (!label) {
    label = graph.addLabel(edge, '')
    graph.setLabelLayoutParameter(
      label,
      edgeLabelModel.createParameterFromCenter(0.5, 'left-of-edge')
    )
  }
  const im = graphComponent.inputMode as GraphEditorInputMode
  if (im && typeof (im as any).editLabel === 'function') {
    void (im as any).editLabel(label)
  }
  showContextMenu.value = false
}

function onDeleteSelectedEdge() {
  if (!graphComponent) {
    return
  }
  const edge = getSelectedIEdge()
  if (!edge) {
    return
  }
  graphComponent.graph.remove(edge)
  selectedEdge.value = null
  lastSelectedIEdge = null
  updateStatsFromGraph()
  statusMessage.value = 'Edge deleted'
  showContextMenu.value = false
}

function onNodeLabelChip(label: string) {
  activeNodeLabelFilter.value = activeNodeLabelFilter.value === label ? null : label
  applyFilterHighlight()
  saveFilterSettingsForCurrent()
}

function onRelChip(label: string) {
  activeRelTypeFilter.value = activeRelTypeFilter.value === label ? null : label
  applyFilterHighlight()
  saveFilterSettingsForCurrent()
}

function clearFilters() {
  activeNodeLabelFilter.value = null
  activeRelTypeFilter.value = null
  applyFilterHighlight()
  showContextMenu.value = false
  saveFilterSettingsForCurrent()
}

function blinkNode(node: INode) {
  if (!graphComponent) return
  const data = (node.tag as NodeData | undefined) ?? { id: 'x', label: '' }
  const highlight = new ShapeNodeStyle({ shape: 'ellipse', fill: 'rgba(250,204,21,0.3)', stroke: '4px #f59e0b' })
  const originalStyle = node.style
  graphComponent.graph.setStyle(node, highlight)
  setTimeout(() => {
    if (graphComponent && graphComponent.graph.contains(node)) {
      graphComponent.graph.setStyle(node, createNodeStyle(data))
    }
  }, 700)
}

function blinkEdge(edge: IEdge) {
  if (!graphComponent) return
  const data = (edge.tag as EdgeData | undefined) ?? {}
  const highlightColor = '#f59e0b'
  const zoom = ((graphComponent as any)?.zoom as number) || 1
  const screenPx = 10 // target on-screen thickness for blink
  const worldThickness = Math.max(2, screenPx / zoom)
  const highlight = new PolylineEdgeStyle({
    stroke: new Stroke({ fill: highlightColor, thickness: worldThickness, lineCap: 'round', lineJoin: 'round' }),
    targetArrow: new Arrow({ type: 'triangle', fill: highlightColor, stroke: highlightColor })
  })
  const original = edge.style
  graphComponent.graph.setStyle(edge, highlight)
  setTimeout(() => {
    if (graphComponent && graphComponent.graph.contains(edge)) {
      graphComponent.graph.setStyle(edge, createEdgeStyle(data))
    }
  }, 700)
}

function ensureMatchesVisible(matches: INode[]) {
  if (!graphComponent || matches.length === 0) return
  try {
    const gc: any = graphComponent
    const center: Point = gc.center as Point
    const rect = graphComponent.htmlElement.getBoundingClientRect()
    const viewW = Math.max(1, rect.width)
    const viewH = Math.max(1, rect.height)
    const currentZoom: number = gc.zoom as number
    const halfWorldW = viewW / (2 * currentZoom)
    const halfWorldH = viewH / (2 * currentZoom)
    let needZoomOut = false
    let maxDx = 0
    let maxDy = 0
    for (const n of matches) {
      const dx = Math.abs(n.layout.center.x - center.x)
      const dy = Math.abs(n.layout.center.y - center.y)
      maxDx = Math.max(maxDx, dx)
      maxDy = Math.max(maxDy, dy)
      if (dx > halfWorldW || dy > halfWorldH) {
        needZoomOut = true
      }
    }
    if (needZoomOut) {
      const margin = 1.1
      const reqHalfW = Math.max(halfWorldW, maxDx * margin)
      const reqHalfH = Math.max(halfWorldH, maxDy * margin)
      const newZoomX = viewW / (2 * reqHalfW)
      const newZoomY = viewH / (2 * reqHalfH)
      const newZoom = Math.min(currentZoom, newZoomX, newZoomY)
      gc.zoom = newZoom
    }
  } catch {}
}

function focusOnPoint(p: Point) {
  if (!graphComponent) return
  try {
    if ('center' in (graphComponent as any)) {
      ;(graphComponent as any).center = p
      ;(graphComponent as any).zoom = Math.max(1, (graphComponent as any).zoom || 1.2)
      return
    }
  } catch {}
  try {
    if (typeof (graphComponent as any).zoomTo === 'function') {
      const w = 400
      const h = 300
      const Rect = (Point as any).constructor?.Rect || (globalThis as any).Rect
      const r = new (Rect || Object as any)(p.x - w / 2, p.y - h / 2, w, h)
      ;(graphComponent as any).zoomTo(r)
      return
    }
  } catch {}
}

function onSearchNodes() {
  if (!graphComponent) return
  const q = searchNodeQuery.value.trim().toLowerCase()
  if (!q) return
  // Determine whether dataset carries explicit node type
  let anyType = false
  for (const n of graphComponent.graph.nodes) {
    const t = ((n.tag as any)?.type as string) || ''
    if (t) { anyType = true; break }
  }
  const matches: INode[] = []
  if (anyType) {
    for (const n of graphComponent.graph.nodes) {
      const tagAny = (n.tag as any) || {}
      const typeStr = (tagAny.type ?? '').toString().toLowerCase()
      if (typeStr && typeStr.includes(q)) {
        matches.push(n)
      }
    }
  } else {
    for (const n of graphComponent.graph.nodes) {
      const tagNd = (n.tag as NodeData | undefined)
      const label = (tagNd?.label ?? tagNd?.id ?? '').toLowerCase()
      const props = Array.isArray(tagNd?.properties) ? (tagNd!.properties as string[]).join(' ').toLowerCase() : ''
      if (label.includes(q) || props.includes(q)) {
        matches.push(n)
      }
    }
  }
  if (matches.length) {
    // Highlight all matches without jumping; only ensure they are visible (possibly zooming out)
    ensureMatchesVisible(matches)
    for (const m of matches) {
      blinkNode(m)
    }
    statusMessage.value = anyType ? `Found ${matches.length} node type match(es)` : `Found ${matches.length} node match(es)`
    return
  }
  statusMessage.value = 'No matching node/type'
}

function onSearchEdges() {
  if (!graphComponent) return
  const q = searchEdgeQuery.value.trim().toLowerCase()
  if (!q) return
  for (const e of graphComponent.graph.edges) {
    const tag = (e.tag as EdgeData | undefined)
    const r = (tag?.relationship ?? tag?.label ?? '').toLowerCase()
    if (r.includes(q)) {
      const src = e.sourceNode.layout.center
      const tgt = e.targetNode.layout.center
      const mid = new Point((src.x + tgt.x) / 2, (src.y + tgt.y) / 2)
      focusOnPoint(mid)
      blinkEdge(e)
      applySelection(e)
      statusMessage.value = `Found relationship: ${tag?.relationship ?? tag?.label ?? ''}`
      return
    }
  }
  statusMessage.value = 'No matching relationship'
}

// No marquee/select mode toggle for now; keep simple: left-drag on blank pans, click selects

// Grouping & basic collapse/expand (manual)
function onGroupSelected() {
  if (!graphComponent) return
  const gc: any = graphComponent
  const selection: any = gc.selection
  const nodes: INode[] = Array.from((selection && selection.selectedNodes) || [])
  if (nodes.length < 2) {
    statusMessage.value = 'Select at least two nodes to group'
    showContextMenu.value = false
    return
  }
  // Compute center
  let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity
  for (const n of nodes) {
    const r = (n as any).layout
    minX = Math.min(minX, r.x)
    minY = Math.min(minY, r.y)
    maxX = Math.max(maxX, r.x + r.width)
    maxY = Math.max(maxY, r.y + r.height)
  }
  const center = new Point((minX + maxX) / 2, (minY + maxY) / 2)
  const graph = graphComponent.graph
  const groupData: NodeData = { id: `group-${Date.now()}`, label: `Group (${nodes.length})` } as any
  const groupNode = graph.createNodeAt(center)
  groupNode.tag = Object.assign(groupData, { isGroup: true, children: nodes.map(n => (n.tag as NodeData)?.id) })
  graph.setStyle(groupNode, new ShapeNodeStyle({ shape: 'round-rectangle', fill: '#e5e7eb', stroke: '3px #334155' }))
  graph.addLabel(groupNode, (groupNode.tag as any).label)
  applySelection(groupNode)
  statusMessage.value = 'Group node created'
  showContextMenu.value = false
}

function onCollapseGroup() {
  if (!graphComponent || !selectedNode.value) return
  const ids: string[] = ((selectedNode.value as any).children as string[]) || []
  const graph = graphComponent.graph
  for (const n of graph.nodes) {
    const id = (n.tag as NodeData | undefined)?.id
    if (id && ids.includes(id)) {
      graph.setStyle(n, new ShapeNodeStyle({ shape: 'ellipse', fill: 'rgba(0,0,0,0)', stroke: '1px rgba(0,0,0,0)' }))
    }
  }
  for (const e of graph.edges) {
    const srcId = (e.sourceNode.tag as NodeData | undefined)?.id
    const tgtId = (e.targetNode.tag as NodeData | undefined)?.id
    if ((srcId && ids.includes(srcId)) || (tgtId && ids.includes(tgtId))) {
      const transparent = 'rgba(0,0,0,0)'
      graph.setStyle(e, new PolylineEdgeStyle({ stroke: new Stroke({ fill: transparent, thickness: 1 }), targetArrow: new Arrow({ type: 'triangle', fill: transparent, stroke: transparent }) }))
    }
  }
  ;(selectedNode.value as any).collapsed = true
  statusMessage.value = 'Group collapsed'
  showContextMenu.value = false
}

function onExpandGroup() {
  if (!graphComponent || !selectedNode.value) return
  const ids: string[] = ((selectedNode.value as any).children as string[]) || []
  const graph = graphComponent.graph
  for (const n of graph.nodes) {
    const tag = (n.tag as NodeData | undefined)
    const id = tag?.id
    if (id && ids.includes(id)) {
      graph.setStyle(n, createNodeStyle(tag!))
    }
  }
  for (const e of graph.edges) {
    const tag = (e.tag as EdgeData | undefined) || {}
    const srcId = (e.sourceNode.tag as NodeData | undefined)?.id
    const tgtId = (e.targetNode.tag as NodeData | undefined)?.id
    if ((srcId && ids.includes(srcId)) || (tgtId && ids.includes(tgtId))) {
      graph.setStyle(e, createEdgeStyle(tag))
    }
  }
  ;(selectedNode.value as any).collapsed = false
  statusMessage.value = 'Group expanded'
  showContextMenu.value = false
}

// Emphasize selected edge with thicker stroke and same color
function highlightSelectedEdgeOnTop() {
  if (!graphComponent || !selectedEdge.value) return
  const graph = graphComponent.graph
  const sel = getSelectedIEdge()
  if (!sel) return

  // Strongly dim all other edges
  for (const e of graph.edges) {
    if (e !== sel) {
      const etag = (e.tag as EdgeData | undefined) || {}
      const dimStyle = dimEdgeStyle(etag)
      // extra dim for contrast
      const dimStroke = new Stroke({ fill: (dimStyle as any).stroke?.fill ?? 'rgba(0,0,0,0.08)', thickness: 1 })
      graph.setStyle(
        e,
        new PolylineEdgeStyle({ stroke: dimStroke, targetArrow: new Arrow({ type: 'triangle', fill: 'rgba(0,0,0,0.08)', stroke: 'rgba(0,0,0,0.08)' }) })
      )
    }
  }

  // Emphasize selected edge with thicker stroke and increased label size
  const etag = (sel.tag as EdgeData | undefined) || {}
  const rel = (etag.relationship ?? etag.label ?? '').trim()
  const color = (etag.color as string) || getColorForRelationship(rel)
  const zoom = ((graphComponent as any)?.zoom as number) || 1
  const screenPx = 12 // desired on-screen thickness for selected edge
  const worldThickness = Math.max(2.5, screenPx / zoom)
  const thick = new PolylineEdgeStyle({
    stroke: new Stroke({ fill: color, thickness: worldThickness, lineCap: 'round', lineJoin: 'round' }),
    targetArrow: new Arrow({ type: 'triangle', fill: color, stroke: color })
  })
  graph.setStyle(sel, thick)
  if (sel.labels && sel.labels.size > 0) {
    const label = sel.labels.get(0)
    try {
      const bigger = Math.max(14, Math.round(baseEdgeFont * 1.4))
      graph.setStyle(
        label,
        new LabelStyle({
          font: new Font({ fontFamily: "Inter, 'Helvetica Neue', Arial, sans-serif", fontSize: bigger, fontWeight: '700' }),
          textFill: '#0f172a',
          padding: 4
        })
      )
    } catch {}
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
            {{ formatManifestLabel(entry) }}
          </option>
        </select>
      </section>
      <section v-if="nodeLabelEntries.length" class="sidebar-section">
        <h2 class="sidebar-subtitle">Node Labels</h2>
        <div class="sidebar-row">
          <input v-model="searchNodeQuery" type="text" class="sidebar-input" placeholder="Search node type" @keydown.enter.prevent="onSearchNodes" />
          <button class="sidebar-btn" type="button" @click="onSearchNodes">Search</button>
        </div>
        <div class="tag-group">
          <span
            v-for="entry in nodeLabelDisplay"
            :key="entry.label"
            class="tag node-tag clickable"
            :class="{ active: activeNodeLabelFilter === entry.label }"
            :style="{ backgroundColor: entry.color }"
            @click="onNodeLabelChip(entry.label)"
          >
            {{ entry.label }}
            <small>({{ entry.count }})</small>
          </span>
        </div>
        <div class="sidebar-row small">
          <label class="mode-label">
            <input type="radio" value="highlight" v-model="filterMode" /> Highlight
          </label>
          <label class="mode-label">
            <input type="radio" value="filter" v-model="filterMode" /> Filter
          </label>
          <button class="sidebar-link" type="button" @click="clearFilters">Clear</button>
        </div>
      </section>
      <section v-if="relationshipEntries.length" class="sidebar-section">
        <h2 class="sidebar-subtitle">Relationship Types</h2>
        <div class="sidebar-row">
          <input v-model="searchEdgeQuery" type="text" class="sidebar-input" placeholder="Search relationship" @keydown.enter.prevent="onSearchEdges" />
          <button class="sidebar-btn" type="button" @click="onSearchEdges">Search</button>
        </div>
        <div class="tag-group">
          <span
            v-for="entry in relationshipDisplay"
            :key="entry.label"
            class="tag relationship-tag clickable"
            :style="entry.style"
            :class="{ active: activeRelTypeFilter === entry.label }"
            @click="onRelChip(entry.label)"
          >
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
          <span class="stat-chip accuracy">Schema Comp {{ schemaCompText }}</span>
          <span class="stat-chip f1">Relationship Comp {{ relationshipCompText }}</span>
          <span class="stat-chip primary">{{ graphStats.nodeCount }} nodes</span>
          <span class="stat-chip secondary">{{ graphStats.edgeCount }} relationships</span>
        </div>
      </header>

      <div class="neo-body">
      <div class="graph-area">
        <div class="graph-toolbar">
          <span class="graph-toolbar-title">Graph View</span>
          <div class="toolbar-spacer"></div>
          <span class="tb-label">Edge</span>
          <button class="tb-btn" title="Shorter edges" @click="onEdgeLenShorter">-</button>
          <button class="tb-btn" title="Longer edges" @click="onEdgeLenLonger">+</button>
          <span class="tb-sep"></span>
          <span class="tb-label">Cluster</span>
          <button class="tb-btn" title="Closer clusters" @click="onClusterCloser">-</button>
          <button class="tb-btn" title="Wider clusters" @click="onClusterWider">+</button>
          <span class="tb-sep"></span>
          <span class="tb-label">Node</span>
          <button class="tb-btn" title="Smaller nodes" @click="onNodeSmaller">-</button>
          <button class="tb-btn" title="Larger nodes" @click="onNodeLarger">+</button>
        </div>
          <div ref="containerRef" class="graph-canvas"></div>
          <!-- Simple context menu -->
          <div
            v-if="showContextMenu"
            class="context-menu"
            :style="{ left: contextMenuLeft + 'px', top: contextMenuTop + 'px' }"
            @click.stop
          >
            
            <button class="ctx-item" type="button" @click="onAddNodeHere">Add node here</button>
            <button class="ctx-item" type="button" @click="onStartAddEdge">Add edge</button>
            <button class="ctx-item" type="button" @click="onGroupSelected">Group selected</button>
            <button v-if="selectedNode && (selectedNode as any).isGroup" class="ctx-item" type="button" @click="onExpandGroup">Expand group</button>
            <button v-if="selectedNode && (selectedNode as any).isGroup" class="ctx-item" type="button" @click="onCollapseGroup">Collapse group</button>
            <hr class="ctx-sep" />
            <button class="ctx-item" type="button" @click="clearFilters">Clear filters/highlights</button>
            <template v-if="selectedEdge">
              <hr class="ctx-sep" />
              <button class="ctx-item" type="button" @click="onEditSelectedEdgeLabel">Edit edge label</button>
              <button class="ctx-item danger" type="button" @click="onDeleteSelectedEdge">Delete edge</button>
            </template>
          </div>
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
              <div v-if="nodePropertyEntries.length" class="detail-section">
                <span class="detail-key">Properties</span>
                <ul class="detail-list">
                  <li v-for="prop in nodePropertyEntries" :key="prop">{{ prop }}</li>
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
              <span class="detail-dot edge" :style="selectedEdgeAccent"></span>
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
  width: 220px;
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

.sidebar-row {
  display: flex;
  gap: 0.4rem;
  align-items: center;
}
.sidebar-row.small {
  gap: 0.75rem;
}
.sidebar-input {
  flex: 1;
  min-width: 0;
  background: #111827;
  color: #f8fafc;
  border: 1px solid rgba(148, 163, 184, 0.3);
  border-radius: 6px;
  padding: 0.45rem 0.6rem;
}
.sidebar-btn {
  border: 1px solid rgba(148,163,184,0.4);
  background: #334155;
  color: #f8fafc;
  padding: 0.45rem 0.6rem;
  border-radius: 6px;
  cursor: pointer;
}
.sidebar-btn:hover {
  background: #475569;
}
.sidebar-link {
  border: none;
  background: transparent;
  color: #e5e7eb;
  cursor: pointer;
  padding: 0.2rem 0.3rem;
}
.sidebar-link:hover { text-decoration: underline; }
.mode-label { color: #cbd5e1; font-size: 0.8rem; }

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
.tag.clickable { cursor: pointer; user-select: none; }
.tag.active { outline: 2px solid rgba(255,255,255,0.7); box-shadow: 0 0 0 2px rgba(148,163,184,0.4) inset; }

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
  color: inherit;
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

/* header-center removed; metrics live in header-right before counts */

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
.stat-chip.accuracy {
  background: #10b981; /* emerald */
  color: #f8fafc;
}
.stat-chip.f1 {
  background: #f59e0b; /* amber */
  color: #1f2937;
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
.toolbar-spacer { flex: 1; }
.tb-btn {
  margin-left: 8px;
  padding: 0.25rem 0.6rem;
  border-radius: 8px;
  border: 1px solid rgba(148,163,184,0.45);
  background: #ffffffaa;
  color: #1e293b;
  cursor: pointer;
}
.tb-btn.active { background: #3b82f6; color: #f8fafc; border-color: #2563eb; }
.tb-sep { display:inline-block; width: 8px; }
.tb-label { margin: 0 4px; color: #334155; font-size: 0.85rem; }

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
.cursor-grab { cursor: grab; }
.cursor-grabbing { cursor: grabbing; }
.context-menu {
  position: fixed;
  z-index: 1000;
  min-width: 160px;
  background: #ffffff;
  border: 1px solid rgba(15, 23, 42, 0.15);
  border-radius: 8px;
  box-shadow: 0 12px 24px rgba(15, 23, 42, 0.18);
  padding: 6px;
}
.ctx-item {
  display: block;
  width: 100%;
  text-align: left;
  padding: 8px 10px;
  border: none;
  background: transparent;
  font-size: 0.9rem;
  color: #0f172a;
  cursor: pointer;
}
.ctx-item:hover {
  background: #f1f5f9;
}
.ctx-item.danger {
  color: #dc2626;
}
.ctx-sep {
  border: none;
  border-top: 1px solid #e2e8f0;
  margin: 6px 4px;
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




















