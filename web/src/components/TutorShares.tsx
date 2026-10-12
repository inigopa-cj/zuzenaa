import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../api'
import { ErrorNote } from '../pages/ClassroomsPage'
import { fmtDateTime, shortSha } from './Feedback'

/**
 * Dudas que el alumno ha enviado desde el tutor. El profesorado las ve y las marca como
 * leídas; el alumno ve las suyas y si ya se han leído.
 */
export function TutorShares({
  org,
  classroom,
  assignment,
  owner,
  teacher,
}: {
  org: string
  classroom: string
  assignment: string
  owner: string
  teacher: boolean
}) {
  const queryClient = useQueryClient()
  const key = ['tutorShares', org, classroom, assignment, owner]
  const shares = useQuery({
    queryKey: key,
    queryFn: () => api.tutorShares(org, classroom, assignment, owner),
    enabled: org.length > 0,
  })
  const read = useMutation({
    mutationFn: (id: number) => api.tutorMarkRead(org, classroom, id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: key })
      void queryClient.invalidateQueries({ queryKey: ['repos', org, classroom, assignment] })
    },
  })

  if (shares.isError) return <ErrorNote message={shares.error.message} />
  const items = shares.data ?? []
  if (items.length === 0) return null
  const pending = items.filter((s) => s.read_at === null).length

  return (
    <section className="shares">
      <h3>
        {teacher ? 'Dudas del alumno' : 'Dudas enviadas a tu profesorado'}{' '}
        {pending ? <span className="badge badge-alert">{pending} sin leer</span> : null}
      </h3>
      <ul className="share-list">
        {items.map((share) => (
          <li key={share.id} className={share.read_at ? 'share read' : 'share'}>
            <div className="share-meta">
              <code>{shortSha(share.commit_sha)}</code>
              <span className="dim">{fmtDateTime(share.created_at)}</span>
              {share.read_at ? (
                <span className="badge">leída {fmtDateTime(share.read_at)}</span>
              ) : (
                <span className="badge badge-alert">sin leer</span>
              )}
            </div>
            {share.note ? <p className="share-note">{share.note}</p> : null}
            {share.transcript.length > 0 ? (
              <details>
                <summary>Conversación con el tutor ({share.transcript.length} mensajes)</summary>
                <ol className="share-transcript">
                  {share.transcript.map((message, index) => (
                    <li key={index} className={message.role === 'user' ? 'chat-user' : 'chat-tutor'}>
                      <span className="fb-label">{message.role === 'user' ? 'Alumno' : 'Tutor'}</span>
                      <p className="chat-answer">{message.text}</p>
                    </li>
                  ))}
                </ol>
              </details>
            ) : null}
            {teacher && !share.read_at ? (
              <button
                type="button"
                className="link-button"
                disabled={read.isPending}
                onClick={() => read.mutate(share.id)}
              >
                Marcar como leída
              </button>
            ) : null}
          </li>
        ))}
      </ul>
    </section>
  )
}
