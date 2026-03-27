// frontend/src/components/layout/Sidebar.tsx
import { NavLink } from "react-router-dom";

const NAV_ITEMS = [
  { to: "/pulse", label: "Outlook" },
  { to: "/launch", label: "Launch" },
  { to: "/narrative", label: "Narrative" },
  { to: "/whales", label: "Whales" },
  { to: "/chains", label: "Chains" },
  { to: "/trending", label: "Trending" },
];

export default function Sidebar() {
  return (
    <nav className="w-48 h-screen bg-terminal-card border-r border-terminal-border flex flex-col p-4 shrink-0">
      <div className="text-terminal-accent font-bold text-lg mb-8 tracking-wider">
        CANDLE
      </div>
      <ul className="space-y-1 flex-1">
        {NAV_ITEMS.map((item) => (
          <li key={item.to}>
            <NavLink
              to={item.to}
              className={({ isActive }) =>
                `block px-3 py-2 text-sm transition-colors ${
                  isActive
                    ? "text-terminal-accent bg-terminal-accent/10 border-l-2 border-terminal-accent"
                    : "text-terminal-muted hover:text-terminal-text"
                }`
              }
            >
              {item.label}
            </NavLink>
          </li>
        ))}
      </ul>
      <div className="border-t border-terminal-border pt-4">
        <NavLink
          to="/settings"
          className="block px-3 py-2 text-sm text-terminal-muted hover:text-terminal-text"
        >
          Settings
        </NavLink>
      </div>
    </nav>
  );
}
