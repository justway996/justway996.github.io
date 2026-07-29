import { workflowAliases } from '../shared/catalog.js';
import type { SkillRecord, WorkflowDefinition, WorkflowStatus } from '../shared/models.js';

export type Recommendation = {
  workflowId: string;
  title: string;
  status: WorkflowStatus;
  reason: string;
};

export function recommendWorkflows(
  query: string,
  catalog: WorkflowDefinition[],
  skills: SkillRecord[],
): Recommendation[] {
  return catalog
    .map((workflow) => ({ workflow, score: scoreWorkflow(query, workflow) }))
    .filter(({ score }) => score > 0)
    .sort((left, right) => right.score - left.score || left.workflow.name.localeCompare(right.workflow.name, 'zh-CN'))
    .slice(0, 3)
    .map(({ workflow }, index) => {
      const status = workflowStatus(workflow, skills);
      return {
        workflowId: workflow.id,
        title: workflow.name,
        status,
        reason: index === 0
          ? `${workflow.name} 最符合“${query.trim()}”的业务目标。${statusReason(status)}`
          : `${workflow.name} 也与“${query.trim()}”相关。${statusReason(status)}`,
      };
    });
}

function scoreWorkflow(query: string, workflow: WorkflowDefinition): number {
  const normalizedQuery = normalize(query);
  if (!normalizedQuery) return 0;

  const fields: Array<[string, number]> = [
    [workflow.name, 40],
    [workflow.category, 30],
    [workflow.description, 20],
    ...(workflowAliases[workflow.id] ?? []).map((alias): [string, number] => [alias, 35]),
  ];

  return fields.reduce((score, [text, weight]) => score + matchScore(normalizedQuery, normalize(text), weight), 0);
}

function matchScore(query: string, text: string, weight: number): number {
  if (!text) return 0;
  const compactQuery = compact(query);
  const compactText = compact(text);
  if (compactQuery.includes(compactText) || compactText.includes(compactQuery)) return weight * 2;

  const queryTerms = terms(query);
  const textTerms = new Set(terms(text));
  return queryTerms.some((term) => term.length > 1 && textTerms.has(term)) ? weight : 0;
}

function workflowStatus(workflow: WorkflowDefinition, skills: SkillRecord[]): WorkflowStatus {
  if (workflow.dependencies.length === 0) return 'unknown';

  const recordsById = new Map<string, SkillRecord[]>();
  for (const skill of skills) {
    const records = recordsById.get(skill.id) ?? [];
    records.push(skill);
    recordsById.set(skill.id, records);
  }

  const dependencyRecords = workflow.dependencies.map(({ skillId }) => recordsById.get(skillId) ?? []);
  if (dependencyRecords.some((records) => records.length === 0)) return 'needs_install';
  if (dependencyRecords.some((records) => records.length > 1)) return 'conflict';

  const effectiveSkills = dependencyRecords.map(([skill]) => skill);
  if (effectiveSkills.some((skill) => !isKnownSkill(skill))) return 'unknown';
  if (effectiveSkills.some((skill) => !skill.enabled)) return 'needs_permission';
  return 'ready';
}

function isKnownSkill(skill: SkillRecord | undefined): skill is SkillRecord {
  return Boolean(
    skill
    && skill.id.trim()
    && skill.name.trim()
    && skill.description.trim()
    && skill.path.trim()
    && Number.isFinite(skill.precedence)
    && skill.precedence >= 0,
  );
}

function normalize(value: string): string {
  return value.toLocaleLowerCase().replace(/\s+/g, ' ').trim();
}

function compact(value: string): string {
  return value.replace(/\s+/g, '');
}

function terms(value: string): string[] {
  return value.match(/[a-z0-9]+|[\u3400-\u9fff]{2,}/gi) ?? [];
}

function statusReason(status: WorkflowStatus): string {
  switch (status) {
    case 'ready': return '所需工具已就绪。';
    case 'needs_install': return '部分所需工具尚未安装。';
    case 'needs_permission': return '部分所需工具需要启用或授权。';
    case 'conflict': return '检测到重复或被遮蔽的工具，需先处理冲突。';
    case 'unknown': return '部分工具元数据无法确认。';
  }
}
