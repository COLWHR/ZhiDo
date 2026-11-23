/**
 * Identity avatar renderer.
 *
 * One visual language for the three populations in the product:
 *  - persona / counselor / user -> AI-illustrated portrait, chosen by discipline
 *  - fallback (asset missing or failed) -> deterministic academic badge / seal
 *
 * The portraits are original illustrations generated for this product and shipped
 * in `public/avatars/ai`, four variants per discipline. A persona's field decides
 * which pool it draws from, so a psychology expert never gets the philosophy look.
 * A custom uploaded image always wins; the badge is only a safety net.
 */

export type IdentityDiscipline =
  | 'philosophy'
  | 'psychology'
  | 'technology'
  | 'business'
  | 'arts'
  | 'humanities'
  | 'counseling'

type DisciplineMeta = {
  label: string
  bg: string
  bgSoft: string
  fg: string
  accent: string
  glyph: string
}

const disciplineMeta: Record<IdentityDiscipline, DisciplineMeta> = {
  philosophy: { label: '哲学', bg: '#15352a', bgSoft: '#245040', fg: '#f7fff9', accent: '#bee83f', glyph: 'ψ' },
  psychology: { label: '心理', bg: '#24384d', bgSoft: '#35536e', fg: '#f6fbff', accent: '#8fc2e8', glyph: '◍' },
  technology: { label: '科技', bg: '#12363c', bgSoft: '#1d535a', fg: '#f2fffd', accent: '#5fe0c8', glyph: '⚙' },
  business: { label: '商业', bg: '#43301f', bgSoft: '#5d442c', fg: '#fffaf5', accent: '#e8b46a', glyph: '◆' },
  arts: { label: '艺术', bg: '#352c46', bgSoft: '#4c3f63', fg: '#fff8ff', accent: '#cbb2ff', glyph: '✦' },
  humanities: { label: '人文', bg: '#262b31', bgSoft: '#3a4149', fg: '#f8fbff', accent: '#d8c7a3', glyph: '§' },
  counseling: { label: '咨询', bg: '#2a3a4a', bgSoft: '#3d5468', fg: '#f4fbff', accent: '#9fd8e8', glyph: '◍' },
}

const disciplineKeywords: Array<[IdentityDiscipline, string[]]> = [
  ['psychology', ['心理', '咨询', '精神', '情绪', '认知', '荣格', '弗洛伊德', '疗愈', '抑郁', '焦虑']],
  ['technology', ['科技', '技术', '算法', '计算机', '工程', '人工智能', 'AI', '数据', '物理', '数学', '生物', '医学', '芯片', '半导体', 'GPU', '英伟达', 'NVIDIA', '算力', '加速计算']],
  ['business', ['商业', '经济', '管理', '金融', '市场', '战略', '投资', '营销', '企业家']],
  ['arts', ['艺术', '文学', '诗', '美学', '设计', '音乐', '绘画', '电影', '建筑']],
  ['philosophy', ['哲学', '伦理', '思想', '形而上', '逻辑', '苏格拉底', '孔子', '尼采', '柏拉图', '亚里士多德', '存在']],
  ['humanities', ['历史', '社会', '政治', '法', '文化', '人类学', '教育', '军事']],
]

const hashString = (value: string) => {
  let hash = 0
  for (let index = 0; index < value.length; index += 1) {
    hash = (hash << 5) - hash + value.charCodeAt(index)
    hash |= 0
  }
  return Math.abs(hash)
}

const svgDataUri = (svg: string) => `data:image/svg+xml;charset=UTF-8,${encodeURIComponent(svg)}`

