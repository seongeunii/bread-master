// 실제 사진을 받기 전 사용하는 코드 기반 예시 일러스트입니다.
export function BreadArt({ kind }: { kind: string }) {
  if (!kind) return <span className="photo-placeholder">사진 확인 필요</span>
  if (kind.startsWith('https://')) return <img className="product-photo" src={kind} alt="상품 사진" loading="lazy" referrerPolicy="no-referrer" />
  const loaf = kind === 'loaf' || kind === 'milk'
  const sandwich = kind === 'sandwich' || kind === 'cheese'
  return <svg viewBox="0 0 240 160" role="img" aria-label="예시 상품 일러스트">
    <ellipse cx="120" cy="139" rx="78" ry="10" fill="#dac6ae" opacity=".45" />
    {loaf ? <><path d="M60 129V66C40 25 91 15 120 41C153 15 198 31 181 68V129Z" fill="#c88c49" /><path d="M74 118V69C58 40 98 32 120 53C143 32 177 43 168 70V118Z" fill={kind === 'milk' ? '#fff0cf' : '#e4b877'} /><path d="M95 71l10 8m30 20l12 6m-56 4l8 5" stroke="#bc8d4e" strokeWidth="5" strokeLinecap="round" /></>
    : kind === 'cake' ? <><path d="M64 130V57L174 70V130Z" fill="#e9b1a0"/><path d="M64 57L118 26L174 70Z" fill="#fff5e4"/><path d="M66 85L173 94M66 111L173 116" stroke="#fff5e4" strokeWidth="12"/><path d="M113 48C83 27 105 11 120 24C139 10 154 33 128 52Z" fill="#cc5651"/><path d="M115 24l5-12 8 13" fill="#708762"/></>
    : sandwich ? <><path d="M47 119L121 28L194 119Z" fill="#d29c64"/><path d="M57 110L121 40L181 110Z" fill="#fff0cc"/><path d="M51 122h141" stroke="#779456" strokeWidth="11"/><path d="M60 131h121" stroke={kind === 'cheese' ? '#efbd54' : '#f1d995'} strokeWidth="10"/><path d="M51 139h141" stroke="#c78a4c" strokeWidth="9"/></>
    : kind === 'danish' ? <><rect x="51" y="42" width="138" height="89" rx="20" fill="#d69c53"/><rect x="64" y="52" width="112" height="67" rx="14" fill="#efc27d"/><path d="M71 55L97 119M102 52L128 121M134 53L160 116" stroke="#765039" strokeWidth="9"/></>
    : <><path d={kind.endsWith('salt') ? 'M41 116Q80 20 159 55Q194 71 199 117Q120 146 41 116Z' : 'M37 115Q43 45 91 41Q120 29 151 44Q196 52 204 113L179 129Q163 101 148 98Q122 84 96 99Q73 106 62 129Z'} fill="#d99848"/><path d="M78 57Q69 85 86 116M112 44Q103 72 115 96M147 49Q136 72 145 98M178 69Q161 90 177 113" stroke="#f5ce8b" strokeWidth="12" strokeLinecap="round"/>{kind.endsWith('salt') && <path d="M102 66h4m34 6h4m-25 17h4" stroke="#fff7e3" strokeWidth="4" strokeLinecap="round"/>}</>}
    {kind === 'butter-salt' && <rect x="102" y="64" width="32" height="20" rx="3" fill="#ffe4a1" />}
    {kind === 'cheese-salt' && <path d="M80 66l70 18-45 30Z" fill="#f5b93c" />}
    {kind === 'choco-croissant' && <path d="M82 57l18 40m18-52l12 47m21-40l10 48" stroke="#6d4230" strokeWidth="8" strokeLinecap="round" />}
    {kind === 'almond-croissant' && <g fill="#fff0cb"><ellipse cx="95" cy="64" rx="7" ry="4"/><ellipse cx="127" cy="53" rx="7" ry="4"/><ellipse cx="149" cy="78" rx="7" ry="4"/><ellipse cx="112" cy="83" rx="7" ry="4"/></g>}
  </svg>
}
