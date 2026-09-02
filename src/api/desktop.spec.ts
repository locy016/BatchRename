import { describe, expect, it } from 'vitest'
import type { DesktopApi } from './desktop'
describe('DesktopApi', () => { it('支持确定性的测试替身', async () => { const fake = { chooseDirectory: async () => 'D:/资料' } as DesktopApi; expect(await fake.chooseDirectory()).toBe('D:/资料') }) })
