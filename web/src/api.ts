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

/** `owner` es siempre el seudónimo del alumno en su clase (p. ej. 3.URGAA). */
export type Repository = {
  id: number
  owner: string
  /** <clase>-<assignment>-<seudónimo>: nunca el nombre real del repo. */
  repo_label: string
  head_sha: string | null
  head_committed_at: number | null
  last_synced_at: number | null
  status: string
  detail: string | null
  /** Dudas enviadas desde el tutor y aún sin leer. */
  pending_questions: number
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

/** Resultado de los tests de Classroom 50 del commit (leído de la release, no ejecutado). */
export type TestResults = {
  passed: number
  total: number
  score: number
  max_score: number
  tests: { name: string; passed: boolean; points: number; max_points: number }[]
}

export type PushOut = {
  owner: string
  assignment: string
  commit_sha: string
  message: string
  tests: TestResults
  analysis: AnalyzeOutcome
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
  tests: TestResults | null
  evolution: string | null
}

/** Progreso del alumno: calculado sobre su histórico de análisis + historia git. */
export type TestPoint = {
  commit: string
  at: number
  passed: number
  total: number
  score: number
  max_score: number
}

export type ProgressAlert = { kind: string; text: string }

export type StudentProgress = {
  owner: string
  analyses: number
  current: TestPoint | null
  timeline: TestPoint[]
  tests: {
    name: string
    passing: boolean
    first_passed_commit: string | null
    first_passed_at: number | null
    regressions: number
  }[]
  regressions: { test: string; commit: string; at: number }[]
  hint_streak: number
  repeated_hint: string | null
  rhythm: {
    commits: number
    analysed_commits: number
    first_at: number
    last_at: number
    active_days: number
    days_since_last: number
    avg_lines: number
    largest_lines: number
    largest_commit: string
  } | null
  alerts: ProgressAlert[]
  summary: string
  latest_hint: string | null
}

/** Evolución de la clase: agrega el progreso de cada alumno (solo profesorado). */
export type ClassEvolution = {
  students: number
  analysed: number
  with_tests: number
  all_passing: number
  avg_ratio: number | null
  tests: { name: string; passing: number; students: number }[]
  timeline: { day: string; avg_ratio: number; students: number }[]
  attention: ClassStudentRow[]
  rows: ClassStudentRow[]
  common_hints: { text: string; students: number }[]
  summary: string
}

export type ClassStudentRow = {
  owner: string
  analyses: number
  passed: number | null
  total: number | null
  score: number | null
  max_score: number | null
  last_commit_at: number | null
  alerts: string[]
}

export type Me = { login: string; name: string | null; avatar_url: string | null }

/** Rol detectado por el backend (staff = profesorado de alguna clase conocida). */
export type Role = {
  role: 'staff' | 'student' | 'unknown'
  staff_of: { org: string; classroom: string }[]
  owns_repos: boolean
}

/** Respuesta del tutor RAG: siempre con sus citas (material, tu feedback o la guía). */
export type TutorReply = {
  answer: string
  citations: {
    number: number
    source: 'material' | 'feedback' | 'zuzenaa' | string
    title: string
    heading: string | null
    snippet: string
    ref: string
  }[]
  blocked: boolean
  provider: string
  /** Preguntas para que el alumno piense (no la solución). */
  guide_questions: string[]
  /** Pasos para abordarlo, en lenguaje natural (sin código). */
  steps: string[]
  /** Apuntes que debería revisar, con el motivo y el fragmento. */
  notes: {
    number: number
    source: string
    title: string
    heading: string | null
    reason: string
    text: string
    ref: string
  }[]
  /** Aviso, p. ej. si el tutor avanzado no está disponible y responde el básico. */
  notice: string | null
}

export type TutorShare = {
  id: number
  analysis_id: number
  commit_sha: string
  note: string | null
  transcript: { role: 'user' | 'tutor'; text: string }[]
  created_at: number
  read_at: number | null
}

export type TutorDocument = {
  id: number
  title: string
  filename: string | null
  chunk_count: number
  created_at: number
}

export type Identity = {
  alias: string
  login: string
  first_name: string | null
  last_name: string | null
}

export type MyAssignment = {
  org: string
  classroom: string
  assignment: string
  owner: string
  /** <clase>-<assignment>-<seudónimo>: nunca el nombre real del repo. */
  repo_label: string
  status: string
  head_sha: string | null
  last_synced_at: number | null
  analyses: number
  last_analysis_at: number | null
  passed: number | null
  total: number | null
  score: number | null
  max_score: number | null
  last_commit_at: number | null
  latest_hint: string | null
  summary: string
  alerts: ProgressAlert[]
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

function tutorBase(org: string, classroom: string): string {
  return `/api/tutor/orgs/${org}/classrooms/${classroom}`
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
      demo_mode: boolean
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
  progress: (org: string, classroom: string, assignment: string, owner: string) =>
    getJson<StudentProgress>(`${assignmentBase(org, classroom, assignment)}/repos/${owner}/progress`),
  classProgress: (org: string, classroom: string, assignment: string) =>
    getJson<ClassEvolution>(`${assignmentBase(org, classroom, assignment)}/progress`),
  role: () => getJson<Role>('/api/me/role'),
  /** Entregas propias; con `preview`, vista previa del profesorado como ese alumno. */
  myAssignments: (preview?: { alias: string; org: string; classroom: string } | null) =>
    getJson<MyAssignment[]>(
      preview
        ? `/api/me/assignments?${new URLSearchParams({ as: preview.alias, org: preview.org, classroom: preview.classroom })}`
        : '/api/me/assignments',
    ),
  tutorChat: (
    org: string,
    classroom: string,
    body: {
      question: string
      assignment?: string | null
      as?: string | null
      /** Corrección desde la que se abre el tutor (su primera fuente). */
      analysis_id?: number | null
    },
  ) => post<TutorReply>(`${tutorBase(org, classroom)}/chat`, body),
  tutorSend: (
    org: string,
    classroom: string,
    assignment: string,
    owner: string,
    body: { analysis_id: number; note: string | null; transcript: TutorShare['transcript'] },
  ) =>
    post<TutorShare>(
      `${tutorBase(org, classroom)}/assignments/${assignment}/repos/${owner}/shares`,
      body,
    ),
  tutorShares: (org: string, classroom: string, assignment: string, owner: string) =>
    getJson<TutorShare[]>(
      `${tutorBase(org, classroom)}/assignments/${assignment}/repos/${owner}/shares`,
    ),
  tutorMarkRead: (org: string, classroom: string, id: number) =>
    post<TutorShare>(`${tutorBase(org, classroom)}/shares/${id}/read`),
  tutorDocuments: (org: string, classroom: string) =>
    getJson<TutorDocument[]>(`${tutorBase(org, classroom)}/documents`),
  tutorUpload: async (org: string, classroom: string, file: File, title?: string) => {
    const form = new FormData()
    form.append('file', file)
    if (title) form.append('title', title)
    const response = await fetch(`${tutorBase(org, classroom)}/documents`, {
      method: 'POST',
      body: form,
    })
    if (!response.ok) throw new Error(await errorMessage(response))
    return (await response.json()) as TutorDocument
  },
  tutorDelete: async (org: string, classroom: string, id: number) => {
    const response = await fetch(`${tutorBase(org, classroom)}/documents/${id}`, {
      method: 'DELETE',
    })
    if (!response.ok) throw new Error(await errorMessage(response))
  },
  /** Solo staff y queda registrado: la única forma de ver quién hay tras un seudónimo. */
  identity: (org: string, classroom: string, assignment: string, owner: string) =>
    getJson<Identity>(`${assignmentBase(org, classroom, assignment)}/repos/${owner}/identity`),
  /** Solo modo demo: el alumno sube su siguiente revisión (tests + descarga + análisis). */
  demoPush: (org: string, classroom: string, assignment: string, owner: string) =>
    post<PushOut>(`/api/demo/orgs/${org}/classrooms/${classroom}/assignments/${assignment}/repos/${owner}/push`),
}
