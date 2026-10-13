import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { api, type Analysis, type TutorReply } from '../api'
import { ErrorNote } from '../pages/ClassroomsPage'
import { TestsBadge, fmtDateTime, shortSha } from './Feedback'

type Message = { role: 'user'; text: string } | { role: 'tutor'; reply: TutorReply }

const SOURCE_LABEL: Record<string, string> = {
  correccion: 'Esta corrección',
  material: 'Material de clase',
  feedback: 'Tu feedback',
  zuzenaa: 'Guía de ZuzenAA',
}

/**
 * Tutor en panel lateral (1/3 de la pantalla), siempre ligado a una corrección: el
 * tutor recibe esa corrección (feedback, pista y tests) como primera fuente, y el
 * alumno puede enviar su duda y la conversación a su profesorado.
 */
export function TutorPanel({
  org,
  classroom,
  assignment,
  owner,
  analysis,
  previewAs,
  canSend,
  onClose,
}: {
  org: string
  classroom: string
  assignment: string
  owner: string
  analysis: Analysis
  previewAs: string | null
  canSend: boolean
  onClose: () => void
}) {
  const queryClient = useQueryClient()
  const [question, setQuestion] = useState('')
  const [messages, setMessages] = useState<Message[]>([])
  const [sending, setSending] = useState(false)
  const [note, setNote] = useState('')
  const [withChat, setWithChat] = useState(true)

  const ask = useMutation({
    mutationFn: (text: string) =>
      api.tutorChat(org, classroom, {
        question: text,
        analysis_id: analysis.id,
        as: previewAs,
      }),
    onSuccess: (reply) => setMessages((prev) => [...prev, { role: 'tutor', reply }]),
  })

  const send = useMutation({
    mutationFn: () =>
      api.tutorSend(org, classroom, assignment, owner, {
        analysis_id: analysis.id,
        note: note.trim() || null,
        transcript: withChat
          ? messages.map((m) =>
              m.role === 'user'
                ? { role: 'user' as const, text: m.text }
                : { role: 'tutor' as const, text: m.reply.answer },
            )
          : [],
      }),
    onSuccess: () => {
      setSending(false)
      setNote('')
      void queryClient.invalidateQueries({ queryKey: ['tutorShares', org, classroom, assignment, owner] })
    },
  })

  function submit(event: FormEvent) {
    event.preventDefault()
    const text = question.trim()
    if (!text || ask.isPending) return
    setMessages((prev) => [...prev, { role: 'user', text }])
    setQuestion('')
    ask.mutate(text)
  }

  return (
    <aside className="tutor-panel" aria-label="Tutor">
      <header className="tutor-panel-head">
        <div>
          <h3>Tutor</h3>
          <p className="dim">
            Sobre la corrección <code>{shortSha(analysis.commit_sha)}</code> ·{' '}
            {fmtDateTime(analysis.created_at)} {analysis.tests ? <TestsBadge tests={analysis.tests} /> : null}
          </p>
        </div>
        <button type="button" className="ghost" aria-label="Cerrar el tutor" onClick={onClose}>
          ✕
        </button>
      </header>

      {analysis.feedback ? (
        <div className="fb-hint tutor-panel-hint">
          <span className="fb-label">Pista de esta corrección</span>
          <p>{analysis.feedback.pista.text}</p>
        </div>
      ) : null}

      <ol className="chat tutor-panel-chat" aria-live="polite">
        {messages.length === 0 ? (
          <li className="chat-hint muted">
            Pregunta lo que no entiendas de esta corrección: el tutor la usa como punto de partida y
            te cita el material de tu clase. Orienta, no resuelve.
          </li>
        ) : null}
        {messages.map((message, index) =>
          message.role === 'user' ? (
            <li key={index} className="chat-msg chat-user">
              <p>{message.text}</p>
            </li>
          ) : (
            <li key={index} className={`chat-msg chat-tutor${message.reply.blocked ? ' blocked' : ''}`}>
              <p className="chat-answer">{message.reply.answer}</p>
              {message.reply.guide_questions.length > 0 ? (
                <div className="tutor-block">
                  <span className="fb-label">Para pensar</span>
                  <ul>
                    {message.reply.guide_questions.map((q) => (
                      <li key={q}>{q}</li>
                    ))}
                  </ul>
                </div>
              ) : null}
              {message.reply.steps.length > 0 ? (
                <div className="tutor-block">
                  <span className="fb-label">Cómo abordarlo</span>
                  <ol>
                    {message.reply.steps.map((step) => (
                      <li key={step}>{step}</li>
                    ))}
                  </ol>
                </div>
              ) : null}
              {message.reply.notes.length > 0 ? (
                <div className="tutor-block tutor-notes">
                  <span className="fb-label">Apuntes que deberías revisar</span>
                  {message.reply.notes.map((note) => (
                    <details key={note.ref}>
                      <summary>
                        <b>
                          {note.title}
                          {note.heading ? ` / ${note.heading}` : ''}
                        </b>{' '}
                        <span className="dim">· {SOURCE_LABEL[note.source] ?? note.source}</span>
                        <br />
                        <span>{note.reason}</span>
                      </summary>
                      <p className="note-text">{note.text}</p>
                    </details>
                  ))}
                </div>
              ) : null}
              {message.reply.notice ? <p className="dim tutor-notice">{message.reply.notice}</p> : null}
              {message.reply.citations.length > 0 ? (
                <ul className="citations">
                  {message.reply.citations.map((cite) => (
                    <li key={cite.ref} title={cite.snippet}>
                      <span className="badge">[{cite.number}]</span>{' '}
                      <span className="dim">{SOURCE_LABEL[cite.source] ?? cite.source}</span>
                      {cite.source === 'correccion' ? null : <> · {cite.title}</>}
                      {cite.heading ? <span className="dim"> / {cite.heading}</span> : null}
                    </li>
                  ))}
                </ul>
              ) : null}
            </li>
          ),
        )}
        {ask.isPending ? <li className="chat-msg chat-tutor muted">Buscando…</li> : null}
      </ol>
      {ask.isError ? <ErrorNote message={ask.error.message} /> : null}

      <form className="chat-form" onSubmit={submit}>
        <textarea
          value={question}
          maxLength={1000}
          rows={2}
          placeholder="Escribe tu duda…"
          aria-label="Tu duda"
          onChange={(event) => setQuestion(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === 'Enter' && !event.shiftKey) submit(event)
          }}
        />
        <button type="submit" disabled={!question.trim() || ask.isPending}>
          Preguntar
        </button>
      </form>

      <footer className="tutor-panel-send">
        {send.isSuccess && !sending ? (
          <p className="note ok">Enviado a tu profesorado. Lo verás en «Dudas enviadas».</p>
        ) : null}
        {!sending ? (
          <button
            type="button"
            className="ghost"
            disabled={!canSend}
            title={canSend ? undefined : 'Solo el propio alumno puede enviar sus dudas.'}
            onClick={() => setSending(true)}
          >
            Enviar a mi profesorado
          </button>
        ) : (
          <form
            className="send-form"
            onSubmit={(event) => {
              event.preventDefault()
              send.mutate()
            }}
          >
            <textarea
              value={note}
              maxLength={2000}
              rows={3}
              placeholder="Explica a tu profesorado qué no entiendes (opcional si envías la conversación)"
              aria-label="Nota para el profesorado"
              onChange={(event) => setNote(event.target.value)}
            />
            <label className="dim">
              <input
                type="checkbox"
                checked={withChat}
                disabled={messages.length === 0}
                onChange={(event) => setWithChat(event.target.checked)}
              />{' '}
              Incluir la conversación con el tutor ({messages.length} mensajes)
            </label>
            <p className="dim">Se envía con tu código de alumno, nunca con tu nombre.</p>
            <div className="actions">
              <button type="submit" disabled={send.isPending}>
                {send.isPending ? 'Enviando…' : 'Enviar'}
              </button>
              <button type="button" className="ghost" onClick={() => setSending(false)}>
                Cancelar
              </button>
            </div>
            {send.isError ? <ErrorNote message={send.error.message} /> : null}
          </form>
        )}
      </footer>
    </aside>
  )
}
