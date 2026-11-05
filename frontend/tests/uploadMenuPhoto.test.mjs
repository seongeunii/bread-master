import assert from 'node:assert/strict'
import test from 'node:test'
import { uploadMenuPhoto } from '../src/features/account/uploadMenuPhoto.ts'

test('photo attachment rejects unsupported files and large files without sending them', async t => {
  const fetch = t.mock.method(globalThis, 'fetch', () => { throw new Error('unexpected request') })
  await assert.rejects(uploadMenuPhoto(new File(['csv'], 'menu.csv', { type: 'text/csv' })), /JPG/)
  await assert.rejects(uploadMenuPhoto(new File([new Uint8Array(5 * 1024 * 1024 + 1)], 'large.jpg', { type: 'image/jpeg' })), /5MB/)
  assert.equal(fetch.mock.callCount(), 0)
})

test('a failed photo upload exposes the error and a retry returns the private photo path', async t => {
  const file = new File(['test-photo'], 'bread.jpg', { type: 'image/jpeg' })
  const fetch = t.mock.method(globalThis, 'fetch', async () => new Response(JSON.stringify({ detail: '사진 저장 실패' }), { status: 503 }))
  await assert.rejects(uploadMenuPhoto(file), /사진 저장 실패/)
  fetch.mock.mockImplementation(async () => new Response(JSON.stringify({ url: '/api/v1/store-admin/photos/test' }), { status: 201 }))
  assert.equal(await uploadMenuPhoto(file), '/api/v1/store-admin/photos/test')
  const [url, options] = fetch.mock.calls[1].arguments
  assert.equal(url, '/api/v1/store-admin/photos')
  assert.equal(options.headers['X-Bread-Client'], 'web')
  assert.equal(options.body, file)
})
