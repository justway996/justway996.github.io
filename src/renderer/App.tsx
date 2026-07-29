import { useCallback, useEffect, useMemo, useState } from 'react';
import { catalog, propDesignerTools } from '../shared/catalog';
import type {
  MaintenancePlan,
  SkillRecord,
  ToolboxApi,
  WorkflowDefinition,
  WorkflowRecommendation,
} from '../shared/models';
import { PlanDialog } from './components/PlanDialog';
import { HomePortal } from './components/HomePortal';
import { Sidebar, type PageId } from './components/Sidebar';
import { DashboardPage } from './pages/DashboardPage';
import { DiscoverPage } from './pages/DiscoverPage';
import { MaintenancePage } from './pages/MaintenancePage';
import { MyToolsPage } from './pages/MyToolsPage';
import { WorkflowsPage } from './pages/WorkflowsPage';

declare global {
  interface Window {
    toolbox?: ToolboxApi;
  }
}

const pageTitles: Record<PageId, string> = {
  dashboard: '总览',
  discover: '发现',
  workflows: '工作流',
  tools: '我的工具',
  maintenance: '维护中心',
};

const pageOrder: PageId[] = ['dashboard', 'discover', 'workflows', 'tools', 'maintenance'];

const demoSkills: SkillRecord[] = propDesignerTools.map((tool, index) => ({
  id: tool.id,
  name: tool.title,
  description: tool.description,
  path: `C:\\Toolbox\\managed\\${tool.id}`,
  source: 'managed',
  enabled: true,
  precedence: 200 - index,
  version: '1.0.0',
}));

const demoPlan: MaintenancePlan = {
  id: 'demo-repair-plan',
  managedRoot: 'C:\\Toolbox\\managed',
  operations: [{ kind: 'copy', path: 'C:\\Toolbox\\managed\\proposal-tool' }],
  impact: '创建一个隔离的受管理副本，现有工具和项目文件保持不变。',
  risk: '低风险。执行前会记录恢复点，可随时撤销本次变更。',
  backup: { manifestPath: 'C:\\Toolbox\\backups\\demo\\manifest.json', entries: [] },
  autoApplyEligible: false,
};

const demoApi: ToolboxApi = {
  scan: async () => demoSkills,
  search: async (query) => {
    const normalized = query.toLocaleLowerCase();
    if (!['ppt', '提案', '演示', '客户', '交付'].some((keyword) => normalized.includes(keyword))) {
      return [];
    }
    return [{
      workflowId: 'prop-client-proposal',
      title: '客户提案 PPT',
      status: 'ready',
      reason: `最符合“${query}”的业务目标，所需工具均已就绪。`,
    }];
  },
  listWorkflows: async () => catalog,
  importPackage: async () => undefined,
  exportWorkflow: async () => undefined,
  previewPlan: async () => demoPlan,
  applyPlan: async () => undefined,
};

export type AppProps = {
  api?: ToolboxApi;
};

