import { BreadArt } from './BreadArt'
import { won } from '../lib/api'
import type { Product } from '../lib/api'
export function ProductCard({ product, onSelect, disabled = false }: { product: Product; onSelect: (product: Product) => void; disabled?: boolean }) {
  return <button className="product-card" onClick={() => onSelect(product)} disabled={disabled}>
    <div className="art"><BreadArt kind={product.illustration} /><span>예시 일러스트</span></div>
    <div className="card-body"><small>{product.category_name}</small><h3>{product.name}</h3><p>{won(product.price)} <span aria-hidden="true">↗</span></p></div>
  </button>
}
