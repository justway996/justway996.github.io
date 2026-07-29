import { existsSync } from 'node:fs';

const configurationFiles = [
  'electron-builder.yml',
  'electron-builder.yaml',
  'electron-builder.json',
];

if (!configurationFiles.some((file) => existsSync(file))) {
  console.error('Desktop packaging configuration is not present. Add it in Task 8 before running dist.');
  process.exit(1);
}
