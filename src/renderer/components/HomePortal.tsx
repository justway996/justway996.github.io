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
        <div>
          <span className="home-portal__brand">TOOLBOX / CHAPTER 01—05</span>
          <h1>选择你的<br />下一页</h1>
        </div>
        <p>五个章节，一条从想法到交付的工作路径。</p>
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
              <span>CHAPTER {item.number}</span>
              <strong>{item.label}</strong>
              <small>{item.descriptor}</small>
            </span>
            <span className="portal-door__arrow" aria-hidden="true">↗</span>
            <span className="portal-traveler" aria-hidden="true">
              <i className="portal-traveler__head" />
              <i className="portal-traveler__body" />
              <i className="portal-traveler__arm portal-traveler__arm--left" />
              <i className="portal-traveler__arm portal-traveler__arm--right" />
              <i className="portal-traveler__leg portal-traveler__leg--left" />
              <i className="portal-traveler__leg portal-traveler__leg--right" />
            </span>
          </button>
        ))}
      </nav>

      <footer className="home-portal__footer">
        <span>PERSONAL WORKSPACE · LOCAL / SECURE / READY</span>
        <span>TURN THE PAGE TO CONTINUE ↗</span>
      </footer>
    </main>
  );
}
