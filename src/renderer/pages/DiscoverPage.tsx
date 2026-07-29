import type { WorkflowRecommendation } from '../../shared/models';
import { SearchPanel } from '../components/SearchPanel';
import { WorkflowCard } from '../components/WorkflowCard';

export type DiscoverPageProps = {
  recommendations: WorkflowRecommendation[];
  searching: boolean;
  onSearch(query: string): Promise<void>;
  onRepair(recommendation: WorkflowRecommendation): Promise<void>;
};

const categories = [
  { icon: '▤', name: '演示文稿', count: '12 个方案', tone: 'mint' },
  { icon: '◇', name: '视觉设计', count: '9 个方案', tone: 'blue' },
  { icon: '⌁', name: '研究整理', count: '8 个方案', tone: 'violet' },
  { icon: '▦', name: '数据分析', count: '7 个方案', tone: 'amber' },
];

export function DiscoverPage({ recommendations, searching, onSearch, onRepair }: DiscoverPageProps) {
  return (
    <div className="page">
      <header className="page-header">
        <div>
          <span className="eyebrow">方案中心</span>
          <h1>发现更高效的工作方式</h1>
          <p>按业务目标查找，不必记住复杂的工具名称。</p>
        </div>
        <span className="page-header__number">02</span>
      </header>

      <section className="discover-search">
        <div>
          <h2>你想解决什么问题？</h2>
          <p>描述产出或场景，我们会检查本机能力并给出可解释的方案。</p>
        </div>
        <SearchPanel onSearch={onSearch} busy={searching} compact />
      </section>

      {recommendations.length > 0 && (
        <section className="section">
          <div className="section-heading">
            <div><span className="eyebrow">匹配结果</span><h2>推荐方案</h2></div>
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
          <div><span className="eyebrow">按成果浏览</span><h2>热门工作类别</h2></div>
        </div>
        <div className="category-grid">
          {categories.map((category) => (
            <button className="category-card" type="button" key={category.name}>
              <span className={`category-card__icon category-card__icon--${category.tone}`}>{category.icon}</span>
              <span><strong>{category.name}</strong><small>{category.count}</small></span>
              <i>↗</i>
            </button>
          ))}
        </div>
      </section>

      <section className="editorial-banner">
        <span className="editorial-banner__number">01</span>
        <div>
          <span className="eyebrow eyebrow--light">本周精选</span>
          <h2>客户提案 PPT</h2>
          <p>一套从客户需求到可编辑演示文稿的成熟交付流程。</p>
        </div>
        <button className="button button--light" type="button" onClick={() => onSearch('客户提案 PPT')}>查看方案 <span>→</span></button>
      </section>
    </div>
  );
}
