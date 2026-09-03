import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'

const readStyle = (name: string) => readFileSync(new URL(name, import.meta.url), 'utf8')

describe('产品主题系统', () => {
  it('应用壳不使用固定浅色背景', () => {
    const source = readStyle('./index.scss')
    expect(source).not.toMatch(/background:\s*#fff/i)
    expect(source).not.toContain('#dfe4ec')
    expect(source).not.toContain('#4f5bd5')
  })

  it('为页面与 Element Plus 浮层提供完整语义颜色映射', () => {
    const tokens = readStyle('./tokens.scss')
    const element = readStyle('./element.scss')
    const requiredTokens = [
      '--surface-raised', '--surface-hover', '--overlay', '--focus-ring',
      '--el-bg-color', '--el-bg-color-overlay', '--el-text-color-primary',
      '--el-border-color', '--el-fill-color-blank', '--el-mask-color',
    ]
    for (const token of requiredTokens) {
      expect(`${tokens}\n${element}`).toContain(token)
    }
    expect(element).toContain('.el-drawer__body')
    expect(element).toContain('.el-popper')
    expect(element).toContain('.el-table')
  })
})
