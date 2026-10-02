import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import {
  createRootRoute,
  createRoute,
  createRouter,
  Link,
  Outlet,
  RouterProvider,
  useParams,
} from '@tanstack/react-router'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import { AppLayout, OrgProvider } from './components/AppLayout'
import { AssignmentPage } from './pages/AssignmentPage'
import { ClassroomPage } from './pages/ClassroomPage'
import { ClassroomsPage } from './pages/ClassroomsPage'
import { MyClassesPage } from './pages/MyClassesPage'
import { SettingsPage } from './pages/SettingsPage'
import { StudentPage } from './pages/StudentPage'

const rootRoute = createRootRoute({
  component: () => (
    <OrgProvider>
      <AppLayout>
        <Outlet />
      </AppLayout>
    </OrgProvider>
  ),
})

const indexRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/',
  component: ClassroomsPage,
})

const classroomRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/classrooms/$classroom',
  component: () => {
    const { classroom } = useParams({ from: classroomRoute.id })
    return <ClassroomPage classroom={classroom} />
  },
})

const assignmentRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/classrooms/$classroom/assignments/$assignment',
  component: () => {
    const { classroom, assignment } = useParams({ from: assignmentRoute.id })
    return <AssignmentPage classroom={classroom} assignment={assignment} />
  },
})

const studentRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/classrooms/$classroom/assignments/$assignment/students/$owner',
  component: () => {
    const { classroom, assignment, owner } = useParams({ from: studentRoute.id })
    return <StudentPage classroom={classroom} assignment={assignment} owner={owner} />
  },
})

const myClassesRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/mis-clases',
  component: MyClassesPage,
})

const studentFeedbackRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/mis-clases/$org/$classroom/$assignment/$owner',
  component: () => {
    const { org, classroom, assignment, owner } = useParams({
      from: studentFeedbackRoute.id,
    })
    return (
      <StudentPage org={org} classroom={classroom} assignment={assignment} owner={owner} />
    )
  },
})

const settingsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/settings',
  component: SettingsPage,
})

const notFoundRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '$',
  component: () => (
    <section>
      <h2>No encontrado</h2>
      <p>
        Esta página no existe. <Link to="/">Volver a las clases</Link>.
      </p>
    </section>
  ),
})

const routeTree = rootRoute.addChildren([
  indexRoute,
  classroomRoute,
  assignmentRoute,
  studentRoute,
  myClassesRoute,
  studentFeedbackRoute,
  settingsRoute,
  notFoundRoute,
])

const router = createRouter({ routeTree })
const queryClient = new QueryClient({
  defaultOptions: { queries: { staleTime: 30_000, retry: 1 } },
})

declare module '@tanstack/react-router' {
  interface Register {
    router: typeof router
  }
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  </StrictMode>,
)
