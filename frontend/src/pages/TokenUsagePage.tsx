import { useCallback, useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import {
  findTokenUsageSummary,
  type TokenUsageSummary,
  type TokenUsageTool,
} from '@/api/tokenUsage';
import ProductNavigation from '@/components/ProductNavigation';
import UsageTideChart from '@/components/UsageTideChart';
import {
  formatCompactTokenCount,
  formatTokenCount,
} from '@/lib/display';

type UsagePeriod = 'today' | '7d' | '30d';
type ToolFilter = 'all' | TokenUsageTool;

const PERIODS: { value: UsagePeriod; label: string; days: number }[] = [
  { value: 'today', label: '今天', days: 1 },
  { value: '7d', label: '7 天', days: 7 },
  { value: '30d', label: '30 天', days: 30 },
];
const TOOLS: { value: ToolFilter; label: string }[] = [
  { value: 'all', label: '全部' },
  { value: 'claude', label: 'Claude' },
  { value: 'codex', label: 'Codex' },
  { value: 'opencode', label: 'OpenCode' },
];
const TOKEN_DETAILS = [
  { field: 'input_tokens', label: '输入' },
  { field: 'output_tokens', label: '输出' },
  { field: 'cache_creation_tokens', label: '缓存写入' },
  { field: 'cache_read_tokens', label: '缓存读取' },
  { field: 'reasoning_tokens', label: '推理' },
] as const;

function isPeriod(value: string | null): value is UsagePeriod {
  return PERIODS.some((period) => period.value === value);
}

function isTool(value: string | null): value is ToolFilter {
  return TOOLS.some((tool) => tool.value === value);
}

function queryRange(period: UsagePeriod): {
  startTime: string;
  endTime: string;
  timezoneOffsetMinutes: number;
} {
  const now = new Date();
  const days = PERIODS.find((item) => item.value === period)?.days ?? 7;
  const start = new Date(now);
  start.setHours(0, 0, 0, 0);
  start.setDate(start.getDate() - (days - 1));
  return {
    startTime: start.toISOString(),
    endTime: now.toISOString(),
    timezoneOffsetMinutes: -now.getTimezoneOffset(),
  };
}

function BackIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="m15 18-6-6 6-6" />
    </svg>
  );
}

