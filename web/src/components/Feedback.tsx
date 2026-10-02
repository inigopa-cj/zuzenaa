import type { Analysis } from '../api'

export function fmtDateTime(value: number | null): string {
  if (!value) return '—'
  return new Date(value * 1000).toLocaleString()
}

export function shortSha(sha: string): string {
  return sha.slice(0, 7)
}

/** Renders validated feedback sections; falls back to the stored markdown. */
export function FeedbackBody({ analysis }: { analysis: Analysis }) {
  const feedback = analysis.feedback
  if (!feedback) {
    const fallback = analysis.feedback_md.replace(/<!--[\s\S]*?-->/g, '').trim()
    return <pre className="feedback-body">{fallback}</pre>
  }
  return (
    <div className="feedback-sections">
      <div className="fb-row">
        <span className="fb-label">Funcionalidad</span>
        <p>{feedback.funcionalidad}</p>
      </div>
      <div className="fb-row">
        <span className="fb-label">Calidad</span>
        <p>{feedback.calidad}</p>
      </div>
      <div className="fb-row">
        <span className="fb-label">Diseño</span>
        <p>{feedback.diseno}</p>
      </div>
      <div className="fb-row fb-hint">
        <span className="fb-label">Pista · nivel {feedback.pista.level}</span>
        <p>{feedback.pista.text}</p>
      </div>
      {feedback.teoria ? (
        <div className="fb-row">
          <span className="fb-label">Teoría</span>
          <p>{feedback.teoria}</p>
        </div>
      ) : null}
    </div>
  )
}
