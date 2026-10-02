import { useQuery } from '@tanstack/react-query'
import { Link } from '@tanstack/react-router'
import { api } from '../api'
import { classroom50Classroom, useClassroom50 } from '../classroom50'
import { useOrg } from '../components/AppLayout'
import { ExternalLink } from '../components/ExternalLink'

export function ClassroomsPage() {
  const org = useOrg()
  const base = useClassroom50()
  const classrooms = useQuery({
    queryKey: ['classrooms', org],
    queryFn: () => api.classrooms(org),
    enabled: org.length > 0,
  })

  if (!org) {
    return (
      <section className="empty">
        <h2>Elige una organización</h2>
        <p>Selecciona una organización en el panel lateral para ver sus clases.</p>
      </section>
    )
  }

  return (
    <section>
      <header className="page-head">
        <h2>Clases</h2>
        <p className="muted">
          {classrooms.isSuccess ? (
            <>
              {classrooms.data.length} {classrooms.data.length === 1 ? 'clase' : 'clases'} en{' '}
              <code>{org}</code>
            </>
          ) : (
            <code>{org}</code>
          )}{' '}
          · descarga sus repos y evalúalos con el agente.
        </p>
      </header>

      {classrooms.isPending && <p className="muted">Cargando clases…</p>}
      {classrooms.isError && <ErrorNote message={classrooms.error.message} />}
      {classrooms.isSuccess && classrooms.data.length === 0 && (
        <section className="empty">
          <h2>Sin clases</h2>
          <p>
            La organización <code>{org}</code> no tiene clases en <code>classroom50</code>. Las
            clases se crean en Classroom 50.
          </p>
        </section>
      )}
      {classrooms.isSuccess && classrooms.data.length > 0 && (
        <ul className="cards">
          {classrooms.data.map((classroom) => (
            <li key={classroom.short_name} className={classroom.active ? 'card' : 'card inactive'}>
              <Link
                className="card-main"
                to="/classrooms/$classroom"
                params={{ classroom: classroom.short_name }}
              >
                <span className="card-title">{classroom.name}</span>
                <span className="card-meta">
                  <code>{classroom.short_name}</code>
                  {classroom.term ? <span>{classroom.term}</span> : null}
                </span>
              </Link>
              <ExternalLink
                className="card-ext"
                href={classroom50Classroom(base, org, classroom.short_name)}
                title="Abrir la clase en Classroom 50"
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

export function ErrorNote({ message }: { message: string }) {
  const needsInit = /not found|init/i.test(message)
  return (
    <p className="note error" role="alert">
      {needsInit
        ? 'Esta organización aún no está preparada en Classroom 50 (`gh teacher init`).'
        : `No se pudo completar (${message}).`}
    </p>
  )
}
