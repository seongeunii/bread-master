import { useEffect, useRef, useState } from 'react'
import { api, won } from '../../lib/api'
import type { Category } from '../../lib/api'
import { BreadArt } from '../../components/BreadArt'
import { PosTerminal } from './PosTerminal'
import type { PosProduct } from './PosTerminal'
type Order = {id:string;lines:{product_id:number;name:string;quantity:number}[];options:{id:number;illustration:string}[]}
type Grade = {points:number;is_correct:boolean;feedback:string;differences:{product_id:number;name:string;expected:number;actual:number}[]}
export function PosPractice(){
 const [catalog,setCatalog]=useState<{categories:Category[];products:PosProduct[]} | null>(null)
 const [manual,setManual]=useState<PosProduct|null>(null),[priceInput,setPriceInput]=useState('')
 const [prices,setPrices]=useState<Record<number,number>>({})
 const [order,setOrder]=useState<Order|null>(null)
 const [cart,setCart]=useState<Record<number,number>>({})
 const [category,setCategory]=useState(0),[page,setPage]=useState(0)
 const [grade,setGrade]=useState<Grade|null>(null),[results,setResults]=useState<Grade[]>([])
 const [busy,setBusy]=useState(false),[error,setError]=useState('')
 const pending=useRef(false),started=useRef(0)
 useEffect(()=>{const c=new AbortController();api<typeof catalog>('/pos-catalog',undefined,c.signal).then(setCatalog).catch(e=>{if(!c.signal.aborted)setError(e.message)});return()=>c.abort()},[])
 async function next(){
  if(pending.current || !catalog)return
  pending.current=true;setBusy(true);setError('')
  try{const q=await api<Order>('/delivery-orders/pos/start',{});setOrder(q);setCart({});setPrices({});setManual(null);setGrade(null);setCategory(0);setPage(0);started.current=performance.now()}
  catch(e){setError(e instanceof Error?e.message:'주문 준비 실패')}
  finally{pending.current=false;setBusy(false)}
 }
 async function pay(){
  if(!order || grade || pending.current)return
  pending.current=true;setBusy(true);setError('')
  try{const r=await api<Grade>(`/delivery-orders/pos/${order.id}/submit`,{items:Object.entries(cart).map(([id,quantity])=>({product_id:Number(id),quantity})),elapsed_ms:Math.min(86400000,Math.round(performance.now()-started.current))});setGrade(r);setResults(old=>[...old,r])}
  catch(e){setError(e instanceof Error?e.message:'결제 연습 확인 실패')}
  finally{pending.current=false;setBusy(false)}
 }
 const total=Object.values(cart).reduce((a,b)=>a+b,0)
 return <section aria-label="사진 주문 POS 연습">
 <div className="scoreboard"><span>POS 결제 연습 · {results.length}/5</span><span>{results.reduce((a,r)=>a+r.points,0)} / 100점</span></div>
 {error && <p className="error" role="alert">{error}</p>}
 {!order ? <div className="practice-panel"><p>주어진 사진의 빵을 수량만큼 누르고 결제를 눌러요. 상품과 수량이 모두 맞으면 20점이에요.</p><button className="primary" disabled={busy || !catalog} onClick={()=>void next()}>POS 결제 연습 시작</button></div> : <>
 <div className="pos-photo-order"><h3>이 빵들을 계산해 주세요</h3><div>{order.lines.map(line=><div key={line.product_id}><BreadArt kind={order.options.find(p=>p.id===line.product_id)!.illustration}/><b>{line.quantity}개</b></div>)}</div><small>같은 상품을 여러 번 누르면 수량이 늘어나요.</small></div>
 {manual && <div className="pos-price-editor"><strong>빵류 · 가격 입력</strong><label>단가(원)<input aria-label="빵류 가격" type="number" min="1" max="999999" value={priceInput} onChange={e=>setPriceInput(e.target.value)}/></label><button className="secondary" disabled={!/^\d+$/.test(priceInput) || Number(priceInput)<1 || Number(priceInput)>999999} onClick={()=>{setPrices(p=>({...p,[manual.id]:Number(priceInput)}));setCart(c=>({...c,[manual.id]:c[manual.id]??1}));setManual(null)}}>가격 적용</button><button className="secondary" onClick={()=>setManual(null)}>닫기</button></div>}
 <PosTerminal categories={catalog?.categories??[]} products={catalog?.products??[]} category={category} page={page} onCategory={id=>{setCategory(id);setPage(0)}} onPage={setPage} onProduct={p=>{if(p.manual_price){setManual(p);setPriceInput(String(prices[p.id]??''))}else setCart(c=>({...c,[p.id]:Math.min(99,(c[p.id]??0)+1)}))}} disabled={busy || !!grade}
 ledger={<><table><thead><tr><th>상품명</th><th>수량</th><th>단가</th><th>삭제</th></tr></thead><tbody>{Object.entries(cart).map(([id,n])=><tr key={id}><td>{catalog?.products.find(p=>p.id===Number(id))?.name}</td><td>{n}</td><td>{won(prices[Number(id)] ?? catalog?.products.find(p=>p.id===Number(id))?.price ?? 0)}{catalog?.products.find(p=>p.id===Number(id))?.manual_price && <button disabled={busy || !!grade} onClick={()=>{setManual(catalog!.products.find(p=>p.id===Number(id))!);setPriceInput(String(prices[Number(id)]??''))}}>가격 수정</button>}</td><td><button className="pos-delete" aria-label={`${catalog?.products.find(p=>p.id===Number(id))?.name} 삭제`} disabled={busy || !!grade} onClick={()=>setCart(c=>{const next={...c};delete next[Number(id)];return next})}>×</button></td></tr>)}</tbody></table>{!total&&<p>오른쪽 상품을 눌러 등록하세요.</p>}<p>총 {total}개 등록 · {won(Object.entries(cart).reduce((sum,[id,n])=>sum+n*(prices[Number(id)]??catalog?.products.find(p=>p.id===Number(id))?.price??0),0))}</p></>}
 controls={<div className="pos-payment"><button className="primary" disabled={busy || !!grade || !total || !!manual} onClick={()=>void pay()}>{busy?'확인 중…':'결제'}</button></div>}/>
 {grade&&<section className={`feedback ${grade.is_correct?'correct':'mistake'}`} role="status"><div><h3>{grade.feedback}</h3><p>+{grade.points}점</p>{grade.differences.map(d=><p key={d.product_id}>{d.name} · 주문 {d.expected}개 / 등록 {d.actual}개</p>)}</div>{results.length<5?<button className="primary" disabled={busy} onClick={()=>void next()}>다음 주문</button>:<button className="primary" onClick={()=>{setOrder(null);setResults([]);setGrade(null);setCart({})}}>다시 연습</button>}</section>}
 </>}
 </section>
}
