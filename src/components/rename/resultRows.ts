import type { DisplayItem } from '../../stores/rename'

export interface ResultDirectory {
  isRoot: boolean
  path: string
  accessibleLabel: string
}

export interface ResultRow extends DisplayItem {
  index: number
  directory: ResultDirectory
  oldName: string
  newName: string
}

const segments = (path: string) => path.split(/[/\\]/).filter(Boolean)

function relativeSource(source: string, root: string) {
  const normalizedSource = source.replace(/\\/g, '/')
  const normalizedRoot = root.replace(/\\/g, '/').replace(/\/$/, '')
  const prefix = `${normalizedRoot}/`
  return normalizedSource.toLocaleLowerCase().startsWith(prefix.toLocaleLowerCase())
    ? normalizedSource.slice(prefix.length)
    : normalizedSource
}

function fileName(path: string) {
  return segments(path).at(-1) ?? path
}

export function createResultRows(items: DisplayItem[], root: string): ResultRow[] {
  return items.map((item, index) => {
    const relativeParts = segments(relativeSource(item.source, root))
    const parent = relativeParts.slice(0, -1).join('\\')
    const isRoot = parent.length === 0
    const path = isRoot ? '根目录' : parent
    return {
      ...item,
      index: index + 1,
      directory: {
        isRoot,
        path,
        accessibleLabel: isRoot ? '根目录' : `所在目录：${path}`,
      },
      oldName: fileName(item.source),
      newName: fileName(item.target),
    }
  })
}
