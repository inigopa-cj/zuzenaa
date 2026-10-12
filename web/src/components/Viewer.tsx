import { useQuery, useQueryClient } from '@tanstack/react-query'
import { createContext, useContext, useState, type ReactNode } from 'react'
import { api, type Role } from '../api'

/**
 * Quién está mirando la web: el rol que detecta el backend (staff/alumno) y, para el
 * profesorado, la **vista previa como alumno**. El alumno se identifica siempre por su
 * seudónimo de clase (p. ej. 3.URGAA), nunca por su login ni su nombre. La vista previa
 * solo cambia lo que se muestra; los permisos los decide siempre el backend.
 */
const PREVIEW_KEY = 'zuzenaa.preview'

export type Preview = { alias: string; org: string; classroom: string }

type ViewerValue = {
  role: Role | null
  /** Alumno que el profesorado está previsualizando (o null). */
  preview: Preview | null
  setPreview: (preview: Preview | null) => void
  /** true si hay que mostrar la superficie del alumno. */
  studentView: boolean
}

const ViewerContext = createContext<ViewerValue>({
  role: null,
  preview: null,
  setPreview: () => undefined,
  studentView: false,
})

function readPreview(): Preview | null {
  try {
    const raw = sessionStorage.getItem(PREVIEW_KEY)
    return raw ? (JSON.parse(raw) as Preview) : null
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
  const [preview, setPreviewState] = useState<Preview | null>(readPreview)

  const setPreview = (value: Preview | null) => {
    try {
      if (value) sessionStorage.setItem(PREVIEW_KEY, JSON.stringify(value))
      else sessionStorage.removeItem(PREVIEW_KEY)
    } catch {
      /* almacenamiento no disponible: la vista previa dura lo que la pestaña */
    }
    setPreviewState(value)
    void queryClient.invalidateQueries({ queryKey: ['myAssignments'] })
  }

  const info = role.data ?? null
  const isStudent = info?.role === 'student'
  // Solo el profesorado puede previsualizar; un alumno siempre se ve a sí mismo.
  const activePreview = !isStudent ? preview : null
  const value: ViewerValue = {
    role: info,
    preview: activePreview,
    setPreview,
    studentView: isStudent || activePreview !== null,
  }
  return <ViewerContext.Provider value={value}>{children}</ViewerContext.Provider>
}

export function useViewer(): ViewerValue {
  return useContext(ViewerContext)
}
