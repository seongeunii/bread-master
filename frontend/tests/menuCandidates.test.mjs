import assert from 'node:assert/strict'
import { test } from 'node:test'
import { candidateFromText } from '../src/features/account/menuCandidates.ts'

test('Korean name and comma price become editable candidates with original slot', () => {
  const item = candidateFromText('소보루\n1,900원\n', 1001, 8, 72.4)
  assert.equal(item.name, '소보루')
  assert.equal(item.price, '1900')
  assert.equal(item.category_id, 1001)
  assert.equal(item.slot, '8')
  assert.match(item.note, /72%/)
})
test('missing price remains blank and blank cells do not become menus', () => {
  assert.equal(candidateFromText(' \n ', 1, 1, 0), null)
  assert.equal(candidateFromText('우유 크림빵', 1, 4, 35).price, '')
  assert.equal(candidateFromText('5입)버터롤\n3900', 1, 2, 90).name, '5입)버터롤')
})
