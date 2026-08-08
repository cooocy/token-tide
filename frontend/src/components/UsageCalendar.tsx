import {
  useEffect,
  useMemo,
  useRef,
  type CSSProperties,
  type KeyboardEvent,
} from 'react';
import { type TokenUsageCalendarDay } from '@/api/tokenUsage';
import { formatTokenCount } from '@/lib/display';

const DAYS_PER_WEEK = 7;
const INTENSITY_THRESHOLDS = [2_500_000, 20_000_000, 40_000_000] as const;
const INTENSITY_LABELS = [
  '无使用',
  '1～250W',
  '>250W～2000W',
  '>2000W～4000W',
  '>4000W',
] as const;

interface UsageCalendarProps {
  availableYears: number[];
  days: TokenUsageCalendarDay[];
  onSelectDate: (date: string) => void;
  onSelectYear: (year: number) => void;
  selectedDate: string;
  todayDate: string;
  year: number;
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

export function usageIntensityLevel(value: number): number {
  if (value <= 0) {
    return 0;
  }
  if (value <= INTENSITY_THRESHOLDS[0]) {
    return 1;
  }
  if (value <= INTENSITY_THRESHOLDS[1]) {
    return 2;
  }
  if (value <= INTENSITY_THRESHOLDS[2]) {
    return 3;
  }
  return 4;
}

export function usageIntensityLabel(value: number): string {
  return INTENSITY_LABELS[usageIntensityLevel(value)];
}

export default function UsageCalendar({
  availableYears,
  days,
  onSelectDate,
  onSelectYear,
  selectedDate,
  todayDate,
  year,
}: UsageCalendarProps) {
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const usageByDate = useMemo(
    () => new Map(days.map((day) => [day.date, day])),
    [days],
  );
  const cells = useMemo<CalendarCell[]>(() => {
    const gridEnd = todayDate.startsWith(`${year}-`)
      ? parseDateKey(todayDate)
      : new Date(year, 11, 31);
    const gridStart = addDays(
      gridEnd,
      -((gridEnd.getDay() + 6) % 7) - 52 * DAYS_PER_WEEK,
    );
    const result: CalendarCell[] = [];
    let current = gridStart;
    while (current <= gridEnd) {
      const date = new Date(current);
      const dateKey = formatDateKey(date);
      result.push({
        date,
        dateKey,
        usage: usageByDate.get(dateKey) ?? null,
      });
      current = addDays(current, 1);
    }
    return result;
  }, [todayDate, usageByDate, year]);
  const weekCount = Math.ceil(cells.length / DAYS_PER_WEEK);
  const gridWidth = weekCount * 16 - 4;
  const monthLabels = useMemo(() => cells.flatMap((cell, index) => (
    cell.date.getDate() === 1
      ? [{
        column: Math.floor(index / DAYS_PER_WEEK) + 1,
        label: `${cell.date.getMonth() + 1}月`,
      }]
      : []
  )), [cells]);
  const activeDayCount = days.filter((day) => day.total_tokens > 0).length;

  useEffect(() => {
    const container = scrollRef.current;
    const target = container?.querySelector<HTMLButtonElement>(
      `button[data-date="${selectedDate}"]`,
    );
    if (!container || !target) {
      return;
    }
    const centeredLeft = target.offsetLeft
      - (container.clientWidth - target.offsetWidth) / 2;
    const todayTarget = todayDate.startsWith(`${year}-`)
      ? container.querySelector<HTMLButtonElement>(
        `button[data-date="${todayDate}"]`,
      )
      : null;
    const latestUsefulLeft = todayTarget
      ? todayTarget.offsetLeft + todayTarget.offsetWidth - container.clientWidth
      : container.scrollWidth - container.clientWidth;
    container.scrollLeft = Math.max(
      0,
      Math.min(centeredLeft, latestUsefulLeft),
    );
  }, [days, selectedDate, todayDate, year]);

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
      nextDate = new Date(year, 0, 1);
    } else if (event.key === 'End') {
      const yearEndKey = `${year}-12-31`;
      nextDate = parseDateKey(yearEndKey < todayDate ? yearEndKey : todayDate);
    } else {
      return;
    }
    event.preventDefault();
    const nextDateKey = formatDateKey(nextDate);
    const target = event.currentTarget
      .closest('[role="grid"]')
      ?.querySelector<HTMLButtonElement>(`button[data-date="${nextDateKey}"]`);
    if (!target) {
      return;
    }
    target.focus();
    onSelectDate(nextDateKey);
  };

  const gridStyle = {
    '--calendar-grid-width': `${gridWidth}px`,
    '--calendar-week-count': weekCount,
  } as CSSProperties;

  return (
    <div className="usage-calendar-layout">
      <nav className="usage-calendar-years" aria-label="日历年份">
        {availableYears.map((availableYear) => (
          <button
            type="button"
            className={availableYear === year ? 'is-active' : undefined}
            aria-pressed={availableYear === year}
            onClick={() => onSelectYear(availableYear)}
            key={availableYear}
          >
            {availableYear}
          </button>
        ))}
      </nav>

      <section className="usage-calendar-card" aria-labelledby="usage-calendar-title">
        <div className="usage-calendar-heading">
          <div>
            <p className="section-kicker">CONTRIBUTION CALENDAR</p>
            <h2 id="usage-calendar-title">{year} 使用日历</h2>
          </div>
          <span>{activeDayCount} 个活跃日</span>
        </div>

        <div className="usage-calendar-frame">
          <div className="usage-calendar-weekdays" aria-hidden="true">
            {['', '一', '', '三', '', '五', ''].map((label, index) => (
              <span key={`${label}-${index}`}>{label}</span>
            ))}
          </div>
          <div className="usage-calendar-scroll" ref={scrollRef}>
            <div className="usage-calendar-content" style={gridStyle}>
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
                aria-label={`${year} 年 Token 用量`}
              >
                {cells.map((cell) => {
                  const tokens = cell.usage?.total_tokens ?? 0;
                  const requests = cell.usage?.event_count ?? 0;
                  const level = usageIntensityLevel(tokens);
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
                      aria-label={`${cell.dateKey}，${formatTokenCount(tokens)} Tokens，${
                        formatTokenCount(requests)
                      } 次请求，强度 ${level}`}
                      title={`${formatTokenCount(tokens)} Tokens · ${
                        formatTokenCount(requests)
                      } 次请求`}
                      onClick={() => onSelectDate(cell.dateKey)}
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
            <p>这一年还没有 Token 用量记录。</p>
          )}
          <div className="usage-calendar-legend" aria-label="固定用量强度分档">
            <span>少</span>
            {INTENSITY_LABELS.map((label, level) => (
              <i
                className={`is-level-${level}`}
                aria-label={label}
                role="img"
                title={label}
                key={label}
              />
            ))}
            <span>多</span>
          </div>
        </div>
      </section>
    </div>
  );
}
