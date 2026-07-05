import { test, expect } from '@playwright/test'

test('start a timer and complete it', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('button', { name: /start/i }).click()
  await expect(page.getByText(/remaining/i)).toBeVisible()
  await page.getByRole('button', { name: /complete/i }).click()
  await expect(page.getByText(/completed/i)).toBeVisible()
})