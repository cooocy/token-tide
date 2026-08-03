import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import {
  findTokenUsageOverview,
  findTokenUsageSummary,
  type TokenUsageOverview,
  type TokenUsageSummary,
  type TokenUsageTool,
  type TokenUsageTotals,
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
type UsageView = 'today' | 'total' | 'analysis';

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
  { value: 'pi', label: 'Pi' },
];
const TOOL_META: Record<TokenUsageTool, { label: string; color: string }> = {
  claude: { label: 'Claude', color: '#dca36a' },
  codex: { label: 'Codex', color: '#32d6c5' },
  opencode: { label: 'OpenCode', color: '#899cff' },
  pi: { label: 'Pi', color: '#e47f96' },
};
const USAGE_VIEWS: {
  value: UsageView;
  kicker: string;
  label: string;
}[] = [
  { value: 'today', kicker: 'TODAY', label: '今日' },
  { value: 'total', kicker: 'ALL-TIME', label: '总计' },
  { value: 'analysis', kicker: 'ANALYSIS', label: '用量分析' },
];
const MODEL_COLORS = [
  '#c4a7ff',
  '#b8e45c',
  '#ffd166',
  '#4cc9f0',
  '#ff6b6b',
] as const;
const OTHER_MODEL_COLOR = '#65757c';
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

function isUsageView(value: string | null): value is UsageView {
  return USAGE_VIEWS.some((view) => view.value === value);
}

