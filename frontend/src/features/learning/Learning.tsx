import { useEffect, useRef, useState } from 'react'
import { api } from '../../lib/api'
import type { Category, Mode, Product, Question, Result } from '../../lib/api'
import { BreadArt } from '../../components/BreadArt'
import { ProductCard } from '../../components/ProductCard'
import { ROUND_SIZE, stages } from './stages'
import { DeliveryAdvanced } from '../delivery/DeliveryAdvanced'
import './Learning.css'

type Props = { products: Product[]; categories: Category[]; initialMode: Mode | null }
export function Learning({ products, categories, initialMode }: Props) {
  const [advancedDelivery, setAdvancedDelivery] = useState(false)
  const [mode, setMode] = useState<Mode | null>(initialMode)
  const [question, setQuestion] = useState<Question | null>(null)
  const [result, setResult] = useState<Result | null>(null)
  const [answers, setAnswers] = useState<Result[]>([])
  const [finished, setFinished] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [category, setCategory] = useState(0)
  const [page, setPage] = useState(0)
  const [selected, setSelected] = useState<number | null>(null)
  const startedAt = useRef(0)
  const requestVersion = useRef(0)
  const submitting = useRef(false)
  const stage = stages.find(s => s.mode === (mode === 'similar-photo' ? 'name' : mode))
  const score = answers.reduce((sum, answer) => sum + answer.points, 0)
  const correctCount = answers.filter(answer => answer.is_correct).length
  useEffect(() => () => { requestVersion.current++ }, [])

  function reset(nextMode: Mode | null) {
    setAdvancedDelivery(false)
    requestVersion.current++; submitting.current = false
    setMode(nextMode); setQuestion(null); setResult(null); setAnswers([])
    setFinished(false); setBusy(false); setError(''); setCategory(0); setPage(0); setSelected(null)
  }
  async function nextQuestion() {
    if (!mode || submitting.current || busy) return
    const version = ++requestVersion.current
    setBusy(true); setQuestion(null); setResult(null); setSelected(null); setError('')
    try {
      const next = await api<Question>('/questions', { mode, exclude_ids: answers.map(a => a.correct_product.id) })
      if (version !== requestVersion.current) return
      setQuestion(next); setCategory(0); setPage(0); startedAt.current = performance.now()
    } catch (e) {
      if (version === requestVersion.current) setError(e instanceof Error ? e.message : '출제에 실패했어요.')
    } finally { if (version === requestVersion.current) setBusy(false) }
  }
  async function submit(id: number, elapsed: number) {
    if (!question || result || busy || submitting.current) return
    submitting.current = true; setBusy(true); setSelected(id); setError('')
    const version = requestVersion.current
    try {
      const answer = await api<Result>(`/questions/${question.id}/answer`, { selected_id: id, elapsed_ms: elapsed })
      if (version !== requestVersion.current) return
      setResult(answer); setAnswers(previous => [...previous, answer])
    } catch (e) {
      if (version === requestVersion.current) { setError(e instanceof Error ? e.message : '답안 제출에 실패했어요. 다시 선택해 주세요.'); setSelected(null) }
    } finally { if (version === requestVersion.current) { submitting.current = false; setBusy(false) } }
  }
  function completeOrNext() {
    if (answers.length === ROUND_SIZE) setFinished(true)
    else void nextQuestion()
  }
  const posProducts = products.filter(p => p.category_id === category)
  const pageSize = 4
  return <section className="learning">
    <div className="section-heading"><div><h2>네 단계, 나에게 필요한 연습부터</h2><p>순서대로 잠금 해제할 필요 없이 원하는 단계를 선택하세요.</p></div><span className="round-rule">{advancedDelivery ? '심화 · 주문당 20점 · 자유 연습' : '5문제 · 정답당 20점 · 100점 만점'}</span></div>
    <div className="stage-grid" aria-label="학습 단계 선택">{stages.map(s => <button key={s.mode} className={`stage-card ${(mode === s.mode || (s.mode === 'name' && mode === 'similar-photo')) ? 'chosen' : ''}`} aria-pressed={mode === s.mode || (s.mode === 'name' && mode === 'similar-photo')} onClick={() => reset(s.mode)}><span className="stage-icon" aria-hidden="true">{s.icon}</span><small>{s.number}단계</small><h3>{s.title}</h3><p>{s.description}</p><span className="stage-action">{(mode === s.mode || (s.mode === 'name' && mode === 'similar-photo')) ? '선택됨 ✓' : '이 단계 선택 →'}</span></button>)}</div>
    {stage?.mode === 'name' && <div className="name-directions" aria-label="상품명 연습 방향"><button className={mode === 'name' ? 'selected' : ''} aria-pressed={mode === 'name'} onClick={() => reset('name')}>사진 보고 이름 선택</button><button className={mode === 'similar-photo' ? 'selected' : ''} aria-pressed={mode === 'similar-photo'} onClick={() => reset('similar-photo')}>이름 보고 사진 선택</button></div>}
    {stage?.mode === 'delivery' && <div className="name-directions" aria-label="배달 연습 난이도"><button aria-pressed={!advancedDelivery} className={!advancedDelivery ? 'selected' : ''} onClick={() => reset('delivery')}>기본 · 사진 1개 선택</button><button aria-pressed={advancedDelivery} className={advancedDelivery ? 'selected' : ''} onClick={() => { reset('delivery'); setAdvancedDelivery(true) }}>심화 · 주문서대로 포장</button></div>}
    {advancedDelivery && stage?.mode === 'delivery' ? <DeliveryAdvanced/> : !stage ? <div className="stage-empty">어떤 연습부터 해볼까요? 위에서 단계를 선택해 주세요.</div> : <div className="round-content">
      <div className="scoreboard"><span>{stage.number}단계 · {stage.title}</span><span>진행 <b>{answers.length} / {ROUND_SIZE}</b></span><span className="score">점수 <b>{score}</b> / 100</span></div>
      <progress aria-label="라운드 진행률" max={ROUND_SIZE} value={answers.length} />
      {error && <div role="alert" className="error">{error}</div>}
      {finished ? <section className="round-summary" aria-labelledby="round-summary-title"><span className="summary-icon" aria-hidden="true">{score === 100 ? '🏆' : score >= 60 ? '👏' : '💪'}</span><p className="eyebrow">ROUND COMPLETE</p><h2 id="round-summary-title">{stage.title} 완료!</h2><div className="final-score">{score}<span> / 100점</span></div><p>{ROUND_SIZE}문제 중 {correctCount}개 정답 · 정답률 {correctCount / ROUND_SIZE * 100}%</p><p>{score === 100 ? '완벽해요! 다음 근무가 한결 든든하겠어요.' : '실수한 상품을 다시 익히면 다음에는 더 잘할 수 있어요.'}</p>{answers.some(a => !a.is_correct) && <div className="round-mistakes"><h3>이번 라운드에서 헷갈린 상품</h3>{answers.filter(a => !a.is_correct).map(a => <div key={a.correct_product.id}><BreadArt kind={a.correct_product.illustration}/><span>{a.correct_product.name}<small>{a.correct_product.category_name}</small></span></div>)}</div>}<div className="summary-actions"><button className="primary" onClick={() => reset(mode)}>같은 단계 다시 연습</button><button className="secondary" onClick={() => reset(null)}>다른 단계 선택</button></div><small className="score-note">점수는 이번 라운드 기준이며 새로고침하면 초기화됩니다.</small></section>
      : <>
        {!question ? <section className="practice-panel"><div><span className="eyebrow">STAGE {stage.number}</span><h2>{stage.title}, 준비됐나요?</h2><p>{stage.description}</p>{(mode === 'name' || mode === 'similar-photo') && <p>유사 이름 그룹의 2~3개 보기에서 선택해요.</p>}</div><button className="primary" disabled={busy} onClick={() => void nextQuestion()}>{busy ? '문제 준비 중…' : error ? '다시 시도 →' : '5문제 연습 시작 →'}</button></section>
        : <>
          <section className="practice-panel"><div><span className="eyebrow">QUESTION {Math.min(answers.length + (result ? 0 : 1), ROUND_SIZE)} / {ROUND_SIZE}</span><h2>{mode === 'similar-photo' ? '이 이름에 맞는 빵 사진을 골라주세요.' : stage.prompt}</h2>{(mode === 'delivery' || mode === 'similar-photo') ? <div className="delivery-order"><small>{mode === 'delivery' ? '배달 주문서 · 1개' : '찾아야 할 상품명'}</small><strong>{question.prompt_name}</strong><p>{mode === 'delivery' ? '주문한 상품과 사진이 일치하는지 확인해 주세요.' : '비슷한 상품 그룹 안에서 정확한 사진을 찾아요.'}</p></div> : <p>{mode === 'pos' ? '카테고리 선택 → 상품 찾기 → 등록하기' : '첫 선택으로 채점해요. 틀려도 정답을 확인하고 다시 배울 수 있어요.'}</p>}</div>{question.illustration && <div className="question-art"><BreadArt kind={question.illustration}/><small>예시 일러스트</small></div>}</section>
          {(mode === 'category' || mode === 'name') && <div className="choices">{question.options.map((option, index) => <button key={option.id} className={selected === option.id ? 'answer-selected' : ''} disabled={busy || !!result} onClick={() => void submit(option.id, Math.round(performance.now() - startedAt.current))}><span>{index + 1}</span>{option.name}</button>)}</div>}
          {(mode === 'delivery' || mode === 'similar-photo') && <div className="delivery-choices" aria-label={mode === 'delivery' ? '배달 상품 사진 선택' : '유사 상품 사진 선택'}>{question.options.map((option, index) => <button key={option.id} className={`picture-choice ${selected === option.id ? 'answer-selected' : ''}`} aria-label={`${index + 1}번 사진 선택`} disabled={busy || !!result} onClick={() => void submit(option.id, Math.round(performance.now() - startedAt.current))}><BreadArt kind={option.illustration!}/><span>{index + 1}번 · {mode === 'delivery' ? '이 상품 담기' : '이 사진 선택'}</span><small>예시 일러스트</small></button>)}</div>}
          {mode === 'pos' && <section className="pos-register" aria-label="교육용 POS"><div className="pos-heading"><h3>교육용 POS</h3><small>상품명 검색 없이 카테고리에서 찾아요.</small></div><div className="categories" aria-label="POS 카테고리">{categories.map(c => <button key={c.id} className={category === c.id ? 'selected' : ''} aria-pressed={category === c.id} onClick={() => { setCategory(c.id); setPage(0) }}>{c.name}</button>)}</div>{category === 0 ? <div className="empty">먼저 위에서 상품 카테고리를 선택해 주세요.</div> : <><div className="product-grid">{posProducts.slice(page * pageSize, (page + 1) * pageSize).map(p => <ProductCard key={p.id} product={p} disabled={busy || !!result} onSelect={p => void submit(p.id, Math.round(performance.now() - startedAt.current))}/>)}</div><div className="pagination"><button disabled={page === 0} onClick={() => setPage(p => p - 1)}>← 이전</button><span>{page + 1} / {Math.max(1, Math.ceil(posProducts.length / pageSize))}</span><button disabled={(page + 1) * pageSize >= posProducts.length} onClick={() => setPage(p => p + 1)}>다음 →</button></div></>}{selected !== null && <div className="register-line">등록한 상품: {products.find(p => p.id === selected)?.name}</div>}</section>}
          {busy && <p role="status">답안을 확인하고 있어요…</p>}
          {result && <section className={`feedback ${result.is_correct ? 'correct' : 'mistake'}`} role="status"><div className="feedback-content"><span className="customer-face" aria-hidden="true">{result.is_correct ? '😊' : mode === 'delivery' ? '😠' : '😟'}</span><div><h2>{result.feedback}</h2><p>정답: {result.correct_product.name} · {result.correct_product.category_name}</p><small>{result.is_correct ? '+20점' : '+0점'} · 선택까지 {(result.elapsed_ms / 1000).toFixed(1)}초</small></div></div><button className="primary" disabled={busy} onClick={completeOrNext}>{answers.length === ROUND_SIZE ? '최종 점수 보기 →' : '다음 문제 →'}</button></section>}
        </>}
      </>}
    </div>}
  </section>
}
