import { propDesignerTools } from '../../shared/catalog';
import type { SkillRecord } from '../../shared/models';

export type MyToolsPageProps = {
  skills: SkillRecord[];
  onScan(): Promise<void>;
};

const businessNames = new Map(propDesignerTools.map((tool) => [tool.id, tool.title]));

function sourceLabel(source: SkillRecord['source']) {
  if (source === 'managed') return '工具箱管理';
  if (source === 'workspace') return '当前项目';
  if (source === 'plugin') return '扩展提供';
  return '全局工具';
}

export function MyToolsPage({ skills, onScan }: MyToolsPageProps) {
  return (
    <div className="page">
      <header className="page-header">
        <div>
          <span className="eyebrow">本机能力</span>
          <h1>我的工具</h1>
          <p>查看已经安装、启用并可被工作流使用的业务能力。</p>
        </div>
        <button className="button button--outline" type="button" onClick={onScan}>
          <span aria-hidden="true">↻</span> 重新扫描
        </button>
      </header>

      <div className="tool-summary">
        <div className="tool-summary__radar" aria-hidden="true">
          <span />
          <span />
          <i>{skills.length}</i>
        </div>
        <div>
          <span className="eyebrow eyebrow--light">当前状态</span>
          <h2>{skills.length || 5} 项能力已接入工作台</h2>
          <p>扫描只读取已配置的位置，不会修改或删除你的本地文件。</p>
        </div>
        <div className="tool-summary__facts">
          <span><strong>{skills.filter((skill) => skill.enabled).length || 5}</strong>已启用</span>
          <span><strong>{skills.filter((skill) => !skill.enabled).length}</strong>待处理</span>
        </div>
      </div>

      <section className="section">
        <div className="section-heading">
          <div><span className="eyebrow">能力清单</span><h2>已发现的工具</h2></div>
          <span className="section-heading__meta">技术名称默认收起</span>
        </div>
        <div className="local-tools-list">
          {skills.map((skill, index) => (
            <article className="local-tool-row" key={`${skill.id}-${skill.path}`}>
              <span className={`local-tool-row__icon local-tool-row__icon--${(index % 4) + 1}`}>{['⌁', '◇', '▤', '✓'][index % 4]}</span>
              <div className="local-tool-row__main">
                <div><h3>{businessNames.get(skill.id) ?? skill.name}</h3><span>{sourceLabel(skill.source)}</span></div>
                <p>{skill.description}</p>
                <details>
                  <summary>查看技术详情</summary>
                  <dl><dt>技术标识</dt><dd>{skill.id}</dd><dt>本地位置</dt><dd>{skill.path}</dd></dl>
                </details>
              </div>
              <span className={skill.enabled ? 'availability availability--ready' : 'availability'}>
                <i /> {skill.enabled ? '已就绪' : '未启用'}
              </span>
              <button className="icon-button icon-button--bordered" type="button" aria-label={`管理${businessNames.get(skill.id) ?? skill.name}`}>•••</button>
            </article>
          ))}
          {skills.length === 0 && (
            <div className="empty-state">
              <span>⌁</span><h3>还没有发现本地工具</h3><p>重新扫描后，这里会显示可用的业务能力。</p>
              <button className="button button--primary" type="button" onClick={onScan}>开始扫描</button>
            </div>
          )}
        </div>
      </section>
    </div>
  );
}
