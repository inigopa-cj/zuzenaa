import { useMutation, useQuery } from '@tanstack/react-query'
import { Link, useNavigate } from '@tanstack/react-router'
import { useState } from 'react'
import { api, type Analysis } from '../api'
import { useOrg } from '../components/AppLayout'
import { FeedbackBody, TestsBadge, fmtDateTime, shortSha } from '../components/Feedback'
import { StudentProgressPanel } from '../components/Progress'
import { useViewer } from '../components/Viewer'
import { ErrorNote } from './ClassroomsPage'

export function StudentPage({
  org: orgProp,
  classroom,
  assignment,
  owner,
}: {
  org?: string
  classroom: string
  assignment: string
  owner: string
}) {
  const contextOrg = useOrg()
  const org = orgProp ?? contextOrg
  const studentSurface = orgProp !== undefined
  const [tab, setTab] = useState<'progreso' | 'historico'>('progreso')

  const { preview, setPreview } = useViewer()
  const navigate = useNavigate()
  // La lista de repos es de profesorado; el alumno lee su entrega de /me/assignments.
  const repos = useQuery({
    queryKey: ['repos', org, classroom, assignment],
    queryFn: () => api.repos(org, classroom, assignment),
    enabled: org.length > 0 && !studentSurface,
  })
  const mine = useQuery({
    queryKey: ['myAssignments', preview],
    queryFn: () => api.myAssignments(preview),
    enabled: studentSurface,
  })
  const history = useQuery({
    queryKey: ['history', org, classroom, assignment, owner],
    queryFn: () => api.history(org, classroom, assignment, owner),
    enabled: org.length > 0,
  })

  const progress = useQuery({
    queryKey: ['progress', org, classroom, assignment, owner],
    queryFn: () => api.progress(org, classroom, assignment, owner),
    enabled: org.length > 0,
  })

  // «Mostrar identidad» (solo staff, registrado en el backend). Mutación, no consulta:
  // así la identidad no queda en la caché y desaparece al salir de la ficha.
  const reveal = useMutation({
    mutationFn: () => api.identity(org, classroom, assignment, owner),
  })

  const repo =
    (studentSurface
      ? mine.data?.find(
          (item) =>
            item.owner === owner && item.classroom === classroom && item.assignment === assignment,
        )
      : repos.data?.find((item) => item.owner === owner)) ?? null
  const reviews = history.data ?? []
  const ascending = [...reviews].reverse()

  return (
    <section>
      <nav className="crumbs">
        {studentSurface ? (
          <Link to="/mis-clases">Mis entregas</Link>
        ) : (
          <Link to="/">Clases</Link>
        )}
        <span aria-hidden="true">/</span>
        {studentSurface ? (
          <span>{classroom}</span>
        ) : (
          <Link to="/classrooms/$classroom" params={{ classroom }}>
            {classroom}
          </Link>
        )}
        <span aria-hidden="true">/</span>
        <span>{assignment}</span>
        <span aria-hidden="true">/</span>
        <span>{owner}</span>
      </nav>

      <header className="page-head">
        <div className="head-row">
          <h2>{studentSurface ? assignment : owner}</h2>
          {!studentSurface ? (
            <div className="actions">
              <button
                type="button"
                className="ghost"
                title="Solo profesorado. Cada consulta queda registrada."
                disabled={reveal.isPending}
                onClick={() => (reveal.isSuccess ? reveal.reset() : reveal.mutate())}
              >
                {reveal.isSuccess ? 'Ocultar identidad' : 'Mostrar identidad'}
              </button>
              <button
                type="button"
                title="Ver la plataforma tal como la ve este alumno (solo lectura)"
                onClick={() => {
                  setPreview({ alias: owner, org, classroom })
                  void navigate({ to: '/mis-clases' })
                }}
              >
                Ver como este alumno
              </button>
            </div>
          ) : null}
        </div>
        <p className="muted">
          {repo ? (
            <>
              <code>{repo.repo_label}</code>
              {repo.head_sha ? <> · {shortSha(repo.head_sha)}</> : null}
              {repo.last_synced_at ? <> · descargado {fmtDateTime(repo.last_synced_at)}</> : null}
            </>
          ) : (
            <>Sigue el recorrido de feedback de esta entrega.</>
          )}
        </p>
        {reveal.isSuccess ? (
          <p className="identity-note" role="status">
            Identidad (solo profesorado, consulta registrada):{' '}
            <b>
              {[reveal.data.first_name, reveal.data.last_name].filter(Boolean).join(' ') ||
                'sin nombre en el roster'}
            </b>{' '}
            · GitHub <code>{reveal.data.login}</code>
          </p>
        ) : null}
        {reveal.isError ? <ErrorNote message={reveal.error.message} /> : null}
        {reviews.length > 0 ? <Pulse reviews={reviews} /> : null}
      </header>

      {history.isPending && <p className="muted">Cargando histórico…</p>}
      {history.isError && <ErrorNote message={history.error.message} />}
      {history.isSuccess && reviews.length === 0 && (
        <section className="empty">
          <h2>Sin revisiones</h2>
          <p>
            Todavía no hay análisis para esta entrega. Lanza un análisis desde el assignment y
            aparecerá aquí con su fecha y commit.
          </p>
        </section>
      )}

      {reviews.length > 0 && (
        <>
          <div className="tabs" role="tablist" aria-label="Vistas de la entrega">
            <button
              type="button"
              role="tab"
              className="tab"
              aria-selected={tab === 'progreso'}
              onClick={() => setTab('progreso')}
            >
              Progreso
            </button>
            <button
              type="button"
              role="tab"
              className="tab"
              aria-selected={tab === 'historico'}
              onClick={() => setTab('historico')}
            >
              Histórico
            </button>
          </div>

          {tab === 'progreso' && progress.isSuccess ? (
            <StudentProgressPanel progress={progress.data} />
          ) : null}
          {tab === 'progreso' && progress.isError ? <ErrorNote message={progress.error.message} /> : null}
          {tab === 'progreso' ? (
            <ol className="timeline">
              {ascending.map((item, index) => {
                const latest = index === ascending.length - 1
                return (
                  <li key={item.id} className={latest ? 'timeline-item latest' : 'timeline-item'}>
                    <span className="timeline-marker" aria-hidden="true" />
                    <div className="timeline-body">
                      <div className="timeline-meta">
                        <code>{shortSha(item.commit_sha)}</code>
                        <time dateTime={new Date(item.created_at * 1000).toISOString()}>
                          {fmtDateTime(item.created_at)}
                        </time>
                        {item.tests ? <TestsBadge tests={item.tests} /> : null}
                        {latest ? <span className="badge">última</span> : null}
                      </div>
                      <p className="timeline-summary">
                        {item.feedback
                          ? item.feedback.funcionalidad
                          : 'Revisión sin resumen estructurado.'}
                      </p>
                      {item.evolution ? (
                        <p className="timeline-evo muted">{item.evolution}</p>
                      ) : null}
                    </div>
                  </li>
                )
              })}
            </ol>
          ) : (
            <div className="history">
              {reviews.map((item) => (
                <article key={item.id} className="feedback">
                  <header>
                    <code>{shortSha(item.commit_sha)}</code>
                    <span className="dim"> · {fmtDateTime(item.created_at)}</span>
                    <span className="dim"> · {item.provider}</span>
                    {item.tests ? <> <TestsBadge tests={item.tests} /></> : null}
                  </header>
                  {item.evolution ? <p className="muted">{item.evolution}</p> : null}
                  <FeedbackBody analysis={item} />
                </article>
              ))}
            </div>
          )}
        </>
      )}
    </section>
  )
}

function Pulse({ reviews }: { reviews: Analysis[] }) {
  const commits = new Set(reviews.map((item) => item.commit_sha)).size
  const first = reviews[reviews.length - 1]
  const last = reviews[0]
  return (
    <div className="pulse">
      <span>
        <b>{reviews.length}</b> revisiones
      </span>
      <span>
        <b>{commits}</b> commits
      </span>
      <span>Primera {fmtDateTime(first.created_at)}</span>
      <span>Última {fmtDateTime(last.created_at)}</span>
    </div>
  )
}
