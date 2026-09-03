import { expect, test } from '@playwright/test'

test('窄屏保持结果区域可见', async ({ page }) => {
  await page.setViewportSize({ width: 760, height: 680 })
  await page.goto('/#/rename')
  await expect(page.getByText('当前目录')).toBeVisible()
})

test('深色外观完整应用到设置抽屉', async ({ page }) => {
  await page.goto('/#/rename')
  await page.locator('.theme-select').click()
  await page.getByText('深色', { exact: true }).click()
  await page.getByRole('button', { name: /设置/ }).click()

  const drawer = page.locator('.settings-drawer.open')
  await expect(drawer).toBeVisible()
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark')
  await expect(drawer).toHaveCSS('width', '420px')
  await expect(drawer).toHaveCSS('background-color', 'rgb(23, 30, 43)')
  await expect(drawer.locator('.setting-card').first()).toHaveCSS(
    'background-color',
    'rgb(23, 30, 43)',
  )

  await expect
    .poll(async () => {
      const box = await drawer.boundingBox()
      const viewport = page.viewportSize()
      return box && viewport ? Math.ceil(box.x + box.width - viewport.width) : Number.MAX_SAFE_INTEGER
    })
    .toBeLessThanOrEqual(0)
})

test('路径提示层的文字与背景保持可读对比', async ({ page }) => {
  await page.goto('/#/rename')
  await page.evaluate(() => {
    const tooltip = document.createElement('div')
    tooltip.className = 'el-popper is-dark path-tooltip-test'
    tooltip.textContent = '项目资料\\设计稿'
    document.body.appendChild(tooltip)
  })

  const colors = await page.locator('.path-tooltip-test').evaluate((element) => {
    const style = getComputedStyle(element)
    return {
      background: style.backgroundColor,
      text: style.color,
    }
  })

  expect(colors.text).not.toBe(colors.background)
})

test('文件列表占满结果区剩余高度且统计栏固定在底部', async ({ page }) => {
  await page.setViewportSize({ width: 1360, height: 840 })
  await page.goto('/#/rename')
  await expect(page.locator('.result-table')).toBeVisible()

  const layout = await page.evaluate(() => {
    const bounds = (selector: string) => {
      const rect = document.querySelector(selector)!.getBoundingClientRect()
      return { top: rect.top, bottom: rect.bottom, height: rect.height }
    }
    return {
      results: bounds('.results'),
      card: bounds('.table-card'),
      table: bounds('.result-table'),
      stats: bounds('.stats'),
    }
  })

  expect(layout.card.height).toBeGreaterThan(600)
  expect(layout.table.height).toBeGreaterThan(540)
  expect(layout.results.bottom - layout.card.bottom).toBeCloseTo(18, 0)
  expect(layout.card.bottom - layout.stats.bottom).toBeLessThanOrEqual(2)
})
