import { propDesignerTools } from '../../shared/catalog';
import type { WorkflowRecommendation } from '../../shared/models';
import { SearchPanel } from '../components/SearchPanel';
import { WorkflowCard } from '../components/WorkflowCard';

const toolIcons = ['⌁', '◌', '▤', '✦', '✓'];

export type DashboardPageProps = {
  recommendations: WorkflowRecommendation[];
  searching: boolean;
  skillCount: number;
  workflowCount: number;
  error?: string;
  onSearch(query: string): Promise<void>;
  onRepair(recommendation: WorkflowRecommendation): Promise<void>;
};

export function DashboardPage({
  recommendations,
  searching,
  skillCount,
  workflowCount,
  error,
  onSearch,
  onRepair,
}: DashboardPageProps) {
  return (
    <div className="page page--dashboard">
      <section className="hero-panel">
        <div className="hero-panel__grid" aria-hidden="true" />
        <div className="hero-panel__orb hero-panel__orb--one" aria-hidden="true" />
        <div className="hero-panel__orb hero-panel__orb--two" aria-hidden="true" />
        <div className="hero-panel__content">
          <span className="eyebrow eyebrow--light">AI 工作能力中心</span>
          <h1>今天想完成什么工作？</h1>
          <p>用自然语言描述任务，我们会为你组合最合适的工具与工作流。</p>
          <SearchPanel onSearch={onSearch} busy={searching} />
          <div className="hero-panel__suggestions">
            <span>试试：</span>
            <button type="button" onClick={() => onSearch('做一份客户提案 PPT')}>客户提案 PPT</button>
            <button type="button" onClick={() => onSearch('整理项目需求')}>整理项目需求</button>
            <button type="button" onClick={() => onSearch('交付前检查')}>交付前检查</button>
          </div>
        </div>
        <aside className="hero-panel__signal" aria-label="工作台状态">
          <span className="signal-ring signal-ring--outer" />
          <span className="signal-ring signal-ring--inner" />
          <span className="signal-core">TB</span>
          <div className="signal-card signal-card--top">
            <span>●</span>
            <div><strong>{skillCount || 5}</strong><small>项能力可用</small></div>
          </div>
          <div className="signal-card signal-card--bottom">
            <span>✦</span>
            <div><strong>{workflowCount || 1}</strong><small>个工作流就绪</small></div>
          </div>
        </aside>
      </section>

      {error && <div className="inline-alert" role="alert">{error}</div>}

      {recommendations.length > 0 && (
        <section className="section results-section" aria-live="polite">
          <div className="section-heading">
            <div>
              <span className="eyebrow">智能匹配结果</span>
              <h2>为你推荐</h2>
            </div>
            <span className="section-heading__meta">按本机就绪度排序</span>
          </div>
          <div className="workflow-grid">
            {recommendations.map((recommendation, index) => (
              <WorkflowCard
                key={recommendation.workflowId}
                recommendation={recommendation}
                featured={index === 0}
                onRepair={() => onRepair(recommendation)}
              />
            ))}
          </div>
        </section>
      )}

      <section className="section">
        <div className="section-heading">
          <div>
            <span className="eyebrow">为你的工作准备</span>
            <h2>道具设计师工具箱</h2>
          </div>
          <button className="text-button" type="button">查看全部工具 <span>→</span></button>
        </div>

        <div className="tool-card-grid">
          {propDesignerTools.map((tool, index) => (
            <article className="tool-card" key={tool.id}>
              <div className={`tool-card__icon tool-card__icon--${index + 1}`}>{toolIcons[index]}</div>
              <span className="tool-card__index">0{index + 1}</span>
              <h3>{tool.title}</h3>
              <p>{tool.description}</p>
              <div className="tool-card__footer">
                <span><i /> 已就绪</span>
                <button type="button" aria-label={`打开${tool.title}`}>↗</button>
              </div>
            </article>
          ))}
        </div>
      </section>

      <section className="dashboard-lower">
        <article className="insight-card">
          <div>
            <span className="eyebrow">工作建议</span>
            <h2>把重复步骤交给工作流</h2>
            <p>将需求梳理、视觉设计和交付检查串联起来，每次都按同一套标准完成。</p>
            <button className="button button--primary" type="button">浏览工作流 <span>→</span></button>
          </div>
          <div className="mini-flow" aria-hidden="true">
            <span>需求</span><i>→</i><span>设计</span><i>→</i><span>交付</span>
          </div>
        </article>
        <article className="activity-card">
          <div className="section-heading section-heading--small">
            <div>
              <span className="eyebrow">系统动态</span>
              <h2>工作台状态</h2>
            </div>
            <span className="live-badge"><i /> 实时</span>
          </div>
          <ul className="activity-list">
            <li><span className="activity-list__icon">✓</span><div><strong>本机工具扫描完成</strong><small>刚刚 · 未发现高风险项</small></div></li>
            <li><span className="activity-list__icon">↗</span><div><strong>1 项维护建议待处理</strong><small>可随时前往维护中心查看</small></div></li>
            <li><span className="activity-list__icon">◇</span><div><strong>工作流版本已锁定</strong><small>你的交付流程不会被静默更新</small></div></li>
          </ul>
        </article>
      </section>
    </div>
  );
}
