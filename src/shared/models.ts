export const workflowStatuses = [
  'ready',
  'needs_install',
  'needs_permission',
  'conflict',
  'unknown',
] as const;

export type WorkflowStatus = typeof workflowStatuses[number];

export type SkillRecord = {
  id: string;
  name: string;
  description: string;
  path: string;
  source: 'global' | 'workspace' | 'plugin' | 'managed';
  enabled: boolean;
  precedence: number;
  version?: string;
};

export type WorkflowDefinition = {
  id: string;
  name: string;
  category: string;
  description: string;
  steps: Array<{ id: string; title: string; toolId: string }>;
  dependencies: Array<{ skillId: string; version?: string }>;
};

export type PreflightResult = {
  workflowId: string;
  status: WorkflowStatus;
  message: string;
};

export type ChangePlan = {
  id: string;
  workflowId: string;
  summary: string;
  changes: Array<{ path: string; description: string }>;
};

export type PlanPreviewRequest =
  | { kind: 'repair' }
  | { kind: 'delete'; paths: string[] }
  | {
    kind: 'update';
    targetPath: string;
    trusted: boolean;
    compatible: boolean;
    permissionsUnchanged: boolean;
  };

export type MaintenanceOperation = {
  kind: 'copy' | 'delete' | 'update';
  path: string;
  sourcePath?: string;
};

export type BackupManifest = {
  manifestPath: string;
  entries: Array<{ path: string; backupPath?: string }>;
};

export type MaintenancePlan = {
  id: string;
  managedRoot: string;
  operations: MaintenanceOperation[];
  impact: string;
  risk: string;
  backup: BackupManifest;
  autoApplyEligible: boolean;
};

export type WorkflowPackageResult = {
  workflow: WorkflowDefinition;
  lock: { dependencies: WorkflowDefinition['dependencies'] };
};

export type WorkflowRecommendation = {
  workflowId: string;
  title: string;
  status: WorkflowStatus;
  reason: string;
};

export type ToolboxApi = {
  scan(): Promise<SkillRecord[]>;
  search(query: string): Promise<WorkflowRecommendation[]>;
  listWorkflows(): Promise<WorkflowDefinition[]>;
  importPackage(): Promise<WorkflowPackageResult | undefined>;
  exportWorkflow(workflowId: string): Promise<string | undefined>;
  previewPlan(request: PlanPreviewRequest): Promise<MaintenancePlan | undefined>;
  applyPlan(planId: string, confirmed: boolean): Promise<void>;
};
