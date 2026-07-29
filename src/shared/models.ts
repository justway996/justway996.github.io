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

export type ToolboxApi = {
  listSkills(): Promise<SkillRecord[]>;
  listWorkflows(): Promise<WorkflowDefinition[]>;
  preflightWorkflow(workflowId: string): Promise<PreflightResult>;
  createChangePlan(workflowId: string): Promise<ChangePlan>;
};
