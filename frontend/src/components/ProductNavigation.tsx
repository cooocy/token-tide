import { NavLink } from 'react-router-dom';

const ENTRIES = [
  { to: '/', label: '余额看板', end: true },
  { to: '/usage', label: 'Token 用量', end: false },
] as const;

export default function ProductNavigation() {
  return (
    <nav className="product-navigation" aria-label="主要功能">
      {ENTRIES.map((entry) => (
        <NavLink
          className={({ isActive }) => isActive ? 'is-active' : undefined}
          end={entry.end}
          to={entry.to}
          key={entry.to}
        >
          {entry.label}
        </NavLink>
      ))}
    </nav>
  );
}
