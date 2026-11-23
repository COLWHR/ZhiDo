import { describe, expect, it } from 'vitest'
import {
  generateAiAvatar,
  generatePersonaAvatar,
  getAvatarInitial,
  isImageAvatar,
  resolveIdentityAvatar
} from '../avatar'

describe('avatar utilities', () => {
  it('generates deterministic image avatars for personas', () => {
    const avatar = generatePersonaAvatar('苏格拉底', '古希腊哲学家', '追问真理')

    expect(avatar).toMatch(/^data:image\/svg\+xml;charset=UTF-8,/)
    expect(isImageAvatar(avatar)).toBe(true)
    expect(generatePersonaAvatar('苏格拉底', '古希腊哲学家', '追问真理')).toBe(avatar)
  })

  it('honours an explicit built-in portrait path', () => {
    const explicit = '/avatars/ai/portrait-marx.webp'

    expect(isImageAvatar(explicit)).toBe(true)
    expect(
      resolveIdentityAvatar('persona', {
        name: '马克思',
        title: '思想家、哲学家',
        avatar: explicit,
      }),
    ).toBe(explicit)
  })

  it('keeps a readable initial fallback', () => {
    expect(getAvatarInitial('Alice')).toBe('A')
    expect(getAvatarInitial('张三')).toBe('张')
    expect(getAvatarInitial('')).toBe('U')
  })

  it('assigns an AI portrait deterministically from the persona discipline', () => {
    expect(generateAiAvatar('philosophy', 'persona:苏格拉底')).toMatch(
      /^\/avatars\/ai\/philosophy-[1-8]\.webp$/,
    )

    const philosopher = resolveIdentityAvatar('persona', {
      name: '苏格拉底',
      title: '古希腊哲学家',
    })
    expect(philosopher).toMatch(/^\/avatars\/ai\/philosophy-[1-8]\.webp$/)
    expect(philosopher).toBe(
      resolveIdentityAvatar('persona', { name: '苏格拉底', title: '古希腊哲学家' }),
    )

    expect(
      resolveIdentityAvatar('persona', { name: '荣格', title: '心理学家' }),
    ).toMatch(/^\/avatars\/ai\/psychology-[1-8]\.webp$/)
    expect(
      resolveIdentityAvatar('persona', { name: '某工程师', title: '人工智能研究员' }),
    ).toMatch(/^\/avatars\/ai\/technology-[1-8]\.webp$/)

    // Portrait gender follows the person when the data makes it explicit.
    expect(
      resolveIdentityAvatar('persona', { name: '黄仁勋', title: 'NVIDIA创始人兼首席执行官' }),
    ).toMatch(/^\/avatars\/ai\/technology-(2|3|5|7)\.webp$/)
    expect(
      resolveIdentityAvatar('persona', {
        name: '扎哈·哈迪德',
        title: '解构主义建筑大师 / 首位女性得主',
      }),
    ).toMatch(/^\/avatars\/ai\/arts-(1|4|6|8)\.webp$/)

    expect(resolveIdentityAvatar('counselor', { name: '林医生' })).toMatch(
      /^\/avatars\/ai\/counseling-[1-8]\.webp$/,
    )
    expect(resolveIdentityAvatar('user', { username: 'alice' })).toMatch(
      /^\/avatars\/ai\/general-[1-8]\.webp$/,
    )
  })

  it('prefers an uploaded image over the built-in portrait', () => {
    const uploaded = '/uploads/avatars/users/42/abc.webp'
    expect(resolveIdentityAvatar('user', { username: 'alice', avatar: uploaded })).toBe(uploaded)
  })
})
