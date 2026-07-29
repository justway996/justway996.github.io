import type { WorkflowDefinition } from '../../shared/models';

export type WorkflowsPageProps = {
  workflows: WorkflowDefinition[];
  onImport(): Promise<void>;
  onExport(workflowId: string): Promise<void>;
};

export function WorkflowsPage({ workflows, onImport, onExport }: WorkflowsPageProps) {
  return (
    <div className="page">
      <header className="page-header">
        <div>
          <span className="eyebrow">可复用流程</span>
          <h1>工作流</h1>
          <p>把稳定的业务步骤保存下来，在每次项目中直接复用。</p>
        </div>
        <button className="button button--primary" type="button" onClick={onImport}>
          <span aria-hidden="true">＋</span> 导入工作流
        </button>
      </header>

      <div className="metric-strip">
        <div><span>已保存</span><strong>{workflows.length}</strong><small>个工作流</small></div>
        <div><span>可直接运行</span><strong>{workflows.length}</strong><small>状态正常</small></div>
        <div><span>锁定依赖</span><strong>{workflows.reduce((sum, workflow) => sum + workflow.dependencies.length, 0)}</strong><small>项能力</small></div>
      </div>

      <section className="section">
        <div className="section-heading">
          <div><span className="eyebrow">你的流程</span><h2>最近使用</h2></div>
          <div className="segmented-control"><button className="is-active" type="button">全部</button><button type="button">已就绪</button><button type="button">需处理</button></div>
        </div>
        <div className="saved-workflow-grid">
          {workflows.map((workflow) => (
            <article className="saved-workflow" key={workflow.id}>
              <div className="saved-workflow__visual">
                <span className="saved-workflow__badge">已锁定</span>
                <div aria-hidden="true"><i>01</i><span>→</span><i>02</i><span>→</span><i>03</i></div>
              </div>
              <div className="saved-workflow__body">
                <span className="eyebrow">{workflow.category}</span>
                <h3>{workflow.name}</h3>
                <p>{workflow.description}</p>
                <div className="saved-workflow__meta">
                  <span><i /> 可运行</span>
                  <span>{workflow.steps.length} 个步骤</span>
                </div>
                <div className="saved-workflow__actions">
                  <button className="button button--primary" type="button">打开工作流</button>
                  <button className="icon-button icon-button--bordered" type="button" onClick={() => onExport(workflow.id)} aria-label={`导出${workflow.name}`}>⇧</button>
                </div>
              </div>
            </article>
          ))}
          <button className="new-workflow-card" type="button" onClick={onImport}>
            <span>＋</span>
            <strong>导入一个工作流</strong>
            <small>支持安全校验的工作流包</small>
          </button>
        </div>
      </section>
    </div>
  );
}