const escapeXml = (value: string) =>
  String(value || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&apos;')

export const getAvatarInitial = (value?: string, fallback = 'U') => {
  const trimmed = String(value || '').trim()
  return trimmed.slice(0, 1).toUpperCase() || fallback
}

export const isImageAvatar = (avatar?: string) => {
  const value = String(avatar || '').trim()
  return (
    value.startsWith('data:image/') ||
    value.startsWith('/avatars/') ||
    value.startsWith('/uploads/') ||
    value.startsWith('http://') ||
    value.startsWith('https://')
  )
}

export const detectDiscipline = (...hints: Array<string | undefined | null>): IdentityDiscipline => {
  const text = hints.filter(Boolean).join(' ')
  if (!text) return 'humanities'

  for (const [discipline, keywords] of disciplineKeywords) {
    if (keywords.some(keyword => text.includes(keyword))) return discipline
  }
  return 'humanities'
}

export const getDisciplineLabel = (discipline: IdentityDiscipline) => disciplineMeta[discipline].label

type PersonaLike = {
  name?: string
  title?: string
  bio?: string
  stance?: string
  theories?: string[] | string
}

const personaSeed = (persona: PersonaLike) =>
  `${persona.name || ''}|${persona.title || ''}|${persona.stance || ''}`

/**
 * Academic badge: discipline field, name initial, discipline glyph watermark and
 * a rank corner. Deterministic for a given persona.
 */
export const generatePersonaBadge = (persona: PersonaLike, rankLabel = '研究员') => {
  const hints = [
    persona.title,
    persona.bio,
    persona.stance,
    Array.isArray(persona.theories) ? persona.theories.join(' ') : persona.theories,
  ]
  const discipline = detectDiscipline(persona.title, ...hints)
  const meta = disciplineMeta[discipline]
  const initial = escapeXml(getAvatarInitial(persona.name, '智'))
  const rank = escapeXml(rankLabel.slice(0, 3))
  const hash = hashString(personaSeed(persona))
  const tilt = -18 + (hash % 36)

  return svgDataUri(`
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128" role="img" aria-label="${initial} ${meta.label}徽章">
      <defs>
        <linearGradient id="field" x1="12" y1="8" x2="118" y2="124" gradientUnits="userSpaceOnUse">
          <stop stop-color="${meta.bgSoft}"/>
          <stop offset="1" stop-color="${meta.bg}"/>
        </linearGradient>
        <linearGradient id="sheen" x1="0" y1="0" x2="0" y2="128" gradientUnits="userSpaceOnUse">
          <stop stop-color="#ffffff" stop-opacity="0.16"/>
          <stop offset="0.55" stop-color="#ffffff" stop-opacity="0"/>
        </linearGradient>
      </defs>
      <rect width="128" height="128" rx="30" fill="url(#field)"/>
      <rect width="128" height="128" rx="30" fill="url(#sheen)"/>
      <g opacity="0.16" transform="rotate(${tilt} 64 66)">
        <text x="64" y="86" text-anchor="middle" font-family="Georgia, 'Times New Roman', serif" font-size="62" fill="${meta.fg}">${meta.glyph}</text>
      </g>
      <rect x="10.5" y="10.5" width="107" height="107" rx="24" fill="none" stroke="${meta.accent}" stroke-opacity="0.34" stroke-width="1.5"/>
      <text x="64" y="82" text-anchor="middle" font-family="system-ui, -apple-system, 'Segoe UI', sans-serif" font-size="46" font-weight="700" fill="${meta.fg}">${initial}</text>
      <rect x="86" y="96" width="32" height="18" rx="8" fill="${meta.accent}" fill-opacity="0.92"/>
      <text x="102" y="109" text-anchor="middle" font-family="system-ui, -apple-system, 'Segoe UI', sans-serif" font-size="10" font-weight="600" fill="${meta.bg}">${rank}</text>
      <circle cx="26" cy="26" r="4" fill="${meta.accent}" fill-opacity="0.8"/>
    </svg>
  `)
}

/** Personal seal: square stamp, double rule, surname initial. */
export const generateUserAvatar = (username?: string) => {
  const seeded = hashString(String(username || 'user'))
  const fields = ['#3c4a44', '#44505f', '#4a4340', '#4b4657', '#3f4b52', '#4c4636']
  const field = fields[seeded % fields.length]
  const initial = escapeXml(getAvatarInitial(username, '我'))

  return svgDataUri(`
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128" role="img" aria-label="${initial} 个人印章">
      <rect width="128" height="128" rx="22" fill="${field}"/>
      <rect x="12" y="12" width="104" height="104" rx="12" fill="none" stroke="#f2ede1" stroke-opacity="0.55" stroke-width="2"/>
      <rect x="19" y="19" width="90" height="90" rx="8" fill="none" stroke="#f2ede1" stroke-opacity="0.24" stroke-width="1"/>
      <text x="64" y="84" text-anchor="middle" font-family="Georgia, 'Songti SC', serif" font-size="52" font-weight="600" fill="#f7f3e8">${initial}</text>
    </svg>
  `)
}

/** Counselling role badge: same skeleton, counselling palette. */
export const generateCounselorAvatar = (name?: string, focus?: string, style?: string) => {
  const discipline: IdentityDiscipline = 'counseling'
  const meta = disciplineMeta[discipline]
  const initial = escapeXml(getAvatarInitial(name, '心'))
  const hash = hashString(`${name || ''}|${focus || ''}|${style || ''}`)

  return svgDataUri(`
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128" role="img" aria-label="${initial} 咨询师徽章">
      <defs>
        <linearGradient id="cfield" x1="10" y1="10" x2="118" y2="120" gradientUnits="userSpaceOnUse">
          <stop stop-color="${meta.bgSoft}"/>
          <stop offset="1" stop-color="${meta.bg}"/>
        </linearGradient>
      </defs>
      <rect width="128" height="128" rx="30" fill="url(#cfield)"/>
      <circle cx="${30 + (hash % 66)}" cy="${28 + (hash % 70)}" r="${14 + (hash % 10)}" fill="${meta.accent}" opacity="0.12"/>
      <rect x="10.5" y="10.5" width="107" height="107" rx="24" fill="none" stroke="${meta.accent}" stroke-opacity="0.3" stroke-width="1.5"/>
      <text x="64" y="82" text-anchor="middle" font-family="system-ui, -apple-system, 'Segoe UI', sans-serif" font-size="46" font-weight="700" fill="${meta.fg}">${initial}</text>
      <rect x="84" y="96" width="34" height="18" rx="8" fill="${meta.accent}" fill-opacity="0.9"/>
      <text x="101" y="109" text-anchor="middle" font-family="system-ui, -apple-system, 'Segoe UI', sans-serif" font-size="10" font-weight="600" fill="${meta.bg}">咨询</text>
    </svg>
  `)
}

/** Backwards-compatible alias used by existing views. */
export const generatePersonaAvatar = (name?: string, title?: string, seedExtra?: string) =>
  generatePersonaBadge({ name, title, bio: seedExtra })

export type AvatarEntity = {
  avatar?: string | null
  avatar_kind?: string | null
  name?: string
  username?: string
  title?: string
  bio?: string
  stance?: string
  theories?: string[] | string
}

/**
 * Resolve what should actually be drawn: a real uploaded image when one exists,
 * otherwise the discipline-matched built-in portrait. Never returns an empty string.
 */
export const resolveIdentityAvatar = (
  kind: 'persona' | 'user' | 'counselor',
  entity: AvatarEntity | null | undefined,
  rankLabel?: string,
) => {
  const avatar = entity?.avatar
  if (isImageAvatar(avatar || '')) return String(avatar)

  if (kind === 'user') {
    return generateAiAvatar(
      'general',
      `user:${entity?.username || entity?.name || 'guest'}`,
      inferAvatarGender(entity?.username || entity?.name),
    )
  }
  if (kind === 'counselor') {
    return generateAiAvatar(
      'counseling',
      `counselor:${entity?.name || ''}|${entity?.title || ''}`,
      inferAvatarGender(entity?.name, `${entity?.title || ''} ${entity?.stance || ''}`),
    )
  }
  const hints = [
    entity?.title,
    entity?.bio,
    entity?.stance,
    Array.isArray(entity?.theories) ? entity.theories.join(' ') : entity?.theories,
  ]
  const discipline = detectDiscipline(...hints)
  return generateAiAvatar(
    discipline,
    `persona:${entity?.name || ''}|${entity?.title || ''}|${entity?.bio || ''}`,
    inferAvatarGender(entity?.name, hints.filter(Boolean).join(' ')),
  )
}

/**
 * Deterministic academic badge / personal seal. Used when the built-in portrait
 * cannot be loaded (offline build, missing asset) and as the legacy export kept
 * for older call sites.
 */
export const generateFallbackAvatar = (
  kind: 'persona' | 'user' | 'counselor',
  entity: AvatarEntity | null | undefined,
  rankLabel?: string,
) => {
  if (kind === 'user') return generateUserAvatar(entity?.username || entity?.name)
  if (kind === 'counselor') {
    return generateCounselorAvatar(entity?.name, entity?.title, entity?.stance)
  }
  return generatePersonaBadge(entity || {}, rankLabel)
}

/** AI portrait pools: eight variants each, original illustrations made for ZhiDo. */
export const AI_AVATAR_VARIANTS = 8

export type AvatarPool = IdentityDiscipline | 'general'
export type AvatarGender = 'male' | 'female' | 'any'

/**
 * Which variant indexes read as male / female in each pool. Kept explicit so a
 * named scholar is never shown with a mismatched portrait; unknown entities
 * fall back to all eight variants.
 */
const AI_AVATAR_GENDER: Record<AvatarPool, Record<'male' | 'female', number[]>> = {
  philosophy: { male: [1, 3, 4, 5, 7], female: [2, 6, 8] },
  psychology: { male: [2, 4, 5, 7], female: [1, 3, 6, 8] },
  technology: { male: [2, 3, 5, 7], female: [1, 4, 6, 8] },
  business: { male: [1, 3, 5, 7], female: [2, 4, 6, 8] },
  arts: { male: [2, 3, 5, 7], female: [1, 4, 6, 8] },
  humanities: { male: [1, 3, 4, 7, 8], female: [2, 5, 6] },
  counseling: { male: [3, 5, 7], female: [1, 2, 4, 6, 8] },
  general: { male: [1, 3, 5, 7], female: [2, 4, 6, 8] },
}

const FEMALE_CONTEXT = ['女性', '女士', '夫人', '母亲', '妈妈', '奶奶', '阿姨', '公主', '皇后', '女王', '太后']
const MALE_CONTEXT = ['男性', '先生', '男士', '父亲', '爸爸', '爷爷', '叔叔', '国王', '皇帝', '王子']
const FEMALE_NAME_CHARS = '婷娜丽敏静芳燕玲霞琴萍红梅兰珍秀娟慧美月莉薇媛婧妍婉琳瑶洁颖倩蓉淑贞凤娇妮娅娃玛莎'
const MALE_NAME_CHARS = '伟强军磊涛鹏杰峰明刚勇毅波斌龙飞超阳辉建国平志宏亮健虎彪坤勋克普凡德华山海洋林森岩松柏'

/**
 * Best-effort gender for choosing a portrait variant. Explicit wording in the
 * title / bio wins; otherwise a light given-name hint; otherwise no preference.
 * This only selects an illustration style, never asserts anyone's identity.
 */
export const inferAvatarGender = (name?: string, context?: string): AvatarGender => {
  const text = String(context || '')
  if (FEMALE_CONTEXT.some(word => text.includes(word))) return 'female'
  if (MALE_CONTEXT.some(word => text.includes(word))) return 'male'

  const chars = Array.from(String(name || ''))
  if (chars.some(char => FEMALE_NAME_CHARS.includes(char))) return 'female'
  if (chars.some(char => MALE_NAME_CHARS.includes(char))) return 'male'
  return 'any'
}

export const generateAiAvatar = (
  pool: AvatarPool,
  seed?: string,
  gender: AvatarGender = 'any',
) => {
  const key = (seed || 'zhido').trim() || 'zhido'
  const all = Array.from({ length: AI_AVATAR_VARIANTS }, (_, index) => index + 1)
  const candidates =
    gender === 'any' ? all : AI_AVATAR_GENDER[pool][gender] || []
  const usable = candidates.length ? candidates : all
  const index = usable[hashString(`${pool}|${key}`) % usable.length]
  return `/avatars/ai/${pool}-${index}.webp`
}
