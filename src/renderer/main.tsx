import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';

const rootElement = document.getElementById('root');

if (!rootElement) {
  throw new Error('Application root is missing.');
}

createRoot(rootElement).render(
  <StrictMode>
    <main>
      <h1>Codex Skill Toolbox</h1>
      <p>Review your tools and workflow readiness before making changes.</p>
    </main>
  </StrictMode>,
);
