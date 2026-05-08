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
  const [candles, setCandles] = useState<Candle[]>([]);
  const [overlay, setOverlay] = useState<OverlayState | null>(null);

  useEffect(() => {
    if (!pattern) return;
    api.getCandles(pattern.symbol, pattern.timeframe).then(setCandles).catch(console.error);
  }, [pattern]);

  useEffect(() => {
    if (!containerRef.current) return;
    const chart = createChart(containerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: "#020617" },
        textColor: "#94a3b8"
      },
      grid: {
        vertLines: { color: "#0f172a" },
        horzLines: { color: "#0f172a" }
      },
      rightPriceScale: {
        borderColor: "#1e293b"
      },
      timeScale: {
        borderColor: "#1e293b",
        timeVisible: true
      },
      height: 620
    });
    const legacyAddCandles = (chart as unknown as { addCandlestickSeries?: Function }).addCandlestickSeries;
    const series =
      typeof legacyAddCandles === "function"
        ? legacyAddCandles.call(chart, { upColor: "#22c55e", downColor: "#ef4444", borderVisible: false })
        : chart.addSeries(CandlestickSeries, {
            upColor: "#22c55e",
            downColor: "#ef4444",
            borderVisible: false
          });

    chartRef.current = chart;
    seriesRef.current = series;

    const resizeObserver = new ResizeObserver(([entry]) => {
      chart.applyOptions({ width: entry.contentRect.width });
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
    if (!chart || !series || !container || !pattern) {
      setOverlay(null);
      return;
    }
    const x = coordFor(pattern.coords.X, chart, series);
    const a = coordFor(pattern.coords.A, chart, series);
    const b = coordFor(pattern.coords.B, chart, series);
    const c = coordFor(pattern.coords.C, chart, series);
    const upper = series.priceToCoordinate(pattern.prz_upper);
    const lower = series.priceToCoordinate(pattern.prz_lower);
    const cTime = chart.timeScale().timeToCoordinate(pattern.coords.C.time as UTCTimestamp);
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
    <section className="flex-1 bg-slate-950 p-4">
      <div className="mb-4 flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold text-white">
            {pattern ? `${pattern.symbol} ${pattern.timeframe}` : "Select an active signal"}
          </h2>
          {pattern && (
            <p className="text-sm text-slate-400">
              PRZ {pattern.prz_lower.toFixed(4)} - {pattern.prz_upper.toFixed(4)}
            </p>
          )}
        </div>
      </div>

      <div className="relative overflow-hidden rounded-2xl border border-slate-800 bg-slate-950">
        <div ref={containerRef} className="h-[620px] w-full" />
        {overlay && (
          <svg className="pointer-events-none absolute inset-0 h-full w-full">
            <polygon points={points(overlay.triangleOne)} fill="rgba(34, 211, 238, 0.16)" stroke="#22d3ee" />
            <polygon points={points(overlay.triangleTwo)} fill="rgba(168, 85, 247, 0.14)" stroke="#a855f7" />
            <rect
              x={overlay.prz.x}
              y={overlay.prz.y}
              width={overlay.prz.width}
              height={overlay.prz.height}
              fill="rgba(250, 204, 21, 0.15)"
              stroke="#facc15"
            />
          </svg>
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
