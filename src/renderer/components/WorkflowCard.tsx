import type { WorkflowRecommendation, WorkflowStatus } from '../../shared/models';
import { StatusPill } from './StatusPill';

type WorkflowCardProps = {
  recommendation: WorkflowRecommendation;
  featured?: boolean;
  onRepair?(): void;
  onRun?(): void;
};

const workflowMeta: Record<string, { category: string; description: string; duration: string; steps: number }> = {
  'prop-client-proposal': {
    category: '商业提案',
    description: '从客户需求梳理到可编辑演示文稿，形成一套完整、可复用的提案交付流程。',
    duration: '约 15 分钟',
    steps: 5,
  },
};

function actionLabel(status: WorkflowStatus) {
  switch (status) {
    case 'ready': return '开始使用';
    case 'conflict': return '修复此工具';
    case 'needs_install': return '查看安装计划';
    case 'needs_permission': return '处理授权';
    case 'unknown': return '查看详情';
  }
}

export function WorkflowCard({ recommendation, featured = false, onRepair, onRun }: WorkflowCardProps) {
  const meta = workflowMeta[recommendation.workflowId] ?? {
    category: '智能工作流',
    description: recommendation.reason,
    duration: '约 10 分钟',
    steps: 3,
  };
  const requiresPlan = recommendation.status !== 'ready';

  return (
    <article className={featured ? 'workflow-card workflow-card--featured' : 'workflow-card'}>
      <div className="workflow-card__topline">
        <span className="workflow-card__category">{meta.category}</span>
        <StatusPill status={recommendation.status} />
      </div>
      <div className="workflow-card__identity">
        <span className="workflow-card__glyph" aria-hidden="true">
          <span>▤</span>
        </span>
        <div>
          <h3>{recommendation.title}</h3>
          <p>{meta.description}</p>
        </div>
      </div>
      <div className="workflow-card__reason">
        <span aria-hidden="true">✦</span>
        <p><strong>为什么推荐</strong>{recommendation.reason}</p>
      </div>
      <div className="workflow-card__footer">
        <div className="workflow-card__facts">
          <span><i aria-hidden="true">◴</i>{meta.duration}</span>
          <span><i aria-hidden="true">◇</i>{meta.steps} 个步骤</span>
        </div>
        <button
          className={requiresPlan ? 'button button--outline' : 'button button--primary'}
          type="button"
          onClick={requiresPlan ? onRepair : onRun}
        >
          {actionLabel(recommendation.status)}
          <span aria-hidden="true">→</span>
        </button>
      </div>
    </article>
  );
}
