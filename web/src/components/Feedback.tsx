import type { Analysis, TestResults } from '../api'

export function fmtDateTime(value: number | null): string {
  if (!value) return '—'
  return new Date(value * 1000).toLocaleString()
}

export function shortSha(sha: string): string {
  return sha.slice(0, 7)
}

/** «2/2 · 15/15 pt» con el color del estado (todo verde o algo falla). */
export function TestsBadge({ tests }: { tests: TestResults }) {
  const green = tests.passed === tests.total
  return (
    <span className={green ? 'badge' : 'badge badge-alert'} title="Tests de Classroom 50">
      tests {tests.passed}/{tests.total} · {tests.score}/{tests.max_score} pt
    </span>
  )
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
      {analysis.tests ? (
        <div className="fb-row">
          <span className="fb-label">Tests</span>
          <ul className="test-list">
            {analysis.tests.tests.map((test) => (
              <li key={test.name}>
                <span className={`dot ${test.passed ? 'success' : 'failure'}`} aria-hidden="true" />{' '}
                <code>{test.name}</code>{' '}
                <span className="dim">
                  {test.passed ? 'pasa' : 'falla'} · {test.points}/{test.max_points} pt
                </span>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
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
