from dataclasses import dataclass
from datetime import UTC, datetime, time, timedelta
from enum import StrEnum
from html import escape
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from token_tide.response import ApplicationError
from token_tide.token_usage.domain import TokenUsageTool
from token_tide.token_usage.schemas import TokenUsageSummary
from token_tide.token_usage.service import TokenUsageService

CARD_WIDTH = 720
CARD_HEIGHT = 220


class UsageCardPeriod(StrEnum):
    SEVEN_DAYS = "7d"
    THIRTY_DAYS = "30d"

    @property
    def days(self) -> int:
        return 7 if self is self.SEVEN_DAYS else 30


class UsageCardTheme(StrEnum):
    DARK = "dark"
    LIGHT = "light"


class UsageCardTool(StrEnum):
    ALL = "all"
    CLAUDE = "claude"
    CODEX = "codex"
    OPENCODE = "opencode"
    PI = "pi"

    @property
    def usage_tool(self) -> TokenUsageTool | None:
        if self is self.ALL:
            return None
        return TokenUsageTool(self.value)


@dataclass(frozen=True)
class CardPalette:
    background: str
    panel_alt: str
    foreground: str
    secondary: str
    muted: str
    accent: str
    line: str
    claude: str
    codex: str
    opencode: str
    pi: str


PALETTES = {
    UsageCardTheme.DARK: CardPalette(
        background="#071820",
        panel_alt="#0c2731",
        foreground="#e7f5f4",
        secondary="#a8cfcb",
        muted="#789b9a",
        accent="#32d6c5",
        line="#23444b",
        claude="#dca36a",
        codex="#32d6c5",
        opencode="#899cff",
        pi="#e47f96",
    ),
    UsageCardTheme.LIGHT: CardPalette(
        background="#f2fbfa",
        panel_alt="#e5f3f1",
        foreground="#12333a",
        secondary="#315b5d",
        muted="#597b7c",
        accent="#087f78",
        line="#c5ddda",
        claude="#b66b26",
        codex="#087f78",
        opencode="#566cd6",
        pi="#c65370",
    ),
}

TOOL_LABELS = {
    TokenUsageTool.CLAUDE: "Claude",
    TokenUsageTool.CODEX: "Codex",
    TokenUsageTool.OPENCODE: "OpenCode",
    TokenUsageTool.PI: "Pi",
}


