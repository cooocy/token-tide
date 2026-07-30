import {
  useEffect,
  useState,
  type CSSProperties,
  type KeyboardEvent,
  type PointerEvent,
} from 'react';
import {
  type TokenUsageDay,
  type TokenUsageTool,
} from '@/api/tokenUsage';
import {
  formatCompactTokenCount,
  formatTokenCount,
} from '@/lib/display';

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
  const selectedIndex = Math.max(
    0,
    days.findIndex((day) => day.date === selected?.date),
  );
  const maximum = Math.max(...days.map((day) => day.total_tokens), 1);

  const selectNearestDate = (event: PointerEvent<HTMLDivElement>): void => {
    if (days.length === 0) {
      return;
    }
    const bounds = event.currentTarget.getBoundingClientRect();
    const ratio = Math.min(
      1,
      Math.max(0, (event.clientX - bounds.left) / bounds.width),
    );
    const index = Math.min(days.length - 1, Math.floor(ratio * days.length));
    setSelectedDate(days[index].date);
  };

  const handlePointerDown = (event: PointerEvent<HTMLDivElement>): void => {
    event.currentTarget.setPointerCapture(event.pointerId);
    selectNearestDate(event);
  };

  const handlePointerMove = (event: PointerEvent<HTMLDivElement>): void => {
    if (!event.currentTarget.hasPointerCapture(event.pointerId)) {
      return;
    }
    selectNearestDate(event);
  };

  const handleKeyDown = (event: KeyboardEvent<HTMLDivElement>): void => {
    if (days.length === 0) {
      return;
    }
    let nextIndex = selectedIndex;
    if (event.key === 'ArrowLeft') {
      nextIndex = Math.max(0, selectedIndex - 1);
    } else if (event.key === 'ArrowRight') {
      nextIndex = Math.min(days.length - 1, selectedIndex + 1);
    } else if (event.key === 'Home') {
      nextIndex = 0;
    } else if (event.key === 'End') {
      nextIndex = days.length - 1;
    } else {
      return;
    }
    event.preventDefault();
    setSelectedDate(days[nextIndex].date);
  };

  return (
    <div className="usage-tide-chart">
      <div className="usage-tide-readout" aria-live="polite">
        <div className="usage-day-summary">
          <span>{selected ? formatDay(selected.date) : '—'}</span>
          <strong
            aria-label={`${formatTokenCount(selected?.total_tokens ?? 0)} Tokens`}
            title={formatTokenCount(selected?.total_tokens ?? 0)}
          >
            {formatCompactTokenCount(selected?.total_tokens ?? 0)} Tokens
          </strong>
        </div>
        <div className="usage-day-tools">
          {TOOL_ORDER.slice().reverse().map((tool) => (
            <span
              className={`is-${tool}`}
              aria-label={`${TOOL_NAMES[tool]} ${
                formatTokenCount(selected?.tools[tool] ?? 0)
              } Tokens`}
              title={formatTokenCount(selected?.tools[tool] ?? 0)}
              key={tool}
            >
              {TOOL_NAMES[tool]} {
                formatCompactTokenCount(selected?.tools[tool] ?? 0)
              }
            </span>
          ))}
        </div>
      </div>

      <div
        className="usage-tide-plot"
        role="slider"
        tabIndex={days.length > 0 ? 0 : -1}
        aria-label="选择每日用量"
        aria-orientation="horizontal"
        aria-valuemin={0}
        aria-valuemax={Math.max(0, days.length - 1)}
        aria-valuenow={selectedIndex}
        aria-valuetext={
          selected
            ? `${selected.date}，${formatTokenCount(selected.total_tokens)} Tokens`
            : '没有用量数据'
        }
        onKeyDown={handleKeyDown}
        onPointerDown={handlePointerDown}
        onPointerMove={handlePointerMove}
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
            <span
              className={isSelected ? 'usage-day is-selected' : 'usage-day'}
              aria-hidden="true"
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
            </span>
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
