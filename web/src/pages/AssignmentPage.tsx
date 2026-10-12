import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useNavigate } from '@tanstack/react-router'
import { useState } from 'react'
import { api } from '../api'
import { classroom50Assignment, useClassroom50 } from '../classroom50'
import { useOrg } from '../components/AppLayout'
import { ExternalLink } from '../components/ExternalLink'
import { ClassEvolutionPanel } from '../components/Progress'
import { ErrorNote } from './ClassroomsPage'

function fmt(value: number | null): string {
  if (!value) return '—'
  return new Date(value * 1000).toLocaleString()
}

export function AssignmentPage({
  classroom,
  assignment,
}: {
  classroom: string
  assignment: string
}) {
  const org = useOrg()
  const base = useClassroom50()
  const queryClient = useQueryClient()
  const navigate = useNavigate()

  const [tab, setTab] = useState<'entregas' | 'evolucion'>('entregas')
  const evolution = useQuery({
    queryKey: ['classProgress', org, classroom, assignment],
    queryFn: () => api.classProgress(org, classroom, assignment),
    enabled: org.length > 0 && tab === 'evolucion',
  })
  const openStudent = (owner: string) =>
    void navigate({
      to: '/classrooms/$classroom/assignments/$assignment/students/$owner',
      params: { classroom, assignment, owner },
    })

  const authStatus = useQuery({ queryKey: ['authStatus'], queryFn: api.authStatus, retry: false })
  const demoMode = authStatus.data?.demo_mode ?? false

  const repos = useQuery({
    queryKey: ['repos', org, classroom, assignment],
    queryFn: () => api.repos(org, classroom, assignment),
    enabled: org.length > 0,
  })

  const sync = useMutation({
    mutationFn: () => api.syncRepos(org, classroom, assignment),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['repos', org, classroom, assignment] }),
  })

  const analyzeAll = useMutation({
    mutationFn: () => api.analyze(org, classroom, assignment),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['repos', org, classroom, assignment] })
      void queryClient.invalidateQueries({ queryKey: ['classProgress', org, classroom, assignment] })
    },
  })

  return (
    <section>
      <nav className="crumbs">
        <Link to="/">Clases</Link>
        <span aria-hidden="true">/</span>
        <Link to="/classrooms/$classroom" params={{ classroom }}>
          {classroom}
        </Link>
        <span aria-hidden="true">/</span>
        <span>{assignment}</span>
      </nav>

      <header className="page-head">
        <div className="head-row">
          <h2>{assignment}</h2>
          <div className="actions">
            <ExternalLink
              className="ext-button"
              href={classroom50Assignment(base, org, classroom, assignment)}
              title="Abrir el assignment en Classroom 50"
            >
              Ver en Classroom 50
            </ExternalLink>
            <button type="button" disabled={sync.isPending} onClick={() => sync.mutate()}>
              {sync.isPending ? 'Descargando…' : 'Descargar repos'}
            </button>
            <button
              type="button"
              disabled={analyzeAll.isPending}
              onClick={() => {
                if (window.confirm('¿Descargar el último push de todos los alumnos y analizarlo?')) {
                  analyzeAll.mutate()
                }
              }}
            >
              {analyzeAll.isPending ? 'Analizando…' : 'Analizar todos'}
            </button>
          </div>
        </div>
        {sync.isSuccess ? (
          <p className="note ok">
            Descargados {sync.data.cloned}, actualizados {sync.data.updated}, errores {sync.data.errors}.
          </p>
        ) : null}
        {sync.isError ? <ErrorNote message={sync.error.message} /> : null}
        {analyzeAll.isSuccess ? (
          <p className="note ok">
            {analyzeAll.data.filter((o) => o.status === 'analysed').length} analizados,{' '}
            {analyzeAll.data.filter((o) => o.status === 'cached').length} sin cambios (ya analizados),{' '}
            {analyzeAll.data.filter((o) => o.status === 'error').length} con error.
          </p>
        ) : null}
        {analyzeAll.isError ? <ErrorNote message={analyzeAll.error.message} /> : null}
      </header>

      <div className="tabs" role="tablist" aria-label="Vistas del assignment">
        <button
          type="button"
          role="tab"
          className="tab"
          aria-selected={tab === 'entregas'}
          onClick={() => setTab('entregas')}
        >
          Entregas
        </button>
        <button
          type="button"
          role="tab"
          className="tab"
          aria-selected={tab === 'evolucion'}
          onClick={() => setTab('evolucion')}
        >
          Evolución de la clase
        </button>
      </div>

      {tab === 'evolucion' && evolution.isPending ? <p className="muted">Calculando evolución…</p> : null}
      {tab === 'evolucion' && evolution.isError ? <ErrorNote message={evolution.error.message} /> : null}
      {tab === 'evolucion' && evolution.isSuccess ? (
        <ClassEvolutionPanel evolution={evolution.data} onStudent={openStudent} />
      ) : null}

      {tab === 'entregas' && repos.isPending && <p className="muted">Cargando repos…</p>}
      {tab === 'entregas' && repos.isError && <ErrorNote message={repos.error.message} />}
      {tab === 'entregas' && repos.isSuccess && repos.data.length === 0 && (
        <section className="empty">
          <h2>Sin repos descargados</h2>
          <p>Pulsa «Descargar repos» para clonar los repositorios de los alumnos a este servidor.</p>
        </section>
      )}

      {tab === 'entregas' && repos.isSuccess && repos.data.length > 0 && (
        <table className="table">
          <thead>
            <tr>
              <th>Alumno</th>
              <th>Estado</th>
              <th>Último commit</th>
              <th>Descargado</th>
              <th aria-label="Acciones" />
            </tr>
          </thead>
          <tbody>
            {repos.data.map((repo) => (
              <tr key={repo.id}>
                <td>
                  <code>{repo.owner}</code>
                </td>
                <td>
                  <span className={`dot ${repo.status === 'ok' ? 'success' : 'error'}`} aria-hidden="true" />{' '}
                  {repo.status}
                </td>
                <td>{repo.head_sha ? repo.head_sha.slice(0, 7) : '—'}</td>
                <td>{fmt(repo.last_synced_at)}</td>
                <td>
                  <RepoActions
                    org={org}
                    classroom={classroom}
                    assignment={assignment}
                    owner={repo.owner}
                    demoMode={demoMode}
                    onHistory={() => openStudent(repo.owner)}
                  />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  )
}

function RepoActions({
  org,
  classroom,
  assignment,
  owner,
  demoMode,
  onHistory,
}: {
  org: string
  classroom: string
  assignment: string
  owner: string
  demoMode: boolean
  onHistory: () => void
}) {
  const queryClient = useQueryClient()
  const refresh = () => {
    void queryClient.invalidateQueries({ queryKey: ['repos', org, classroom, assignment] })
    void queryClient.invalidateQueries({ queryKey: ['history', org, classroom, assignment, owner] })
    void queryClient.invalidateQueries({ queryKey: ['progress', org, classroom, assignment, owner] })
    void queryClient.invalidateQueries({ queryKey: ['classProgress', org, classroom, assignment] })
  }
  const analyze = useMutation({
    mutationFn: (force: boolean) =>
      api.analyze(org, classroom, assignment, { owner, force }),
    onSuccess: refresh,
  })
  // Modo demo: el alumno sube su siguiente revisión; Classroom 50 corre los tests y
  // ZuzenAA descarga y analiza sin pulsar «Analizar».
  const push = useMutation({
    mutationFn: () => api.demoPush(org, classroom, assignment, owner),
    onSuccess: refresh,
  })
  return (
    <span className="actions">
      {demoMode ? (
        <button
          type="button"
          className="link-button"
          disabled={push.isPending}
          title="Demo: el alumno hace commit + push de su siguiente revisión"
          onClick={() => push.mutate()}
        >
          {push.isPending ? 'Subiendo…' : 'Simular push'}
        </button>
      ) : null}
      <button
        type="button"
        className="link-button"
        disabled={analyze.isPending}
        title="Descarga el último push y lo analiza"
        onClick={() => analyze.mutate(false)}
      >
        {analyze.isPending ? 'Analizando…' : 'Analizar'}
      </button>
      <button type="button" className="link-button" disabled={analyze.isPending} onClick={() => analyze.mutate(true)}>
        Reanalizar
      </button>
      <button type="button" className="link-button" onClick={onHistory}>
        Ver ficha
      </button>
      {push.isSuccess ? (
        <span className="dim">
          {push.data.commit_sha.slice(0, 7)} · tests {push.data.tests.passed}/{push.data.tests.total} ·{' '}
          {push.data.analysis.status}
        </span>
      ) : null}
      {push.isError ? <span className="dim">{push.error.message}</span> : null}
      {analyze.isSuccess && analyze.data[0] ? (
        <span className="dim">
          {analyze.data[0].status === 'cached' ? 'sin cambios' : analyze.data[0].status}
          {analyze.data[0].reason ? ` · ${analyze.data[0].reason}` : ''}
        </span>
      ) : null}
      {analyze.isError ? <span className="dim">{analyze.error.message}</span> : null}
    </span>
  )
}
