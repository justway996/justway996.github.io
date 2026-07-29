import type { WorkflowDefinition } from './models.js';

export type PropDesignerTool = {
  id: string;
  title: string;
  description: string;
};

export const propDesignerTools: PropDesignerTool[] = [
  { id: 'proposal-brief', title: '客户需求梳理', description: '将客户目标整理为清晰的提案简报。' },
  { id: 'proposal-storyline', title: '提案故事线', description: '形成面向决策者的商业叙事和页面结构。' },
  { id: 'pptx-from-layouts', title: 'PPT 版式制作', description: '基于版式创建可编辑的 PowerPoint 页面。' },
  { id: 'proposal-visuals', title: '提案视觉设计', description: '为商业提案准备统一的视觉素材和版式。' },
  { id: 'proposal-review', title: '交付前检查', description: '检查客户提案的完整性、可读性和交付风险。' },
];

export const catalog: WorkflowDefinition[] = [
  {
    id: 'prop-client-proposal',
    name: '客户提案 PPT',
    category: '商业提案',
    description: '从客户需求到可编辑 PPT 的商业提案交付流程。',
    steps: propDesignerTools.map((tool) => ({ id: tool.id, title: tool.title, toolId: tool.id })),
    dependencies: propDesignerTools.map((tool) => ({ skillId: tool.id })),
  },
];

export const workflowAliases: Record<string, string[]> = {
  'prop-client-proposal': [
    '客户提案',
    '提案PPT',
    '商业提案',
    'client proposal',
    'proposal deck',
    'pitch deck',
  ],
};
