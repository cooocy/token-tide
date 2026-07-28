import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { findBalances, type ProviderBalance, type ProviderStatus } from '@/api/balance';
import ProviderMark from '@/components/ProviderMark';
import {
  formatAmount,
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
  const [error, setError] = useState<string | null>(null);

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

  const summary = useMemo(() => {
    const items = providers ?? [];
    const healthyCount = items.filter((provider) => provider.status === 'SUCCESS').length;
    return { healthyCount, total: items.length };
  }, [providers]);

  return (
    <main className="app-shell dashboard-page" aria-busy={loading}>
      <header className="dashboard-header">
        <div className="brand-lockup">
          <span className="brand-mark" aria-hidden="true">
            <img src="/favicon.svg" alt="" />
          </span>
          <div>
            <p className="brand-name">TokenTide</p>
            <p className="brand-caption">多平台余额监控</p>
          </div>
        </div>
        {providers && providers.length > 0 && (
          <div
            className="health-summary"
            aria-label={`${summary.healthyCount} 个平台运行正常，共 ${summary.total} 个平台`}
          >
            <span className="health-pulse" aria-hidden="true" />
            {summary.healthyCount} / {summary.total}
          </div>
        )}
      </header>

      <section className="overview-heading" aria-labelledby="overview-title">
        <div>
          <p className="section-kicker">BALANCE DASHBOARD</p>
          <h1 id="overview-title">余额看板</h1>
        </div>
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
      </div>

      {loading && !providers && (
        <section className="provider-stack" aria-label="正在读取余额看板">
          {[0, 1, 2].map((item) => (
            <div className="provider-card skeleton-card" key={item}>
              <div className="skeleton-card-heading">
                <span className="skeleton-mark" />
                <span className="skeleton-line is-short" />
                <span className="skeleton-line is-action" />
              </div>
              <div className="skeleton-balance-row">
                <span className="skeleton-line is-currency" />
                <span className="skeleton-line is-amount" />
              </div>
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
        <section className="provider-stack" aria-label="余额看板列表">
          {providers.map((provider) => {
            const status = STATUS_META[provider.status];
            const firstCurrency = provider.balances[0]?.currency;
            const historyUrl = `/providers/${provider.provider}/history${
              firstCurrency ? `?currency=${encodeURIComponent(firstCurrency)}` : ''
            }`;
            const isUnavailable = provider.balances.some(
              (balance) => !balance.is_available,
            );

            return (
              <article
                className={`provider-card ${status.className}`}
                key={provider.provider}
              >
                <div className="provider-card-heading">
                  <div className="provider-identity">
                    <ProviderMark provider={provider.provider} />
                    <div>
                      <h2>{formatProviderName(provider.provider)}</h2>
                      <span className="provider-update-meta">
                        <span>
                          {provider.status === 'NEVER_REFRESHED'
                            ? status.label
                            : formatRelativeTime(provider.last_success_at)}
                        </span>
                        {provider.status !== 'SUCCESS' &&
                          provider.status !== 'NEVER_REFRESHED' && (
                            <span className="provider-refresh-status">
                              {status.label}
                            </span>
                          )}
                        {isUnavailable && (
                          <span className="availability-note">平台暂不可用</span>
                        )}
                      </span>
                    </div>
                  </div>
                  <div className="provider-card-tools">
                    <Link
                      className="history-link"
                      to={historyUrl}
                      aria-label={`查看 ${formatProviderName(provider.provider)} 余额潮位`}
                    >
                      <span>余额潮位</span>
                      <ArrowIcon />
                    </Link>
                  </div>
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

    </main>
  );
}
