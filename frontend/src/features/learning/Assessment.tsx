import { useEffect, useState } from 'react'
import { api } from '../../lib/api'
import type { Question } from '../../lib/api'
import { QuestionChoices } from './QuestionChoices'
import './Learning.css'
import './Assessment.css'

type Exam = { id: string; questions: (Question & { selected_id: number | null })[] }
type Summary = {
  id: string
  score: number
  max_score: number
  submitted_at: string
  areas: Record<string, { correct: number; total: number }>
}
type ResultPage = { results: Summary[]; has_more: boolean }
type Mine = ResultPage & { active: Exam | null }

const areas: Record<string, string> = {
  category: '카테고리 분류',
  'photo-to-name': '사진 보고 상품명 선택',
  'name-to-photo': '이름 보고 사진 선택',
  delivery: '배달 상품 찾기',
  pos: 'POS 메뉴 찾기',
}

function errorMessage(error: unknown) {
  return error instanceof Error ? error.message : '다시 시도해 주세요.'
}

function ResultList({ results }: { results: Summary[] }) {
  return results.length ? <ul className="assessment-results">{results.map(result => <li key={result.id}>
    <div><strong>{result.score} / {result.max_score}점</strong>
      <small>{new Date(result.submitted_at.replace(' ', 'T') + 'Z').toLocaleString('ko-KR')}</small></div>
    <ul>{Object.entries(result.areas).map(([key, area]) =>
      <li key={key}>{areas[key] ?? key} · {area.correct} / {area.total} 정답</li>)}</ul>
  </li>)}</ul> : <p>아직 제출한 평가가 없어요.</p>
}

function ResultHistory({ path, initial }: { path: string; initial?: ResultPage }) {
  const [page, setPage] = useState(initial)
  const [offset, setOffset] = useState(0)
  const [error, setError] = useState('')
  const [reload, setReload] = useState(0)

  useEffect(() => {
    if (initial && offset === 0 && reload === 0) return
    const controller = new AbortController()
    const query = path.includes('?') ? '&' : '?'
    api<ResultPage>(`${path}${query}offset=${offset}`, undefined, controller.signal)
      .then(setPage).catch(err => { if (!controller.signal.aborted) setError(errorMessage(err)) })
    return () => controller.abort()
  }, [path, offset, initial, reload])

  function go(next: number) {
    setPage(undefined)
    setError('')
    setOffset(next)
  }

  return <>
    {error ? <><p role="alert">{error}</p><button className="secondary" onClick={() => {
      setError(''); setReload(value => value + 1)
    }}>다시 불러오기</button></> : page ? <ResultList results={page.results}/> : <p role="status">결과를 불러오는 중이에요…</p>}
    <div className="assessment-actions">
      {offset > 0 && <button className="secondary" onClick={() => go(offset - 20)}>이전 결과</button>}
      {page?.has_more && <button className="secondary" onClick={() => go(offset + 20)}>다음 결과</button>}
    </div>
  </>
}

export function WorkerAssessmentResults({ workerId }: { workerId: string }) {
  return <ResultHistory key={workerId} path={`/assessments/store-results?worker_id=${encodeURIComponent(workerId)}`}/>
}

export function Assessment() {
  const [initial, setInitial] = useState<Mine>()
  const [exam, setExam] = useState<Exam | null>(null)
  const [position, setPosition] = useState(0)
  const [result, setResult] = useState<Summary>()
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [reload, setReload] = useState(0)

  useEffect(() => {
    const controller = new AbortController()
    api<Mine>('/assessments/mine', undefined, controller.signal).then(data => {
      setInitial(data)
      setExam(data.active)
      const unanswered = data.active?.questions.findIndex(q => q.selected_id === null) ?? -1
      setPosition(unanswered < 0 ? 0 : unanswered)
    }).catch(err => { if (!controller.signal.aborted) setError(errorMessage(err)) })
    return () => controller.abort()
  }, [reload])

  async function perform(action: () => Promise<void>) {
    if (busy) return
    setBusy(true)
    setError('')
    try { await action() }
    catch (err) { setError(errorMessage(err)) }
    finally { setBusy(false) }
  }

  const question = exam?.questions[position]
  const answered = exam?.questions.filter(q => q.selected_id !== null).length ?? 0

  return <section className="assessment" aria-label="업무 평가">
    {error && <p className="error" role="alert">{error}</p>}
    {!initial ? error ? <button className="secondary" onClick={() => {
      setError(''); setReload(value => value + 1)
    }}>다시 불러오기</button> : <p role="status">평가 기록을 불러오는 중이에요…</p> : exam && question ? <>
      <div className="scoreboard">
        <strong>{position + 1} / {exam.questions.length}번 문제</strong>
        <span>답안 저장 {answered} / {exam.questions.length}</span>
      </div>
      <QuestionChoices question={question} selected={question.selected_id} disabled={busy}
        onSelect={selected_id => void perform(async () => {
          const saved = await api<{ selected_id: number }>(`/assessments/${exam.id}/questions/${question.id}/answer`, { selected_id })
          setExam(current => current && { ...current, questions: current.questions.map(q =>
            q.id === question.id ? { ...q, selected_id: saved.selected_id } : q) })
        })}/>
      <div className="assessment-actions">
        <button className="secondary" disabled={busy || position === 0} onClick={() => setPosition(position - 1)}>이전 문제</button>
        <button className="secondary" disabled={busy || position === exam.questions.length - 1} onClick={() => setPosition(position + 1)}>다음 문제</button>
        <button className="primary" disabled={busy || answered !== exam.questions.length}
          onClick={() => void perform(async () => {
            const saved = await api<Summary>(`/assessments/${exam.id}/submit`, {})
            setResult(saved)
            setExam(null)
            const results = [saved, ...initial.results.filter(item => item.id !== saved.id)]
            setInitial({ active: null, results: results.slice(0, 20), has_more: initial.has_more || results.length > 20 })
          })}>평가 제출</button>
      </div>
      <p>제출하기 전에는 답안을 다시 선택할 수 있어요.</p>
    </> : <>
      {result && <div role="status"><h3>평가를 제출했어요</h3><ResultList results={[result]}/></div>}
      <section className="practice-panel">
        <div><h2>업무 준비도 평가</h2>
          <p>총 10문항이에요. 카테고리 분류, 사진 보고 상품명 선택, 이름 보고 사진 선택, 배달 상품 찾기, POS 메뉴 찾기를 각 2문항씩 풀어요.</p>
          <p>제출하면 총점과 영역별 결과를 본인과 소속 매장 관리자가 확인할 수 있어요.</p>
        </div>
        <button className="primary" disabled={busy} onClick={() => void perform(async () => {
          setExam(await api<Exam>('/assessments/start', {}))
          setResult(undefined)
          setPosition(0)
        })}>{busy ? '평가 준비 중…' : result ? '다시 응시하기' : '평가 시작'}</button>
      </section>
      <h3>지난 평가 결과</h3>
      <ResultHistory key={result?.id ?? 'initial'} path="/assessments/mine" initial={initial}/>
    </>}
  </section>
}
