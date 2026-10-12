import { useQuery, useQueryClient } from '@tanstack/react-query'
import { createContext, useContext, useState, type ReactNode } from 'react'
import { api, type Role } from '../api'

/**
 * Quién está mirando la web: el rol que detecta el backend (staff/alumno) y, para el
 * profesorado, la **vista previa como alumno**. La vista previa solo cambia lo que se
 * muestra; los permisos los decide siempre el backend.
 */
const PREVIEW_KEY = 'zuzenaa.previewAs'

type ViewerValue = {
  role: Role | null
  /** Login del alumno que el profesorado está previsualizando (o null). */
  previewAs: string | null
  setPreviewAs: (login: string | null) => void
  /** true si hay que mostrar la superficie del alumno. */
  studentView: boolean
  /** Login cuyas entregas se muestran en la superficie del alumno. */
  studentLogin: string | null
}

const ViewerContext = createContext<ViewerValue>({
  role: null,
  previewAs: null,
  setPreviewAs: () => undefined,
  studentView: false,
  studentLogin: null,
})

function readPreview(): string | null {
  try {
    return sessionStorage.getItem(PREVIEW_KEY)
  } catch {
    return null
  }
}

export function ViewerProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient()
  const me = useQuery({ queryKey: ['me'], queryFn: api.me, retry: false })
  const role = useQuery({
    queryKey: ['role'],
    queryFn: api.role,
    retry: false,
    enabled: me.isSuccess,
    staleTime: 5 * 60_000,
  })
  const [previewAs, setPreviewState] = useState<string | null>(readPreview)

  const setPreviewAs = (login: string | null) => {
    try {
      if (login) sessionStorage.setItem(PREVIEW_KEY, login)
      else sessionStorage.removeItem(PREVIEW_KEY)
    } catch {
      /* almacenamiento no disponible: la vista previa dura lo que la pestaña */
    }
    setPreviewState(login)
    void queryClient.invalidateQueries({ queryKey: ['myAssignments'] })
  }

  const info = role.data ?? null
  const isStudent = info?.role === 'student'
  // Solo el profesorado puede previsualizar; un alumno siempre se ve a sí mismo.
  const activePreview = !isStudent && previewAs ? previewAs : null
  const value: ViewerValue = {
    role: info,
    previewAs: activePreview,
    setPreviewAs,
    studentView: isStudent || activePreview !== null,
    studentLogin: activePreview ?? (me.data?.login ?? null),
  }
  return <ViewerContext.Provider value={value}>{children}</ViewerContext.Provider>
}

export function useViewer(): ViewerValue {
  return useContext(ViewerContext)
}
