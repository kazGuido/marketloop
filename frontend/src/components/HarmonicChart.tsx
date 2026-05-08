import {
  CandlestickSeries,
  ColorType,
  createChart,
  type IChartApi,
  type ISeriesApi,
  type UTCTimestamp
} from "lightweight-charts";
import { useEffect, useMemo, useRef, useState } from "react";

import { api } from "../lib/api";
import type { Candle, Pattern, PivotCoord } from "../types/api";

interface HarmonicChartProps {
  pattern: Pattern | null;
}

interface OverlayPoint {
  x: number;
  y: number;
}

interface OverlayState {
  triangleOne: OverlayPoint[];
  triangleTwo: OverlayPoint[];
  prz: { x: number; y: number; width: number; height: number };
}

export function HarmonicChart({ pattern }: HarmonicChartProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const patternRef = useRef<Pattern | null>(pattern);
  const [candles, setCandles] = useState<Candle[]>([]);
  const [overlay, setOverlay] = useState<OverlayState | null>(null);

  useEffect(() => {
    patternRef.current = pattern;
  }, [pattern]);

  useEffect(() => {
    if (!pattern) return;
    api.getCandles(pattern.symbol, pattern.timeframe).then(setCandles).catch(console.error);
  }, [pattern]);

  useEffect(() => {
    if (!containerRef.current) return;
    const chart = createChart(containerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: "#0d0e10" },
        textColor: "#b9cbbb"
      },
      grid: {
        vertLines: { color: "rgba(59, 75, 62, 0.35)" },
        horzLines: { color: "rgba(59, 75, 62, 0.35)" }
      },
      rightPriceScale: {
        borderColor: "#3b4b3e"
      },
      timeScale: {
        borderColor: "#3b4b3e",
        timeVisible: true
      },
      crosshair: {
        vertLine: { color: "#4cd6ff", labelBackgroundColor: "#1f2022" },
        horzLine: { color: "#4cd6ff", labelBackgroundColor: "#1f2022" }
      },
      height: containerRef.current.clientHeight || 620
    });
    const legacyAddCandles = (chart as unknown as { addCandlestickSeries?: Function }).addCandlestickSeries;
    const series =
      typeof legacyAddCandles === "function"
        ? legacyAddCandles.call(chart, {
            upColor: "#00e383",
            downColor: "#d30017",
            wickUpColor: "#00e383",
            wickDownColor: "#d30017",
            borderVisible: false
          })
        : chart.addSeries(CandlestickSeries, {
            upColor: "#00e383",
            downColor: "#d30017",
            wickUpColor: "#00e383",
            wickDownColor: "#d30017",
            borderVisible: false
          });

    chartRef.current = chart;
    seriesRef.current = series;

    const resizeObserver = new ResizeObserver(([entry]) => {
      chart.applyOptions({
        width: entry.contentRect.width,
        height: Math.max(entry.contentRect.height, 360)
      });
      updateOverlay();
    });
    resizeObserver.observe(containerRef.current);

    return () => {
      resizeObserver.disconnect();
      chart.remove();
      chartRef.current = null;
      seriesRef.current = null;
    };
    // The overlay updater reads refs and latest pattern/candles through the effect below.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const chartData = useMemo(
    () =>
      candles.map((candle) => ({
        time: candle.time as UTCTimestamp,
        open: candle.open,
        high: candle.high,
        low: candle.low,
        close: candle.close
      })),
    [candles]
  );

  useEffect(() => {
    if (!seriesRef.current || chartData.length === 0) return;
    seriesRef.current.setData(chartData);
    chartRef.current?.timeScale().fitContent();
    updateOverlay();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [chartData, pattern]);

  function updateOverlay() {
    const chart = chartRef.current;
    const series = seriesRef.current;
    const container = containerRef.current;
    const currentPattern = patternRef.current;
    if (!chart || !series || !container || !currentPattern) {
      setOverlay(null);
      return;
    }
    const x = coordFor(currentPattern.coords.X, chart, series);
    const a = coordFor(currentPattern.coords.A, chart, series);
    const b = coordFor(currentPattern.coords.B, chart, series);
    const c = coordFor(currentPattern.coords.C, chart, series);
    const upper = series.priceToCoordinate(currentPattern.prz_upper);
    const lower = series.priceToCoordinate(currentPattern.prz_lower);
    const cTime = chart.timeScale().timeToCoordinate(currentPattern.coords.C.time as UTCTimestamp);
    if ([x, a, b, c].some((point) => !point) || upper == null || lower == null || cTime == null) {
      setOverlay(null);
      return;
    }
    setOverlay({
      triangleOne: [x!, a!, b!],
      triangleTwo: [a!, b!, c!],
      prz: {
        x: cTime,
        y: Math.min(upper, lower),
        width: container.clientWidth - cTime,
        height: Math.abs(lower - upper)
      }
    });
  }

  return (
    <section className="flex min-w-0 flex-1 flex-col border-r border-outline-variant bg-surface-container-lowest">
      <div className="flex h-8 shrink-0 items-center justify-between border-b border-outline-variant bg-surface px-md">
        <div className="flex min-w-0 items-center gap-md">
          <span className="truncate font-data-mono text-data-mono text-primary-fixed-dim">
            {pattern?.symbol ?? "NO-SIGNAL"}
          </span>
          <span className="font-data-mono text-data-mono text-on-surface-variant opacity-60">
            {pattern?.timeframe ?? "--"}
          </span>
          {pattern && (
            <span className="hidden font-data-mono text-data-mono text-primary-container sm:inline">
              PRZ {pattern.prz_lower.toFixed(4)} - {pattern.prz_upper.toFixed(4)}
            </span>
          )}
        </div>
        <div className="flex items-center gap-sm font-data-mono text-[10px] text-on-surface-variant">
          <span>{candles.length.toString().padStart(3, "0")} CANDLES</span>
          <span className="hidden sm:inline">SNAP</span>
          <span className="hidden sm:inline">FULLSCREEN</span>
        </div>
      </div>

      <div className="relative min-h-[420px] flex-1 overflow-hidden bg-surface-container-lowest">
        <div className="technical-grid pointer-events-none absolute inset-0 opacity-60" />
        <div ref={containerRef} className="absolute inset-0 h-full w-full" />
        {overlay && (
          <svg className="pointer-events-none absolute inset-0 h-full w-full">
            <polygon points={points(overlay.triangleOne)} fill="rgba(76, 214, 255, 0.08)" stroke="#4cd6ff" />
            <polygon points={points(overlay.triangleTwo)} fill="rgba(0, 255, 148, 0.08)" stroke="#00ff94" />
            <rect
              x={overlay.prz.x}
              y={overlay.prz.y}
              width={overlay.prz.width}
              height={overlay.prz.height}
              fill="rgba(0, 255, 148, 0.08)"
              stroke="#00e383"
              strokeDasharray="4 4"
            />
          </svg>
        )}
        {!pattern && (
          <div className="absolute left-1/2 top-1/2 w-[min(28rem,calc(100%-2rem))] -translate-x-1/2 -translate-y-1/2 border border-dashed border-outline-variant bg-surface/80 p-lg text-center backdrop-blur">
            <div className="font-label-caps text-label-caps uppercase text-primary-fixed-dim">Awaiting active pattern</div>
            <p className="mt-sm font-body-sm text-body-sm text-on-surface-variant">
              Select a signal once the scanner publishes an active harmonic setup.
            </p>
          </div>
        )}
        {pattern && (
          <div className="absolute left-md top-md border border-outline-variant bg-surface/80 p-sm backdrop-blur">
            <div className="grid gap-xs font-data-mono text-[11px]">
              <span className="text-primary-container">SCORE: {pattern.confluence_score}</span>
              <span className="text-tertiary-fixed-dim">PATTERN: {pattern.pattern_type}</span>
              <span className="text-on-surface-variant">DIR: {pattern.direction}</span>
            </div>
          </div>
        )}
      </div>
    </section>
  );
}

function coordFor(point: PivotCoord, chart: IChartApi, series: ISeriesApi<"Candlestick">): OverlayPoint | null {
  const x = chart.timeScale().timeToCoordinate(point.time as UTCTimestamp);
  const y = series.priceToCoordinate(point.price);
  if (x == null || y == null) return null;
  return { x, y };
}

function points(input: OverlayPoint[]): string {
  return input.map((point) => `${point.x},${point.y}`).join(" ");
}
