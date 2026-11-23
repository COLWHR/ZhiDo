import request from '@/utils/request'

export interface TeamMember {
  persona_id: number
  role: string
  name: string
  title?: string | null
  bio?: string | null
  avatar?: string | null
}

export interface Team {
  id: number
  owner_id: number
  name: string
  description: string
  members: TeamMember[]
  created_at?: string | null
}

export interface TeamAttachment {
  id?: number
  file_name: string
  mime_type?: string | null
  kind?: string | null
  storage_url: string
  preview_url?: string | null
  size?: number | null
  meta?: Record<string, any>
}

export interface TeamMessage {
  id: number
  team_id: number
  sender_type: 'user' | 'assistant' | 'system'
  user_id?: number | null
  persona_id?: number | null
  speaker_name: string
  content: string
  attachments: TeamAttachment[]
  mentioned_persona_ids: number[]
  message_type: string
  created_at?: string | null
}

const noCache = { headers: { 'Cache-Control': 'no-cache' } }

export const teamApi = {
  list: () => request.get('/teams/', noCache).then((r) => r.data as Team[]),

  detail: (id: number) => request.get(`/teams/${id}`, noCache).then((r) => r.data as Team),

  create: (payload: { name: string; description?: string; persona_ids: number[] }) =>
    request.post('/teams/', payload).then((r) => r.data as Team),

  remove: (id: number) => request.delete(`/teams/${id}`).then((r) => r.data),

  addMembers: (id: number, personaIds: number[]) =>
    request.post(`/teams/${id}/members`, { persona_ids: personaIds }).then((r) => r.data as Team),

  removeMember: (id: number, personaId: number) =>
    request.delete(`/teams/${id}/members/${personaId}`).then((r) => r.data),

  messages: (id: number) =>
    request.get(`/teams/${id}/messages`, noCache).then((r) => r.data as TeamMessage[]),
}
