import client from '@/api/client';

export type ProviderStatus = 'NEVER_REFRESHED' | 'RUNNING' | 'SUCCESS' | 'FAILED';

export interface BalanceValue {
  currency: string;
  available_amount: string;
  prepaid_amount: string | null;
  granted_amount: string | null;
  is_available: boolean;
  observed_at: string;
}

export interface ProviderBalance {
  provider: string;
  status: ProviderStatus;
  last_refresh_at: string | null;
  last_success_at: string | null;
  error_code: string | null;
  error_message: string | null;
  balances: BalanceValue[];
}

export interface BalanceHistory {
  provider: string;
  currency: string | null;
  points: BalanceValue[];
}

export interface ProviderRefreshResult {
  provider: string;
  status: 'SUCCESS' | 'FAILED';
  started_at: string;
  finished_at: string;
  snapshot_count: number;
  error_code: string | null;
  error_message: string | null;
}

export interface HistoryQuery {
  currency?: string;
  startTime?: string;
  endTime?: string;
  limit?: number;
}

export function findBalances(): Promise<ProviderBalance[]> {
  return client.get<unknown, ProviderBalance[]>('/balances');
}

export function findBalanceHistory(
  provider: string,
  query: HistoryQuery = {},
): Promise<BalanceHistory> {
  return client.get<unknown, BalanceHistory>(`/balances/${provider}/history`, {
    params: {
      currency: query.currency,
      'start-time': query.startTime,
      'end-time': query.endTime,
      limit: query.limit,
    },
  });
}

export function refreshBalances(): Promise<ProviderRefreshResult[]> {
  return client.post<unknown, ProviderRefreshResult[]>('/refresh');
}

export function refreshProvider(provider: string): Promise<ProviderRefreshResult> {
  return client.post<unknown, ProviderRefreshResult>(`/refresh/${provider}`);
}
