import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useParams, useSearchParams } from 'react-router-dom';
import { findBalanceHistory, type BalanceHistory } from '@/api/balance';
import BalanceTrendChart from '@/components/BalanceTrendChart';
import ProviderMark from '@/components/ProviderMark';
import {
  formatAmount,
  formatDateTime,
  formatProviderName,
  formatSignedAmount,
} from '@/lib/display';

function BackIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="m15 18-6-6 6-6" />
    </svg>
  );
}

export default function ProviderHistoryPage() {
  const { provider = '' } = useParams();
  const [searchParams, setSearchParams] = useSearchParams();
  const [history, setHistory] = useState<BalanceHistory | null>(null);
  const [currencies, setCurrencies] = useState<string[]>([]);
  const [selectedCurrency, setSelectedCurrency] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadCurrency = useCallback(
    async (currency: string, preserveCurrent = true): Promise<boolean> => {
      if (!provider) {
        setError('缺少平台名称');
        setLoading(false);
        return false;
      }

      try {
        setError(null);
        const data = await findBalanceHistory(
          provider,
          currency ? { currency } : {},
        );
        setHistory(data);
        return true;
      } catch (loadError) {
        if (!preserveCurrent) {
          setHistory(null);
        }
        setError(loadError instanceof Error ? loadError.message : '历史加载失败');
        return false;
      } finally {
        setLoading(false);
      }
    },
    [provider],
  );

  useEffect(() => {
    let cancelled = false;

    const initialize = async (): Promise<void> => {
      if (!provider) {
        setError('缺少平台名称');
        setLoading(false);
        return;
      }

      setHistory(null);
      setCurrencies([]);
      setLoading(true);
      setError(null);

      try {
        const overview = await findBalanceHistory(provider);
        if (cancelled) {
          return;
        }

        const availableCurrencies = Array.from(
          new Set(overview.points.map((point) => point.currency)),
        ).sort();
        const requestedCurrency = searchParams.get('currency') ?? '';
        const initialCurrency = availableCurrencies.includes(requestedCurrency)
          ? requestedCurrency
          : (overview.currency ?? availableCurrencies[0] ?? '');

        setCurrencies(availableCurrencies);
        setSelectedCurrency(initialCurrency);

        if (initialCurrency) {
          setSearchParams({ currency: initialCurrency }, { replace: true });
          const filtered = await findBalanceHistory(provider, {
            currency: initialCurrency,
          });
          if (!cancelled) {
            setHistory(filtered);
          }
        } else {
          setHistory(overview);
        }
      } catch (loadError) {
        if (!cancelled) {
          setError(loadError instanceof Error ? loadError.message : '历史加载失败');
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };

    void initialize();
    return () => {
      cancelled = true;
    };
    // The query parameter is read once when a provider route opens. Currency
    // changes use loadCurrency directly so they do not restart initialization.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [provider]);

  const handleCurrencyChange = async (currency: string): Promise<void> => {
    if (currency === selectedCurrency) {
      return;
    }
    setSelectedCurrency(currency);
    setSearchParams({ currency }, { replace: true });
    setHistory(null);
    setLoading(true);
    await loadCurrency(currency, false);
  };

  const points = useMemo(
    () =>
      [...(history?.points ?? [])].sort(
        (left, right) =>
          new Date(left.observed_at).getTime() - new Date(right.observed_at).getTime(),
      ),
    [history],
  );
  const latestPoint = points.at(-1);
  const firstPoint = points[0];
  const change =
    latestPoint && firstPoint
      ? Number(latestPoint.available_amount) - Number(firstPoint.available_amount)
      : 0;

  return (
    <main className="app-shell history-page" aria-busy={loading}>
      <header className="history-header">
        <Link className="back-link" to="/" aria-label="返回平台余额">
          <BackIcon />
        </Link>
        <div className="history-provider">
          <ProviderMark provider={provider} />
          <div>
            <p>{formatProviderName(provider)}</p>
            <span>余额历史</span>
          </div>
        </div>
      </header>

      <div className="message-stack" aria-live="polite">
        {error && (
          <div className="inline-message is-error" role="alert">
            <span>{error}</span>
            {!history && (
              <button
                type="button"
                className="text-button"
                onClick={() => {
                  setLoading(true);
                  void loadCurrency(selectedCurrency, false);
                }}
              >
                重试
              </button>
            )}
          </div>
        )}
      </div>

      {loading && !history && (
        <section className="history-skeleton" aria-label="正在读取余额历史">
          <span className="skeleton-line is-short" />
          <span className="skeleton-line is-hero" />
          <span className="skeleton-chart" />
        </section>
      )}

      {history && (
        <>
          <section className="balance-hero" aria-labelledby="history-balance-title">
            <div className="balance-hero-heading">
              <p className="section-kicker">AVAILABLE BALANCE</p>
            </div>
            <div className="hero-value-row">
              <div>
                <span id="history-balance-title">{selectedCurrency || '余额'}</span>
                <strong>
                  {latestPoint ? formatAmount(latestPoint.available_amount) : '—'}
                </strong>
              </div>
              {points.length > 1 && Number.isFinite(change) && (
                <span
                  className={`balance-change ${
                    change > 0 ? 'is-positive' : change < 0 ? 'is-negative' : ''
                  }`}
                >
                  {formatSignedAmount(change)}
                  <small>本段变化</small>
                </span>
              )}
            </div>

            {currencies.length > 1 && (
              <div className="currency-tabs" aria-label="选择币种">
                {currencies.map((currency) => (
                  <button
                    type="button"
                    className={currency === selectedCurrency ? 'is-active' : ''}
                    aria-pressed={currency === selectedCurrency}
                    onClick={() => void handleCurrencyChange(currency)}
                    key={currency}
                  >
                    {currency}
                  </button>
                ))}
              </div>
            )}
          </section>

          <section className={`chart-panel ${loading ? 'is-loading' : ''}`}>
            <div className="section-heading">
              <div>
                <p className="section-kicker">TIDE TRACE</p>
                <h1>余额潮位</h1>
              </div>
              <span>最近 {points.length} 条</span>
            </div>
            <BalanceTrendChart
              key={selectedCurrency}
              currency={selectedCurrency}
              points={points}
            />
          </section>

          <section className="history-records" aria-labelledby="records-title">
            <div className="section-heading">
              <div>
                <p className="section-kicker">LOGBOOK</p>
                <h2 id="records-title">最近记录</h2>
              </div>
              <span>{selectedCurrency}</span>
            </div>

            {points.length === 0 ? (
              <div className="empty-panel is-compact">
                <h2>还没有历史记录</h2>
                <p>定时任务刷新后，新的余额快照会显示在这里。</p>
              </div>
            ) : (
              <ol className="record-list">
                {[...points].reverse().map((point, index) => (
                  <li key={`${point.currency}-${point.observed_at}`}>
                    <span className="record-node" aria-hidden="true" />
                    <div>
                      <time dateTime={point.observed_at}>
                        {formatDateTime(point.observed_at)}
                      </time>
                      {index === 0 && <span className="latest-label">最新</span>}
                    </div>
                    <strong>{formatAmount(point.available_amount)}</strong>
                  </li>
                ))}
              </ol>
            )}
          </section>
        </>
      )}
    </main>
  );
}
