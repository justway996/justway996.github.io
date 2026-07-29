import { type FormEvent, useState } from 'react';

export type SearchPanelProps = {
  onSearch(query: string): Promise<void>;
  busy?: boolean;
  compact?: boolean;
};

export function SearchPanel({ onSearch, busy = false, compact = false }: SearchPanelProps) {
  const [query, setQuery] = useState('');

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const normalized = query.trim();
    if (!normalized || busy) return;
    await onSearch(normalized);
  }

  return (
    <form className={compact ? 'search-panel search-panel--compact' : 'search-panel'} onSubmit={submit}>
      <label className="search-panel__field">
        <span className="sr-only">描述你想完成的工作</span>
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <circle cx="10.5" cy="10.5" r="6" />
          <path d="m15 15 4.5 4.5" />
        </svg>
        <input
          type="search"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="描述你想完成的工作，例如：做一份客户提案 PPT"
        />
        <kbd>⌘ K</kbd>
      </label>
      <button className="button button--accent search-panel__button" type="submit" disabled={!query.trim() || busy}>
        {busy ? '正在匹配…' : '查找方案'}
        <span aria-hidden="true">↗</span>
      </button>
    </form>
  );
}
