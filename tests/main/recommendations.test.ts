import { describe, expect, it } from 'vitest';
import { catalog } from '../../src/shared/catalog';
import { recommendWorkflows } from '../../src/main/recommendations';
import type { SkillRecord } from '../../src/shared/models';

const readySkills: SkillRecord[] = [
  'proposal-brief',
  'proposal-storyline',
  'pptx-from-layouts',
  'proposal-visuals',
  'proposal-review',
].map((id, index) => ({
  id,
  name: id,
  description: 'Ready for business proposals',
  path: `C:\\skills\\${id}`,
  source: 'workspace',
  enabled: true,
  precedence: index + 1,
}));

const shadowedPptSkills: SkillRecord[] = [
  ...readySkills,
  {
    ...readySkills[2],
    path: 'C:\\global-skills\\pptx-from-layouts',
    source: 'global',
    precedence: 1,
  },
];

describe('workflow recommendations', () => {
  it('recommends the client proposal workflow for PPT searches', () => {
    const results = recommendWorkflows('我要做客户提案PPT', catalog, readySkills);

    expect(results[0]).toMatchObject({ workflowId: 'prop-client-proposal', status: 'ready' });
    expect(results).toHaveLength(1);
  });

  it('does not mark a shadowed dependency as ready', () => {
    const results = recommendWorkflows('做 PPT', catalog, shadowedPptSkills);

    expect(results[0]?.status).toBe('conflict');
  });
});
