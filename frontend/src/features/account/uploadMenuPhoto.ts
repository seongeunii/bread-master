export async function uploadMenuPhoto(file: File): Promise<string> {
  if (file.size > 5 * 1024 * 1024) throw new Error('사진은 5MB 이하로 올려 주세요.')
  if (!['image/jpeg', 'image/png', 'image/webp'].includes(file.type)) throw new Error('JPG·PNG·WebP 사진을 선택해 주세요.')
  const response = await fetch('/api/v1/store-admin/photos', {
    method: 'POST', credentials: 'same-origin',
    headers: { 'X-Bread-Client': 'web', 'Content-Type': file.type }, body: file,
  })
  const result = await response.json()
  if (!response.ok) throw new Error(typeof result.detail === 'string' ? result.detail : '사진을 올리지 못했어요.')
  return result.url
}
