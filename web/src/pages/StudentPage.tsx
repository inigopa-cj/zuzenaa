import { useQuery } from '@tanstack/react-query'
import { Link } from '@tanstack/react-router'
import { useState } from 'react'
import { api, type Analysis } from '../api'
import { useOrg } from '../components/AppLayout'
import { FeedbackBody, fmtDateTime, shortSha } from '../components/Feedback'
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

  const repos = useQuery({
    queryKey: ['repos', org, classroom, assignment],
    queryFn: () => api.repos(org, classroom, assignment),
    enabled: org.length > 0,
  })
  const history = useQuery({
    queryKey: ['history', org, classroom, assignment, owner],
    queryFn: () => api.history(org, classroom, assignment, owner),
    enabled: org.length > 0,
  })

  const repo = repos.data?.find((item) => item.owner === owner) ?? null
  const reviews = history.data ?? []
  const ascending = [...reviews].reverse()

  return (
    <section>
      <nav className="crumbs">
        {studentSurface ? (
          <Link to="/mis-clases">Mis clases</Link>
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
        <h2>{owner}</h2>
        <p className="muted">
          {repo ? (
            <>
              <code>{repo.repo_full_name}</code>
              {repo.head_sha ? <> · {shortSha(repo.head_sha)}</> : null}
              {repo.last_synced_at ? <> · descargado {fmtDateTime(repo.last_synced_at)}</> : null}
            </>
          ) : (
            <>Sigue el recorrido de feedback de esta entrega.</>
          )}
        </p>
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
