import type { Mode } from '../../lib/api'
export const ROUND_SIZE = 5
export const stages: { mode: Mode; number: number; title: string; description: string; icon: string; prompt: string }[] = [
  { mode: 'category', number: 1, title: '카테고리 맞히기', description: '빵의 모습을 보고 어느 카테고리인지 찾아요.', icon: '🗂️', prompt: '이 빵은 어느 카테고리에 있나요?' },
  { mode: 'name', number: 2, title: '비슷한 상품명 구분', description: '사진 → 이름, 이름 → 사진 두 방향으로 비슷한 빵을 구분해요.', icon: '🥐', prompt: '비슷한 이름 중 정확한 상품명을 골라주세요.' },
  { mode: 'delivery', number: 3, title: '배달 연습', description: '주문서의 빵 이름을 보고 알맞은 사진을 골라요.', icon: '🛵', prompt: '주문한 빵을 골라 배달 봉투에 담아주세요.' },
  { mode: 'pos', number: 4, title: 'POS 연습', description: '사진 속 빵을 카테고리에서 찾아 POS에 등록해요.', icon: '🧾', prompt: '사진 속 빵을 POS에서 찾아 등록해 주세요.' },
]
