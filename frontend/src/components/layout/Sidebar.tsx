import { useState } from 'react';
import { NavLink, useLocation } from 'react-router-dom';
import { useAuth } from '../../app/AuthContext';
import { useTheme } from '../../app/ThemeContext';

const navItems = [
  { path: '/app/dashboard', label: 'Dashboard', icon: '◻' },
  { path: '/app/parcels', label: 'Parcels', icon: '▭' },
  { path: '/app/buildings', label: 'Buildings', icon: '⬜' },
  { path: '/app/units', label: 'Units', icon: '▫' },
  { path: '/app/vdc', label: 'VDC', icon: '⊞' },
  { path: '/app/validation', label: 'Validation', icon: '⊡' },
  { path: '/app/ownership', label: 'Ownership', icon: '⊙' },
  { path: '/app/visualization', label: '3D View', icon: '◈' },
];

export function Sidebar() {
  const [collapsed, setCollapsed] = useState(false);
  const location = useLocation();

  return (
    <aside
      style={{
        width: collapsed ? '60px' : '240px',
        background: 'var(--sidebar-bg)',
        color: 'var(--sidebar-fg)',
        display: 'flex',
        flexDirection: 'column',
        transition: 'width 200ms ease',
        overflow: 'hidden',
        flexShrink: 0,
        borderRight: '1px solid var(--border)',
      }}
    >
      {/* Logo */}
      <div
        style={{
          padding: collapsed ? '1rem 0.75rem' : '1rem 1.25rem',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          borderBottom: '1px solid rgba(255,255,255,0.08)',
          minHeight: '56px',
        }}
      >
        {!collapsed && (
          <span style={{ fontWeight: 700, fontSize: '1rem', color: '#fff', letterSpacing: '-0.02em' }}>
            GEOSIX
          </span>
        )}
        <button
          onClick={() => setCollapsed(!collapsed)}
          aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          style={{
            background: 'none',
            border: 'none',
            color: 'var(--sidebar-fg)',
            fontSize: '1rem',
            cursor: 'pointer',
            padding: '0.25rem',
            borderRadius: '4px',
          }}
        >
          {collapsed ? '»' : '«'}
        </button>
      </div>

      {/* Navigation */}
      <nav style={{ flex: 1, padding: '0.5rem 0', overflowY: 'auto' }}>
        {navItems.map((item) => {
          const isActive = location.pathname === item.path;
          return (
            <NavLink
              key={item.path}
              to={item.path}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '0.75rem',
                padding: collapsed ? '0.625rem 0.75rem' : '0.625rem 1.25rem',
                color: isActive ? '#fff' : 'var(--sidebar-fg)',
                background: isActive ? 'var(--sidebar-active)' : 'transparent',
                textDecoration: 'none',
                fontSize: '0.875rem',
                fontWeight: isActive ? 500 : 400,
                borderRadius: '0',
                transition: 'background 150ms ease',
              }}
              onMouseEnter={(e) => {
                if (!isActive) e.currentTarget.style.background = 'var(--sidebar-hover)';
              }}
              onMouseLeave={(e) => {
                if (!isActive) e.currentTarget.style.background = 'transparent';
              }}
            >
              <span style={{ fontSize: '1rem', width: '1.25rem', textAlign: 'center' }}>{item.icon}</span>
              {!collapsed && <span>{item.label}</span>}
            </NavLink>
          );
        })}
      </nav>
    </aside>
  );
}
