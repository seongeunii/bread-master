import { useEffect, useRef, useState } from 'react'
import type { Worker } from 'tesseract.js'
import workerUrl from 'tesseract.js/dist/worker.min.js?url'
import type { Category } from '../../lib/api'
import { candidateFromText } from './menuCandidates'
import type { MenuCandidate } from './menuCandidates'

type Crop = { left: number; top: number; width: number; height: number }
const labels: Record<keyof Crop, string> = { left: '왼쪽 (%)', top: '위 (%)', width: '너비 (%)', height: '높이 (%)' }

export function PhotoRecognition({ categories, onCandidates }: {
  categories: Category[]
  onCandidates: (rows: MenuCandidate[]) => void
}) {
  const [image, setImage] = useState<ImageBitmap>()
  const [preview, setPreview] = useState('')
  const [crop, setCrop] = useState<Crop>({ left: 0, top: 0, width: 100, height: 100 })
  const [columns, setColumns] = useState(5)
  const [rows, setRows] = useState(5)
  const [category, setCategory] = useState(categories[0]?.id ?? 0)
  const [start, setStart] = useState(1)
  const [busy, setBusy] = useState(false)
  const [status, setStatus] = useState('')
  const [error, setError] = useState('')
  const worker = useRef<Worker | null>(null)
  const run = useRef(0)

  useEffect(() => () => {
    run.current += 1
    void worker.current?.terminate().catch(() => {})
  }, [])
  useEffect(() => () => { if (preview) URL.revokeObjectURL(preview) }, [preview])
  useEffect(() => () => image?.close(), [image])

  async function select(file?: File) {
    if (!file) return
    setError('')
    if (file.size > 5 * 1024 * 1024 || !['image/jpeg', 'image/png', 'image/webp'].includes(file.type)) {
      setError('5MB 이하 JPG·PNG·WebP 사진을 선택하세요.')
      return
    }
    try {
      const bitmap = await createImageBitmap(file)
      if (bitmap.width * bitmap.height > 16000000) {
        bitmap.close()
        throw new Error('사진은 1600만 화소 이하로 선택하세요.')
      }
      setImage(bitmap)
      setPreview(URL.createObjectURL(file))
    } catch (err) { setError(err instanceof Error ? err.message : '사진을 읽지 못했어요.') }
  }

  function cancel() {
    run.current += 1
    void worker.current?.terminate().catch(() => {})
    worker.current = null
    setBusy(false)
    setStatus('인식을 취소했어요.')
  }

  async function recognize() {
    if (!image || busy) return
    if (!category || !Number.isInteger(start) || start < 1 || start + rows * columns - 1 > 500
      || crop.width <= 0 || crop.height <= 0 || crop.left < 0 || crop.top < 0
      || crop.left + crop.width > 100 || crop.top + crop.height > 100) {
      setError('카테고리·시작 칸·인식 영역을 확인하세요.')
      return
    }
    const token = ++run.current
    setBusy(true)
    setError('')
    setStatus('한국어 인식 모델을 준비하고 있어요…')
    let engine: Worker | undefined
    try {
      const { createWorker, PSM } = await import('tesseract.js')
      engine = await createWorker('kor+eng', 1, { workerPath: workerUrl, corePath: 'https://cdn.jsdelivr.net/npm/tesseract.js-core@6.1.2' })
      if (token !== run.current) return
      worker.current = engine
      await engine.setParameters({ tessedit_pageseg_mode: PSM.SPARSE_TEXT })
      const candidates: MenuCandidate[] = []
      const canvas = document.createElement('canvas')
      const context = canvas.getContext('2d')
      if (!context) throw new Error('이 브라우저에서 사진을 처리할 수 없어요.')
      const width = image.width * crop.width / 100 / columns
      const height = image.height * crop.height / 100 / rows
      for (let index = 0; index < rows * columns; index += 1) {
        if (token !== run.current) return
        setStatus(`${index + 1}/${rows * columns}칸 인식 중…`)
        canvas.width = Math.max(1, Math.min(1000, Math.round(width * 2)))
        canvas.height = Math.max(1, Math.min(1000, Math.round(height * 2)))
        context.fillStyle = 'white'
        context.fillRect(0, 0, canvas.width, canvas.height)
        context.drawImage(image,
          image.width * crop.left / 100 + (index % columns) * width,
          image.height * crop.top / 100 + Math.floor(index / columns) * height,
          width, height, 0, 0, canvas.width, canvas.height)
        const result = await engine.recognize(canvas)
        const candidate = candidateFromText(result.data.text, category, start + index, result.data.confidence)
        if (candidate) candidates.push(candidate)
      }
      if (token !== run.current) return
      if (!candidates.length) throw new Error('글자를 찾지 못했어요. 메뉴 영역과 사진 선명도를 확인하세요.')
      onCandidates(candidates)
      setStatus(`${candidates.length}개 후보를 가져왔어요. 아래에서 확인·수정하세요.`)
    } catch (err) {
      if (token === run.current) setError(err instanceof Error ? err.message : '인식에 실패했어요. 네트워크와 사진을 확인하세요.')
    } finally {
      await engine?.terminate()
      if (token === run.current) { worker.current = null; setBusy(false) }
    }
  }

  return <section className="ocr-panel" aria-label="POS 사진 인식">
    <p>상품 칸 영역에 맞춰 인식 범위를 조정하세요. 칸은 왼쪽 위부터 행 순서대로 읽어요. 첫 실행에는 인식 모델 다운로드가 필요해요.</p>
    <fieldset disabled={busy}>
      <label>POS 화면 사진<input type="file" accept="image/jpeg,image/png,image/webp" onChange={event => { void select(event.target.files?.[0]); event.target.value = '' }}/></label>
      {preview && <div className="ocr-image"><img src={preview} alt="인식할 POS 원본"/><span style={{ left: crop.left + '%', top: crop.top + '%', width: crop.width + '%', height: crop.height + '%' }}>
        {Array.from({ length: rows * columns }, (_, index) => <i key={index} style={{ left: ((index % columns) * 100 / columns) + '%', top: (Math.floor(index / columns) * 100 / rows) + '%', width: (100 / columns) + '%', height: (100 / rows) + '%' }}>{start + index}</i>)}
      </span></div>}
      <div className="import-row">
        {(Object.keys(labels) as (keyof Crop)[]).map(key => <label key={key}>{labels[key]}<input type="number" min={0} max={100} value={crop[key]} onChange={event => setCrop({ ...crop, [key]: Number(event.target.value) })}/></label>)}
        <label>가로 칸 수<input type="number" min={1} max={5} value={columns} onChange={event => setColumns(Math.max(1, Math.min(5, Math.round(Number(event.target.value)))))}/></label>
        <label>세로 칸 수<input type="number" min={1} max={5} value={rows} onChange={event => setRows(Math.max(1, Math.min(5, Math.round(Number(event.target.value)))))}/></label>
        <label>저장할 카테고리<select value={category} onChange={event => setCategory(Number(event.target.value))}>{categories.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
        <label>시작 칸번호<input type="number" min={1} max={500} value={start} onChange={event => setStart(Number(event.target.value))}/></label>
      </div>
      <button className="primary" type="button" disabled={!image} onClick={() => void recognize()}>사진에서 메뉴 읽기</button>
    </fieldset>
    {busy && <button type="button" className="account-secondary" onClick={cancel}>인식 취소</button>}
    {status && <p role="status">{status}</p>}
    {error && <p role="alert" className="account-error">{error}</p>}
  </section>
}
