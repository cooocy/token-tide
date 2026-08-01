import client from '@/api/client';

export type TokenUsageTool = 'claude' | 'codex' | 'opencode' | 'pi';

export interface TokenUsageTotals {
  event_count: number;
  input_tokens: number;
  output_tokens: number;
  cache_creation_tokens: number;
  cache_read_tokens: number;
  reasoning_tokens: number;
  total_tokens: number;
}

export interface TokenUsageToolSummary extends TokenUsageTotals {
  tool: TokenUsageTool;
}

export interface TokenUsageDay {
  date: string;
  total_tokens: number;
  tools: Record<TokenUsageTool, number>;
}

export interface TokenUsageModelSummary {
  model: string;
  event_count: number;
  total_tokens: number;
}

export interface TokenUsageSummary {
  start_time: string;
  end_time: string;
  timezone_offset_minutes: number;
  totals: TokenUsageTotals;
  tools: TokenUsageToolSummary[];
  timeline: TokenUsageDay[];
  models: TokenUsageModelSummary[];
}

export interface TokenUsageOverview {
  totals: TokenUsageTotals;
  tools: TokenUsageToolSummary[];
  models: TokenUsageModelSummary[];
}

export interface TokenUsageSummaryQuery {
  startTime: string;
  endTime: string;
  timezoneOffsetMinutes: number;
  tool?: TokenUsageTool;
}

export interface TokenUsageTotalsQuery {
  tool?: TokenUsageTool;
}

export function findTokenUsageSummary(
  query: TokenUsageSummaryQuery,
): Promise<TokenUsageSummary> {
  return client.get<unknown, TokenUsageSummary>('/token-usage/summary', {
    params: {
      tool: query.tool,
      'start-time': query.startTime,
      'end-time': query.endTime,
      'timezone-offset-minutes': query.timezoneOffsetMinutes,
    },
  });
}

export function findTokenUsageOverview(): Promise<TokenUsageOverview> {
  return client.get<unknown, TokenUsageOverview>('/token-usage/overview');
}

export function findTokenUsageTotals(
  query: TokenUsageTotalsQuery = {},
): Promise<TokenUsageTotals> {
  return client.get<unknown, TokenUsageTotals>('/token-usage/totals', {
    params: {
      tool: query.tool,
    },
  });
}
