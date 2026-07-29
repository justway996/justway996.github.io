import type { SkillRecord } from '../../shared/models';

export type MaintenancePageProps = {
  skills: SkillRecord[];
  onScan(): Promise<void>;
};

export function MaintenancePage({ skills, onScan }: MaintenancePageProps) {
  const duplicateCount = new Set(skills.map((skill) => skill.id)).size === skills.length
    ? 0
    : skills.length - new Set(skills.map((skill) => skill.id)).size;

  return (
    <div className="page">
      <header className="page-header">
        <div>
          <span className="eyebrow">安全与兼容</span>
          <h1>维护中心</h1>
          <p>所有更改都先生成计划、创建恢复点，再由你确认执行。</p>
        </div>
        <button className="button button--primary" type="button" onClick={onScan}>
          <span aria-hidden="true">↻</span> 立即检查
        </button>
      </header>

      <div className="health-grid">
        <article className="health-card health-card--primary">
          <div className="health-score"><svg viewBox="0 0 44 44"><circle cx="22" cy="22" r="18" /><circle className="health-score__value" cx="22" cy="22" r="18" /></svg><strong>92</strong></div>
          <div><span className="eyebrow eyebrow--light">整体状态</span><h2>工作台运行良好</h2><p>核心能力已就绪，仍有一项低风险建议。</p></div>
        </article>
        <article className="health-card"><span className="health-card__icon">✓</span><div><small>可用工具</small><strong>{skills.filter((skill) => skill.enabled).length}</strong><span>状态正常</span></div></article>
        <article className="health-card"><span className="health-card__icon health-card__icon--warning">!</span><div><small>重复项目</small><strong>{duplicateCount}</strong><span>{duplicateCount ? '建议处理' : '未发现'}</span></div></article>
        <article className="health-card"><span className="health-card__icon">↶</span><div><small>恢复点</small><strong>1</strong><span>可随时撤销</span></div></article>
      </div>

      <section className="section">
        <div className="section-heading">
          <div><span className="eyebrow">待处理事项</span><h2>维护建议</h2></div>
          <span className="section-heading__meta">按影响程度排序</span>
        </div>
        <div className="maintenance-list">
          <article className="maintenance-item">
            <span className="maintenance-item__severity">建议</span>
            <span className="maintenance-item__icon">↗</span>
            <div>
              <h3>检查演示文稿能力的更新</h3>
              <p>有一个兼容更新可用。查看影响后再决定是否升级，现有工作流仍保持锁定版本。</p>
              <div><span>低风险</span><span>不会新增权限</span><span>可恢复</span></div>
            </div>
            <button className="button button--outline" type="button">查看计划</button>
          </article>
          {duplicateCount > 0 && (
            <article className="maintenance-item maintenance-item--warning">
              <span className="maintenance-item__severity">冲突</span>
              <span className="maintenance-item__icon">!</span>
              <div>
                <h3>发现同名工具的多个副本</h3>
                <p>系统会优先保留你的原始内容，并建议创建隔离的受管理副本。</p>
                <div><span>{duplicateCount} 个重复项</span><span>需要确认</span></div>
              </div>
              <button className="button button--outline" type="button">修复此工具</button>
            </article>
          )}
        </div>
      </section>

      <section className="safety-note">
        <span>⌾</span>
        <div><strong>工具箱的安全承诺</strong><p>扫描始终只读。安装、更新、修复或删除前，你都会先看到准确的变更范围和恢复方式。</p></div>
        <button className="text-button" type="button">了解安全机制 →</button>
      </section>
    </div>
  );
}
