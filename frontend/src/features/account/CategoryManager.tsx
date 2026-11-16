import { useRef, useState } from 'react'
import type { Category } from '../../lib/api'
import './CategoryManager.css'

export type CategoryDraft = { id?: number; name: string }
type EditableCategory = CategoryDraft & { key: string }

export function CategoryManager({ categories, productCounts, busy, onSave }: {
  categories: Category[]
  productCounts: Map<number, number>
  busy: boolean
  onSave: (items: CategoryDraft[]) => void
}) {
  const initial = () => categories.map(item => ({ ...item, key: String(item.id) }))
  const [items, setItems] = useState<EditableCategory[]>(initial)
  const [selected, setSelected] = useState(String(categories[0]?.id ?? ''))
  const dragged = useRef<string | null>(null)
  const [dropTarget, setDropTarget] = useState<string | null>(null)
  const index = items.findIndex(item => item.key === selected)
  const item = items[index]
  const count = item?.id === undefined ? 0 : productCounts.get(item.id) ?? 0
  const changed = JSON.stringify(items.map(({ id, name }) => ({ id, name: name.trim() }))) !== JSON.stringify(categories.map(({ id, name }) => ({ id, name })))
  const names = items.map(entry => entry.name.trim())
  const invalid = names.some(name => !name) || new Set(names).size !== names.length

  function move(from: number, to: number) {
    if (busy || from < 0 || to < 0 || from >= items.length || to >= items.length || from === to) return
    const next = [...items]
    const [moved] = next.splice(from, 1)
    next.splice(to, 0, moved)
    setItems(next)
  }

  function cancel() {
    setItems(initial())
    setSelected(String(categories[0]?.id ?? ''))
    setDropTarget(null)
    dragged.current = null
  }

  return <details className="category-manager category-grid-manager">
    <summary>카테고리 관리 <small>{items.length}개</small></summary>
    <form onSubmit={event => {
      event.preventDefault()
      if (!busy && changed && !invalid) onSave(items.map(({ id, name }) => ({ id, name: name.trim() })))
    }}>
      <fieldset disabled={busy}>
        <div className="category-toolbar">
          <p>카테고리를 선택해 수정하세요. 드래그하거나 이동 버튼으로 순서를 바꿀 수 있어요.</p>
          <button type="button" className="account-secondary" disabled={items.length >= 50} onClick={() => {
            const key = crypto.randomUUID()
            setItems([...items, { key, name: '' }])
            setSelected(key)
          }}>＋ 카테고리 추가</button>
        </div>
        <div className="category-grid" aria-label="카테고리 선택 및 순서">
          {items.map((entry, position) => {
            const original = categories.find(category => category.id === entry.id)
            const modified = !original || original.name !== entry.name.trim() || categories[position]?.id !== entry.id
            return <button key={entry.key} type="button" className={dropTarget === entry.key ? 'category-drop-target' : ''}
              aria-pressed={selected === entry.key} draggable={!busy}
              onClick={() => setSelected(entry.key)}
              onDragStart={event => {
                dragged.current = entry.key
                event.dataTransfer.effectAllowed = 'move'
                event.dataTransfer.setData('text/plain', entry.key)
              }}
              onDragOver={event => {
                if (!busy && dragged.current && dragged.current !== entry.key) {
                  event.preventDefault()
                  event.dataTransfer.dropEffect = 'move'
                  setDropTarget(entry.key)
                }
              }}
              onDragEnd={() => { dragged.current = null; setDropTarget(null) }}
              onDrop={event => {
                event.preventDefault()
                move(items.findIndex(candidate => candidate.key === dragged.current), position)
                dragged.current = null
                setDropTarget(null)
              }}>
              <span className="category-tile-top"><small>{String(position + 1).padStart(2, '0')}</small>{modified && <small className="category-change">변경됨</small>}</span>
              <strong>{entry.name || '새 카테고리'}</strong>
              <span className="category-tile-count">상품 {entry.id === undefined ? 0 : productCounts.get(entry.id) ?? 0}개</span>
            </button>
          })}
        </div>
        {item && <div className="category-editor" aria-label="선택한 카테고리 편집">
          <div className="category-editor-title"><strong>선택한 카테고리</strong><span>{index + 1} / {items.length}</span></div>
          <label htmlFor="category-edit-name">카테고리 이름</label>
          <input id="category-edit-name" required maxLength={40} value={item.name} placeholder="카테고리 이름을 입력하세요" onChange={event => {
            setItems(items.map(entry => entry.key === selected ? { ...entry, name: event.target.value } : entry))
          }}/>
          {invalid && <p className="account-error" role="status">모든 카테고리에 서로 다른 이름을 입력하세요.</p>}
          <div className="category-editor-actions">
            <div><button type="button" className="account-secondary" disabled={index === 0} onClick={() => move(index, index - 1)}>← 앞으로</button>
              <button type="button" className="account-secondary" disabled={index === items.length - 1} onClick={() => move(index, index + 1)}>뒤로 →</button></div>
            <button type="button" className="account-secondary" disabled={items.length === 1 || count > 0} aria-describedby="category-delete-help" onClick={() => {
              const next = items.filter(entry => entry.key !== selected)
              setItems(next)
              setSelected(next[Math.min(index, next.length - 1)].key)
            }}>카테고리 삭제</button>
          </div>
          <p id="category-delete-help" className="category-hint">{count > 0 ? `상품 ${count}개가 있어요. 상품을 다른 카테고리로 옮기면 삭제할 수 있어요.` : items.length === 1 ? '카테고리는 최소 1개가 필요해요.' : '상품이 없는 카테고리는 삭제할 수 있어요.'}</p>
        </div>}
        <div className="category-save-bar">
          <p role="status">{changed ? '변경사항을 저장하면 POS와 학습 화면에 반영돼요.' : '저장된 순서대로 표시하고 있어요.'}</p>
          <div><button type="button" className="account-secondary" disabled={!changed} onClick={cancel}>취소</button>
            <button type="submit" className="primary" disabled={!changed || invalid}>{busy ? '저장 중…' : '변경사항 저장'}</button></div>
        </div>
      </fieldset>
    </form>
  </details>
}
