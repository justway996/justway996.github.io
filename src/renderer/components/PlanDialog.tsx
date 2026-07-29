import { useEffect, useState } from 'react';
import type { MaintenancePlan } from '../../shared/models';

export type PlanDialogProps = {
  plan: MaintenancePlan;
  onCancel(): void;
  onConfirm(planId: string): Promise<void>;
};

function operationLabel(kind: MaintenancePlan['operations'][number]['kind']) {
  if (kind === 'copy') return '创建隔离副本';
  if (kind === 'delete') return '移除受管理项目';
  return '更新受管理项目';
}

export function PlanDialog({ plan, onCancel, onConfirm }: PlanDialogProps) {
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    function closeOnEscape(event: KeyboardEvent) {
      if (event.key === 'Escape' && !submitting) onCancel();
    }
    window.addEventListener('keydown', closeOnEscape);
    return () => window.removeEventListener('keydown', closeOnEscape);
  }, [onCancel, submitting]);

  async function confirm() {
    setSubmitting(true);
    try {
      await onConfirm(plan.id);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="dialog-backdrop" role="presentation" onMouseDown={(event) => {
      if (event.target === event.currentTarget && !submitting) onCancel();
    }}>
      <section className="plan-dialog" role="dialog" aria-modal="true" aria-labelledby="plan-dialog-title">
        <div className="plan-dialog__header">
          <span className="plan-dialog__icon" aria-hidden="true">✦</span>
          <div>
            <span className="eyebrow">安全变更预览</span>
            <h2 id="plan-dialog-title">确认修复计划</h2>
          </div>
          <button className="icon-button" type="button" onClick={onCancel} aria-label="关闭">×</button>
        </div>

        <div className="plan-dialog__summary">
          <span className="plan-dialog__check" aria-hidden="true">✓</span>
          <div>
            <strong>系统推荐：保留现有内容</strong>
            <p>{plan.impact}</p>
          </div>
        </div>

        <div className="plan-dialog__section">
          <h3>将要变更的项目</h3>
          <div className="operation-list">
            {plan.operations.map((operation, index) => (
              <div className="operation-item" key={`${operation.kind}-${operation.path}-${index}`}>
                <span>{index + 1}</span>
                <div>
                  <strong>{operationLabel(operation.kind)}</strong>
                  <p>仅处理工具箱受管理范围，不覆盖你原有的文件。</p>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="plan-dialog__risk">
          <span aria-hidden="true">↶</span>
          <p><strong>已准备恢复点</strong>{plan.risk}</p>
        </div>

        <div className="plan-dialog__actions">
          <button className="button button--ghost" type="button" onClick={onCancel} disabled={submitting}>暂不处理</button>
          <button className="button button--primary" type="button" onClick={confirm} disabled={submitting}>
            {submitting ? '正在执行…' : '确认并执行'}
          </button>
        </div>
      </section>
    </div>
  );
}
