import { useNavigate } from 'react-router-dom'

import { clearToken } from '../api/client'

export default function Dashboard() {
  const navigate = useNavigate()

  const handleLogout = () => {
    clearToken()
    navigate('/')
  }

  return (
    <div style={{ padding: '2rem' }}>
      <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h1>LinkGuard Admin Dashboard</h1>
        <button onClick={handleLogout}>Log out</button>
      </header>

      <section style={{ marginTop: '2rem' }}>
        <p>Welcome to the LinkGuard admin dashboard.</p>
        <p>This is a placeholder view. Metrics, charts, and organization settings will appear here later.</p>
      </section>
    </div>
  )
}