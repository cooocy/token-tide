import { useId, type CSSProperties } from 'react';
import {
  formatCompactTokenCount,
  formatTokenCount,
} from '@/lib/display';

export interface UsageDistributionItem {
  id: string;
  label: string;
  value: number;
  color: string;
}

interface UsageDistributionChartProps {
  kicker: string;
  title: string;
  items: UsageDistributionItem[];
  centerValue: string;
  centerLabel: string;
}

function formatPercentage(value: number, total: number): string {
  if (total <= 0) {
    return '0%';
  }
  const percentage = (value / total) * 100;
  return `${percentage < 0.1 ? '<0.1' : percentage.toFixed(1)}%`;
}

export default function UsageDistributionChart({
  kicker,
  title,
  items,
  centerValue,
  centerLabel,
}: UsageDistributionChartProps) {
  const titleId = useId();
  const descriptionId = useId();
  const positiveItems = items.filter((item) => item.value > 0);
  const total = positiveItems.reduce((sum, item) => sum + item.value, 0);
  let offset = 0;

  const description = positiveItems.length === 0
    ? `${title}暂无用量`
    : positiveItems.map((item) => (
      `${item.label} ${formatTokenCount(item.value)} Tokens，${
        formatPercentage(item.value, total)
      }`
    )).join('；');

  return (
    <section
      className="usage-distribution-card"
      aria-labelledby={titleId}
    >
      <div className="usage-distribution-heading">
        <p className="section-kicker">{kicker}</p>
        <h2 id={titleId}>{title}</h2>
      </div>

      <div className="usage-distribution-body">
        <div className="usage-donut">
          <svg
            viewBox="0 0 120 120"
            role="img"
            aria-labelledby={`${titleId} ${descriptionId}`}
          >
            <desc id={descriptionId}>{description}</desc>
            <circle
              className="usage-donut-track"
              cx="60"
              cy="60"
              r="43"
              pathLength="100"
            />
            {positiveItems.map((item) => {
              const percentage = (item.value / total) * 100;
              const dashOffset = -offset;
              offset += percentage;
              return (
                <circle
                  className="usage-donut-segment"
                  cx="60"
                  cy="60"
                  r="43"
                  pathLength="100"
                  stroke={item.color}
                  strokeDasharray={`${percentage} ${100 - percentage}`}
                  strokeDashoffset={dashOffset}
                  key={item.id}
                />
              );
            })}
          </svg>
          <div className="usage-donut-center" aria-hidden="true">
            <strong>{centerValue}</strong>
            <span>{centerLabel}</span>
          </div>
        </div>

        {positiveItems.length > 0 ? (
          <ol className="usage-distribution-legend">
            {positiveItems.map((item) => (
              <li key={item.id}>
                <i
                  style={{ '--distribution-color': item.color } as CSSProperties}
                  aria-hidden="true"
                />
                <span title={item.label}>{item.label}</span>
                <strong
                  title={`${formatTokenCount(item.value)} Tokens`}
                  aria-label={`${formatTokenCount(item.value)} Tokens`}
                >
                  {formatCompactTokenCount(item.value)}
                </strong>
                <small>{formatPercentage(item.value, total)}</small>
              </li>
            ))}
          </ol>
        ) : (
          <p className="usage-distribution-empty">暂无用量</p>
        )}
      </div>
    </section>
  );
}
