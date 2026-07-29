import { useEffect, useState } from 'react';
import approvedCover from '../assets/approved-homepage-cover.png';
import type { PageId } from './Sidebar';

const portalItems: Array<{
  id: PageId;
  label: string;
  eyebrow: string;
  title: string;
  description: string;
}> = [
  {
    id: 'dashboard',
    label: '总览',
    eyebrow: 'AI 工作能力中心',
    title: '今天想完成什么工作？',
    description: '用自然语言描述任务，我们会为你组合最合适的工具与工作流。',
  },
  {
    id: 'discover',
    label: '发现',
    eyebrow: '方案中心',
    title: '发现更高效的工作方式',
    description: '按业务目标查找，不必记住复杂的工具名称。',
  },
  {
    id: 'workflows',
    label: '工作流',
    eyebrow: '可复用流程',
    title: '工作流',
    description: '把稳定的业务步骤保存下来，在每次项目中直接复用。',
  },
  {
    id: 'tools',
    label: '我的工具',
    eyebrow: '本机能力',
    title: '我的工具',
    description: '查看已经安装、启用并可被工作流使用的业务能力。',
  },
  {
    id: 'maintenance',
    label: '维护中心',
    eyebrow: '安全与兼容',
    title: '维护中心',
    description: '所有更改都先生成计划、创建恢复点，再由你确认执行。',
  },
];

type BookPhase = 'idle' | 'selected' | 'flip-fast' | 'flip-slow' | 'child-emerge';

export type HomePortalProps = {
  onNavigate(page: PageId): void;
  turningPage?: PageId;
};

export function HomePortal({ onNavigate, turningPage }: HomePortalProps) {
  const [hoveredPage, setHoveredPage] = useState<PageId>();
  const [bookPhase, setBookPhase] = useState<BookPhase>('idle');
  const [title, setTitle] = useState('我的工作成长之旅');
  const [subtitle, setSubtitle] = useState("A PROFESSIONAL'S GROWTH JOURNEY");
  const [supportingCopy, setSupportingCopy] = useState('持续探索，持续成长，找到属于自己的工作路径。');
  const targetContent = portalItems.find((item) => item.id === turningPage);

  useEffect(() => {
    if (!turningPage) {
      setBookPhase('idle');
      return undefined;
    }

    setBookPhase('selected');
    const phaseTimers = [
      window.setTimeout(() => setBookPhase('flip-fast'), 140),
      window.setTimeout(() => setBookPhase('flip-slow'), 380),
      window.setTimeout(() => setBookPhase('child-emerge'), 640),
    ];

    return () => phaseTimers.forEach((timer) => window.clearTimeout(timer));
  }, [turningPage]);

  return (
    <main
      className={[
        'home-portal',
        'home-cover',
        turningPage ? 'home-portal--turning' : '',
        turningPage ? `home-cover--${bookPhase}` : '',
      ].filter(Boolean).join(' ')}
      data-hovered-page={hoveredPage}
      data-selected-page={turningPage}
      data-book-phase={turningPage ? bookPhase : undefined}
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
                hoveredPage === item.id ? 'portal-door--pull-forward' : '',
                turningPage === item.id ? 'portal-door--turning' : '',
              ].filter(Boolean).join(' ')}
              key={item.id}
              type="button"
              aria-label={item.label}
              data-hover-treatment={hoveredPage === item.id ? 'depth-only' : undefined}
              onMouseEnter={() => setHoveredPage(item.id)}
              onMouseLeave={() => setHoveredPage(undefined)}
              onFocus={() => setHoveredPage(item.id)}
              onBlur={() => setHoveredPage(undefined)}
              onClick={() => {
                if (!turningPage) onNavigate(item.id);
              }}
            >
              <span className="portal-door__page-surface" aria-hidden="true">
                <img src={approvedCover} alt="" draggable="false" />
              </span>
            </button>
          ))}
        </nav>

        {targetContent && (
          <section
            className="home-cover__page-stack"
            aria-label={`${targetContent.label}页面预览`}
          >
            {[0, 1, 2].map((pageIndex) => (
              <article
                className="home-cover__flip-page"
                aria-hidden={pageIndex === 0 ? undefined : true}
                key={pageIndex}
              >
                <span>{targetContent.eyebrow}</span>
                <h2>{targetContent.title}</h2>
                <p>{targetContent.description}</p>
                <i aria-hidden="true" />
                <i aria-hidden="true" />
                <i aria-hidden="true" />
              </article>
            ))}
          </section>
        )}
      </div>
    </main>
  );
}
