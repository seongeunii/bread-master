import { useEffect, useState } from 'react'
import { api } from '../../lib/api'
import type { Category, Product } from '../../lib/api'
import { BreadArt } from '../../components/BreadArt'
import { PosTerminal } from '../pos/PosTerminal'
import type { PosProduct } from '../pos/PosTerminal'
export function Catalog({products,onDetail}:{products:Product[];onDetail:(p:Product)=>void}){
 const [layout,setLayout]=useState<{categories:Category[];products:PosProduct[]} | null>(null)
 const [category,setCategory]=useState(0),[page,setPage]=useState(0)
 const [selected,setSelected]=useState<PosProduct|null>(null),[error,setError]=useState('')
 const [search,setSearch]=useState('')
 useEffect(()=>{const c=new AbortController();api<typeof layout>('/pos-catalog',undefined,c.signal).then(setLayout).catch(e=>{if(!c.signal.aborted)setError(e.message)});return()=>c.abort()},[])
 const missing=products.filter(p=>!layout?.products.some(item=>(item.source_product_id ?? item.id)===p.id))
 const entries=search.trim()?[...(layout?.products??[]),...missing].filter(p=>p.name.includes(search.trim())).map((p,i)=>({...p,category_id:2000,pos_slot:i})):[...(layout?.products??[]),...missing.map((p,i)=>({...p,category_id:1999,pos_slot:i}))]
 const categories=search.trim()?[{id:2000,name:'검색 결과'}]:[...(layout?.categories??[]),{id:1999,name:'POS 미배치 상품'}]
 const currentCategory=search.trim()?2000:category
 return <section aria-label="POS 배치 상품 도감"><div className="section-heading"><div><h2>상품 도감</h2><p>POS 위치로 상품을 익혀요. 사이트 상품 {products.length}개 · POS 메뉴 {layout?.products.length ?? 0}개 · 미배치 {missing.length}개</p></div><label className="search">상품명 검색<input value={search} onChange={e=>{setSearch(e.target.value);setPage(0)}} placeholder="상품명 검색"/></label></div>
 {error&&<p className="error" role="alert">{error}</p>}
 {!layout?<p>상품 배치를 불러오는 중이에요.</p>:<PosTerminal categories={categories} products={entries} category={currentCategory} page={page} onCategory={id=>{setCategory(id);setPage(0)}} onPage={setPage} onProduct={setSelected} selected={selected?.id} ledger={selected?<><BreadArt kind={selected.illustration}/><h3>{selected.name}</h3><p>{layout.products.some(p=>p.id===selected.id)?'POS 분류: '+layout.products.find(p=>p.id===selected.id)?.category_name:'POS 위치 미확인'}</p><button className="secondary" onClick={()=>onDetail(selected)}>상품 상세 보기</button></>:<p>오른쪽 상품을 선택하면 정보를 확인할 수 있어요.</p>} controls={<p>‘POS 미배치 상품’과 검색 결과의 배열은 도감 탐색용입니다.</p>}/>}
 </section>
}