def find_card_summary(
    service: TokenUsageService,
    period: UsageCardPeriod,
    tool: UsageCardTool,
    timezone_name: str,
    now: datetime | None = None,
) -> TokenUsageSummary:
    try:
        calendar_timezone = ZoneInfo(timezone_name)
    except (ZoneInfoNotFoundError, ValueError):
        raise ApplicationError(
            422,
            42205,
            "Unknown token usage card timezone",
        ) from None

    current_time = now or datetime.now(UTC)
    if current_time.tzinfo is None:
        raise ValueError("now must include timezone")
    local_now = current_time.astimezone(calendar_timezone)
    start_date = local_now.date() - timedelta(days=period.days - 1)
    start_time = datetime.combine(start_date, time.min, calendar_timezone)
    offset = local_now.utcoffset()
    timezone_offset_minutes = int(offset.total_seconds() // 60) if offset else 0

    return service.summary(
        tool=tool.usage_tool,
        start_time=start_time,
        end_time=current_time,
        timezone_offset_minutes=timezone_offset_minutes,
        calendar_timezone=calendar_timezone,
    )


def format_compact_count(value: int) -> str:
    units = ((1_000, "K"), (1_000_000, "M"), (1_000_000_000, "B"))
    if value < units[0][0]:
        return f"{value:,}"

    unit_index = (
        2
        if value >= units[2][0]
        else 1
        if value >= units[1][0]
        else 0
    )
    divisor, suffix = units[unit_index]
    rounded_tenths = (value * 10 + divisor // 2) // divisor
    if rounded_tenths >= 10_000 and unit_index < len(units) - 1:
        unit_index += 1
        divisor, suffix = units[unit_index]
        rounded_tenths = (value * 10 + divisor // 2) // divisor
    rendered = (
        f"{rounded_tenths // 10}.{rounded_tenths % 10}"
        if rounded_tenths % 10
        else str(rounded_tenths // 10)
    )
    return f"{rendered}{suffix}"


def render_usage_card(
    summary: TokenUsageSummary,
    period: UsageCardPeriod,
    tool: UsageCardTool,
    theme: UsageCardTheme,
) -> str:
    palette = PALETTES[theme]
    today_date = (
        summary.end_time
        + timedelta(minutes=summary.timezone_offset_minutes)
    ).date()
    today_tokens = next(
        (
            day.total_tokens
            for day in reversed(summary.timeline)
            if day.date == today_date
        ),
        0,
    )
    tool_totals = {item.tool: item.total_tokens for item in summary.tools}
    total_tokens = summary.totals.total_tokens
    period_label = f"{period.days} DAY TOKENS"
    filter_label = "ALL AGENTS" if tool is UsageCardTool.ALL else tool.value.upper()
    title = (
        f"TokenTide: {total_tokens:,} Tokens across the last "
        f"{period.days} days"
    )
    description = (
        f"Today {today_tokens:,} Tokens from "
        f"{summary.totals.event_count:,} requests in the selected period."
    )

    tool_colors = {
        TokenUsageTool.CLAUDE: palette.claude,
        TokenUsageTool.CODEX: palette.codex,
        TokenUsageTool.OPENCODE: palette.opencode,
        TokenUsageTool.PI: palette.pi,
    }
    chart_left = 258.0
    chart_right = 526.0
    chart_top = 56.0
    chart_bottom = 174.0
    chart_height = chart_bottom - chart_top
    day_count = max(len(summary.timeline), 1)
    slot_width = (chart_right - chart_left) / day_count
    bar_width = min(23.0, max(3.6, slot_width * 0.58))
    maximum = max((day.total_tokens for day in summary.timeline), default=0)
    maximum = max(maximum, 1)
    bar_elements: list[str] = []
    tide_points: list[str] = []

    for index, day in enumerate(summary.timeline):
        x = chart_left + index * slot_width + (slot_width - bar_width) / 2
        total_height = (
            0.0
            if day.total_tokens == 0
            else max(3.0, day.total_tokens / maximum * chart_height)
        )
        top = chart_bottom - total_height
        tide_points.append(f"{x + bar_width / 2:.2f},{top:.2f}")
        bar_elements.append(
            f'<rect x="{x:.2f}" y="{chart_top:.2f}" width="{bar_width:.2f}" '
            f'height="{chart_height:.2f}" rx="{bar_width / 2:.2f}" '
            f'fill="{palette.panel_alt}" />'
        )
        segment_bottom = chart_bottom
        for usage_tool in TokenUsageTool:
            value = day.tools[usage_tool]
            if value <= 0 or day.total_tokens <= 0:
                continue
            segment_height = total_height * value / day.total_tokens
            segment_bottom -= segment_height
            bar_elements.append(
                f'<rect x="{x:.2f}" y="{segment_bottom:.2f}" '
                f'width="{bar_width:.2f}" height="{segment_height + 0.35:.2f}" '
                f'rx="{min(bar_width / 2, segment_height / 2):.2f}" '
                f'fill="{tool_colors[usage_tool]}" />'
            )

    if not tide_points:
        tide_points = [
            f"{chart_left:.2f},{chart_bottom:.2f}",
            f"{chart_right:.2f},{chart_bottom:.2f}",
        ]

    date_labels: list[str] = []
    if summary.timeline:
        label_indices = (
            range(len(summary.timeline))
            if period is UsageCardPeriod.SEVEN_DAYS
            else (0, len(summary.timeline) // 2, len(summary.timeline) - 1)
        )
        for index in dict.fromkeys(label_indices):
            day = summary.timeline[index]
            x = chart_left + index * slot_width + slot_width / 2
            date_labels.append(
                f'<text class="micro data" x="{x:.2f}" y="194" '
                f'text-anchor="middle">{day.date:%m/%d}</text>'
            )

    mix_rows: list[str] = []
    visible_tools = (
        list(TokenUsageTool)
        if tool is UsageCardTool.ALL
        else [tool.usage_tool]
    )
    for index, usage_tool in enumerate(visible_tools):
        if usage_tool is None:
            continue
        value = tool_totals.get(usage_tool, 0)
        percentage = value / total_tokens * 100 if total_tokens else 0
        y = 64 + index * 29
        mix_rows.append(
            f'<circle cx="574" cy="{y - 3}" r="4" '
            f'fill="{tool_colors[usage_tool]}" />'
            f'<text class="label" x="586" y="{y}">'
            f'{escape(TOOL_LABELS[usage_tool])}</text>'
            f'<text class="data mix-value" x="696" y="{y}" text-anchor="end">'
            f'{percentage:.1f}%</text>'
        )

    empty_note = (
        '<text class="empty" x="258" y="121">No usage yet</text>'
        if total_tokens == 0
        else ""
    )
    bars = "".join(bar_elements)
    dates = "".join(date_labels)
    mix = "".join(mix_rows)
    points = " ".join(tide_points)

    return f'''<svg xmlns="http://www.w3.org/2000/svg"
  width="{CARD_WIDTH}" height="{CARD_HEIGHT}"
  viewBox="0 0 {CARD_WIDTH} {CARD_HEIGHT}"
  role="img" aria-labelledby="card-title card-description">
  <title id="card-title">{escape(title)}</title>
  <desc id="card-description">{escape(description)}</desc>
  <defs>
    <linearGradient id="mark" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="{palette.accent}" />
      <stop offset="1" stop-color="{palette.opencode}" />
    </linearGradient>
    <filter id="glow" x="-30%" y="-30%" width="160%" height="160%">
      <feGaussianBlur stdDeviation="2" result="blur" />
      <feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge>
    </filter>
  </defs>
  <style>
    .display {{ font-family: "Avenir Next", "Segoe UI", sans-serif; }}
    .data {{ font-family: "SFMono-Regular", "Roboto Mono", monospace; }}
    .kicker {{ fill: {palette.muted}; font: 650 9px "SFMono-Regular", "Roboto Mono", monospace; letter-spacing: 1.1px; }}
    .label {{ fill: {palette.secondary}; font: 500 11px "Avenir Next", "Segoe UI", sans-serif; }}
    .micro {{ fill: {palette.muted}; font-size: 8px; }}
    .mix-value {{ fill: {palette.foreground}; font-size: 9px; }}
    .empty {{ fill: {palette.muted}; font: 500 12px "Avenir Next", "Segoe UI", sans-serif; }}
  </style>
  <rect x="1" y="1" width="718" height="218" rx="18"
    fill="{palette.background}" stroke="{palette.line}" stroke-width="2" />
  <path d="M230 20V200M548 20V200" stroke="{palette.line}" />
  <g transform="translate(23 23) scale(.083)" fill="url(#mark)">
    <path d="M27 153C13 88 62 24 128 24s115 64 101 129l-14 8c19-56-24-120-87-120S22 105 41 161l-14-8Z" />
    <rect x="105" y="99" width="25" height="72" rx="7" />
    <rect x="145" y="69" width="25" height="102" rx="7" />
    <path d="M22 168c28-25 53-24 87-4 39 24 76 47 125-5-8 24-28 43-56 52-31 10-59-5-88-23-26-16-45-23-62-7l-6-13Z" />
    <path d="M36 205c20-12 41-7 66 9 29 19 58 26 94 10-19 18-42 28-68 28-40 0-74-18-92-47Z" />
  </g>
  <text class="display" x="50" y="38" fill="{palette.foreground}"
    font-size="13" font-weight="650">TokenTide</text>
  <text class="kicker" x="24" y="68">{period_label}</text>
  <text class="display" x="22" y="112" fill="{palette.foreground}"
    font-size="39" font-weight="500" letter-spacing="-2">{escape(format_compact_count(total_tokens))}</text>
  <text class="data" x="24" y="132" fill="{palette.muted}"
    font-size="9">{total_tokens:,} Tokens</text>
  <text class="kicker" x="24" y="169">TODAY</text>
  <text class="data" x="24" y="193" fill="{palette.foreground}"
    font-size="14" font-weight="650">{escape(format_compact_count(today_tokens))}</text>
  <text class="kicker" x="118" y="169">REQUESTS</text>
  <text class="data" x="118" y="193" fill="{palette.foreground}"
    font-size="14" font-weight="650">{summary.totals.event_count:,}</text>
  <text class="kicker" x="250" y="38">DAILY TIDE</text>
  {bars}
  <polyline points="{points}" fill="none" stroke="{palette.accent}"
    stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"
    opacity=".72" filter="url(#glow)" />
  {empty_note}
  {dates}
  <text class="kicker" x="570" y="38">TOOL MIX</text>
  {mix}
  <rect x="570" y="177" width="126" height="22" rx="11" fill="{palette.panel_alt}" />
  <text class="data" x="633" y="192" text-anchor="middle"
    fill="{palette.accent}" font-size="8" font-weight="650"
    letter-spacing=".7">{filter_label}</text>
</svg>'''
