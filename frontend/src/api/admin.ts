import request from '@/utils/request'

export interface AdminUser {
  id: number
  username: string
  role: string
  avatar: string | null
  created_at: string | null
  credits_balance: number
}

export interface AdminConfig {
  key: string
  value: string | null
  category: string | null
  label: string | null
  description: string | null
  updated_at: string | null
  updated_by: number | null
}

const noCache = { headers: { 'Cache-Control': 'no-cache' } }

export const adminApi = {
  overview: () => request.get('/admin/overview', noCache).then((r) => r.data),

  users: (params?: { keyword?: string; limit?: number; offset?: number }) =>
    request.get('/admin/users', { ...noCache, params }).then((r) => r.data as AdminUser[]),

  userTransactions: (id: number) =>
    request.get(`/admin/users/${id}/transactions`, noCache).then((r) => r.data),

  adjustCredits: (id: number, amount: number, note?: string) =>
    request
      .patch(`/admin/users/${id}/credits`, { amount, note })
      .then((r) => r.data),

  setRole: (id: number, role: string) =>
    request.patch(`/admin/users/${id}/role`, { role }).then((r) => r.data),

  configs: (category?: string) =>
    request
      .get('/admin/config', { ...noCache, params: category ? { category } : {} })
      .then((r) => r.data as AdminConfig[]),

  updateConfig: (key: string, value: string | null) =>
    request.put(`/admin/config/${key}`, { value }).then((r) => r.data),

  personas: () => request.get('/admin/personas', noCache).then((r) => r.data),

  updatePersona: (id: number, payload: Record<string, unknown>) =>
    request.put(`/admin/personas/${id}`, payload).then((r) => r.data),

  personaKnowledge: (id: number) =>
    request.get(`/admin/personas/${id}/knowledge`, noCache).then((r) => r.data),

  deleteKnowledge: (docId: number) =>
    request.delete(`/admin/knowledge/${docId}`).then((r) => r.data),

  skills: () => request.get('/admin/skills', noCache).then((r) => r.data),

  updateSkill: (id: number, payload: Record<string, unknown>) =>
    request.put(`/admin/skills/${id}`, payload).then((r) => r.data),

  auditLogs: (limit?: number) =>
    request.get('/admin/audit-logs', { ...noCache, params: { limit } }).then((r) => r.data),
}

export const creditsApi = {
  my: () => request.get('/users/me/credits', noCache).then((r) => r.data),
}
