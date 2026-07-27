import { useMemo, useState, type PointerEvent } from 'react';
import type { BalanceChangeEvent } from '@/api/balance';
import { formatAmount, formatDateTime } from '@/lib/display';

interface BalanceTrendChartProps {
  currency: string;
  events: BalanceChangeEvent[];
}

interface ChartPoint {
  source: BalanceChangeEvent;
  x: number;
  y: number;
}

const WIDTH = 640;
const HEIGHT = 248;
const PADDING_X = 20;
const PADDING_TOP = 22;
const PADDING_BOTTOM = 28;

export default function BalanceTrendChart({
  currency,
  events,
}: BalanceTrendChartProps) {
  const chart = useMemo(() => {
    const sorted = [...events]
      .filter((event) => Number.isFinite(Number(event.current_amount)))
      .sort(
        (left, right) =>
          new Date(left.occurred_at).getTime() -
            new Date(right.occurred_at).getTime() || left.id - right.id,
      );
    const values = sorted.flatMap((event, index) => {
      const current = Number(event.current_amount);
      if (index !== 0 || event.previous_amount === null) {
        return [current];
      }
      const previous = Number(event.previous_amount);
      return Number.isFinite(previous) ? [previous, current] : [current];
    });
    const rawMin = Math.min(...values);
    const rawMax = Math.max(...values);
    const spread = rawMax - rawMin;
    const breathingRoom =
      spread === 0 ? Math.max(Math.abs(rawMax) * 0.05, 1) : spread * 0.12;
    const min = rawMin - breathingRoom;
    const max = rawMax + breathingRoom;
    const chartWidth = WIDTH - PADDING_X * 2;
    const chartHeight = HEIGHT - PADDING_TOP - PADDING_BOTTOM;

    const yForValue = (value: number): number =>
      PADDING_TOP + ((max - value) / (max - min)) * chartHeight;
    const chartPoints: ChartPoint[] = sorted.map((source, index) => {
      const value = Number(source.current_amount);
      const x = PADDING_X + ((index + 1) / (sorted.length + 1)) * chartWidth;
      const y = PADDING_TOP + ((max - value) / (max - min)) * chartHeight;
      return { source, x, y };
    });

    const first = sorted[0];
    const initialValue =
      first?.previous_amount === null || first?.previous_amount === undefined
        ? Number(first?.current_amount)
        : Number(first.previous_amount);
    const initialY = yForValue(initialValue);
    const line =
      chartPoints.length > 0
        ? [
            `M ${PADDING_X} ${initialY}`,
            ...chartPoints.map((point) => `H ${point.x} V ${point.y}`),
            `H ${WIDTH - PADDING_X}`,
          ].join(' ')
        : '';
    const floor = HEIGHT - PADDING_BOTTOM;
    const area =
      chartPoints.length > 0
        ? `${line} L ${WIDTH - PADDING_X} ${floor} L ${PADDING_X} ${floor} Z`
        : '';

    return {
      points: chartPoints,
      line,
      area,
      rawMin,
      rawMax,
    };
  }, [events]);

  const [selectedIndex, setSelectedIndex] = useState<number | null>(null);
  const activeIndex =
    selectedIndex === null
      ? Math.max(0, chart.points.length - 1)
      : Math.min(selectedIndex, Math.max(0, chart.points.length - 1));
  const activePoint = chart.points[activeIndex];

  const selectNearestPoint = (event: PointerEvent<HTMLDivElement>): void => {
    if (chart.points.length === 0) {
      return;
    }
    const bounds = event.currentTarget.getBoundingClientRect();
    const ratio = Math.min(
      1,
      Math.max(0, (event.clientX - bounds.left) / bounds.width),
    );
    const svgX = ratio * WIDTH;
    const nearest = chart.points.reduce(
      (best, point, index) =>
        Math.abs(point.x - svgX) < Math.abs(chart.points[best].x - svgX)
          ? index
          : best,
      0,
    );
    setSelectedIndex(nearest);
  };

  if (chart.points.length === 0) {
    return <p className="empty-copy">当前币种还没有可绘制的余额事件。</p>;
  }

  return (
    <div
      className="trend-chart"
      onPointerDown={selectNearestPoint}
      onPointerMove={selectNearestPoint}
    >
      <div className="trend-readout" aria-live="polite">
        <div>
          <span>{formatDateTime(activePoint.source.occurred_at)}</span>
          <strong>
            {currency} {formatAmount(activePoint.source.current_amount)}
          </strong>
        </div>
        <div className="trend-range" aria-label="图表余额范围">
          <span>低 {formatAmount(chart.rawMin.toFixed(2))}</span>
          <span>高 {formatAmount(chart.rawMax.toFixed(2))}</span>
        </div>
      </div>
      <svg
        className="trend-svg"
        viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
        role="img"
        aria-label={`${currency} 余额阶梯趋势，共 ${chart.points.length} 个事件`}
        preserveAspectRatio="none"
      >
        <line
          className="trend-guide"
          x1={PADDING_X}
          y1={HEIGHT / 2}
          x2={WIDTH - PADDING_X}
          y2={HEIGHT / 2}
        />
        <path className="trend-area" d={chart.area} />
        <path className="trend-line" d={chart.line} />
        {activePoint && (
          <>
            <line
              className="trend-cursor"
              x1={activePoint.x}
              y1={PADDING_TOP}
              x2={activePoint.x}
              y2={HEIGHT - PADDING_BOTTOM}
            />
            <circle
              className="trend-point-halo"
              cx={activePoint.x}
              cy={activePoint.y}
              r="10"
            />
            <circle
              className="trend-point"
              cx={activePoint.x}
              cy={activePoint.y}
              r="4"
            />
          </>
        )}
      </svg>
    </div>
  );
}
