import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  findBalances,
  refreshBalances,
  type ProviderBalance,
} from '@/api/balance';

export default function DashboardPage() {
  const [providers, setProviders] = useState<ProviderBalance[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadBalances = useCallback(async (): Promise<void> => {
    try {
      setError(null);
      setProviders(await findBalances());
    } catch (loadError) {
      setProviders(null);
      setError(loadError instanceof Error ? loadError.message : '余额加载失败');
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
    try {
      await refreshBalances();
      await loadBalances();
    } catch (refreshError) {
      setError(refreshError instanceof Error ? refreshError.message : '刷新失败');
    } finally {
      setRefreshing(false);
    }
  };

  return (
    <main className="page-shell">
      <header className="page-header">
        <div>
          <p className="eyebrow">TokenTide</p>
          <h1>平台余额</h1>
          <p className="page-description">这里是数据流骨架，最终 Dashboard 视觉将在后续设计。</p>
        </div>
        <button type="button" onClick={handleRefresh} disabled={refreshing}>
          {refreshing ? '刷新中…' : '刷新全部'}
        </button>
      </header>

      {loading && <p className="state-message">正在读取余额…</p>}
      {error && <p className="state-message error">{error}</p>}
      {!loading && !error && providers?.length === 0 && (
        <p className="state-message">配置文件中还没有启用的平台。</p>
      )}

      <section className="provider-list" aria-label="平台余额列表">
        {providers?.map((provider) => (
          <article className="provider-row" key={provider.provider}>
            <div>
              <h2>{provider.provider}</h2>
              <p>{provider.status}</p>
            </div>
            <div className="balance-list">
              {provider.balances.length === 0 && <span>暂无余额快照</span>}
              {provider.balances.map((balance) => (
                <strong key={balance.currency}>
                  {balance.currency} {balance.available_amount}
                </strong>
              ))}
            </div>
            <Link to={`/providers/${provider.provider}/history`}>查看历史</Link>
          </article>
        ))}
      </section>
    </main>
  );
}
