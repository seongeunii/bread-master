import { useState } from 'react'
import type { Category } from '../../lib/api'

export type CategoryDraft = { id?: number; name: string }

export function CategoryManager({ categories, occupied, busy, onSave }: {
  categories: Category[]
  occupied: Set<number>
  busy: boolean
  onSave: (items: CategoryDraft[]) => void
}) {
  const [items, setItems] = useState<CategoryDraft[]>(categories)
  function move(index: number, offset: number) {
    const next = [...items]
    const destination = index + offset
    const moved = next[index]
    next[index] = next[destination]
    next[destination] = moved
    setItems(next)
  }
  return <details className="category-manager">
    <summary>카테고리 관리</summary>
    <p>이름과 표시 순서를 수정할 수 있어요. 상품이 있는 분류는 상품을 옮긴 뒤 삭제하세요.</p>
    <fieldset disabled={busy}>
      {items.map((item, index) => <div className="category-edit-row" key={item.id ?? `new-${index}`}>
        <label>카테고리 {index + 1}<input required maxLength={40} value={item.name} onChange={event => setItems(items.map((entry, i) => i === index ? { ...entry, name: event.target.value } : entry))}/></label>
        <button type="button" disabled={index === 0} onClick={() => move(index, -1)} aria-label={`${index + 1}번 카테고리 위로`}>↑</button>
        <button type="button" disabled={index === items.length - 1} onClick={() => move(index, 1)} aria-label={`${index + 1}번 카테고리 아래로`}>↓</button>
        <button type="button" disabled={items.length === 1 || (item.id !== undefined && occupied.has(item.id))} onClick={() => setItems(items.filter((_, i) => i !== index))}>삭제</button>
      </div>)}
      <div className="account-actions">
        <button type="button" className="account-secondary" disabled={items.length >= 50} onClick={() => setItems([...items, { name: '' }])}>카테고리 추가</button>
        <button type="button" className="primary" disabled={items.some(item => !item.name.trim())} onClick={() => onSave(items)}>카테고리 저장</button>
      </div>
    </fieldset>
  </details>
}
