import type { WorkflowStatus } from '../../shared/models';

const statusLabels: Record<WorkflowStatus, string> = {
  ready: '立即可用',
  needs_install: '需要安装',
  needs_permission: '需要授权',
  conflict: '存在冲突',
  unknown: '待确认',
};

export function StatusPill({ status }: { status: WorkflowStatus }) {
  return (
    <span className={`status-pill status-pill--${status}`}>
      <span className="status-pill__dot" aria-hidden="true" />
      {statusLabels[status]}
    </span>
  );
}
