import type { ReactNode } from 'react'
import { Navigate } from 'react-router-dom'

import { getToken } from '../api/client'

type ProtectedRouteProps = {
  children: ReactNode
}

export default function ProtectedRoute({ children }: ProtectedRouteProps) {
  const token = getToken()

  if (!token) {
    return <Navigate to="/" replace />
  }

  return <>{children}</>
}