import { useQuery } from '@tanstack/react-query'
import { api } from '../api'
import { useOrg } from '../components/AppLayout'
import { ErrorNote } from './ClassroomsPage'

export function SettingsPage() {
  const org = useOrg()
  const me = useQuery({ queryKey: ['me'], queryFn: api.me, retry: false })
  const auth = useQuery({ queryKey: ['authStatus'], queryFn: api.authStatus, retry: false })

  return (
    <section>
      <header className="page-head">
        <h2>Ajustes</h2>
        <p className="muted">Sesión, autenticación y organización activa.</p>
      </header>

      <h3>Sesión</h3>
      <table className="table">
        <tbody>
          <tr>
            <th>Usuario</th>
            <td>{me.isSuccess ? me.data.login : me.isError ? 'sin sesión' : '…'}</td>
          </tr>
        </tbody>
      </table>
      {me.isError ? (
        <p className="muted">
          No hay sesión. <a href="/api/auth/login">Iniciar sesión con GitHub</a>.
        </p>
      ) : (
        <form
          className="inline-form"
          onSubmit={(event) => {
            event.preventDefault()
            void fetch('/api/auth/logout', { method: 'POST' }).then(() => window.location.reload())
          }}
        >
          <div className="form-actions">
            <button type="submit">Cerrar sesión</button>
          </div>
        </form>
      )}

      <h3>Autenticación (OAuth)</h3>
      {auth.isPending && <p className="muted">Cargando…</p>}
      {auth.isError && <ErrorNote message={auth.error.message} />}
      {auth.isSuccess && (
        <table className="table">
          <tbody>
            <tr>
              <th>OAuth configurado</th>
              <td>{auth.data.oauth_configured ? 'sí' : 'no'}</td>
            </tr>
            <tr>
              <th>Atajo por token de entorno</th>
              <td>{auth.data.env_token_allowed ? 'activo (desarrollo)' : 'no'}</td>
            </tr>
            <tr>
              <th>Callback</th>
              <td>
                <code>{auth.data.callback_url}</code>
              </td>
            </tr>
          </tbody>
        </table>
      )}

      <h3>Organización</h3>
      {org ? (
        <table className="table">
          <tbody>
            <tr>
              <th>Organización</th>
              <td>
                <code>{org}</code>
              </td>
            </tr>
            <tr>
              <th>Repo de configuración</th>
              <td>
                <code>{org}/classroom50</code>
              </td>
            </tr>
          </tbody>
        </table>
      ) : (
        <p className="muted">Ninguna seleccionada.</p>
      )}
    </section>
  )
}
