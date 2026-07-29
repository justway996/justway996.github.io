import { describe, expect, it } from 'vitest';
import { workflowStatuses } from '../../src/shared/models';

describe('workflow status contract', () => {
  it('contains all user-visible preflight states', () => {
    expect(workflowStatuses).toEqual([
      'ready', 'needs_install', 'needs_permission', 'conflict', 'unknown',
    ]);
  });
});
