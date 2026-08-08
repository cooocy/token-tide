import {
  useEffect,
  useMemo,
  useRef,
  useState,
  type CSSProperties,
  type KeyboardEvent,
} from 'react';
import { type TokenUsageCalendarDay } from '@/api/tokenUsage';
import {
  formatCompactTokenCount,
  formatTokenCount,
} from '@/lib/display';

const WEEK_COUNT = 53;
const DAYS_PER_WEEK = 7;
const CALENDAR_DATE_FORMATTER = new Intl.DateTimeFormat('zh-CN', {
  year: 'numeric',
  month: 'long',
  day: 'numeric',
  weekday: 'short',
});

interface UsageCalendarProps {
  days: TokenUsageCalendarDay[];
  endDate: string;
  startDate: string;
}

interface CalendarCell {
  date: Date;
  dateKey: string;
  usage: TokenUsageCalendarDay | null;
}

function parseDateKey(value: string): Date {
  const [year, month, day] = value.split('-').map(Number);
  return new Date(year, month - 1, day);
}

function formatDateKey(value: Date): string {
  const year = value.getFullYear();
  const month = String(value.getMonth() + 1).padStart(2, '0');
  const day = String(value.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

function addDays(value: Date, amount: number): Date {
  const next = new Date(value);
  next.setDate(next.getDate() + amount);
  return next;
}

function formatCalendarDate(value: string): string {
  return CALENDAR_DATE_FORMATTER.format(parseDateKey(value));
}

function intensityLevel(value: number, maximum: number): number {
  if (value <= 0 || maximum <= 0) {
    return 0;
  }
  return Math.min(
    4,
    Math.max(1, Math.ceil((Math.log1p(value) / Math.log1p(maximum)) * 4)),
  );
}

export default function UsageCalendar({
  days,
  endDate,
  startDate,
}: UsageCalendarProps) {
  const [selectedDate, setSelectedDate] = useState(endDate);
  const [previewDate, setPreviewDate] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const usageByDate = useMemo(
    () => new Map(days.map((day) => [day.date, day])),
    [days],
  );
  const cells = useMemo<CalendarCell[]>(() => {
    const start = parseDateKey(startDate);
    return Array.from({ length: WEEK_COUNT * DAYS_PER_WEEK }, (_, index) => {
      const date = addDays(start, index);
      const dateKey = formatDateKey(date);
      return {
        date,
        dateKey,
        usage: dateKey <= endDate ? usageByDate.get(dateKey) ?? null : null,
      };
    });
  }, [endDate, startDate, usageByDate]);
  const weeks = useMemo(
    () => Array.from(
      { length: WEEK_COUNT },
      (_, index) => cells.slice(index * DAYS_PER_WEEK, (index + 1) * DAYS_PER_WEEK),
    ),
    [cells],
  );
  const monthLabels = useMemo(() => weeks.flatMap((week, index) => {
    const firstOfMonth = week.find((cell) => cell.date.getDate() === 1);
    const labelDate = firstOfMonth ?? (index === 0 ? week[0] : null);
    return labelDate
      ? [{
        column: index + 1,
        label: `${labelDate.date.getMonth() + 1}月`,
      }]
      : [];
  }), [weeks]);
  const maximum = Math.max(...days.map((day) => day.total_tokens), 0);
  const activeDayCount = days.filter((day) => day.total_tokens > 0).length;
  const displayedDate = previewDate ?? selectedDate;
  const displayedUsage = usageByDate.get(displayedDate) ?? {
    date: displayedDate,
    event_count: 0,
    total_tokens: 0,
  };

  useEffect(() => {
    setSelectedDate(endDate);
    setPreviewDate(null);
  }, [endDate, startDate]);

  useEffect(() => {
    const container = scrollRef.current;
    if (!container) {
      return;
    }
    container.scrollLeft = container.scrollWidth;
  }, [days]);

  const focusDate = (
    event: KeyboardEvent<HTMLButtonElement>,
    dateKey: string,
  ): void => {
    let nextDate = parseDateKey(dateKey);
    if (event.key === 'ArrowUp') {
      nextDate = addDays(nextDate, -1);
    } else if (event.key === 'ArrowDown') {
      nextDate = addDays(nextDate, 1);
    } else if (event.key === 'ArrowLeft') {
      nextDate = addDays(nextDate, -7);
    } else if (event.key === 'ArrowRight') {
      nextDate = addDays(nextDate, 7);
    } else if (event.key === 'Home') {
      nextDate = parseDateKey(startDate);
    } else if (event.key === 'End') {
      nextDate = parseDateKey(endDate);
    } else {
      return;
    }
    event.preventDefault();
    const nextDateKey = formatDateKey(nextDate);
    if (nextDateKey < startDate || nextDateKey > endDate) {
      return;
    }
    const target = event.currentTarget
      .closest('[role="grid"]')
      ?.querySelector<HTMLButtonElement>(`button[data-date="${nextDateKey}"]`);
    target?.focus();
    setSelectedDate(nextDateKey);
  };

  return (
    <section className="usage-calendar-card" aria-labelledby="usage-calendar-title">
      <div className="usage-calendar-heading">
        <div>
          <p className="section-kicker">CONTRIBUTION CALENDAR</p>
          <h2 id="usage-calendar-title">使用日历</h2>
        </div>
        <span>过去 53 周 · {activeDayCount} 个活跃日</span>
      </div>

      <div className="usage-calendar-readout" aria-live="polite">
        <span>{formatCalendarDate(displayedDate)}</span>
        <div>
          <strong
            aria-label={`${formatTokenCount(displayedUsage.total_tokens)} Tokens`}
            title={formatTokenCount(displayedUsage.total_tokens)}
          >
            {formatCompactTokenCount(displayedUsage.total_tokens)} Tokens
          </strong>
          <small>
            {formatTokenCount(displayedUsage.total_tokens)} Tokens · {' '}
            {formatTokenCount(displayedUsage.event_count)} 次请求
          </small>
        </div>
      </div>

      <div className="usage-calendar-frame">
        <div className="usage-calendar-weekdays" aria-hidden="true">
          {['', '一', '', '三', '', '五', ''].map((label, index) => (
            <span key={`${label}-${index}`}>{label}</span>
          ))}
        </div>
        <div className="usage-calendar-scroll" ref={scrollRef}>
          <div className="usage-calendar-content">
            <div className="usage-calendar-months" aria-hidden="true">
              {monthLabels.map((item) => (
                <span
                  style={{ gridColumn: item.column } as CSSProperties}
                  key={`${item.column}-${item.label}`}
                >
                  {item.label}
                </span>
              ))}
            </div>
            <div
              className="usage-calendar-grid"
              role="grid"
              aria-label="最近 53 周 Token 用量"
            >
              {cells.map((cell) => {
                if (cell.dateKey > endDate) {
                  return (
                    <span
                      className="usage-calendar-day is-future"
                      aria-hidden="true"
                      key={cell.dateKey}
                    />
                  );
                }
                const tokens = cell.usage?.total_tokens ?? 0;
                const requests = cell.usage?.event_count ?? 0;
                const level = intensityLevel(tokens, maximum);
                const isSelected = cell.dateKey === selectedDate;
                return (
                  <button
                    type="button"
                    className={`usage-calendar-day is-level-${level}${
                      isSelected ? ' is-selected' : ''
                    }`}
                    role="gridcell"
                    tabIndex={isSelected ? 0 : -1}
                    data-date={cell.dateKey}
                    aria-selected={isSelected}
                    aria-label={`${formatCalendarDate(cell.dateKey)}，${
                      formatTokenCount(tokens)
                    } Tokens，${formatTokenCount(requests)} 次请求`}
                    title={`${formatTokenCount(tokens)} Tokens · ${
                      formatTokenCount(requests)
                    } 次请求`}
                    onClick={() => setSelectedDate(cell.dateKey)}
                    onFocus={() => setPreviewDate(cell.dateKey)}
                    onBlur={() => setPreviewDate(null)}
                    onMouseEnter={() => setPreviewDate(cell.dateKey)}
                    onMouseLeave={() => setPreviewDate(null)}
                    onKeyDown={(event) => focusDate(event, cell.dateKey)}
                    key={cell.dateKey}
                  />
                );
              })}
            </div>
          </div>
        </div>
      </div>

      <div className="usage-calendar-footer">
        {activeDayCount === 0 && (
          <p>还没有 Token 用量记录，采集器上报后会显示在这里。</p>
        )}
        <div className="usage-calendar-legend" aria-label="用量强度从少到多">
          <span>少</span>
          {[0, 1, 2, 3, 4].map((level) => (
            <i className={`is-level-${level}`} aria-hidden="true" key={level} />
          ))}
          <span>多</span>
        </div>
      </div>
    </section>
  );
}
