import { useQuery } from '@tanstack/react-query'
import { Link } from '@tanstack/react-router'
import { api, type MyAssignment } from '../api'
import { fmtDateTime } from '../components/Feedback'
import { useViewer } from '../components/Viewer'
import { ErrorNote } from './ClassroomsPage'

/** Superficie del alumno: una tarjeta por entrega con tests, pista actual y avisos. */
export function MyClassesPage() {
  const { preview } = useViewer()
  const me = useQuery({ queryKey: ['me'], queryFn: api.me, retry: false })
  const mine = useQuery({
    queryKey: ['myAssignments', preview],
    queryFn: () => api.myAssignments(preview),
    retry: false,
    enabled: me.isSuccess,
  })

  if (me.isError) {
    return (
      <section className="empty">
        <h2>Inicia sesión</h2>
        <p>
          Entra con GitHub para ver tus entregas, tus tests y todo tu feedback.{' '}
          <a href="/api/auth/login">Iniciar sesión</a>.
        </p>
      </section>
    )
  }

  const items = mine.data ?? []
  const groups = groupByClassroom(items)

  return (
    <section>
      <header className="page-head">
        <h2>Mis entregas</h2>
        <p className="muted">
          Cómo van tus tests, la pista de tu última revisión y tu progreso. En cada clase
          apareces con tu <b>código</b>, nunca con tu nombre.
        </p>
      </header>

      {mine.isPending && me.isSuccess && <p className="muted">Cargando…</p>}
      {mine.isError && <ErrorNote message={mine.error.message} />}
      {mine.isSuccess && items.length === 0 && (
        <section className="empty">
          <h2>Sin entregas todavía</h2>
          <p>
            Cuando tu profesorado descargue tu entrega, aparecerá aquí. Cada push que hagas se
            analizará y verás su feedback.
          </p>
        </section>
      )}

      {groups.map((group) => (
        <section key={`${group.org}/${group.classroom}`} className="entrega-group">
          <h3>
            {group.classroom} <span className="dim">· {group.org}</span>{' '}
            <span className="badge" title="Tu código en esta clase">
              {group.items[0].owner}
            </span>
          </h3>
          <div className="entregas">
            {group.items.map((item) => (
              <AssignmentCard key={item.repo_label} item={item} />
            ))}
          </div>
        </section>
      ))}
    </section>
  )
}

function AssignmentCard({ item }: { item: MyAssignment }) {
  const notAccepted = item.status === 'error'
  const hasTests = item.total !== null && item.max_score !== null
  const ratio = hasTests && item.max_score ? (item.score ?? 0) / item.max_score : 0
  const allGreen = hasTests && item.passed === item.total

  return (
    <article className="entrega">
      <header className="entrega-head">
        <h4>{item.assignment}</h4>
        {hasTests ? (
          <span className={allGreen ? 'badge' : 'badge badge-alert'}>
            tests {item.passed}/{item.total}
          </span>
        ) : null}
      </header>

      {notAccepted ? (
        <p className="muted">
          Todavía no hay repo para esta entrega: acepta el assignment en Classroom 50 y haz tu
          primer push.
        </p>
      ) : (
        <>
          {hasTests ? (
            <div className="meter" title={`${item.score}/${item.max_score} puntos`}>
              <span className="meter-track" aria-hidden="true">
                <span className="meter-bar" style={{ width: `${Math.max(ratio * 100, 1)}%` }} />
              </span>
              <span className="meter-label">
                <b>{item.score}</b>/{item.max_score} puntos
              </span>
            </div>
          ) : (
            <p className="muted">Sin resultado de tests todavía.</p>
          )}

          {item.latest_hint ? (
            <div className="fb-hint entrega-hint">
              <span className="fb-label">Tu pista ahora</span>
              <p>{item.latest_hint}</p>
            </div>
          ) : null}

          {item.alerts.length > 0 ? (
            <ul className="alert-list">
              {item.alerts.map((alert) => (
                <li key={alert.kind}>
                  <span className="badge badge-alert">aviso</span> {alert.text}
                </li>
              ))}
            </ul>
          ) : null}
        </>
      )}

      <footer className="entrega-foot">
        <span className="dim">
          {item.analyses} revisión(es)
          {item.last_commit_at ? ` · último commit ${fmtDateTime(item.last_commit_at)}` : ''}
        </span>
        {!notAccepted ? (
          <Link
            className="link-action"
            to="/mis-clases/$org/$classroom/$assignment/$owner"
            params={{
              org: item.org,
              classroom: item.classroom,
              assignment: item.assignment,
              owner: item.owner,
            }}
          >
            Ver mi progreso →
          </Link>
        ) : null}
      </footer>
    </article>
  )
}

type Group = { org: string; classroom: string; items: MyAssignment[] }

function groupByClassroom(items: MyAssignment[]): Group[] {
  const groups = new Map<string, Group>()
  for (const item of items) {
    const key = `${item.org}/${item.classroom}`
    const group = groups.get(key)
    if (group) group.items.push(item)
    else groups.set(key, { org: item.org, classroom: item.classroom, items: [item] })
  }
  return [...groups.values()]
}
