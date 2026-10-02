import { useQuery } from '@tanstack/react-query'
import { Link } from '@tanstack/react-router'
import { api, type MyAssignment } from '../api'
import { fmtDateTime } from '../components/Feedback'
import { ErrorNote } from './ClassroomsPage'

export function MyClassesPage() {
  const me = useQuery({ queryKey: ['me'], queryFn: api.me, retry: false })
  const mine = useQuery({
    queryKey: ['myAssignments'],
    queryFn: api.myAssignments,
    retry: false,
    enabled: me.isSuccess,
  })

  if (me.isError) {
    return (
      <section className="empty">
        <h2>Inicia sesión</h2>
        <p>
          Entra con GitHub para ver tus clases, tus entregas y todo tu feedback.{' '}
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
        <h2>Mis clases</h2>
        <p className="muted">
          {me.isSuccess ? (
            <>
              <code>{me.data.login}</code> ·{' '}
            </>
          ) : null}
          tus entregas y el feedback de cada revisión.
        </p>
      </header>

      {mine.isPending && <p className="muted">Cargando…</p>}
      {mine.isError && <ErrorNote message={mine.error.message} />}
      {mine.isSuccess && items.length === 0 && (
        <section className="empty">
          <h2>Sin entregas todavía</h2>
          <p>
            Cuando tu profesorado descargue y analice tu entrega, aparecerá aquí con su feedback.
          </p>
        </section>
      )}

      {groups.map((group) => (
        <div key={`${group.org}/${group.classroom}`}>
          <h3>
            {group.classroom} <span className="dim">· {group.org}</span>
          </h3>
          <table className="table">
            <thead>
              <tr>
                <th>Assignment</th>
                <th>Repo</th>
                <th>Revisiones</th>
                <th>Última</th>
                <th aria-label="Acciones" />
              </tr>
            </thead>
            <tbody>
              {group.items.map((item) => (
                <tr key={item.repo_full_name}>
                  <td>{item.assignment}</td>
                  <td>
                    <code>{item.repo_full_name}</code>
                  </td>
                  <td>{item.analyses}</td>
                  <td>{item.last_analysis_at ? fmtDateTime(item.last_analysis_at) : '—'}</td>
                  <td>
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
                      Ver feedback
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ))}
    </section>
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
