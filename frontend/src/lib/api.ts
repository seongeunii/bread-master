export type Category = { id: number; name: string }
export type Product = { id: number; name: string; price: number; category_id: number; category_name: string; illustration: string; description: string; is_sample: boolean }
export type Mode = 'category' | 'name' | 'similar-photo' | 'delivery' | 'pos'
export type Question = { id: string; mode: Mode; illustration: string | null; prompt_name: string | null; options: { id: number; name?: string; illustration?: string }[] }
export type Result = { points: number; feedback: string; is_correct: boolean; elapsed_ms: number; correct_product: Product }

export async function api<T>(path: string, body?: unknown, signal?: AbortSignal): Promise<T> {
  const response = await fetch(`/api/v1${path}`, {
    method: body === undefined ? 'GET' : 'POST',
    headers: body === undefined ? undefined : { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body), signal,
  })
  if (!response.ok) {
    const error = await response.json().catch(() => null)
    throw new Error(typeof error?.detail === 'string' ? error.detail : `요청 실패 (${response.status})`)
  }
  return response.json()
}
export const won = (price: number) => `${price.toLocaleString('ko-KR')}원`

export type InventoryProduct = Product & { quantity: number }
export type InventorySave = { category_id: number; items: { product_id: number; quantity: number }[] }
export type InventoryPractice = { id: string; products: InventoryProduct[]; saved_categories: Record<string, InventorySave> }