export default function TokenUsagePage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const period = isPeriod(searchParams.get('period'))
    ? searchParams.get('period') as UsagePeriod
    : '7d';
  const tool = isTool(searchParams.get('tool'))
    ? searchParams.get('tool') as ToolFilter
    : 'all';
  const [summary, setSummary] = useState<TokenUsageSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);

  const loadSummary = useCallback(async (): Promise<void> => {
    setLoading(true);
    setError(null);
    setSummary(null);
    try {
      const range = queryRange(period);
      setSummary(
        await findTokenUsageSummary({
          ...range,
          tool: tool === 'all' ? undefined : tool,
        }),
      );
    } catch (loadError) {
      setSummary(null);
      setError(loadError instanceof Error ? loadError.message : '使用量加载失败');
    } finally {
      setLoading(false);
    }
  }, [period, tool]);

  useEffect(() => {
    void loadSummary();
  }, [loadSummary, reloadKey]);

  const updateFilter = (
    nextPeriod: UsagePeriod = period,
    nextTool: ToolFilter = tool,
  ): void => {
    setSearchParams({ period: nextPeriod, tool: nextTool });
  };

  const largestModelTotal = Math.max(
    ...(summary?.models.map((model) => model.total_tokens) ?? []),
    1,
  );

  return (
    <main className="app-shell usage-page" aria-busy={loading}>
      <header className="history-header usage-header">
        <Link className="back-link" to="/" aria-label="返回余额看板">
          <BackIcon />
        </Link>
        <div className="usage-header-title">
          <span className="brand-mark" aria-hidden="true">
            <img src="/favicon.svg" alt="" />
          </span>
          <div>
            <p>TokenUsage</p>
            <span>Token 用量</span>
          </div>
        </div>
      </header>

      <ProductNavigation />

      <section className="usage-filter-panel" aria-label="使用量筛选">
        <div className="usage-filter-row">
          <span>时间</span>
          <div className="usage-segments">
            {PERIODS.map((item) => (
              <button
                type="button"
                className={item.value === period ? 'is-active' : ''}
                aria-pressed={item.value === period}
                onClick={() => updateFilter(item.value)}
                key={item.value}
              >
                {item.label}
              </button>
            ))}
          </div>
        </div>
        <div className="usage-filter-row">
          <span>工具</span>
          <div className="usage-segments is-scrollable">
            {TOOLS.map((item) => (
              <button
                type="button"
                className={item.value === tool ? 'is-active' : ''}
                aria-pressed={item.value === tool}
                onClick={() => updateFilter(period, item.value)}
                key={item.value}
              >
                {item.label}
              </button>
            ))}
          </div>
        </div>
      </section>

      <div className="message-stack usage-message" aria-live="polite">
        {error && (
          <div className="inline-message is-error" role="alert">
            <span>{error}</span>
            <button
              type="button"
              className="text-button"
              onClick={() => setReloadKey((value) => value + 1)}
            >
              重试
            </button>
          </div>
        )}
      </div>

      {loading && !summary && (
        <section className="usage-skeleton" aria-label="正在读取使用量">
          <span className="skeleton-line is-short" />
          <span className="skeleton-line is-hero" />
          <span className="skeleton-chart" />
        </section>
      )}

      {summary && (
        <>
          <section className="usage-hero" aria-labelledby="usage-total-title">
            <div className="usage-hero-heading">
              <div>
                <p className="section-kicker" id="usage-total-title">TOTAL</p>
              </div>
              <span>{formatTokenCount(summary.totals.event_count)} 次请求</span>
            </div>
            <strong
              aria-label={`${formatTokenCount(summary.totals.total_tokens)} Tokens`}
              title={`${formatTokenCount(summary.totals.total_tokens)} Tokens`}
            >
              {formatCompactTokenCount(summary.totals.total_tokens)}
            </strong>
            <p className="usage-unit">TOKENS 分布</p>
            <dl className="usage-token-details">
              {TOKEN_DETAILS.map((item) => (
                <div key={item.field}>
                  <dt>{item.label}</dt>
                  <dd
                    aria-label={`${formatTokenCount(summary.totals[item.field])} Tokens`}
                    title={formatTokenCount(summary.totals[item.field])}
                  >
                    {formatCompactTokenCount(summary.totals[item.field])}
                  </dd>
                </div>
              ))}
            </dl>
          </section>

          {summary.totals.event_count === 0 ? (
            <section className="empty-panel usage-empty">
              <span className="empty-symbol" aria-hidden="true">∿</span>
              <h2>这个时段还没有使用量</h2>
              <p>切换时间或工具后再看看，采集器上报的数据会显示在这里。</p>
            </section>
          ) : (
            <div className="usage-analysis-grid">
              <section className="usage-panel usage-tide-panel">
                <div className="section-heading">
                  <div>
                    <p className="section-kicker">DAILY TOKEN</p>
                    <h1>用量潮线</h1>
                  </div>
                </div>
                <UsageTideChart days={summary.timeline} />
              </section>

              <section className="usage-panel usage-model-panel">
                <div className="section-heading">
                  <div>
                    <p className="section-kicker">MODEL DEPTH</p>
                    <h2>模型用量</h2>
                  </div>
                  <span>{summary.models.length} 个模型</span>
                </div>
                <ol className="usage-model-list">
                  {summary.models.map((model) => (
                    <li key={model.model}>
                      <div className="usage-model-heading">
                        <span title={model.model}>{model.model}</span>
                        <strong
                          aria-label={`${formatTokenCount(model.total_tokens)} Tokens`}
                          title={formatTokenCount(model.total_tokens)}
                        >
                          {formatCompactTokenCount(model.total_tokens)}
                        </strong>
                      </div>
                      <div className="usage-model-track" aria-hidden="true">
                        <span
                          style={{
                            width: `${Math.max(
                              (model.total_tokens / largestModelTotal) * 100,
                              1.5,
                            )}%`,
                          }}
                        />
                      </div>
                      <small>
                        {formatTokenCount(model.event_count)} 次 · {
                          summary.totals.total_tokens > 0
                            ? `${(
                              (model.total_tokens / summary.totals.total_tokens) * 100
                            ).toFixed(1)}%`
                            : '0%'
                        }
                      </small>
                    </li>
                  ))}
                </ol>
              </section>
            </div>
          )}
        </>
      )}
    </main>
  );
}
