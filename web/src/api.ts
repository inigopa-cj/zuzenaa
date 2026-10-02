/** API client for ZuzenAA (repos + análisis + histórico). */

export type Classroom = {
  short_name: string
  name: string
  term: string | null
  active: boolean
  team: { id: number; slug: string } | null
}

export type AssignmentTest = { name: string; type: string; points: number }

export type Assignment = {
  slug: string
  name: string
  description: string | null
  mode: string
  autograder: string
  template: { owner: string; repo: string; branch: string | null } | null
  tests: AssignmentTest[]
  feedback_pr: boolean
  submission_mode: string | null
}

export type Student = {
  username: string
  first_name: string | null
  last_name: string | null
  email: string | null
  section: string | null
  github_id: number | null
  role: string | null
}

export type Repository = {
  id: number
  owner: string
  repo_full_name: string
  head_sha: string | null
  head_committed_at: number | null
  last_synced_at: number | null
  status: string
  detail: string | null
}

export type SyncOut = {
  total: number
  cloned: number
  updated: number
  skipped: number
  errors: number
}

export type AnalyzeOutcome = {
  owner: string
  status: string
  commit_sha: string | null
  analysis_id: number | null
  reason: string | null
}

export type Hint = { level: number; text: string }

export type Feedback = {
  funcionalidad: string
  calidad: string
  diseno: string
  pista: Hint
  teoria: string | null
}

export type Analysis = {
  id: number
  owner: string
  commit_sha: string
  commit_committed_at: number | null
  created_at: number
  provider: string
  feedback_md: string
  feedback: Feedback | null
  evolution: string | null
}

export type Me = { login: string; name: string | null; avatar_url: string | null }

export type MyAssignment = {
  org: string
  classroom: string
  assignment: string
  owner: string
  repo_full_name: string
  head_sha: string | null
  last_synced_at: number | null
  analyses: number
  last_analysis_at: number | null
}

async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(path, { headers: { Accept: 'application/json' } })
  if (!response.ok) throw new Error(await errorMessage(response))
  return (await response.json()) as T
}

async function post<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch(path, {
    method: 'POST',
    headers: body ? { 'Content-Type': 'application/json' } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  })
  if (!response.ok) throw new Error(await errorMessage(response))
  return (await response.json()) as T
}

async function errorMessage(response: Response): Promise<string> {
  try {
    const payload = (await response.json()) as { detail?: string }
    if (payload.detail) return payload.detail
  } catch {
    /* non-JSON */
  }
  return `HTTP ${response.status}`
}

function assignmentBase(org: string, classroom: string, assignment: string): string {
  return `/api/orgs/${org}/classrooms/${classroom}/assignments/${assignment}`
}

export const api = {
  me: () => getJson<Me>('/api/auth/me'),
  authStatus: () =>
    getJson<{
      oauth_configured: boolean
      env_token_allowed: boolean
      scopes: string
      callback_url: string
      classroom50_url: string
    }>('/api/auth/status'),
  orgs: () => getJson<{ login: string }[]>('/api/orgs'),
  classrooms: (org: string) => getJson<Classroom[]>(`/api/orgs/${org}/classrooms`),
  assignments: (org: string, classroom: string) =>
    getJson<Assignment[]>(`/api/orgs/${org}/classrooms/${classroom}/assignments`),
  roster: (org: string, classroom: string) =>
    getJson<Student[]>(`/api/orgs/${org}/classrooms/${classroom}/roster`),
  repos: (org: string, classroom: string, assignment: string) =>
    getJson<Repository[]>(`${assignmentBase(org, classroom, assignment)}/repos`),
  syncRepos: (org: string, classroom: string, assignment: string) =>
    post<SyncOut>(`${assignmentBase(org, classroom, assignment)}/repos/sync`),
  analyze: (org: string, classroom: string, assignment: string, opts?: { owner?: string; force?: boolean }) =>
    post<AnalyzeOutcome[]>(`${assignmentBase(org, classroom, assignment)}/analysis`, {
      owner: opts?.owner,
      force: opts?.force ?? false,
    }),
  history: (org: string, classroom: string, assignment: string, owner: string) =>
    getJson<Analysis[]>(`${assignmentBase(org, classroom, assignment)}/repos/${owner}/analyses`),
  myAssignments: () => getJson<MyAssignment[]>('/api/me/assignments'),
}
