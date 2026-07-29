import type { ReactNode } from 'react';

export type PageId = 'dashboard' | 'discover' | 'workflows' | 'tools' | 'maintenance';

type NavigationItem = {
  id: PageId;
  label: string;
  icon: ReactNode;
};

const navigation: NavigationItem[] = [
  {
    id: 'dashboard',
    label: '总览',
    icon: (
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <rect x="4" y="4" width="6" height="6" rx="1.5" />
        <rect x="14" y="4" width="6" height="6" rx="1.5" />
        <rect x="4" y="14" width="6" height="6" rx="1.5" />
        <rect x="14" y="14" width="6" height="6" rx="1.5" />
      </svg>
    ),
  },
  {
    id: 'discover',
    label: '发现',
    icon: (
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <circle cx="11" cy="11" r="6.5" />
        <path d="m16 16 4 4" />
        <path d="m9 13 1.6-4.1L15 7l-1.8 4.4L9 13Z" />
      </svg>
    ),
  },
  {
    id: 'workflows',
    label: '工作流',
    icon: (
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <circle cx="6" cy="6" r="2.5" />
        <circle cx="18" cy="12" r="2.5" />
        <circle cx="6" cy="18" r="2.5" />
        <path d="M8.5 6h3a3 3 0 0 1 3 3v0a3 3 0 0 0 3 3" />
        <path d="M8.5 18h3a3 3 0 0 0 3-3v0a3 3 0 0 1 3-3" />
      </svg>
    ),
  },
  {
    id: 'tools',
    label: '我的工具',
    icon: (
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M4 8.5h16v10A1.5 1.5 0 0 1 18.5 20h-13A1.5 1.5 0 0 1 4 18.5v-10Z" />
        <path d="M9 8.5V6a2 2 0 0 1 2-2h2a2 2 0 0 1 2 2v2.5" />
        <path d="M4 13h16M10 12v2M14 12v2" />
      </svg>
    ),
  },
  {
    id: 'maintenance',
    label: '维护中心',
    icon: (
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M14.2 5.1a5 5 0 0 0-6.5 6.6L4 15.4a1.8 1.8 0 0 0 0 2.5L6.1 20a1.8 1.8 0 0 0 2.5 0l3.7-3.7a5 5 0 0 0 6.6-6.5l-3.3 3.3-2.7-2.7 3.3-3.3Z" />
      </svg>
    ),
  },
];

export type SidebarProps = {
  activePage: PageId;
  onNavigate(page: PageId): void;
};

export function Sidebar({ activePage, onNavigate }: SidebarProps) {
  return (
    <aside className="sidebar">
      <div className="brand">
        <span className="brand__mark" aria-hidden="true">
          <span />
          <span />
          <span />
        </span>
        <div>
          <strong>TOOLBOX</strong>
          <span>工作能力中心</span>
        </div>
      </div>

      <nav className="sidebar__nav" aria-label="主要功能">
        <span className="sidebar__label">工作台</span>
        {navigation.map((item) => (
          <button
            className={activePage === item.id ? 'nav-item nav-item--active' : 'nav-item'}
            key={item.id}
            type="button"
            onClick={() => onNavigate(item.id)}
            aria-label={item.label}
            aria-current={activePage === item.id ? 'page' : undefined}
          >
            <span className="nav-item__icon">{item.icon}</span>
            {item.label}
            {item.id === 'maintenance' && <span className="nav-item__count">1</span>}
          </button>
        ))}
      </nav>

      <div className="sidebar__footer">
        <div className="system-state">
          <span className="system-state__pulse" />
          <div>
            <strong>本机服务正常</strong>
            <span>上次扫描 · 刚刚</span>
          </div>
        </div>
        <div className="profile">
          <span className="profile__avatar">Y</span>
          <div>
            <strong>个人工作区</strong>
            <span>本地模式</span>
          </div>
          <span className="profile__more">•••</span>
        </div>
      </div>
    </aside>
  );
}
