import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useNavigate } from '@tanstack/react-router'
import { api } from '../api'
import { classroom50Assignment, useClassroom50 } from '../classroom50'
import { useOrg } from '../components/AppLayout'
import { ExternalLink } from '../components/ExternalLink'
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
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['repos', org, classroom, assignment] }),
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
                if (window.confirm('¿Analizar la entrega de todos los alumnos descargados?')) {
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
            {analyzeAll.data.filter((o) => o.status === 'cached').length} en caché.
          </p>
        ) : null}
        {analyzeAll.isError ? <ErrorNote message={analyzeAll.error.message} /> : null}
      </header>

      {repos.isPending && <p className="muted">Cargando repos…</p>}
      {repos.isError && <ErrorNote message={repos.error.message} />}
      {repos.isSuccess && repos.data.length === 0 && (
        <section className="empty">
          <h2>Sin repos descargados</h2>
          <p>Pulsa «Descargar repos» para clonar los repositorios de los alumnos a este servidor.</p>
        </section>
      )}

      {repos.isSuccess && repos.data.length > 0 && (
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
                    onHistory={() =>
                      void navigate({
                        to: '/classrooms/$classroom/assignments/$assignment/students/$owner',
                        params: { classroom, assignment, owner: repo.owner },
                      })
                    }
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
  onHistory,
}: {
  org: string
  classroom: string
  assignment: string
  owner: string
  onHistory: () => void
}) {
  const queryClient = useQueryClient()
  const analyze = useMutation({
    mutationFn: (force: boolean) =>
      api.analyze(org, classroom, assignment, { owner, force }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['repos', org, classroom, assignment] }),
  })
  return (
    <span className="actions">
      <button type="button" className="link-button" disabled={analyze.isPending} onClick={() => analyze.mutate(false)}>
        Analizar
      </button>
      <button type="button" className="link-button" disabled={analyze.isPending} onClick={() => analyze.mutate(true)}>
        Reanalizar
      </button>
      <button type="button" className="link-button" onClick={onHistory}>
        Ver ficha
      </button>
    </span>
  )
}
