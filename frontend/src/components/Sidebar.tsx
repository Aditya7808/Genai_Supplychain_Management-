import React from 'react';
import {
  LayoutDashboard,
  BotMessageSquare,
  TrendingUp,
  ArrowLeftRight,
  SlidersHorizontal,
  CheckCircle2,
  Sparkles,
} from 'lucide-react';

interface SidebarProps {
  activeTab: string;
  onSelectTab: (tab: string) => void;
  pendingApprovalsCount?: number;
  alertCount?: number;
}

export const Sidebar: React.FC<SidebarProps> = ({
  activeTab,
  onSelectTab,
  pendingApprovalsCount = 0,
  alertCount = 0,
}) => {
  const navItems = [
    {
      id: 'dashboard',
      label: 'Executive Overview',
      icon: <LayoutDashboard size={18} />,
      badge: alertCount > 0 ? `${alertCount} risks` : undefined,
      badgeColor: 'badge-critical',
    },
    {
      id: 'chat',
      label: 'AI Demand Copilot',
      icon: <BotMessageSquare size={18} />,
      badge: 'GenAI',
      badgeColor: 'badge-healthy',
    },
    {
      id: 'forecast',
      label: 'Forecasting Engine',
      icon: <TrendingUp size={18} />,
    },
    {
      id: 'transfers',
      label: 'Stock Rebalancing',
      icon: <ArrowLeftRight size={18} />,
    },
    {
      id: 'whatif',
      label: 'What-If Simulation',
      icon: <SlidersHorizontal size={18} />,
    },
    {
      id: 'approvals',
      label: 'Approval Queue',
      icon: <CheckCircle2 size={18} />,
      badge: pendingApprovalsCount > 0 ? String(pendingApprovalsCount) : undefined,
      badgeColor: 'badge-warning',
    },
  ];

  return (
    <aside className="sidebar">
      <div className="sidebar-header">
        <div className="logo-badge">
          <Sparkles size={20} color="#6366f1" />
          <span>GenAI_Supplychain_Assistance</span>
        </div>
      </div>

      <ul className="nav-list">
        {navItems.map((item) => {
          const isActive = activeTab === item.id;
          return (
            <li
              key={item.id}
              className={`nav-item ${isActive ? 'active' : ''}`}
              onClick={() => onSelectTab(item.id)}
            >
              {item.icon}
              <span>{item.label}</span>
              {item.badge && (
                <span className={`nav-badge ${item.badgeColor}`}>
                  {item.badge}
                </span>
              )}
            </li>
          );
        })}
      </ul>

      <div style={{ padding: '16px 20px', borderTop: '1px solid var(--border-glass)' }}>
        <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Vector Store</div>
        <div style={{ fontSize: '12px', color: '#38bdf8', fontWeight: 600, marginTop: '2px' }}>
          ChromaDB (89 docs)
        </div>
        <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '8px' }}>Active Model</div>
        <div style={{ fontSize: '12px', color: '#10b981', fontWeight: 600, marginTop: '2px' }}>
          Llama 3.3 70B :free
        </div>
      </div>
    </aside>
  );
};
