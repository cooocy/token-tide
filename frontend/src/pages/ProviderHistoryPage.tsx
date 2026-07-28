import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useParams, useSearchParams } from 'react-router-dom';
import {
  findBalanceHistory,
  findBalances,
  type BalanceHistory,
  type ProviderBalance,
} from '@/api/balance';
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
  const [providerBalance, setProviderBalance] = useState<ProviderBalance | null>(
    null,
  );
  const [currencies, setCurrencies] = useState<string[]>([]);
  const [selectedCurrency, setSelectedCurrency] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);

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
      setProviderBalance(null);
      setCurrencies([]);
      setLoading(true);
      setError(null);

      try {
        const balances = await findBalances();
        if (cancelled) {
          return;
        }

        const currentProvider =
          balances.find((balance) => balance.provider === provider) ?? null;
        const availableCurrencies = (currentProvider?.balances ?? [])
          .map((balance) => balance.currency)
          .sort();
        const requestedCurrency = searchParams.get('currency') ?? '';
        const initialCurrency = availableCurrencies.includes(requestedCurrency)
          ? requestedCurrency
          : (availableCurrencies[0] ?? '');

        setProviderBalance(currentProvider);
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
          const unfiltered = await findBalanceHistory(provider);
          if (!cancelled) {
            setHistory(unfiltered);
          }
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
  }, [provider, reloadKey]);

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

  const events = useMemo(
    () =>
      [...(history?.events ?? [])].sort(
        (left, right) =>
          new Date(left.occurred_at).getTime() -
            new Date(right.occurred_at).getTime() || left.id - right.id,
      ),
    [history],
  );
  const currentBalance = providerBalance?.balances.find(
    (balance) => balance.currency === selectedCurrency,
  );
  const flowSummary = useMemo(
    () =>
      events.reduce(
        (summary, event) => {
          if (event.change_amount === null) {
            return summary;
          }
          const amount = Number(event.change_amount);
          if (!Number.isFinite(amount)) {
            return summary;
          }
          if (event.change_type === 'SUPPLY') {
            summary.supply += amount;
          } else if (event.change_type === 'CONSUMPTION') {
            summary.consumption += Math.abs(amount);
          }
          summary.hasEvents = true;
          return summary;
        },
        { supply: 0, consumption: 0, hasEvents: false },
      ),
    [events],
  );

  return (
    <main className="app-shell history-page" aria-busy={loading}>
      <header className="history-header">
        <Link className="back-link" to="/" aria-label="返回余额看板">
          <BackIcon />
        </Link>
        <div className="history-provider">
          <ProviderMark provider={provider} />
          <div>
            <p>{formatProviderName(provider)}</p>
            <span>余额潮位</span>
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
                  setReloadKey((value) => value + 1);
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
                  {currentBalance
                    ? formatAmount(currentBalance.available_amount)
                    : '—'}
                </strong>
              </div>
              {flowSummary.hasEvents && (
                <span className="balance-flow">
                  <span
                    className="is-supply"
                    aria-label={`本段补给 +${formatAmount(flowSummary.supply.toFixed(2))}`}
                  >
                    +{formatAmount(flowSummary.supply.toFixed(2))}
                  </span>
                  <span
                    className={
                      flowSummary.consumption > 0 ? 'is-consumption' : ''
                    }
                    aria-label={`本段消耗 ${
                      flowSummary.consumption > 0
                        ? `-${formatAmount(flowSummary.consumption.toFixed(2))}`
                        : '0'
                    }`}
                  >
                    {flowSummary.consumption > 0
                      ? `-${formatAmount(flowSummary.consumption.toFixed(2))}`
                      : '0'}
                  </span>
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
                <p className="section-kicker">BALANCE TRACE</p>
                <h1>余额潮位</h1>
              </div>
              <span>最近 {events.length} 个事件</span>
            </div>
            <BalanceTrendChart
              key={selectedCurrency}
              currency={selectedCurrency}
              events={events}
            />
          </section>

          <section className="history-records" aria-labelledby="records-title">
            <div className="section-heading">
              <div>
                <p className="section-kicker">LOGBOOK</p>
                <h2 id="records-title">余额变动</h2>
              </div>
              <span>{selectedCurrency}</span>
            </div>

            {events.length === 0 ? (
              <div className="empty-panel is-compact">
                <h2>还没有余额变动</h2>
                <p>定时采样会持续记录余额，发生变化后会显示在这里。</p>
              </div>
            ) : (
              <ol className="record-list">
                {[...events].reverse().map((event, index) => (
                  <li
                    className={`is-${event.change_type.toLowerCase()}`}
                    key={event.id}
                  >
                    <span className="record-node" aria-hidden="true" />
                    <div>
                      <time dateTime={event.occurred_at}>
                        {formatDateTime(event.occurred_at)}
                      </time>
                      {index === 0 && (
                        <span className="latest-label">最近变动</span>
                      )}
                      {event.change_type === 'INITIAL' && (
                        <span className="record-event">初始余额</span>
                      )}
                    </div>
                    <div className="record-values">
                      <strong>{formatAmount(event.current_amount)}</strong>
                      {event.change_amount !== null && (
                        <span>
                          {formatSignedAmount(Number(event.change_amount))}
                        </span>
                      )}
                    </div>
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
