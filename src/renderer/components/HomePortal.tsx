import type { PageId } from './Sidebar';

const portalItems: Array<{
  id: PageId;
  number: string;
  label: string;
  descriptor: string;
}> = [
  { id: 'dashboard', number: '01', label: '总览', descriptor: 'Overview' },
  { id: 'discover', number: '02', label: '发现', descriptor: 'Discover' },
  { id: 'workflows', number: '03', label: '工作流', descriptor: 'Workflows' },
  { id: 'tools', number: '04', label: '我的工具', descriptor: 'My tools' },
  { id: 'maintenance', number: '05', label: '维护中心', descriptor: 'Maintenance' },
];

export type HomePortalProps = {
  onNavigate(page: PageId): void;
  turningPage?: PageId;
};

export function HomePortal({ onNavigate, turningPage }: HomePortalProps) {
  return (
    <main className={turningPage ? 'home-portal home-portal--turning' : 'home-portal'}>
      <header className="home-portal__header">
        <span className="home-portal__brand">TOOLBOX</span>
        <p>选择一个入口，开始今天的工作</p>
      </header>

      <nav className="portal-doors" aria-label="工具箱入口">
        {portalItems.map((item) => (
          <button
            className={[
              'portal-door',
              `portal-door--${item.id}`,
              turningPage === item.id ? 'portal-door--turning' : '',
            ].filter(Boolean).join(' ')}
            key={item.id}
            type="button"
            aria-label={item.label}
            onClick={() => {
              if (!turningPage) onNavigate(item.id);
            }}
          >
            <span className="portal-door__number">{item.number}</span>
            <span className="portal-door__label">
              <strong>{item.label}</strong>
              <small>{item.descriptor}</small>
            </span>
            <span className="portal-door__arrow" aria-hidden="true">↗</span>
          </button>
        ))}
      </nav>

      <div className="portal-figure" aria-hidden="true">
        <span className="portal-figure__head" />
        <span className="portal-figure__torso" />
        <span className="portal-figure__arm portal-figure__arm--left" />
        <span className="portal-figure__arm portal-figure__arm--right" />
        <span className="portal-figure__leg portal-figure__leg--left" />
        <span className="portal-figure__leg portal-figure__leg--right" />
      </div>

      <footer className="home-portal__footer">
        <span>PERSONAL WORKSPACE</span>
        <span>LOCAL / SECURE / READY</span>
      </footer>
    </main>
  );
}
