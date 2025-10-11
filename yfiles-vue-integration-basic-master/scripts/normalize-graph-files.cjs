#!/usr/bin/env node
const fs = require('fs/promises')
const path = require('path')

async function normalize() {
  const projectRoot = path.resolve(__dirname, '..')
  const graphsDir = path.join(projectRoot, 'yfiles_graphs')

  let entries
  try {
    entries = await fs.readdir(graphsDir, { withFileTypes: true })
  } catch (error) {
    console.error(`Unable to read directory ${graphsDir}:`, error.message)
    process.exit(1)
  }

  let renamed = 0
  for (const entry of entries) {
    if (!entry.isFile()) {
      continue
    }

    const originalName = entry.name
    const originalPath = path.join(graphsDir, originalName)

    const ext = path.extname(originalName)
    const nameWithoutExt = ext ? originalName.slice(0, -ext.length) : originalName

    if (nameWithoutExt.toLowerCase() === 'manifest') {
      continue
    }

    const normalizedBase = nameWithoutExt.endsWith('_yfiles')
      ? nameWithoutExt
      : `${nameWithoutExt}_yfiles`

    const targetName = `${normalizedBase}.json`

    if (targetName === originalName) {
      continue
    }

    const targetPath = path.join(graphsDir, targetName)

    try {
      await fs.access(targetPath)
      console.warn(`Skip renaming ${originalName}: target ${targetName} already exists`)
      continue
    } catch (_) {}

    await fs.rename(originalPath, targetPath)
    renamed++
    console.log(`Renamed ${originalName} -> ${targetName}`)
  }

  if (renamed === 0) {
    console.log('No files required renaming. All graph files already follow the *_yfiles.json convention.')
  } else {
    console.log(`Renamed ${renamed} file(s). If you maintain a manifest, regenerate it to pick up new file names.`)
  }
}

normalize().catch(error => {
  console.error('Failed to normalize graph files:', error)
  process.exit(1)
})