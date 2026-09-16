import React from 'react';
import { ShieldCheck, Activity } from 'lucide-react';

interface TopbarProps {
  title: string;
  subtitle?: string;
  isBackendHealthy?: boolean;
}

export const Topbar: React.FC<TopbarProps> = ({
  title,
  subtitle,
  isBackendHealthy = true,
}) => {
  return (
    <header className="topbar">
      <div>
        <h1 className="topbar-title">{title}</h1>
        {subtitle && (
          <p style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '2px' }}>
            {subtitle}
          </p>
        )}
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
        <div
          className="badge"
          style={{
            background: isBackendHealthy ? 'rgba(16, 185, 129, 0.12)' : 'rgba(244, 63, 94, 0.15)',
            color: isBackendHealthy ? '#34d399' : '#fb7185',
            border: `1px solid ${isBackendHealthy ? 'rgba(16, 185, 129, 0.3)' : 'rgba(244, 63, 94, 0.3)'}`,
            padding: '6px 12px',
          }}
        >
          <span className="badge-pulse" />
          <span>{isBackendHealthy ? 'FastAPI & ChromaDB Online' : 'Connecting to Server...'}</span>
        </div>

        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            fontSize: '13px',
            color: 'var(--text-secondary)',
            background: 'rgba(255, 255, 255, 0.04)',
            padding: '6px 14px',
            borderRadius: 'var(--radius-full)',
            border: '1px solid var(--border-glass)',
          }}
        >
          <ShieldCheck size={16} color="#6366f1" />
          <span>Human-in-the-Loop Mode</span>
        </div>
      </div>
    </header>
  );
};
