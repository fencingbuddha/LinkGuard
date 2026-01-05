import type { ReactNode } from 'react'
import { Navigate, useLocation } from 'react-router-dom'

import { getToken } from '../api/client'

type ProtectedRouteProps = {
  children: ReactNode
  redirectTo?: string
}

export default function ProtectedRoute({ children, redirectTo = '/login' }: ProtectedRouteProps) {
  const token = getToken()
  const location = useLocation()

  if (!token) {
    return <Navigate to={redirectTo} replace state={{ from: location }} />
  }

  return <>{children}</>
}