export function App({ api }: AppProps) {
  const toolboxApi = useMemo(() => api ?? window.toolbox ?? demoApi, [api]);
  const [isHome, setIsHome] = useState(true);
  const [portalTarget, setPortalTarget] = useState<PageId>();
  const [activePage, setActivePage] = useState<PageId>('dashboard');
  const [skills, setSkills] = useState<SkillRecord[]>([]);
  const [workflows, setWorkflows] = useState<WorkflowDefinition[]>([]);
  const [recommendations, setRecommendations] = useState<WorkflowRecommendation[]>([]);
  const [searching, setSearching] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string>();
  const [notice, setNotice] = useState<string>();
  const [plan, setPlan] = useState<MaintenancePlan>();
  const [transitionDirection, setTransitionDirection] = useState<'forward' | 'backward'>('forward');

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(undefined);
    try {
      const [nextSkills, nextWorkflows] = await Promise.all([
        toolboxApi.scan(),
        toolboxApi.listWorkflows(),
      ]);
      setSkills(nextSkills);
      setWorkflows(nextWorkflows);
    } catch (caught) {
      setError(toMessage(caught, '无法读取本机工具，请稍后重试。'));
    } finally {
      setLoading(false);
    }
  }, [toolboxApi]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  useEffect(() => {
    if (!portalTarget) return undefined;

    const transitionTimer = window.setTimeout(() => {
      setIsHome(false);
      setPortalTarget(undefined);
    }, 820);

    return () => window.clearTimeout(transitionTimer);
  }, [portalTarget]);

  const search = useCallback(async (query: string) => {
    setSearching(true);
    setError(undefined);
    try {
      const results = await toolboxApi.search(query);
      setRecommendations(results);
      if (results.length === 0) setNotice('暂未找到完全匹配的方案，换一种成果描述试试。');
      else setNotice(undefined);
    } catch (caught) {
      setError(toMessage(caught, '方案搜索暂时不可用。'));
    } finally {
      setSearching(false);
    }
  }, [toolboxApi]);

  const previewRepair = useCallback(async (_recommendation: WorkflowRecommendation) => {
    setError(undefined);
    try {
      const nextPlan = await toolboxApi.previewPlan({ kind: 'repair' });
      if (nextPlan) setPlan(nextPlan);
    } catch (caught) {
      setError(toMessage(caught, '无法生成安全修复计划。'));
    }
  }, [toolboxApi]);

  const applyRepair = useCallback(async (planId: string) => {
    try {
      await toolboxApi.applyPlan(planId, true);
      setPlan(undefined);
      setNotice('修复计划已执行，并已保留恢复点。');
      await refresh();
    } catch (caught) {
      setError(toMessage(caught, '计划未能执行，未对现有内容做出变更。'));
    }
  }, [refresh, toolboxApi]);

  const importWorkflow = useCallback(async () => {
    try {
      const imported = await toolboxApi.importPackage();
      if (imported) {
        setNotice(`“${imported.workflow.name}”已通过安全检查。`);
        setWorkflows((current) => (
          current.some((workflow) => workflow.id === imported.workflow.id)
            ? current
            : [...current, imported.workflow]
        ));
      }
    } catch (caught) {
      setError(toMessage(caught, '工作流包未通过安全检查。'));
    }
  }, [toolboxApi]);

  const exportWorkflow = useCallback(async (workflowId: string) => {
    try {
      const output = await toolboxApi.exportWorkflow(workflowId);
      if (output) setNotice('工作流已安全导出，不包含账号凭据或私人文件。');
    } catch (caught) {
      setError(toMessage(caught, '无法导出这个工作流。'));
    }
  }, [toolboxApi]);

  const navigate = useCallback((nextPage: PageId) => {
    if (isHome) {
      setActivePage(nextPage);
      if (window.matchMedia?.('(prefers-reduced-motion: reduce)').matches) {
        setIsHome(false);
      } else {
        setPortalTarget(nextPage);
      }
      return;
    }
    if (nextPage === activePage) return;
    setTransitionDirection(
      pageOrder.indexOf(nextPage) > pageOrder.indexOf(activePage) ? 'forward' : 'backward',
    );
    setActivePage(nextPage);
  }, [activePage, isHome]);

  if (isHome) {
    return (
      <HomePortal
        onNavigate={navigate}
        turningPage={portalTarget}
      />
    );
  }

  return (
    <div className="app-shell" data-motion-safe="true">
      <Sidebar activePage={activePage} onNavigate={navigate} />
      <main className="app-main">
        <div className="topbar">
          <div className="topbar__breadcrumb"><span>TOOLBOX</span><i>/</i><strong>{pageTitles[activePage]}</strong></div>
          <div className="topbar__actions">
            <span className="sync-state"><i /> 本机已连接</span>
            <button className="icon-button topbar__notification" type="button" aria-label="通知">
              <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6.5 9a5.5 5.5 0 0 1 11 0c0 6 2.5 6 2.5 7.5H4C4 15 6.5 15 6.5 9ZM10 19h4" /></svg>
              <span />
            </button>
          </div>
        </div>

        {notice && (
          <div className="toast" role="status">
            <span>✓</span>{notice}
            <button type="button" onClick={() => setNotice(undefined)} aria-label="关闭提示">×</button>
          </div>
        )}

        {loading && <div className="loading-line" aria-label="正在读取工作台状态"><span /></div>}

        <div
          className={`page-transition page-transition--${transitionDirection}`}
          key={activePage}
        >
          {activePage === 'dashboard' && (
            <DashboardPage
              recommendations={recommendations}
              searching={searching}
              skillCount={skills.length}
              workflowCount={workflows.length}
              error={error}
              onSearch={search}
              onRepair={previewRepair}
            />
          )}
          {activePage === 'discover' && (
            <DiscoverPage
              recommendations={recommendations}
              searching={searching}
              onSearch={search}
              onRepair={previewRepair}
            />
          )}
          {activePage === 'workflows' && (
            <WorkflowsPage workflows={workflows} onImport={importWorkflow} onExport={exportWorkflow} />
          )}
          {activePage === 'tools' && <MyToolsPage skills={skills} onScan={refresh} />}
          {activePage === 'maintenance' && <MaintenancePage skills={skills} onScan={refresh} />}
        </div>
      </main>

      {plan && <PlanDialog plan={plan} onCancel={() => setPlan(undefined)} onConfirm={applyRepair} />}
    </div>
  );
}

function toMessage(caught: unknown, fallback: string): string {
  return caught instanceof Error && caught.message ? caught.message : fallback;
}
