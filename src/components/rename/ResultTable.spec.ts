import { describe, expect, it } from 'vitest'
import type { DisplayItem } from '../../stores/rename'
import { createResultRows } from './resultRows'

describe('文件结果行', () => {
  it('生成连续序号，根目录使用明确文字，子目录收拢为带完整路径提示的图标', () => {
    const items: DisplayItem[] = [
      {
        source: 'C:\\测试\\根文件.txt', target: 'C:\\测试\\根文件.txt',
        kind: '文件', status: '已匹配', detail: '匹配',
      },
      {
        source: 'C:\\测试\\一层\\二层\\子文件.txt',
        target: 'C:\\测试\\一层\\二层\\子文件.txt',
        kind: '文件', status: '已匹配', detail: '匹配',
      },
    ]

    const rows = createResultRows(items, 'C:\\测试')

    expect(rows[0].index).toBe(1)
    expect(rows[1].index).toBe(2)
    expect(rows[0].directory).toEqual({ isRoot: true, path: '根目录', accessibleLabel: '根目录' })
    expect(rows[1].directory).toEqual({
      isRoot: false,
      path: '一层\\二层',
      accessibleLabel: '所在目录：一层\\二层',
    })
  })
})
