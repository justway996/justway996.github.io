import { useState } from 'react';
import approvedCover from '../assets/approved-homepage-cover.png';
import type { PageId } from './Sidebar';

const portalItems: Array<{
  id: PageId;
  label: string;
}> = [
  { id: 'dashboard', label: '总览' },
  { id: 'discover', label: '发现' },
  { id: 'workflows', label: '工作流' },
  { id: 'tools', label: '我的工具' },
  { id: 'maintenance', label: '维护中心' },
];

export type HomePortalProps = {
  onNavigate(page: PageId): void;
  turningPage?: PageId;
};

export function HomePortal({ onNavigate, turningPage }: HomePortalProps) {
  const [hoveredPage, setHoveredPage] = useState<PageId>();
  const [title, setTitle] = useState('我的工作成长之旅');
  const [subtitle, setSubtitle] = useState("A PROFESSIONAL'S GROWTH JOURNEY");
  const [supportingCopy, setSupportingCopy] = useState('持续探索，持续成长，找到属于自己的工作路径。');

  return (
    <main
      className={turningPage ? 'home-portal home-cover home-portal--turning' : 'home-portal home-cover'}
      data-hovered-page={hoveredPage}
      data-selected-page={turningPage}
    >
      <div className="home-cover__frame">
        <img
          className="home-cover__art"
          src={approvedCover}
          alt="个人工具箱首页封面"
        />

        <section className="home-cover__narrative" aria-label="可编辑封面文案">
          <textarea
            aria-label="中文标题"
            className="home-cover__title"
            rows={2}
            value={title}
            onChange={(event) => setTitle(event.target.value)}
          />
          <textarea
            aria-label="英文副标题"
            className="home-cover__subtitle"
            rows={2}
            value={subtitle}
            onChange={(event) => setSubtitle(event.target.value)}
          />
          <textarea
            aria-label="支持文案"
            className="home-cover__support"
            rows={3}
            value={supportingCopy}
            onChange={(event) => setSupportingCopy(event.target.value)}
          />
        </section>

        <nav className="portal-doors" aria-label="工具箱入口">
          {portalItems.map((item) => (
            <button
              className={[
                'portal-door',
                `portal-door--${item.id}`,
                hoveredPage === item.id ? 'portal-door--hovered' : '',
                turningPage === item.id ? 'portal-door--turning' : '',
              ].filter(Boolean).join(' ')}
              key={item.id}
              type="button"
              aria-label={item.label}
              onMouseEnter={() => setHoveredPage(item.id)}
              onMouseLeave={() => setHoveredPage(undefined)}
              onFocus={() => setHoveredPage(item.id)}
              onBlur={() => setHoveredPage(undefined)}
              onClick={() => {
                if (!turningPage) onNavigate(item.id);
              }}
            />
          ))}
        </nav>

        <div className="home-cover__page-stack" aria-hidden="true">
          <span />
          <span />
          <span />
        </div>
      </div>
    </main>
  );
}
