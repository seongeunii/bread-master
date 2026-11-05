export type MenuCandidate = {
  name: string
  price: string
  category_id: number
  slot: string
  photo: string
  source_url?: string
  note?: string
}

export function candidateFromText(text: string, categoryId: number, slot: number, confidence: number): MenuCandidate | null {
  const cleaned = text.replace(/[|_]/g, ' ').trim()
  if (!cleaned) return null
  const priceMatch = cleaned.match(/(?:₩\s*)?(\d{1,3}(?:,\d{3})+|\d{3,8})\s*원?\s*$/)
  const name = (priceMatch ? cleaned.slice(0, priceMatch.index) : cleaned).replace(/\s+/g, ' ').trim()
  return {
    name, price: priceMatch ? priceMatch[1].replace(/,/g, '') : '',
    category_id: categoryId, slot: String(slot), photo: '',
    note: `인식 신뢰도 ${Math.round(confidence)}% · 상품명·가격과 원본 칸을 확인하세요.`,
  }
}
