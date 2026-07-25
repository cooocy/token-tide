import { useCallback, useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import {
  findBalanceHistory,
  refreshProvider,
  type BalanceHistory,
} from '@/api/balance';

export default function ProviderHistoryPage() {
  const { provider = '' } = useParams();
  const [history, setHistory] = useState<BalanceHistory | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadHistory = useCallback(async (): Promise<void> => {
    if (!provider) {
      setError('缺少平台名称');
      setLoading(false);
      return;
    }
    try {
      setError(null);
      setHistory(await findBalanceHistory(provider));
    } catch (loadError) {
      setHistory(null);
      setError(loadError instanceof Error ? loadError.message : '历史加载失败');
    } finally {
      setLoading(false);
    }
  }, [provider]);

  useEffect(() => {
    setHistory(null);
    setLoading(true);
    void loadHistory();
  }, [loadHistory]);

  const handleRefresh = async (): Promise<void> => {
    if (!provider) {
      return;
    }
    setRefreshing(true);
    try {
      await refreshProvider(provider);
      await loadHistory();
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
          <Link to="/">← 返回余额</Link>
          <h1>{provider} 历史</h1>
          <p className="page-description">当前使用表格验证历史数据，图表方案后续确定。</p>
        </div>
        <button type="button" onClick={handleRefresh} disabled={refreshing}>
          {refreshing ? '刷新中…' : '刷新平台'}
        </button>
      </header>

      {loading && <p className="state-message">正在读取历史…</p>}
      {error && <p className="state-message error">{error}</p>}
      {history && (
        <div className="history-table-wrapper">
          <table>
            <thead>
              <tr>
                <th>时间</th>
                <th>币种</th>
                <th>可用余额</th>
                <th>赠送余额</th>
              </tr>
            </thead>
            <tbody>
              {history.points.map((point) => (
                <tr key={`${point.currency}-${point.observed_at}`}>
                  <td>{new Date(point.observed_at).toLocaleString()}</td>
                  <td>{point.currency}</td>
                  <td>{point.available_amount}</td>
                  <td>{point.granted_amount ?? '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {history.points.length === 0 && <p className="state-message">暂无历史快照。</p>}
        </div>
      )}
    </main>
  );
}
