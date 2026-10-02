import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useNavigate } from '@tanstack/react-router'
import {
  createContext,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from 'react'
import { api } from '../api'
import { classroom50Org, useClassroom50 } from '../classroom50'

const ORG_KEY = 'zuzenaa.org'

type OrgContextValue = { org: string; setOrg: (org: string) => void }
const OrgContext = createContext<OrgContextValue>({ org: '', setOrg: () => undefined })

export function OrgProvider({ children }: { children: ReactNode }) {
  const [org, setOrgState] = useState(() => localStorage.getItem(ORG_KEY) ?? '')
  const setOrg = (value: string) => {
    localStorage.setItem(ORG_KEY, value)
    setOrgState(value)
  }
  return <OrgContext.Provider value={{ org, setOrg }}>{children}</OrgContext.Provider>
}

export function useOrg(): string {
  return useContext(OrgContext).org
}

function OrgPicker() {
  const { org, setOrg } = useContext(OrgContext)
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [manual, setManual] = useState(false)
  const [draft, setDraft] = useState(org)

  const orgs = useQuery({ queryKey: ['orgs'], queryFn: api.orgs, retry: false })

  useEffect(() => {
    setDraft(org)
  }, [org])

  function useOrgNow(value: string) {
    setOrg(value)
    void queryClient.invalidateQueries()
    void navigate({ to: '/' })
  }

  if (!manual && orgs.isSuccess && orgs.data.length > 0) {
    return (
      <div className="org-picker">
        <span className="rail-section-label">Organización</span>
        <select
          id="org-select"
          aria-label="Organización"
          value={org}
          onChange={(event) => useOrgNow(event.target.value)}
        >
          <option value="">Elegir…</option>
          {orgs.data.map((item) => (
            <option key={item.login} value={item.login}>
              {item.login}
            </option>
          ))}
        </select>
        <button type="button" className="ghost" onClick={() => setManual(true)}>
          Escribir otra
        </button>
      </div>
    )
  }

  return (
    <form
      className="org-picker"
      onSubmit={(event) => {
        event.preventDefault()
        useOrgNow(draft.trim())
      }}
    >
      <span className="rail-section-label">Organización</span>
      <input
        id="org"
        aria-label="Organización"
        value={draft}
        placeholder="p. ej. mi-centro"
        onChange={(event) => setDraft(event.target.value)}
      />
      <button type="submit">Usar</button>
      {orgs.isError ? (
        <p className="rail-note">Inicia sesión para leer tus organizaciones.</p>
      ) : null}
    </form>
  )
}

function Session() {
  const queryClient = useQueryClient()
  const { data: me, isError } = useQuery({ queryKey: ['me'], queryFn: api.me, retry: false })
  const status = useQuery({ queryKey: ['authStatus'], queryFn: api.authStatus, retry: false })

  if (isError || !me) {
    if (status.isSuccess && !status.data.oauth_configured && !status.data.env_token_allowed) {
      return (
        <span className="session muted" title="Configura las credenciales de la OAuth App">
          OAuth sin configurar
        </span>
      )
    }
    return <a href="/api/auth/login">Iniciar sesión</a>
  }
  return (
    <span className="session">
      {me.avatar_url ? <img src={me.avatar_url} alt="" width={22} height={22} /> : null}
      <strong>{me.login}</strong>
      <button
        type="button"
        onClick={() =>
          void fetch('/api/auth/logout', { method: 'POST' }).then(() => {
            void queryClient.invalidateQueries()
            window.location.reload()
          })
        }
      >
        Salir
      </button>
    </span>
  )
}

function Classroom50Link() {
  const org = useOrg()
  const base = useClassroom50()
  const href = org ? classroom50Org(base, org) : base
  return (
    <a className="rail-link" href={href} target="_blank" rel="noreferrer">
      <RailIcon name="external" />
      Classroom 50
    </a>
  )
}

export function AppLayout({ children }: { children: ReactNode }) {
  return (
    <div className="shell">
      <aside className="rail">
        <Link to="/" className="brand">
          <span aria-hidden="true" className="brand-mark" />
          ZuzenAA
        </Link>

        <nav className="rail-nav">
          <RailLink to="/" exact label="Clases" icon="classes" />
          <RailLink to="/mis-clases" label="Mis clases" icon="student" />
          <RailLink to="/settings" label="Ajustes" icon="settings" />
          <Classroom50Link />
        </nav>

        <div className="rail-foot">
          <OrgPicker />
        </div>
      </aside>
      <div className="content">
        <header className="topbar">
          <span className="tagline">Evaluación formativa sobre Classroom 50</span>
          <Session />
        </header>
        {children}
      </div>
    </div>
  )
}

type IconName = 'classes' | 'student' | 'settings' | 'external'

function RailIcon({ name }: { name: IconName }) {
  const paths: Record<IconName, string> = {
    classes:
      'M3 5.5A1.5 1.5 0 014.5 4h15A1.5 1.5 0 0121 5.5v13A1.5 1.5 0 0119.5 20h-15A1.5 1.5 0 013 18.5v-13zM3 8h18M8 8v12',
    student:
      'M12 12a4 4 0 100-8 4 4 0 000 8zM4.5 20a7.5 7.5 0 0115 0',
    external: 'M14 4h6v6M20 4l-9 9M19 14v5a1 1 0 01-1 1H5a1 1 0 01-1-1V6a1 1 0 011-1h5',
    settings:
      'M12 15a3 3 0 100-6 3 3 0 000 6zM19.4 15a1.7 1.7 0 00.3 1.9l.1.1a2 2 0 11-2.8 2.8l-.1-.1a1.7 1.7 0 00-2.9 1.2 2 2 0 11-4 0 1.7 1.7 0 00-2.9-1.2l-.1.1a2 2 0 11-2.8-2.8l.1-.1A1.7 1.7 0 004 15a2 2 0 010-4 1.7 1.7 0 001.1-2.8l-.1-.1a2 2 0 112.8-2.8l.1.1A1.7 1.7 0 0010 4.6a2 2 0 014 0 1.7 1.7 0 002.9 1.2l.1-.1a2 2 0 112.8 2.8l-.1.1A1.7 1.7 0 0020 11a2 2 0 010 4z',
  }
  return (
    <svg
      className="rail-icon"
      width="16"
      height="16"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d={paths[name]} />
    </svg>
  )
}

function RailLink({
  to,
  label,
  icon,
  exact,
}: {
  to: string
  label: string
  icon: IconName
  exact?: boolean
}) {
  return (
    <Link
      to={to}
      className="rail-link"
      activeOptions={exact ? { exact: true } : undefined}
      activeProps={{ 'aria-current': 'page' }}
    >
      <RailIcon name={icon} />
      {label}
    </Link>
  )
}
