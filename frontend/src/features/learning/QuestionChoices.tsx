import type { Question } from '../../lib/api'
import { BreadArt } from '../../components/BreadArt'

const prompts = {
  category: '이 빵은 어느 카테고리에 있나요?',
  name: '사진과 일치하는 상품명을 골라 주세요.',
  'similar-photo': '이 이름에 맞는 상품 사진을 골라 주세요.',
  delivery: '주문한 상품의 사진을 골라 주세요.',
  pos: '사진 속 상품을 찾아 주세요.',
}

export function QuestionChoices({ question, selected, disabled, onSelect }: {
  question: Question
  selected: number | null
  disabled: boolean
  onSelect: (id: number) => void
}) {
  const photos = question.mode === 'delivery' || question.mode === 'similar-photo'
  return <>
    <div className="practice-panel">
      <div><h3>{prompts[question.mode]}</h3>{question.prompt_name && <p><strong>{question.prompt_name}</strong></p>}</div>
      {question.illustration && <div className="question-art"><BreadArt kind={question.illustration}/></div>}
    </div>
    <div className={photos ? 'delivery-choices' : 'choices'} aria-label="답안 보기">
      {question.options.map((option, index) => <button
        key={option.id}
        className={`${photos ? 'picture-choice' : ''} ${selected === option.id ? 'answer-selected' : ''}`}
        disabled={disabled} aria-pressed={selected === option.id} onClick={() => onSelect(option.id)}>
        {option.illustration && <BreadArt kind={option.illustration}/>}
        <span>{index + 1}번</span>{option.category_name && <small>{option.category_name}</small>}{option.name}
      </button>)}
    </div>
  </>
}
