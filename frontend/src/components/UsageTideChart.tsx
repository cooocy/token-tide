import { useEffect, useState, type CSSProperties } from 'react';
import {
  type TokenUsageDay,
  type TokenUsageTool,
} from '@/api/tokenUsage';
import { formatTokenCount } from '@/lib/display';

const TOOL_ORDER: TokenUsageTool[] = ['opencode', 'codex', 'claude'];
const TOOL_NAMES: Record<TokenUsageTool, string> = {
  claude: 'Claude',
  codex: 'Codex',
  opencode: 'OpenCode',
};

interface UsageTideChartProps {
  days: TokenUsageDay[];
}

function formatDay(value: string): string {
  const [, month = '', day = ''] = value.split('-');
  return `${month}/${day}`;
}

export default function UsageTideChart({ days }: UsageTideChartProps) {
  const [selectedDate, setSelectedDate] = useState(days.at(-1)?.date ?? '');

  useEffect(() => {
    setSelectedDate(days.at(-1)?.date ?? '');
  }, [days]);

  const selected = days.find((day) => day.date === selectedDate) ?? days.at(-1);
  const maximum = Math.max(...days.map((day) => day.total_tokens), 1);

  return (
    <div className="usage-tide-chart">
      <div className="usage-tide-readout" aria-live="polite">
        <div>
          <span>{selected ? formatDay(selected.date) : '—'}</span>
          <strong>{formatTokenCount(selected?.total_tokens ?? 0)}</strong>
        </div>
        <div className="usage-day-tools">
          {TOOL_ORDER.slice().reverse().map((tool) => (
            <span className={`is-${tool}`} key={tool}>
              {TOOL_NAMES[tool]} {formatTokenCount(selected?.tools[tool] ?? 0, true)}
            </span>
          ))}
        </div>
      </div>

      <div
        className="usage-tide-plot"
        style={{ '--usage-day-count': days.length } as CSSProperties}
      >
        {days.map((day, index) => {
          const height = day.total_tokens === 0
            ? 0
            : Math.max((day.total_tokens / maximum) * 100, 3);
          const isSelected = day.date === selected?.date;
          const showLabel =
            index === 0 || index === days.length - 1 || isSelected;

          return (
            <button
              type="button"
              className={isSelected ? 'usage-day is-selected' : 'usage-day'}
              aria-label={`${day.date}，${formatTokenCount(day.total_tokens)} Token`}
              aria-pressed={isSelected}
              onClick={() => setSelectedDate(day.date)}
              key={day.date}
            >
              <span className="usage-day-track">
                <span
                  className="usage-day-fill"
                  style={{ height: `${height}%` }}
                >
                  {TOOL_ORDER.map((tool) => {
                    const value = day.tools[tool];
                    if (value === 0 || day.total_tokens === 0) {
                      return null;
                    }
                    return (
                      <span
                        className={`usage-day-segment is-${tool}`}
                        style={{ flexBasis: `${(value / day.total_tokens) * 100}%` }}
                        key={tool}
                      />
                    );
                  })}
                </span>
              </span>
              <span className={showLabel ? 'usage-day-label' : 'usage-day-label is-hidden'}>
                {formatDay(day.date)}
              </span>
            </button>
          );
        })}
      </div>

      <div className="usage-tool-legend" aria-label="工具颜色图例">
        {TOOL_ORDER.slice().reverse().map((tool) => (
          <span className={`is-${tool}`} key={tool}>
            <i aria-hidden="true" />
            {TOOL_NAMES[tool]}
          </span>
        ))}
      </div>
    </div>
  );
}
