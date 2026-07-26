import client from '@/api/client';

export type ProviderStatus = 'NEVER_REFRESHED' | 'RUNNING' | 'SUCCESS' | 'FAILED';

export interface BalanceValue {
  currency: string;
  available_amount: string;
  is_available: boolean;
  observed_at: string;
}

export type BalanceChangeType = 'SUPPLY' | 'CONSUMPTION' | 'UNCHANGED';

export interface BalanceHistoryPoint extends BalanceValue {
  change_amount: string | null;
  change_type: BalanceChangeType | null;
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
  points: BalanceHistoryPoint[];
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
