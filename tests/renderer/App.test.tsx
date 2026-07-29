// @vitest-environment jsdom

import '@testing-library/jest-dom/vitest';
import { readFileSync } from 'node:fs';
import { act, cleanup, fireEvent, render, screen, within } from '@testing-library/react';
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

afterEach(() => {
  cleanup();
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

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

function enterPortalPage(label: '总览' | '发现' | '工作流' | '我的工具' | '维护中心') {
  vi.stubGlobal('matchMedia', vi.fn().mockReturnValue({
    matches: true,
    media: '(prefers-reduced-motion: reduce)',
    onchange: null,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    addListener: vi.fn(),
    removeListener: vi.fn(),
    dispatchEvent: vi.fn(),
  }));
  fireEvent.click(screen.getByRole('button', { name: label }));
}

describe('Toolbox application', () => {
  it('uses the approved cover with five stable portal controls and opens 工作流 exactly', async () => {
    vi.useFakeTimers();
    const api = createApi({
      workflowId: proposalWorkflow.id,
      title: proposalWorkflow.name,
      status: 'ready',
      reason: '所需工具已就绪。',
    });

    const rendererDocument = new DOMParser().parseFromString(
      readFileSync('src/renderer/index.html', 'utf8'),
      'text/html',
    );

    expect(rendererDocument.documentElement.getAttribute('lang')).toBe('zh-CN');
    expect(rendererDocument.documentElement.getAttribute('translate')).toBe('no');

    render(<App api={api} />);
    expect(screen.getByRole('img', { name: '个人工具箱首页封面' })).toHaveAttribute(
      'src',
      expect.stringContaining('approved-homepage-cover'),
    );
    const portal = screen.getByRole('navigation', { name: '工具箱入口' });
    const controls = within(portal).getAllByRole('button');

    expect(controls).toHaveLength(5);
    expect(controls.map((control) => control.getAttribute('aria-label'))).toEqual([
      '总览',
      '发现',
      '工作流',
      '我的工具',
      '维护中心',
    ]);

    fireEvent.click(within(portal).getByRole('button', { name: '工作流' }));
    act(() => vi.advanceTimersByTime(820));

    expect(screen.getByRole('heading', { name: '工作流', level: 1 })).toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: '发现', level: 1 })).not.toBeInTheDocument();
    expect(screen.getByRole('navigation', { name: '主要功能' })).toBeInTheDocument();
    expect(screen.queryByRole('navigation', { name: '工具箱入口' })).not.toBeInTheDocument();
  });

  it('updates the rendered cover copy when the narrative fields are edited', async () => {
    const api = createApi({
      workflowId: proposalWorkflow.id,
      title: proposalWorkflow.name,
      status: 'ready',
      reason: '所需工具已就绪。',
    });
    const user = userEvent.setup();

    render(<App api={api} />);

    const title = screen.getByRole('textbox', { name: '中文标题' });
    const subtitle = screen.getByRole('textbox', { name: '英文副标题' });
    const supportingCopy = screen.getByRole('textbox', { name: '支持文案' });

    expect(title).toHaveValue('我的工作成长之旅');
    expect(subtitle).toHaveValue("A PROFESSIONAL'S GROWTH JOURNEY");

    await user.clear(title);
    await user.type(title, '我的摄影成长之旅');
    await user.clear(subtitle);
    await user.type(subtitle, "A PHOTOGRAPHER'S GROWTH JOURNEY");
    await user.clear(supportingCopy);
    await user.type(supportingCopy, '持续观察，持续创作。');

    expect(title).toHaveValue('我的摄影成长之旅');
    expect(subtitle).toHaveValue("A PHOTOGRAPHER'S GROWTH JOURNEY");
    expect(supportingCopy).toHaveValue('持续观察，持续创作。');
  });

  it('pulls a hovered page forward with depth only and no white outline box', () => {
    const styles = readFileSync('src/renderer/styles.css', 'utf8');
    const approvedCoverStyles = styles.slice(styles.indexOf('/* Approved homepage cover'));
    vi.useFakeTimers();
    const api = createApi({
      workflowId: proposalWorkflow.id,
      title: proposalWorkflow.name,
      status: 'ready',
      reason: '所需工具已就绪。',
    });

    render(<App api={api} />);

    const portal = screen.getByRole('navigation', { name: '工具箱入口' });
    const workflowDoor = within(portal).getByRole('button', { name: '工作流' });
    fireEvent.mouseEnter(workflowDoor);

    expect(screen.getByRole('main')).toHaveAttribute('data-hovered-page', 'workflows');
    expect(workflowDoor).toHaveClass('portal-door--hovered');
    expect(workflowDoor).toHaveClass('portal-door--pull-forward');
    expect(workflowDoor).toHaveAttribute('data-hover-treatment', 'depth-only');
    expect(approvedCoverStyles).toMatch(
      /\.home-cover \.portal-door--pull-forward\s*\{[^}]*border-color:\s*transparent;[^}]*box-shadow:[^}]*rgba\(0,\s*0,\s*0,/s,
    );
    expect(approvedCoverStyles).not.toMatch(
      /\.home-cover \.portal-door--pull-forward\s*\{[^}]*box-shadow:[^}]*(?:#fff|rgba\(255,\s*255,\s*255,)/s,
    );
  });

  it('shows target content while visiting every book phase before opening its target', () => {
    vi.useFakeTimers();
    const api = createApi({
      workflowId: proposalWorkflow.id,
      title: proposalWorkflow.name,
      status: 'ready',
      reason: '所需工具已就绪。',
    });

    render(<App api={api} />);

    const workflowDoor = screen.getByRole('button', { name: '工作流' });
    fireEvent.click(workflowDoor);

    const cover = screen.getByRole('main');
    const preview = screen.getByRole('region', { name: '工作流页面预览' });

    expect(cover).toHaveAttribute('data-book-phase', 'selected');
    expect(preview).toHaveTextContent('工作流');
    expect(preview).toHaveTextContent('把稳定的业务步骤保存下来，在每次项目中直接复用。');
    expect(screen.queryByRole('heading', { name: '工作流', level: 1 })).not.toBeInTheDocument();

    act(() => vi.advanceTimersByTime(140));
    expect(cover).toHaveAttribute('data-book-phase', 'flip-fast');
    expect(preview).toHaveTextContent('把稳定的业务步骤保存下来，在每次项目中直接复用。');

    act(() => vi.advanceTimersByTime(240));
    expect(cover).toHaveAttribute('data-book-phase', 'flip-slow');
    expect(preview).toHaveTextContent('把稳定的业务步骤保存下来，在每次项目中直接复用。');

    act(() => vi.advanceTimersByTime(260));
    expect(cover).toHaveAttribute('data-book-phase', 'child-emerge');

    act(() => vi.advanceTimersByTime(180));

    expect(screen.getByRole('heading', { name: '工作流', level: 1 })).toBeInTheDocument();
  });

  it('opens the selected portal target immediately when reduced motion is preferred', () => {
    vi.stubGlobal('matchMedia', vi.fn().mockReturnValue({
      matches: true,
      media: '(prefers-reduced-motion: reduce)',
      onchange: null,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      addListener: vi.fn(),
      removeListener: vi.fn(),
      dispatchEvent: vi.fn(),
    }));
    const api = createApi({
      workflowId: proposalWorkflow.id,
      title: proposalWorkflow.name,
      status: 'ready',
      reason: '所需工具已就绪。',
    });

    render(<App api={api} />);
    fireEvent.click(screen.getByRole('button', { name: '工作流' }));

    expect(screen.getByRole('heading', { name: '工作流', level: 1 })).toBeInTheDocument();
    expect(screen.queryByRole('navigation', { name: '工具箱入口' })).not.toBeInTheDocument();
  });

  it('shows the five business navigation categories', () => {
    const api = createApi({
      workflowId: proposalWorkflow.id,
      title: proposalWorkflow.name,
      status: 'ready',
      reason: '所需工具已就绪。',
    });

    render(<App api={api} />);
    enterPortalPage('总览');

    expect(screen.getByRole('navigation', { name: '主要功能' })).toBeInTheDocument();
    for (const label of ['总览', '发现', '工作流', '我的工具', '维护中心']) {
      expect(screen.getByRole('button', { name: label })).toBeInTheDocument();
    }
  });

  it('marks page navigation with direction and a reduced-motion-safe root contract', async () => {
    const api = createApi({
      workflowId: proposalWorkflow.id,
      title: proposalWorkflow.name,
      status: 'ready',
      reason: '所需工具已就绪。',
    });

    const { container } = render(<App api={api} />);
    enterPortalPage('总览');
    const appShell = container.querySelector('.app-shell');

    expect(appShell).toHaveAttribute('data-motion-safe', 'true');

    await userEvent.click(screen.getByRole('button', { name: '发现' }));
    expect(container.querySelector('.page-transition')).toHaveClass('page-transition--forward');

    await userEvent.click(screen.getByRole('button', { name: '总览' }));
    expect(container.querySelector('.page-transition')).toHaveClass('page-transition--backward');
  });

  it('shows a business recommendation instead of raw Skills for a PPT search', async () => {
    const api = createApi({
      workflowId: proposalWorkflow.id,
      title: proposalWorkflow.name,
      status: 'ready',
      reason: '最符合“做 PPT”的业务目标，所需工具已就绪。',
    });

    render(<App api={api} />);
    enterPortalPage('总览');
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
    enterPortalPage('总览');
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
