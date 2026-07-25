import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  findBalances,
  refreshBalances,
  type ProviderBalance,
  type ProviderStatus,
} from '@/api/balance';
import {
  formatAmount,
  formatProviderMark,
  formatProviderName,
  formatRelativeTime,
} from '@/lib/display';

interface StatusMeta {
  className: string;
  label: string;
}

const STATUS_META: Record<ProviderStatus, StatusMeta> = {
  SUCCESS: { className: 'is-success', label: '运行正常' },
  RUNNING: { className: 'is-running', label: '正在更新' },
  FAILED: { className: 'is-failed', label: '更新失败' },
  NEVER_REFRESHED: { className: 'is-idle', label: '等待首次更新' },
};

function RefreshIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M20 11a8 8 0 1 0-2.34 5.66M20 5v6h-6" />
    </svg>
  );
}

function ArrowIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="m9 18 6-6-6-6" />
    </svg>
  );
}

export default function DashboardPage() {
  const [providers, setProviders] = useState<ProviderBalance[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const loadBalances = useCallback(async (preserveCurrent = false): Promise<boolean> => {
    try {
      setError(null);
      setProviders(await findBalances());
      return true;
    } catch (loadError) {
      if (!preserveCurrent) {
        setProviders(null);
      }
      setError(loadError instanceof Error ? loadError.message : '余额加载失败');
      return false;
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadBalances();
  }, [loadBalances]);

  const handleRefresh = async (): Promise<void> => {
    setRefreshing(true);
    setError(null);
    setNotice(null);
    try {
      const results = await refreshBalances();
      const loaded = await loadBalances(true);
      if (loaded) {
        const failedCount = results.filter((result) => result.status === 'FAILED').length;
        setNotice(
          failedCount > 0
            ? `${results.length - failedCount} 个平台已更新，${failedCount} 个失败`
            : `${results.length} 个平台已更新`,
        );
      }
    } catch (refreshError) {
      setError(refreshError instanceof Error ? refreshError.message : '刷新失败');
    } finally {
      setRefreshing(false);
    }
  };

  const summary = useMemo(() => {
    const items = providers ?? [];
    const healthyCount = items.filter((provider) => provider.status === 'SUCCESS').length;
    const latestSuccess = items
      .map((provider) => provider.last_success_at)
      .filter((value): value is string => value !== null)
      .sort((left, right) => new Date(right).getTime() - new Date(left).getTime())[0] ?? null;
    return { healthyCount, latestSuccess, total: items.length };
  }, [providers]);

  return (
    <main className="app-shell dashboard-page" aria-busy={loading || refreshing}>
      <header className="dashboard-header">
        <div className="brand-lockup">
          <span className="brand-mark" aria-hidden="true">
            T
          </span>
          <div>
            <p className="brand-name">TokenTide</p>
            <p className="brand-caption">AI 账户余额潮位</p>
          </div>
        </div>
        {providers && providers.length > 0 && (
          <div className="health-summary">
            <span className="health-pulse" aria-hidden="true" />
            {summary.healthyCount} / {summary.total} 正常
          </div>
        )}
      </header>

      <section className="overview-heading" aria-labelledby="overview-title">
        <p className="section-kicker">CURRENT TIDE</p>
        <h1 id="overview-title">平台余额</h1>
        <p>{formatRelativeTime(summary.latestSuccess)}</p>
      </section>

      <div className="message-stack" aria-live="polite">
        {error && (
          <div className="inline-message is-error" role="alert">
            <span>{error}</span>
            {!providers && (
              <button type="button" className="text-button" onClick={() => void loadBalances()}>
                重试
              </button>
            )}
          </div>
        )}
        {notice && <div className="inline-message is-success">{notice}</div>}
      </div>

      {loading && !providers && (
        <section className="provider-stack" aria-label="正在读取平台余额">
          {[0, 1, 2].map((item) => (
            <div className="provider-card skeleton-card" key={item}>
              <span className="skeleton-line is-short" />
              <span className="skeleton-line is-amount" />
              <span className="skeleton-line" />
            </div>
          ))}
        </section>
      )}

      {!loading && !error && providers?.length === 0 && (
        <section className="empty-panel">
          <span className="empty-symbol" aria-hidden="true">
            ∿
          </span>
          <h2>还没有平台</h2>
          <p>在服务配置中启用平台后，余额会出现在这里。</p>
        </section>
      )}

      {providers && providers.length > 0 && (
        <section className="provider-stack" aria-label="平台余额列表">
          {providers.map((provider) => {
            const status = STATUS_META[provider.status];
            const firstCurrency = provider.balances[0]?.currency;
            const historyUrl = `/providers/${provider.provider}/history${
              firstCurrency ? `?currency=${encodeURIComponent(firstCurrency)}` : ''
            }`;

            return (
              <article
                className={`provider-card ${status.className}`}
                key={provider.provider}
              >
                <span className="tide-node" aria-hidden="true" />
                <div className="provider-card-heading">
                  <div className="provider-identity">
                    <span className="provider-mark" aria-hidden="true">
                      {formatProviderMark(provider.provider)}
                    </span>
                    <div>
                      <h2>{formatProviderName(provider.provider)}</h2>
                      <p className="provider-status">
                        <span aria-hidden="true" />
                        {status.label}
                      </p>
                    </div>
                  </div>
                  <Link
                    className="history-link"
                    to={historyUrl}
                    aria-label={`查看 ${formatProviderName(provider.provider)} 余额历史`}
                  >
                    <ArrowIcon />
                  </Link>
                </div>

                <div className="balance-grid">
                  {provider.balances.length === 0 && (
                    <p className="empty-copy">还没有可用的余额快照</p>
                  )}
                  {provider.balances.map((balance) => (
                    <div className="balance-value" key={balance.currency}>
                      <span>{balance.currency}</span>
                      <strong>{formatAmount(balance.available_amount)}</strong>
                    </div>
                  ))}
                </div>

                <div className="provider-meta">
                  <span>{formatRelativeTime(provider.last_success_at)}</span>
                  {provider.balances.some((balance) => !balance.is_available) && (
                    <span className="availability-note">平台暂不可用</span>
                  )}
                </div>

                {provider.status === 'FAILED' && provider.error_message && (
                  <details className="error-details">
                    <summary>查看失败原因</summary>
                    <p>{provider.error_message}</p>
                  </details>
                )}
              </article>
            );
          })}
        </section>
      )}

      <div className="action-dock">
        <button
          type="button"
          className="primary-action"
          onClick={handleRefresh}
          disabled={refreshing || loading}
        >
          <RefreshIcon />
          {refreshing ? '正在刷新所有平台…' : '刷新全部平台'}
        </button>
      </div>
    </main>
  );
}
