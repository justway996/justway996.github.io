import { contextBridge, ipcRenderer } from 'electron';
import type { ToolboxApi } from '../shared/models.js';

const toolbox: ToolboxApi = {
  scan: () => ipcRenderer.invoke('toolbox:scan'),
  search: (query) => ipcRenderer.invoke('toolbox:search', query),
  listWorkflows: () => ipcRenderer.invoke('toolbox:list-workflows'),
  importPackage: () => ipcRenderer.invoke('toolbox:import-package'),
  exportWorkflow: (workflowId) => ipcRenderer.invoke('toolbox:export-workflow', workflowId),
  previewPlan: (request) => ipcRenderer.invoke('toolbox:preview-plan', request),
  applyPlan: (planId, confirmed) => ipcRenderer.invoke('toolbox:apply-plan', planId, confirmed),
};

contextBridge.exposeInMainWorld('toolbox', toolbox);
