import { useMemo, useState, type PointerEvent } from 'react';
import type { BalanceValue } from '@/api/balance';
import {
  formatAmount,
  formatDateTime,
} from '@/lib/display';

interface BalanceTrendChartProps {
  currency: string;
  points: BalanceValue[];
}

interface ChartPoint {
  source: BalanceValue;
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
  points,
}: BalanceTrendChartProps) {
  const chart = useMemo(() => {
    const sorted = [...points]
      .filter((point) => Number.isFinite(Number(point.available_amount)))
      .sort(
        (left, right) =>
          new Date(left.observed_at).getTime() - new Date(right.observed_at).getTime(),
      );
    const values = sorted.map((point) => Number(point.available_amount));
    const rawMin = Math.min(...values);
    const rawMax = Math.max(...values);
    const spread = rawMax - rawMin;
    const breathingRoom = spread === 0 ? Math.max(Math.abs(rawMax) * 0.05, 1) : spread * 0.12;
    const min = rawMin - breathingRoom;
    const max = rawMax + breathingRoom;
    const chartWidth = WIDTH - PADDING_X * 2;
    const chartHeight = HEIGHT - PADDING_TOP - PADDING_BOTTOM;

    const chartPoints: ChartPoint[] = sorted.map((source, index) => {
      const value = Number(source.available_amount);
      const x =
        sorted.length === 1
          ? WIDTH / 2
          : PADDING_X + (index / (sorted.length - 1)) * chartWidth;
      const y = PADDING_TOP + ((max - value) / (max - min)) * chartHeight;
      return { source, x, y };
    });

    const line = chartPoints
      .map((point, index) => `${index === 0 ? 'M' : 'L'} ${point.x} ${point.y}`)
      .join(' ');
    const floor = HEIGHT - PADDING_BOTTOM;
    const area =
      chartPoints.length > 0
        ? `${line} L ${chartPoints.at(-1)?.x ?? PADDING_X} ${floor} L ${
            chartPoints[0].x
          } ${floor} Z`
        : '';

    return {
      points: chartPoints,
      line,
      area,
      rawMin,
      rawMax,
    };
  }, [points]);

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
    const ratio = Math.min(1, Math.max(0, (event.clientX - bounds.left) / bounds.width));
    setSelectedIndex(Math.round(ratio * (chart.points.length - 1)));
  };

  if (chart.points.length === 0) {
    return <p className="empty-copy">当前币种还没有可绘制的余额记录。</p>;
  }

  return (
    <div
      className="trend-chart"
      onPointerDown={selectNearestPoint}
      onPointerMove={selectNearestPoint}
    >
      <div className="trend-readout" aria-live="polite">
        <div>
          <span>{formatDateTime(activePoint.source.observed_at)}</span>
          <strong>
            {currency} {formatAmount(activePoint.source.available_amount)}
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
        aria-label={`${currency} 余额趋势，共 ${chart.points.length} 条记录`}
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
