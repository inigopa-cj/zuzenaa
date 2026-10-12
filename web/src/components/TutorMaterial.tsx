import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useRef, useState, type FormEvent } from 'react'
import { api } from '../api'
import { ErrorNote } from '../pages/ClassroomsPage'
import { fmtDateTime } from './Feedback'

/** Material del tutor de una clase (solo profesorado): subir .md/.txt, ver y quitar. */
export function TutorMaterial({ org, classroom }: { org: string; classroom: string }) {
  const queryClient = useQueryClient()
  const fileRef = useRef<HTMLInputElement>(null)
  const [title, setTitle] = useState('')
  const key = ['tutorDocuments', org, classroom]

  const docs = useQuery({
    queryKey: key,
    queryFn: () => api.tutorDocuments(org, classroom),
    enabled: org.length > 0,
  })
  const upload = useMutation({
    mutationFn: (file: File) => api.tutorUpload(org, classroom, file, title),
    onSuccess: () => {
      setTitle('')
      if (fileRef.current) fileRef.current.value = ''
      void queryClient.invalidateQueries({ queryKey: key })
    },
  })
  const remove = useMutation({
    mutationFn: (id: number) => api.tutorDelete(org, classroom, id),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: key }),
  })

  function submit(event: FormEvent) {
    event.preventDefault()
    const file = fileRef.current?.files?.[0]
    if (file) upload.mutate(file)
  }

  return (
    <section className="tutor-material">
      <h3>Material del tutor</h3>
      <p className="muted">
        Apuntes y teoría en Markdown o texto (.md, .txt). El tutor los usa para responder al
        alumnado de esta clase, citando cada fragmento. Todo se procesa en este servidor.
      </p>
      <form className="upload-form" onSubmit={submit}>
        <input ref={fileRef} type="file" accept=".md,.markdown,.txt" aria-label="Fichero" />
        <input
          type="text"
          value={title}
          placeholder="Título (opcional)"
          aria-label="Título"
          onChange={(event) => setTitle(event.target.value)}
        />
        <button type="submit" disabled={upload.isPending}>
          {upload.isPending ? 'Indexando…' : 'Subir'}
        </button>
      </form>
      {upload.isError ? <ErrorNote message={upload.error.message} /> : null}
      {docs.isError ? <ErrorNote message={docs.error.message} /> : null}
      {docs.isSuccess && docs.data.length === 0 ? (
        <p className="muted">Todavía no hay material: el tutor solo usará el feedback y la guía.</p>
      ) : null}
      {docs.isSuccess && docs.data.length > 0 ? (
        <table className="table">
          <thead>
            <tr>
              <th>Documento</th>
              <th>Fragmentos</th>
              <th>Subido</th>
              <th aria-label="Acciones" />
            </tr>
          </thead>
          <tbody>
            {docs.data.map((doc) => (
              <tr key={doc.id}>
                <td>
                  {doc.title} {doc.filename ? <span className="dim">· {doc.filename}</span> : null}
                </td>
                <td>{doc.chunk_count}</td>
                <td>{fmtDateTime(doc.created_at)}</td>
                <td>
                  <button
                    type="button"
                    className="link-button"
                    disabled={remove.isPending}
                    onClick={() => {
                      if (window.confirm(`¿Quitar «${doc.title}» del tutor?`)) remove.mutate(doc.id)
                    }}
                  >
                    Quitar
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : null}
    </section>
  )
}
