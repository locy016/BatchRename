import { describe, expect, it } from 'vitest'
import router from './index'

describe('应用路由', () => {
  it('操作日志作为唯一历史与撤回入口', () => {
    const paths = router.getRoutes().map((route) => route.path)

    expect(paths).toContain('/history')
    expect(paths).not.toContain('/undo')
  })
})
