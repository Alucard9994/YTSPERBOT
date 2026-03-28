import { NavLink } from 'react-router-dom';
import { enabledModules } from '../config/modules.js';

export default function Sidebar() {
  const modules = enabledModules();

  return (
    <aside className="sidebar">
      <div className="sidebar-brand">YTSPERBOT</div>
      <nav className="sidebar-nav">
        {modules.map((mod) => (
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
      </nav>
    </aside>
  );
}
