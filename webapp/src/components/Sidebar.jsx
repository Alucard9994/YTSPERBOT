import { NavLink } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { enabledModules } from '../config/modules.js';
import { fetchSystemStatus } from '../api/client.js';

export default function Sidebar() {
  const modules = enabledModules();
  const monitoring = modules.filter((m) => m.section !== 'sistema');
  const sistema    = modules.filter((m) => m.section === 'sistema');

  const { data } = useQuery({
    queryKey: ['system-status'],
    queryFn: fetchSystemStatus,
    staleTime: 5 * 60_000,
    retry: false,
  });

  return (
    <aside className="sidebar">
      <div className="sidebar-brand">
        YTSPERBOT
        <div style={{ fontSize: 11, color: 'var(--text-dim)', fontWeight: 400, marginTop: 2 }}>
          Trend Monitor · v2.0
        </div>
      </div>

      <nav className="sidebar-nav">
        <div className="nav-section">Monitoring</div>
        {monitoring.map((mod) => (
          <NavLink
            key={mod.id}
            to={mod.path}
            end={mod.path === '/'}
            className={({ isActive }) => `sidebar-item${isActive ? ' active' : ''}`}
            title={mod.description}
          >
            <span className="sidebar-icon">{mod.icon}</span>
            <span className="sidebar-label">{mod.label}</span>
          </NavLink>
        ))}

        {sistema.length > 0 && (
          <>
            <div className="nav-section" style={{ marginTop: 8 }}>Sistema</div>
            {sistema.map((mod) => (
              <NavLink
                key={mod.id}
                to={mod.path}
                className={({ isActive }) => `sidebar-item${isActive ? ' active' : ''}`}
                title={mod.description}
              >
                <span className="sidebar-icon">{mod.icon}</span>
                <span className="sidebar-label">{mod.label}</span>
              </NavLink>
            ))}
          </>
        )}
      </nav>

      {/* Bot status panel */}
      <div className="sidebar-status">
        <div className="sidebar-status-label">Bot status</div>
        <div className="sidebar-status-row">
          <span className="status-dot ok" />
          <span className="sidebar-status-text">Online</span>
          {data?.db_size_mb != null && (
            <span className="sidebar-status-db">DB {data.db_size_mb} MB</span>
          )}
        </div>
      </div>
    </aside>
  );
}
