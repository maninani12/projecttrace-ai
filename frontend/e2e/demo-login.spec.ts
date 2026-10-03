import { test, expect } from '@playwright/test'

test('seeded demo account signs in, persists across reload and signs out', async ({ page }) => {
  await page.goto('/')
  await page.getByLabel('Email', { exact: true }).fill('demo@projecttrace.ai')
  await page.getByLabel('Password', { exact: true }).fill('incorrect-demo-password')
  await page.getByRole('button', { name: 'Sign in', exact: true }).click()
  await expect(page.getByRole('alert')).toContainText('Email or password is incorrect.')

  // These are published local-demo credentials, not production secrets.
  await page.getByLabel('Password', { exact: true }).fill('ProjectTrace@123')
  const responsePromise = page.waitForResponse(response => response.url().endsWith('/api/v1/auth/login') && response.request().method() === 'POST')
  await page.getByRole('button', { name: 'Sign in', exact: true }).click()
  const response = await responsePromise
  expect(response.status()).toBe(200)
  expect((await response.json()).user.email).toBe('demo@projecttrace.ai')
  await expect(page.getByRole('button', { name: 'Sign out', exact: true })).toBeVisible()
  expect((await page.context().cookies()).find(cookie => cookie.name === 'pt_session')?.httpOnly).toBe(true)

  await page.reload()
  await expect(page.getByRole('button', { name: 'Sign out', exact: true })).toBeVisible()
  const me = await page.request.get('/api/v1/auth/me')
  expect(me.status()).toBe(200)
  expect((await me.json()).user.email).toBe('demo@projecttrace.ai')
  await page.getByRole('button', { name: 'Sign out', exact: true }).click()
  await expect(page.getByRole('button', { name: 'Sign in', exact: true })).toBeVisible()
  expect((await page.request.get('/api/v1/auth/me')).status()).toBe(401)
})
