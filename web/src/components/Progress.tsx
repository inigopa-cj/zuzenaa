import type { ClassEvolution, StudentProgress } from '../api'
import { fmtDateTime, shortSha } from './Feedback'

function pct(ratio: number): string {
  return `${Math.round(ratio * 100)} %`
}

function fmtDay(value: number): string {
  return new Date(value * 1000).toLocaleDateString()
}

/** Muestra como mucho ~6 etiquetas de eje (siempre la primera y la última). */
function showCaption(index: number, count: number): boolean {
  const step = Math.ceil(count / 6)
  return index === count - 1 || (index % step === 0 && count - 1 - index >= step / 2)
}

/** Columnas verticales de una sola serie (0–100 %), con tooltip por columna. */
function ColumnStrip({
  label,
  items,
}: {
  label: string
  items: { key: string; ratio: number; tip: string; caption: string }[]
}) {
  return (
    <figure className="strip" aria-label={label}>
      <div className="strip-plot">
        {items.map((item) => (
          <div key={item.key} className="strip-col" title={item.tip}>
            <span className="strip-bar" style={{ height: `${Math.max(item.ratio * 100, 2)}%` }} />
          </div>
        ))}
      </div>
      <div className="strip-axis" aria-hidden="true">
        {items.map((item, index) => (
          <span key={item.key}>{showCaption(index, items.length) ? item.caption : ''}</span>
        ))}
      </div>
    </figure>
  )
}

