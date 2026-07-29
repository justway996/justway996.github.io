import { describe, expect, it } from 'vitest';
import { getRendererUrl } from '../../src/main/renderer-url';

describe('Electron renderer launcher', () => {
  it('uses the Vite server URL during local development', () => {
    expect(getRendererUrl(false, 'dist/main', 'http://127.0.0.1:5173')).toBe('http://127.0.0.1:5173');
  });
});
