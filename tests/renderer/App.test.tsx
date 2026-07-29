// @vitest-environment jsdom

import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { App } from '../../src/renderer/App';
import type {
  MaintenancePlan,
  ToolboxApi,
  WorkflowDefinition,
  WorkflowRecommendation,
} from '../../src/shared/models';

const proposalWorkflow: WorkflowDefinition = {
  id: 'prop-client-proposal',
  name: '客户提案 PPT',
  category: '商业提案',
  description: '从客户需求到可编辑 PPT 的商业提案交付流程。',
  steps: [
    { id: 'brief', title: '客户需求梳理', toolId: 'proposal-brief' },
    { id: 'slides', title: 'PPT 版式制作', toolId: 'pptx-from-layouts' },
  ],
  dependencies: [
    { skillId: 'proposal-brief' },
    { skillId: 'pptx-from-layouts' },
  ],
};

afterEach(cleanup);

function createApi(
  recommendation: WorkflowRecommendation,
  plan?: MaintenancePlan,
): ToolboxApi & { applyPlan: ReturnType<typeof vi.fn> } {
  return {
    scan: vi.fn().mockResolvedValue([]),
    search: vi.fn().mockResolvedValue([recommendation]),
    listWorkflows: vi.fn().mockResolvedValue([proposalWorkflow]),
    importPackage: vi.fn().mockResolvedValue(undefined),
    exportWorkflow: vi.fn().mockResolvedValue(undefined),
    previewPlan: vi.fn().mockResolvedValue(plan),
    applyPlan: vi.fn().mockResolvedValue(undefined),
  };
}

describe('Toolbox application', () => {
  it('shows the five business navigation categories', () => {
    const api = createApi({
      workflowId: proposalWorkflow.id,
      title: proposalWorkflow.name,
      status: 'ready',
      reason: '所需工具已就绪。',
    });

    render(<App api={api} />);

    expect(screen.getByRole('navigation', { name: '主要功能' })).toBeInTheDocument();
    for (const label of ['总览', '发现', '工作流', '我的工具', '维护中心']) {
      expect(screen.getByRole('button', { name: label })).toBeInTheDocument();
    }
  });

  it('shows a business recommendation instead of raw Skills for a PPT search', async () => {
    const api = createApi({
      workflowId: proposalWorkflow.id,
      title: proposalWorkflow.name,
      status: 'ready',
      reason: '最符合“做 PPT”的业务目标，所需工具已就绪。',
    });

    render(<App api={api} />);
    await userEvent.type(screen.getByRole('searchbox'), '做 PPT');
    await userEvent.click(screen.getByRole('button', { name: '查找方案' }));

    expect(await screen.findByRole('heading', { name: '客户提案 PPT' })).toBeInTheDocument();
    expect(screen.getByText('立即可用')).toBeInTheDocument();
    expect(screen.queryByText('pptx-from-layouts')).not.toBeInTheDocument();
  });

  it('previews a conflict plan and requires confirmation before applying it', async () => {
    const plan: MaintenancePlan = {
      id: 'repair-plan-1',
      managedRoot: 'C:\\toolbox-managed',
      operations: [
        {
          kind: 'copy',
          path: 'C:\\toolbox-managed\\pptx-from-layouts',
          sourcePath: 'C:\\skills\\pptx-from-layouts',
        },
      ],
      impact: '创建隔离的受管理副本，保留现有工具。',
      risk: '低风险，可通过恢复点撤销。',
      backup: {
        manifestPath: 'C:\\toolbox-managed\\.backups\\repair-plan-1\\manifest.json',
        entries: [],
      },
      autoApplyEligible: false,
    };
    const api = createApi({
      workflowId: proposalWorkflow.id,
      title: proposalWorkflow.name,
      status: 'conflict',
      reason: '检测到重复工具，需要先处理。',
    }, plan);

    render(<App api={api} />);
    await userEvent.type(screen.getByRole('searchbox'), '做 PPT');
    await userEvent.click(screen.getByRole('button', { name: '查找方案' }));
    await userEvent.click(await screen.findByRole('button', { name: '修复此工具' }));

    expect(screen.getByRole('dialog', { name: '确认修复计划' })).toBeInTheDocument();
    expect(screen.getByText('将要变更的项目')).toBeInTheDocument();
    expect(api.applyPlan).not.toHaveBeenCalled();

    await userEvent.click(screen.getByRole('button', { name: '确认并执行' }));
    expect(api.applyPlan).toHaveBeenCalledWith('repair-plan-1', true);
  });
});