/** Progreso del alumno: resumen, curva de tests, estado por test y ritmo de trabajo. */
export function StudentProgressPanel({ progress }: { progress: StudentProgress }) {
  const { current, rhythm } = progress
  return (
    <section className="progress-panel" aria-label="Resumen de la evolución">
      <p className="progress-summary">{progress.summary}</p>

      {progress.alerts.length > 0 ? (
        <ul className="alert-list">
          {progress.alerts.map((alert) => (
            <li key={alert.kind}>
              <span className="badge badge-alert">aviso</span> {alert.text}
            </li>
          ))}
        </ul>
      ) : null}

      <div className="progress-grid">
        {progress.timeline.length > 0 ? (
          <div>
            <h3 className="progress-title">
              Puntos de tests por revisión
              {current ? (
                <span className="dim">
                  {' '}
                  · ahora {current.score}/{current.max_score}
                </span>
              ) : null}
            </h3>
            <ColumnStrip
              label="Puntos de tests por revisión"
              items={progress.timeline.map((pt) => ({
                key: pt.commit,
                ratio: pt.max_score ? pt.score / pt.max_score : 0,
                caption: shortSha(pt.commit),
                tip: `${shortSha(pt.commit)} · ${fmtDateTime(pt.at)} · ${pt.passed}/${pt.total} tests · ${pt.score}/${pt.max_score} pt`,
              }))}
            />
          </div>
        ) : null}

        {progress.tests.length > 0 ? (
          <div>
            <h3 className="progress-title">Tests de Classroom 50</h3>
            <ul className="test-list">
              {progress.tests.map((test) => (
                <li key={test.name}>
                  <span className={`dot ${test.passing ? 'success' : 'failure'}`} aria-hidden="true" />{' '}
                  <code>{test.name}</code>{' '}
                  <span className="dim">
                    {test.passing ? 'pasa' : 'falla'}
                    {test.first_passed_commit ? ` · pasó por primera vez en ${shortSha(test.first_passed_commit)}` : ''}
                    {test.regressions ? ` · se rompió ${test.regressions} vez/veces` : ''}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        ) : null}

        {rhythm ? (
          <div>
            <h3 className="progress-title">Ritmo de trabajo</h3>
            <dl className="facts">
              <dt>Commits</dt>
              <dd>
                {rhythm.commits} ({rhythm.analysed_commits} analizados)
              </dd>
              <dt>Días con actividad</dt>
              <dd>{rhythm.active_days}</dd>
              <dt>Periodo</dt>
              <dd>
                {fmtDay(rhythm.first_at)} – {fmtDay(rhythm.last_at)}
              </dd>
              <dt>Último commit</dt>
              <dd>hace {rhythm.days_since_last} día(s)</dd>
              <dt>Tamaño medio</dt>
              <dd>
                {rhythm.avg_lines} líneas · mayor {rhythm.largest_lines} ({shortSha(rhythm.largest_commit)})
              </dd>
            </dl>
          </div>
        ) : null}
      </div>
    </section>
  )
}

const ALERT_LABELS: Record<string, string> = {
  sin_analisis: 'sin análisis',
  regresion: 'regresión',
  pista_repetida: 'pista repetida',
  sin_avance: 'sin avance',
}

/** Evolución de la clase: agrega el progreso de cada alumno (solo profesorado). */
export function ClassEvolutionPanel({
  evolution,
  onStudent,
}: {
  evolution: ClassEvolution
  onStudent: (owner: string) => void
}) {
  return (
    <section className="progress-panel" aria-label="Evolución de la clase">
      <p className="progress-summary">{evolution.summary}</p>

      <div className="pulse">
        <span>
          <b>{evolution.students}</b> entregas
        </span>
        <span>
          <b>{evolution.analysed}</b> con análisis
        </span>
        <span>
          <b>{evolution.with_tests}</b> con resultado de tests
        </span>
        <span>
          <b>{evolution.all_passing}</b> con todos los tests
        </span>
        {evolution.avg_ratio !== null ? (
          <span>
            Media <b>{pct(evolution.avg_ratio)}</b> de los puntos
          </span>
        ) : null}
      </div>

      <div className="progress-grid">
        {evolution.timeline.length > 0 ? (
          <div>
            <h3 className="progress-title">Media de puntos de la clase por día</h3>
            <ColumnStrip
              label="Media de puntos de la clase por día"
              items={evolution.timeline.map((point) => ({
                key: point.day,
                ratio: point.avg_ratio,
                caption: point.day.slice(5),
                tip: `${point.day} · media ${pct(point.avg_ratio)} · ${point.students} alumno(s) con resultado`,
              }))}
            />
          </div>
        ) : null}

        {evolution.tests.length > 0 ? (
          <div>
            <h3 className="progress-title">Qué tests cuestan más</h3>
            <ul className="rate-list">
              {evolution.tests.map((test) => {
                const ratio = test.students ? test.passing / test.students : 0
                return (
                  <li key={test.name} title={`${test.passing} de ${test.students} alumnos lo pasan`}>
                    <code>{test.name}</code>
                    <span className="rate-track" aria-hidden="true">
                      <span className="rate-bar" style={{ width: `${Math.max(ratio * 100, 1)}%` }} />
                    </span>
                    <span className="dim">
                      {pct(ratio)} · {test.passing}/{test.students}
                    </span>
                  </li>
                )
              })}
            </ul>
          </div>
        ) : null}

        {evolution.common_hints.length > 0 ? (
          <div>
            <h3 className="progress-title">Pistas que se repiten en la clase</h3>
            <ul className="hint-list">
              {evolution.common_hints.map((hint) => (
                <li key={hint.text}>
                  <b>{hint.students}</b> alumnos · {hint.text}
                </li>
              ))}
            </ul>
          </div>
        ) : null}
      </div>

      <h3 className="progress-title">Por alumno</h3>
      <table className="table">
        <thead>
          <tr>
            <th>Alumno</th>
            <th>Análisis</th>
            <th>Tests</th>
            <th>Puntos</th>
            <th>Último commit</th>
            <th>Avisos</th>
          </tr>
        </thead>
        <tbody>
          {evolution.rows.map((row) => (
            <tr key={row.owner}>
              <td>
                <button type="button" className="link-button" onClick={() => onStudent(row.owner)}>
                  {row.owner}
                </button>
              </td>
              <td>{row.analyses}</td>
              <td>{row.total !== null ? `${row.passed}/${row.total}` : '—'}</td>
              <td>{row.max_score !== null ? `${row.score}/${row.max_score}` : '—'}</td>
              <td>{row.last_commit_at ? fmtDay(row.last_commit_at) : '—'}</td>
              <td>
                {row.alerts.length > 0
                  ? row.alerts.map((kind) => (
                      <span key={kind} className="badge badge-alert">
                        {ALERT_LABELS[kind] ?? kind}
                      </span>
                    ))
                  : '—'}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  )
}
