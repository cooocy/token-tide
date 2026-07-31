import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import {
  findTokenUsageOverview,
  findTokenUsageSummary,
  type TokenUsageOverview,
  type TokenUsageSummary,
  type TokenUsageTool,
} from '@/api/tokenUsage';
import ProductHeader from '@/components/ProductHeader';
import ProductNavigation from '@/components/ProductNavigation';
import UsageDistributionChart, {
  type UsageDistributionItem,
} from '@/components/UsageDistributionChart';
import UsageTideChart from '@/components/UsageTideChart';
import {
  formatCompactTokenCount,
  formatTokenCount,
} from '@/lib/display';

type UsagePeriod = 'today' | '7d' | '30d';
type ToolFilter = 'all' | TokenUsageTool;

const PERIODS: { value: UsagePeriod; label: string }[] = [
  { value: 'today', label: '今天' },
  { value: '7d', label: '7 天' },
  { value: '30d', label: '30 天' },
];
const PERIOD_DAYS: Record<UsagePeriod, number> = {
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
const TOOL_META: Record<TokenUsageTool, { label: string; color: string }> = {
  claude: { label: 'Claude', color: '#dca36a' },
  codex: { label: 'Codex', color: '#32d6c5' },
  opencode: { label: 'OpenCode', color: '#899cff' },
};
const MODEL_COLORS = [
  '#32d6c5',
  '#899cff',
  '#dca36a',
  '#e47f96',
  '#67b9e8',
] as const;
const OTHER_MODEL_COLOR = '#789b9a';
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

function queryRange(period: UsagePeriod): {
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

function toolDistribution(overview: TokenUsageOverview): UsageDistributionItem[] {
  return overview.tools.map((item) => ({
    id: item.tool,
    label: TOOL_META[item.tool].label,
    value: item.total_tokens,
    color: TOOL_META[item.tool].color,
  }));
}

function modelDistribution(overview: TokenUsageOverview): UsageDistributionItem[] {
  const models = overview.models.filter((item) => item.total_tokens > 0);
  const leading = models.slice(0, MODEL_COLORS.length);
  const items: UsageDistributionItem[] = leading.map((item, index) => ({
    id: item.model,
    label: item.model,
    value: item.total_tokens,
    color: MODEL_COLORS[index],
  }));
  const otherValue = models
    .slice(MODEL_COLORS.length)
    .reduce((sum, item) => sum + item.total_tokens, 0);
  if (otherValue > 0) {
    items.push({
      id: 'other-models',
      label: '其他',
      value: otherValue,
      color: OTHER_MODEL_COLOR,
    });
  }
  return items;
}

export default function TokenUsagePage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const period = isPeriod(searchParams.get('period'))
    ? searchParams.get('period') as UsagePeriod
    : '7d';
  const tool = isTool(searchParams.get('tool'))
    ? searchParams.get('tool') as ToolFilter
    : 'all';
  const [overview, setOverview] = useState<TokenUsageOverview | null>(null);
  const [summary, setSummary] = useState<TokenUsageSummary | null>(null);
  const [overviewLoading, setOverviewLoading] = useState(true);
  const [summaryLoading, setSummaryLoading] = useState(true);
  const [overviewError, setOverviewError] = useState<string | null>(null);
  const [summaryError, setSummaryError] = useState<string | null>(null);
  const [overviewReloadKey, setOverviewReloadKey] = useState(0);
  const [summaryReloadKey, setSummaryReloadKey] = useState(0);
  const overviewRequestId = useRef(0);
  const summaryRequestId = useRef(0);

  const loadOverview = useCallback(async (): Promise<void> => {
    const currentRequestId = overviewRequestId.current + 1;
    overviewRequestId.current = currentRequestId;
    setOverviewLoading(true);
    setOverviewError(null);
    try {
      const data = await findTokenUsageOverview();
      if (overviewRequestId.current === currentRequestId) {
        setOverview(data);
      }
    } catch (loadError) {
      if (overviewRequestId.current === currentRequestId) {
        setOverview(null);
        setOverviewError(
          loadError instanceof Error ? loadError.message : '累计用量加载失败',
        );
      }
    } finally {
      if (overviewRequestId.current === currentRequestId) {
        setOverviewLoading(false);
      }
    }
  }, []);

  const loadSummary = useCallback(async (): Promise<void> => {
    const currentRequestId = summaryRequestId.current + 1;
    summaryRequestId.current = currentRequestId;
    setSummaryLoading(true);
    setSummaryError(null);
    try {
      const data = await findTokenUsageSummary({
        ...queryRange(period),
        tool: tool === 'all' ? undefined : tool,
      });
      if (summaryRequestId.current === currentRequestId) {
        setSummary(data);
      }
    } catch (loadError) {
      if (summaryRequestId.current === currentRequestId) {
        setSummary(null);
        setSummaryError(
          loadError instanceof Error ? loadError.message : '用量分析加载失败',
        );
      }
    } finally {
      if (summaryRequestId.current === currentRequestId) {
        setSummaryLoading(false);
      }
    }
  }, [period, tool]);

  useEffect(() => {
    void loadOverview();
    return () => {
      overviewRequestId.current += 1;
    };
  }, [loadOverview, overviewReloadKey]);

  useEffect(() => {
    void loadSummary();
    return () => {
      summaryRequestId.current += 1;
    };
  }, [loadSummary, summaryReloadKey]);

  const updateFilter = (
    nextPeriod: UsagePeriod = period,
    nextTool: ToolFilter = tool,
  ): void => {
    if (nextPeriod === period && nextTool === tool) {
      return;
    }
    setSummaryLoading(true);
    setSummaryError(null);
    setSummary(null);
    setSearchParams({ period: nextPeriod, tool: nextTool });
  };

  const toolItems = useMemo(
    () => overview ? toolDistribution(overview) : [],
    [overview],
  );
  const modelItems = useMemo(
    () => overview ? modelDistribution(overview) : [],
    [overview],
  );
  const usedToolCount = overview?.tools.filter(
    (item) => item.total_tokens > 0,
  ).length ?? 0;
  const usedModelCount = overview?.models.filter(
    (item) => item.total_tokens > 0,
  ).length ?? 0;
  const largestModelTotal = Math.max(
    ...(summary?.models.map((model) => model.total_tokens) ?? []),
    1,
  );

  return (
    <main
      className="app-shell usage-page"
      aria-busy={overviewLoading || summaryLoading}
    >
      <ProductHeader />
      <ProductNavigation />

      <section className="usage-hero" aria-labelledby="usage-title">
        <div className="section-heading usage-overview-heading">
          <div>
            <p className="section-kicker">ALL-TIME OVERVIEW</p>
            <h1 id="usage-title">Token 用量</h1>
          </div>
        </div>

        <div className="message-stack usage-message" aria-live="polite">
          {overviewError && (
            <div className="inline-message is-error" role="alert">
              <span>{overviewError}</span>
              <button
                type="button"
                className="text-button"
                onClick={() => setOverviewReloadKey((value) => value + 1)}
              >
                重试
              </button>
            </div>
          )}
        </div>

        {overviewLoading && !overview && (
          <div className="usage-overview-skeleton" aria-label="正在读取累计用量">
            <span className="skeleton-line is-hero" />
            <span className="skeleton-chart" />
            <span className="skeleton-chart" />
          </div>
        )}

        {overview && (
          <div className="usage-overview-grid">
            <section
              className="usage-total-reading"
              aria-labelledby="usage-total-title"
            >
              <p className="section-kicker">TOTAL TOKENS</p>
              <h2 id="usage-total-title">累计总用量</h2>
              <div className="usage-total-metric-row">
                <strong
                  aria-label={`${formatTokenCount(
                    overview.totals.total_tokens,
                  )} Tokens`}
                >
                  {formatCompactTokenCount(overview.totals.total_tokens)}
                </strong>
                <div className="usage-total-meta">
                  <span className="usage-total-exact">
                    {formatTokenCount(overview.totals.total_tokens)} Tokens
                  </span>
                  <span className="usage-request-count">
                    {formatTokenCount(overview.totals.event_count)} 次请求
                  </span>
                </div>
              </div>
            </section>

            <UsageDistributionChart
              kicker="TOOL SHARE"
              title="按工具"
              items={toolItems}
              centerValue={formatTokenCount(usedToolCount)}
              centerLabel="个工具"
            />
            <UsageDistributionChart
              kicker="MODEL SHARE"
              title="按模型"
              items={modelItems}
              centerValue={formatTokenCount(usedModelCount)}
              centerLabel="个模型"
            />
          </div>
        )}
      </section>

      <section className="usage-analysis" aria-labelledby="usage-analysis-title">
        <div className="section-heading usage-analysis-heading">
          <div>
            <p className="section-kicker">FILTERED ANALYSIS</p>
            <h2 id="usage-analysis-title">用量分析</h2>
          </div>
          {summary && (
            <span>{formatTokenCount(summary.totals.event_count)} 次请求</span>
          )}
        </div>

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

        <div className="message-stack usage-message" aria-live="polite">
          {summaryError && (
            <div className="inline-message is-error" role="alert">
              <span>{summaryError}</span>
              <button
                type="button"
                className="text-button"
                onClick={() => setSummaryReloadKey((value) => value + 1)}
              >
                重试
              </button>
            </div>
          )}
        </div>

        {summaryLoading && !summary && (
          <div className="usage-skeleton" aria-label="正在读取用量分析">
            <span className="skeleton-line is-short" />
            <span className="skeleton-chart" />
          </div>
        )}

        {summary && (
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
                      aria-label={`${
                        formatTokenCount(summary.totals[item.field])
                      } Tokens`}
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
                      <p className="section-kicker">DAILY USAGE</p>
                      <h2>每日用量</h2>
                    </div>
                  </div>
                  <UsageTideChart days={summary.timeline} />
                </section>

                <section className="usage-panel usage-model-panel">
                  <div className="section-heading">
                    <div>
                      <p className="section-kicker">MODEL USAGE</p>
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
                            aria-label={`${
                              formatTokenCount(model.total_tokens)
                            } Tokens`}
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
                                (
                                  model.total_tokens
                                  / summary.totals.total_tokens
                                ) * 100
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
      </section>
    </main>
  );
}
