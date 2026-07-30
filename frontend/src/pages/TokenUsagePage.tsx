import { useCallback, useEffect, useRef, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import {
  findTokenUsageSummary,
  findTokenUsageTotals,
  type TokenUsageSummary,
  type TokenUsageTool,
  type TokenUsageTotals,
} from '@/api/tokenUsage';
import ProductNavigation from '@/components/ProductNavigation';
import ProductHeader from '@/components/ProductHeader';
import UsageTideChart from '@/components/UsageTideChart';
import {
  formatCompactTokenCount,
  formatTokenCount,
} from '@/lib/display';

type UsagePeriod = 'today' | '7d' | '30d' | 'total';
type RangedUsagePeriod = Exclude<UsagePeriod, 'total'>;
type ToolFilter = 'all' | TokenUsageTool;

const PERIODS: { value: UsagePeriod; label: string }[] = [
  { value: 'today', label: '今天' },
  { value: '7d', label: '7 天' },
  { value: '30d', label: '30 天' },
  { value: 'total', label: '总计' },
];
const PERIOD_DAYS: Record<RangedUsagePeriod, number> = {
  today: 1,
  '7d': 7,
  '30d': 30,
};
const TOOLS: { value: ToolFilter; label: string }[] = [
  { value: 'all', label: '全部' },
  { value: 'claude', label: 'Claude' },
  { value: 'codex', label: 'Codex' },
  { value: 'opencode', label: 'OpenCode' },
];
const TOKEN_DETAILS = [
  { field: 'input_tokens', label: '输入', prominence: 'primary' },
  { field: 'output_tokens', label: '输出', prominence: 'primary' },
  { field: 'cache_creation_tokens', label: '缓存写入', prominence: 'secondary' },
  { field: 'cache_read_tokens', label: '缓存读取', prominence: 'secondary' },
  { field: 'reasoning_tokens', label: '推理', prominence: 'secondary' },
] as const;

function isPeriod(value: string | null): value is UsagePeriod {
  return PERIODS.some((period) => period.value === value);
}

function isTool(value: string | null): value is ToolFilter {
  return TOOLS.some((tool) => tool.value === value);
}

function queryRange(period: RangedUsagePeriod): {
  startTime: string;
  endTime: string;
  timezoneOffsetMinutes: number;
} {
  const now = new Date();
  const days = PERIOD_DAYS[period];
  const start = new Date(now);
  start.setHours(0, 0, 0, 0);
  start.setDate(start.getDate() - (days - 1));
  return {
    startTime: start.toISOString(),
    endTime: now.toISOString(),
    timezoneOffsetMinutes: -now.getTimezoneOffset(),
  };
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
  const [historicalTotals, setHistoricalTotals] =
    useState<TokenUsageTotals | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);
  const requestId = useRef(0);

  const loadUsage = useCallback(async (): Promise<void> => {
    const currentRequestId = requestId.current + 1;
    requestId.current = currentRequestId;
    setLoading(true);
    setError(null);
    setSummary(null);
    setHistoricalTotals(null);
    try {
      const selectedTool = tool === 'all' ? undefined : tool;
      if (period === 'total') {
        const data = await findTokenUsageTotals({
          tool: selectedTool,
        });
        if (requestId.current === currentRequestId) {
          setHistoricalTotals(data);
        }
      } else {
        const range = queryRange(period);
        const data = await findTokenUsageSummary({
          ...range,
          tool: selectedTool,
        });
        if (requestId.current === currentRequestId) {
          setSummary(data);
        }
      }
    } catch (loadError) {
      if (requestId.current === currentRequestId) {
        setSummary(null);
        setHistoricalTotals(null);
        setError(
          loadError instanceof Error ? loadError.message : '使用量加载失败',
        );
      }
    } finally {
      if (requestId.current === currentRequestId) {
        setLoading(false);
      }
    }
  }, [period, tool]);

  useEffect(() => {
    void loadUsage();
    return () => {
      requestId.current += 1;
    };
  }, [loadUsage, reloadKey]);

  const updateFilter = (
    nextPeriod: UsagePeriod = period,
    nextTool: ToolFilter = tool,
  ): void => {
    if (nextPeriod === period && nextTool === tool) {
      return;
    }
    setLoading(true);
    setError(null);
    setSummary(null);
    setHistoricalTotals(null);
    setSearchParams({ period: nextPeriod, tool: nextTool });
  };

  const totals = period === 'total' ? historicalTotals : summary?.totals;
  const largestModelTotal = Math.max(
    ...(summary?.models.map((model) => model.total_tokens) ?? []),
    1,
  );

  return (
    <main className="app-shell usage-page" aria-busy={loading}>
      <ProductHeader />

      <ProductNavigation />

      <section className="usage-hero" aria-labelledby="usage-title">
        <div className="usage-hero-heading">
          <div>
            <p className="section-kicker">TOKEN USAGE</p>
            <h1 id="usage-title">Token 用量</h1>
          </div>
          {totals && (
            <span>{formatTokenCount(totals.event_count)} 次请求</span>
          )}
        </div>

        {totals && (
          <div className="usage-total">
            <strong
              aria-label={`${formatTokenCount(totals.total_tokens)} Tokens`}
            >
              {formatCompactTokenCount(totals.total_tokens)}
            </strong>
            <p>{formatTokenCount(totals.total_tokens)} Tokens</p>
          </div>
        )}

        <div className="usage-filter-panel" aria-label="使用量筛选">
          <div className="usage-filter-row">
            <span>时间</span>
            <div className="usage-segments is-grid is-periods">
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
            <div className="usage-segments is-grid">
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

      {loading && !totals && (
        <section className="usage-skeleton" aria-label="正在读取使用量">
          <span className="skeleton-line is-short" />
          <span className="skeleton-line is-hero" />
          <span className="skeleton-chart" />
        </section>
      )}

      {totals && (
        <>
          <section
            className="usage-token-breakdown"
            aria-labelledby="usage-breakdown-title"
          >
            <div className="section-heading">
              <div>
                <p className="section-kicker">TOKEN BREAKDOWN</p>
                <h2 id="usage-breakdown-title">Token 分布</h2>
              </div>
            </div>
            <dl className="usage-token-details">
              {TOKEN_DETAILS.map((item) => (
                <div className={`is-${item.prominence}`} key={item.field}>
                  <dt>{item.label}</dt>
                  <dd
                    aria-label={`${formatTokenCount(totals[item.field])} Tokens`}
                    title={formatTokenCount(totals[item.field])}
                  >
                    {formatCompactTokenCount(totals[item.field])}
                  </dd>
                </div>
              ))}
            </dl>
          </section>

          {totals.event_count === 0 ? (
            <section className="empty-panel usage-empty">
              <span className="empty-symbol" aria-hidden="true">∿</span>
              <h2>
                {period === 'total'
                  ? '还没有累计用量'
                  : '这个时段还没有使用量'}
              </h2>
              <p>
                {period === 'total'
                  ? '采集器上报的数据会累计显示在这里。'
                  : '切换时间或工具后再看看，采集器上报的数据会显示在这里。'}
              </p>
            </section>
          ) : summary ? (
            <div className="usage-analysis-grid">
              <section className="usage-panel usage-tide-panel">
                <div className="section-heading">
                  <div>
                    <p className="section-kicker">DAILY USAGE</p>
                    <h2>每日用量</h2>
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
          ) : null}
        </>
      )}
    </main>
  );
}
