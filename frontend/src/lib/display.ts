const PROVIDER_NAMES: Record<string, string> = {
  openrouter: 'OpenRouter',
  deepseek: 'DeepSeek',
  siliconflow: 'SiliconFlow',
  xai: 'xAI',
  opencode: 'OpenCode',
};

const PROVIDER_MARKS: Record<string, string> = {
  openrouter: 'OR',
  deepseek: 'DS',
  siliconflow: 'SF',
  xai: 'X',
};

export function formatProviderName(provider: string): string {
  return PROVIDER_NAMES[provider.toLowerCase()] ?? provider;
}

export function formatProviderMark(provider: string): string {
  return PROVIDER_MARKS[provider.toLowerCase()] ?? provider.slice(0, 2).toUpperCase();
}

export function formatAmount(value: string): string {
  const match = value.trim().match(/^(-?)(\d+)(?:\.(\d+))?$/);
  if (!match) {
    return value;
  }

  const [, sign, integer, decimal = ''] = match;
  const groupedInteger = integer.replace(/\B(?=(\d{3})+(?!\d))/g, ',');
  return `${sign}${groupedInteger}.${decimal.padEnd(2, '0').slice(0, 2)}`;
}

export function formatRelativeTime(value: string | null): string {
  if (!value) {
    return '尚未成功更新';
  }

  const timestamp = new Date(value).getTime();
  if (!Number.isFinite(timestamp)) {
    return '更新时间未知';
  }

  const seconds = Math.max(0, Math.floor((Date.now() - timestamp) / 1000));
  if (seconds < 60) {
    return '刚刚';
  }
  if (seconds < 3600) {
    return `${Math.floor(seconds / 60)} 分钟前`;
  }
  if (seconds < 86400) {
    return `${Math.floor(seconds / 3600)} 小时前`;
  }
  if (seconds < 604800) {
    return `${Math.floor(seconds / 86400)} 天前`;
  }
  return formatDateTime(value);
}

export function formatDateTime(value: string): string {
  const date = new Date(value);
  if (!Number.isFinite(date.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).format(date);
}

export function formatSignedAmount(value: number): string {
  if (!Number.isFinite(value)) {
    return '—';
  }

  const sign = value > 0 ? '+' : '';
  return `${sign}${value.toFixed(2)}`;
}

export function formatTokenCount(value: number): string {
  if (!Number.isFinite(value)) {
    return '—';
  }
  return new Intl.NumberFormat('zh-CN', { maximumFractionDigits: 0 }).format(value);
}

const TOKEN_UNITS = [
  { divisor: 10_000, suffix: 'W' },
  { divisor: 100_000_000, suffix: 'E' },
] as const;

export function formatCompactTokenCount(value: number): string {
  if (!Number.isFinite(value)) {
    return '—';
  }

  const absoluteValue = Math.abs(value);
  if (absoluteValue < TOKEN_UNITS[0].divisor) {
    return formatTokenCount(value);
  }

  let unitIndex = absoluteValue >= TOKEN_UNITS[1].divisor ? 1 : 0;
  let scaledValue = value / TOKEN_UNITS[unitIndex].divisor;
  const nextUnit = TOKEN_UNITS[unitIndex + 1];
  if (
    nextUnit &&
    Math.round(Math.abs(scaledValue) * 10) / 10 >=
      nextUnit.divisor / TOKEN_UNITS[unitIndex].divisor
  ) {
    unitIndex += 1;
    scaledValue = value / TOKEN_UNITS[unitIndex].divisor;
  }

  return `${new Intl.NumberFormat('en-US', {
    maximumFractionDigits: 1,
  }).format(scaledValue)}${TOKEN_UNITS[unitIndex].suffix}`;
}
