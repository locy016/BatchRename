import { expect, test } from '@playwright/test'

test('操作日志是唯一的历史和撤回入口', async ({ page }) => {
  await page.goto('/#/history')

  await expect(page.getByRole('heading', { name: '操作日志' })).toBeVisible()
  await expect(page.getByText('在同一页面完成安全检查与整批撤回')).toBeVisible()
  await expect(page.getByRole('link', { name: '撤回管理' })).toHaveCount(0)
})

test('帮助菜单分别进入使用说明和关于页面', async ({ page }) => {
  await page.goto('/#/rename')
  await page.getByTestId('help-menu').click()
  await page.getByRole('menuitem', { name: '使用说明' }).click()
  await expect(page).toHaveURL(/#\/help\/guide$/)
  await expect(page.getByRole('heading', { name: '使用说明' })).toBeVisible()

  await page.getByTestId('help-menu').click()
  await page.getByRole('menuitem', { name: '关于' }).click()
  await expect(page).toHaveURL(/#\/help\/about$/)
  await expect(page.getByRole('heading', { name: '关于' })).toBeVisible()
})
