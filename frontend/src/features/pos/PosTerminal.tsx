import type { ReactNode } from 'react'
import type { Category, Product } from '../../lib/api'
import { BreadArt } from '../../components/BreadArt'
import { won } from '../../lib/api'
import './PosTerminal.css'
export type PosProduct = Product & {pos_slot?: number}
type Props = {categories: Category[]; products: PosProduct[]; category: number; page: number; onCategory:(id:number)=>void; onPage:(page:number)=>void; onProduct:(p:PosProduct)=>void; disabled?:boolean; selected?:number|null; locked?:boolean; ledger:ReactNode; controls:ReactNode; stock?:Record<number,number>}
export function PosTerminal({categories,products,category,page,onCategory,onPage,onProduct,disabled,selected,locked,ledger,controls,stock}:Props) {
  const rows = products.filter(p=>p.category_id===category)
  const pages = Math.max(1,Math.ceil((Math.max(-1,...rows.map((p,i)=>p.pos_slot ?? i))+1)/25))
  return <section className="training-terminal" aria-label="교육용 POS 단말기">
    <div className="terminal-title"><strong>BREAD MASTER · 연습 POS</strong><small>실제 결제·재고 시스템 연동 없음</small></div>
    <div className="terminal-tabs" aria-label="POS 카테고리">{categories.map(c=><button key={c.id} aria-pressed={category===c.id} disabled={disabled || (locked && c.id!==category)} className={category===c.id?'selected':''} onClick={()=>onCategory(c.id)}>{c.name}</button>)}</div>
    <div className="terminal-body"><section className="terminal-ledger" aria-label="등록 내역"><h3>등록 내역</h3>{ledger}</section><section className="terminal-products" aria-label="POS 상품 선택"><div className="terminal-grid">{Array.from({length:25},(_,slot)=>{
      const p=rows.find((p,i)=>(p.pos_slot ?? i)===page*25+slot)
      return p ? <button key={slot} aria-label={`POS 상품 ${p.name}`} aria-pressed={selected===p.id} disabled={disabled} onClick={()=>onProduct(p)}><BreadArt kind={p.illustration}/><span>{p.name}</span><small>{stock ? `재고 ${stock[p.id]}개` : p.price_known ? won(p.price) : '가격 미등록'}</small></button> : <div key={slot} className="terminal-blank" aria-label="빈 상품 칸"/>
    })}</div>{!category && <p>상단에서 카테고리를 선택하세요.</p>}<div className="pagination"><button disabled={disabled || page===0} onClick={()=>onPage(page-1)}>← 이전 페이지</button><span>{page+1} / {pages}</span><button disabled={disabled || page+1>=pages} onClick={()=>onPage(page+1)}>다음 페이지 →</button></div></section></div>
    <div className="terminal-controls">{controls}</div>
    <small className="terminal-note">사진에서 확인한 칸 위치를 반영한 교육용 화면입니다. 미확인 상품 칸은 비워 두었습니다.</small>
  </section>
}
export function NumberPad({value,onChange,disabled=false}:{value:string;onChange:(value:string)=>void;disabled?:boolean}) {
 return <div className="terminal-keypad" aria-label="수량 숫자 키패드">{['7','8','9','4','5','6','1','2','3','지움','0','←'].map(key=><button key={key} disabled={disabled} onClick={()=>onChange(key==='지움'?'':key==='←'?value.slice(0,-1):(value==='0'?'':value)+key)}>{key}</button>)}</div>
}
