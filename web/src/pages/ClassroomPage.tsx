import { useQuery } from '@tanstack/react-query'
import { Link } from '@tanstack/react-router'
import { api } from '../api'
import {
  classroom50Assignment,
  classroom50Assignments,
  useClassroom50,
} from '../classroom50'
import { useOrg } from '../components/AppLayout'
import { ExternalLink } from '../components/ExternalLink'
import { ErrorNote } from './ClassroomsPage'

export function ClassroomPage({ classroom }: { classroom: string }) {
  const org = useOrg()
  const base = useClassroom50()
  const assignments = useQuery({
    queryKey: ['assignments', org, classroom],
    queryFn: () => api.assignments(org, classroom),
    enabled: org.length > 0,
  })

  return (
    <section>
      <nav className="crumbs">
        <Link to="/">Clases</Link>
        <span aria-hidden="true">/</span>
        <span>{classroom}</span>
      </nav>

      <header className="page-head">
        <div className="head-row">
          <h2>{classroom}</h2>
          <ExternalLink
            className="ext-button"
            href={classroom50Assignments(base, org, classroom)}
            title="Abrir los assignments de la clase en Classroom 50"
          >
            Ver en Classroom 50
          </ExternalLink>
        </div>
        <p className="muted">Elige un assignment para descargar sus repos y evaluarlos.</p>
      </header>

      {assignments.isPending && <p className="muted">Cargando assignments…</p>}
      {assignments.isError && <ErrorNote message={assignments.error.message} />}
      {assignments.isSuccess && assignments.data.length === 0 && (
        <p className="muted">Esta clase no tiene assignments en Classroom 50.</p>
      )}
      {assignments.isSuccess && assignments.data.length > 0 && (
        <ul className="cards">
          {assignments.data.map((assignment) => (
            <li key={assignment.slug} className="card">
              <Link
                className="card-main"
                to="/classrooms/$classroom/assignments/$assignment"
                params={{ classroom, assignment: assignment.slug }}
              >
                <span className="card-title">{assignment.name}</span>
                <span className="card-meta">
                  <code>{assignment.slug}</code>
                  <span>{assignment.mode}</span>
                  <span>{assignment.tests.length} tests</span>
                </span>
              </Link>
              <ExternalLink
                className="card-ext"
                href={classroom50Assignment(base, org, classroom, assignment.slug)}
                title="Abrir el assignment en Classroom 50"
              >
                Classroom 50
              </ExternalLink>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
