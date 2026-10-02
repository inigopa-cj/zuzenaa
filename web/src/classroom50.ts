/** Deep links into the Classroom 50 web app (configurable, self-host friendly). */

import { useQuery } from '@tanstack/react-query'
import { api } from './api'

export const CLASSROOM50_FALLBACK = 'https://classroom50.org'

export function useClassroom50(): string {
  const status = useQuery({
    queryKey: ['authStatus'],
    queryFn: api.authStatus,
    retry: false,
    staleTime: 5 * 60_000,
  })
  return (status.data?.classroom50_url ?? CLASSROOM50_FALLBACK).replace(/\/$/, '')
}

function segment(value: string): string {
  return encodeURIComponent(value)
}

export function classroom50Org(base: string, org: string): string {
  return `${base}/${segment(org)}`
}

export function classroom50Classroom(base: string, org: string, classroom: string): string {
  return `${base}/${segment(org)}/${segment(classroom)}`
}

export function classroom50Assignments(base: string, org: string, classroom: string): string {
  return `${classroom50Classroom(base, org, classroom)}/assignments`
}

export function classroom50Assignment(
  base: string,
  org: string,
  classroom: string,
  assignment: string,
): string {
  return `${classroom50Assignments(base, org, classroom)}/${segment(assignment)}`
}