function resolveUsageView(
  requestedView: string | null,
  hasAnalysisFilters: boolean,
): UsageView {
  if (isUsageView(requestedView)) {
    return requestedView;
  }
  if (requestedView === null && hasAnalysisFilters) {
    return 'analysis';
  }
  return 'today';
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

function toolDistribution(
  usage: Pick<TokenUsageOverview, 'tools'>,
): UsageDistributionItem[] {
  return usage.tools.map((item) => ({
    id: item.tool,
    label: TOOL_META[item.tool].label,
    value: item.total_tokens,
    color: TOOL_META[item.tool].color,
  }));
}

function modelDistribution(
  usage: Pick<TokenUsageOverview, 'models'>,
): UsageDistributionItem[] {
  const models = usage.models.filter((item) => item.total_tokens > 0);
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

interface UsageTokenReadingProps {
  className?: string;
  detailsLabel: string;
  kicker: string;
  title: string;
  titleId: string;
  totals: TokenUsageTotals;
}

function UsageTokenReading({
  className,
  detailsLabel,
  kicker,
  title,
  titleId,
  totals,
}: UsageTokenReadingProps) {
  return (
    <section
      className={`usage-total-reading${className ? ` ${className}` : ''}`}
      aria-labelledby={titleId}
    >
      <p className="section-kicker">{kicker}</p>
      <h2 id={titleId}>{title}</h2>
      <div className="usage-total-body">
        <div className="usage-total-metric-row">
          <strong
            aria-label={`${formatTokenCount(totals.total_tokens)} Tokens`}
          >
            {formatCompactTokenCount(totals.total_tokens)}
          </strong>
          <div className="usage-total-meta">
            <span className="usage-total-exact">
              {formatTokenCount(totals.total_tokens)} Tokens
            </span>
            <span className="usage-request-count">
              {formatTokenCount(totals.event_count)} 次请求
            </span>
          </div>
        </div>

        <div className="usage-lifetime-breakdown">
          <p>{detailsLabel}</p>
          <dl>
            {TOKEN_DETAILS.map((item) => (
              <div className={`is-${item.prominence}`} key={item.field}>
                <dt>{item.label}</dt>
                <dd
                  aria-label={`${
                    formatTokenCount(totals[item.field])
                  } Tokens`}
                  title={formatTokenCount(totals[item.field])}
                >
                  {formatCompactTokenCount(totals[item.field])}
                </dd>
              </div>
            ))}
          </dl>
        </div>
      </div>
    </section>
  );
}

export default function TokenUsagePage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const requestedView = searchParams.get('view');
  const view = resolveUsageView(
    requestedView,
    searchParams.has('period') || searchParams.has('tool'),
  );
  const period = isPeriod(searchParams.get('period'))
    ? searchParams.get('period') as UsagePeriod
    : '7d';
  const tool = isTool(searchParams.get('tool'))
    ? searchParams.get('tool') as ToolFilter
    : 'all';
  const [todaySummary, setTodaySummary] = useState<TokenUsageSummary | null>(
    null,
  );
  const [overview, setOverview] = useState<TokenUsageOverview | null>(null);
  const [summary, setSummary] = useState<TokenUsageSummary | null>(null);
  const [todayLoading, setTodayLoading] = useState(false);
  const [overviewLoading, setOverviewLoading] = useState(false);
  const [summaryLoading, setSummaryLoading] = useState(false);
  const [todayError, setTodayError] = useState<string | null>(null);
  const [overviewError, setOverviewError] = useState<string | null>(null);
  const [summaryError, setSummaryError] = useState<string | null>(null);
  const todayRequestId = useRef(0);
  const overviewRequestId = useRef(0);
  const summaryRequestId = useRef(0);
  const summaryDataKey = useRef<string | null>(null);
  const toolSegmentsRef = useRef<HTMLDivElement | null>(null);
  const activeToolButtonRef = useRef<HTMLButtonElement | null>(null);
  const summaryQueryKey = `${period}:${tool}`;

  const loadTodaySummary = useCallback(async (): Promise<void> => {
    const currentRequestId = todayRequestId.current + 1;
    todayRequestId.current = currentRequestId;
    setTodayLoading(true);
    setTodayError(null);
    try {
      const data = await findTokenUsageSummary(queryRange('today'));
      if (todayRequestId.current === currentRequestId) {
        setTodaySummary(data);
      }
    } catch (loadError) {
      if (todayRequestId.current === currentRequestId) {
        setTodaySummary(null);
        setTodayError(
          loadError instanceof Error ? loadError.message : '今日用量加载失败',
        );
      }
    } finally {
      if (todayRequestId.current === currentRequestId) {
        setTodayLoading(false);
      }
    }
  }, []);

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
    summaryDataKey.current = summaryQueryKey;
    setSummaryLoading(true);
    setSummaryError(null);
    setSummary(null);
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
  }, [period, summaryQueryKey, tool]);

  useEffect(() => {
    if (requestedView === view) {
      return;
    }
    const nextSearchParams = new URLSearchParams(searchParams);
    nextSearchParams.set('view', view);
    setSearchParams(nextSearchParams, { replace: true });
  }, [requestedView, searchParams, setSearchParams, view]);

  useEffect(() => {
    if (view !== 'today' || todaySummary || todayError || todayLoading) {
      return;
    }
    void loadTodaySummary();
  }, [loadTodaySummary, todayError, todayLoading, todaySummary, view]);

  useEffect(() => {
    if (view !== 'total' || overview || overviewError || overviewLoading) {
      return;
    }
    void loadOverview();
  }, [loadOverview, overview, overviewError, overviewLoading, view]);

  useEffect(() => {
    const hasCurrentState = summaryDataKey.current === summaryQueryKey
      && Boolean(summary || summaryError || summaryLoading);
    if (view !== 'analysis' || hasCurrentState) {
      return;
    }
    void loadSummary();
  }, [
    loadSummary,
    summary,
    summaryError,
    summaryLoading,
    summaryQueryKey,
    view,
  ]);

  useEffect(() => {
    return () => {
      todayRequestId.current += 1;
      overviewRequestId.current += 1;
      summaryRequestId.current += 1;
    };
  }, []);

  useEffect(() => {
    const container = toolSegmentsRef.current;
    const activeButton = activeToolButtonRef.current;
    if (
      !container
      || !activeButton
      || !window.matchMedia('(max-width: 420px)').matches
    ) {
      return;
    }

    const containerBounds = container.getBoundingClientRect();
    const buttonBounds = activeButton.getBoundingClientRect();
    if (
      buttonBounds.left >= containerBounds.left
      && buttonBounds.right <= containerBounds.right
    ) {
      return;
    }

    const prefersReducedMotion = window.matchMedia(
      '(prefers-reduced-motion: reduce)',
    ).matches;
    container.scrollTo({
      left: container.scrollLeft
        + buttonBounds.left
        - containerBounds.left
        - (container.clientWidth - buttonBounds.width) / 2,
      behavior: prefersReducedMotion ? 'auto' : 'smooth',
    });
  }, [tool, view]);

  const updateFilter = (
    nextPeriod: UsagePeriod = period,
    nextTool: ToolFilter = tool,
  ): void => {
    if (nextPeriod === period && nextTool === tool) {
      return;
    }
    summaryRequestId.current += 1;
    summaryDataKey.current = null;
    setSummaryLoading(false);
    setSummaryError(null);
    setSummary(null);
    const nextSearchParams = new URLSearchParams(searchParams);
    nextSearchParams.set('view', 'analysis');
    nextSearchParams.set('period', nextPeriod);
    nextSearchParams.set('tool', nextTool);
    setSearchParams(nextSearchParams);
  };

  const viewHref = (nextView: UsageView): string => {
    const nextSearchParams = new URLSearchParams(searchParams);
    nextSearchParams.set('view', nextView);
    return `/usage?${nextSearchParams.toString()}`;
  };

  const todayToolItems = useMemo(
    () => todaySummary ? toolDistribution(todaySummary) : [],
    [todaySummary],
  );
  const todayModelItems = useMemo(
    () => todaySummary ? modelDistribution(todaySummary) : [],
    [todaySummary],
  );
  const totalToolItems = useMemo(
    () => overview ? toolDistribution(overview) : [],
    [overview],
  );
  const totalModelItems = useMemo(
    () => overview ? modelDistribution(overview) : [],
    [overview],
  );
  const todayUsedToolCount = todaySummary?.tools.filter(
    (item) => item.total_tokens > 0,
  ).length ?? 0;
  const todayUsedModelCount = todaySummary?.models.filter(
    (item) => item.total_tokens > 0,
  ).length ?? 0;
  const totalUsedToolCount = overview?.tools.filter(
    (item) => item.total_tokens > 0,
  ).length ?? 0;
  const totalUsedModelCount = overview?.models.filter(
    (item) => item.total_tokens > 0,
  ).length ?? 0;
  const displayedSummary = summaryDataKey.current === summaryQueryKey
    ? summary
    : null;
  const displayedSummaryError = summaryDataKey.current === summaryQueryKey
    ? summaryError
    : null;
  const largestModelTotal = Math.max(
    ...(displayedSummary?.models.map((model) => model.total_tokens) ?? []),
    1,
  );
  const activeLoading = view === 'today'
    ? todayLoading || (!todaySummary && !todayError)
    : view === 'total'
      ? overviewLoading || (!overview && !overviewError)
      : summaryLoading || (!displayedSummary && !displayedSummaryError);

  return (
    <main
      className="app-shell usage-page"
      aria-busy={activeLoading}
    >
      <ProductHeader />
      <ProductNavigation />

      <h1 className="usage-page-title">Token 用量</h1>
      <nav className="usage-view-navigation" aria-label="Token 用量视图">
        <div className="usage-view-rail">
          {USAGE_VIEWS.map((item) => (
            <Link
              id={`usage-view-${item.value}`}
              className={item.value === view ? 'is-active' : undefined}
              aria-current={item.value === view ? 'page' : undefined}
              to={viewHref(item.value)}
              key={item.value}
            >
              <span>{item.kicker}</span>
              <strong>{item.label}</strong>
            </Link>
          ))}
        </div>
      </nav>

      {view === 'today' && (
        <section
          className="usage-view-panel usage-today"
          aria-labelledby="usage-view-today"
        >
          {todayError && (
            <div
              className="message-stack usage-message"
              aria-live="polite"
            >
              <div className="inline-message is-error" role="alert">
                <span>{todayError}</span>
                <button
                  type="button"
                  className="text-button"
                  onClick={() => void loadTodaySummary()}
                >
                  重试
                </button>
              </div>
            </div>
          )}

          {!todaySummary && !todayError && (
            <div
              className="usage-overview-skeleton"
              aria-label="正在读取今日用量"
            >
              <span className="skeleton-line is-hero" />
              <span className="skeleton-chart" />
              <span className="skeleton-chart" />
            </div>
          )}

          {todaySummary && (
            <div className="usage-overview-grid">
              <UsageTokenReading
                detailsLabel="今日明细"
                kicker="TOKEN BREAKDOWN"
                title="Tokens 分布"
                titleId="usage-today-title"
                totals={todaySummary.totals}
              />

              <UsageDistributionChart
                kicker="TOOL SHARE"
                title="按工具"
                items={todayToolItems}
                centerValue={formatTokenCount(todayUsedToolCount)}
                centerLabel="个工具"
              />
              <UsageDistributionChart
                kicker="MODEL SHARE"
                title="按模型"
                items={todayModelItems}
                centerValue={formatTokenCount(todayUsedModelCount)}
                centerLabel="个模型"
              />
            </div>
          )}
        </section>
      )}

      {view === 'total' && (
        <section
          className="usage-view-panel usage-hero"
          aria-labelledby="usage-view-total"
        >
          {overviewError && (
            <div
              className="message-stack usage-message"
              aria-live="polite"
            >
              <div className="inline-message is-error" role="alert">
                <span>{overviewError}</span>
                <button
                  type="button"
                  className="text-button"
                  onClick={() => void loadOverview()}
                >
                  重试
                </button>
              </div>
            </div>
          )}

          {!overview && !overviewError && (
            <div className="usage-overview-skeleton" aria-label="正在读取累计用量">
              <span className="skeleton-line is-hero" />
              <span className="skeleton-chart" />
              <span className="skeleton-chart" />
            </div>
          )}

          {overview && (
            <div className="usage-overview-grid">
              <UsageTokenReading
                detailsLabel="累计明细"
                kicker="TOKEN BREAKDOWN"
                title="Tokens 分布"
                titleId="usage-total-title"
                totals={overview.totals}
              />

              <UsageDistributionChart
                kicker="TOOL SHARE"
                title="按工具"
                items={totalToolItems}
                centerValue={formatTokenCount(totalUsedToolCount)}
                centerLabel="个工具"
              />
              <UsageDistributionChart
                kicker="MODEL SHARE"
                title="按模型"
                items={totalModelItems}
                centerValue={formatTokenCount(totalUsedModelCount)}
                centerLabel="个模型"
              />
            </div>
          )}
        </section>
      )}

      {view === 'analysis' && (
        <section
          className="usage-view-panel usage-analysis"
          aria-labelledby="usage-view-analysis"
        >
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
              <div
                className="usage-segments is-grid is-tools"
                ref={toolSegmentsRef}
              >
                {TOOLS.map((item) => (
                  <button
                    type="button"
                    className={item.value === tool ? 'is-active' : ''}
                    aria-pressed={item.value === tool}
                    onClick={() => updateFilter(period, item.value)}
                    ref={item.value === tool ? activeToolButtonRef : undefined}
                    key={item.value}
                  >
                    {item.label}
                  </button>
                ))}
              </div>
            </div>
          </div>

          {displayedSummaryError && (
            <div
              className="message-stack usage-message"
              aria-live="polite"
            >
              <div className="inline-message is-error" role="alert">
                <span>{displayedSummaryError}</span>
                <button
                  type="button"
                  className="text-button"
                  onClick={() => void loadSummary()}
                >
                  重试
                </button>
              </div>
            </div>
          )}

          {!displayedSummary && !displayedSummaryError && (
            <div className="usage-skeleton" aria-label="正在读取用量分析">
              <span className="skeleton-line is-short" />
              <span className="skeleton-chart" />
            </div>
          )}

          {displayedSummary && (
            <>
              <UsageTokenReading
                className="usage-period-reading"
                detailsLabel="区间明细"
                kicker="PERIOD BREAKDOWN"
                title="区间分布"
                titleId="usage-breakdown-title"
                totals={displayedSummary.totals}
              />

              {displayedSummary.totals.event_count === 0 ? (
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
                    <UsageTideChart days={displayedSummary.timeline} />
                  </section>

                  <section className="usage-panel usage-model-panel">
                    <div className="section-heading">
                      <div>
                        <p className="section-kicker">MODEL USAGE</p>
                        <h2>模型用量</h2>
                      </div>
                      <span>{displayedSummary.models.length} 个模型</span>
                    </div>
                    <ol className="usage-model-list">
                      {displayedSummary.models.map((model) => (
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
                                  (
                                    model.total_tokens / largestModelTotal
                                  ) * 100,
                                  1.5,
                                )}%`,
                              }}
                            />
                          </div>
                          <small>
                            {formatTokenCount(model.event_count)} 次 · {
                              displayedSummary.totals.total_tokens > 0
                                ? `${(
                                  (
                                    model.total_tokens
                                    / displayedSummary.totals.total_tokens
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
      )}
    </main>
  );
}
