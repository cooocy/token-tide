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
  opencode: 'OC',
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
    return '刚刚更新';
  }
  if (seconds < 3600) {
    return `${Math.floor(seconds / 60)} 分钟前更新`;
  }
  if (seconds < 86400) {
    return `${Math.floor(seconds / 3600)} 小时前更新`;
  }
  if (seconds < 604800) {
    return `${Math.floor(seconds / 86400)} 天前更新`;
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
