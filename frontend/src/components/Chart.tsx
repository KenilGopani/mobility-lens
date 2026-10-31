import { useEffect, useRef, useState } from 'react';
import type { Data, Layout } from 'plotly.js';

export function Chart({
  data,
  title,
  stacked = false,
  axisLabel = 'Score points',
}: {
  data: Data[];
  title: string;
  stacked?: boolean;
  axisLabel?: string;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    const target = ref.current;
    if (!target) return;
    let active = true;
    let dispose: (() => void) | undefined;
    void import('plotly.js-basic-dist-min')
      .then(async ({ default: Plotly }) => {
        if (!active) return;
        const layout: Partial<Layout> = {
          autosize: true,
          height: 300,
          margin: { t: 20, r: 20, b: 65, l: 50 },
          paper_bgcolor: 'transparent',
          plot_bgcolor: 'transparent',
          font: { family: 'Arial, sans-serif', color: '#52605c' },
          barmode: stacked ? 'stack' : 'group',
          yaxis: { title: { text: axisLabel }, gridcolor: '#e6ebe7', rangemode: 'tozero' },
          legend: { orientation: 'h' },
        };
        dispose = () => Plotly.purge(target);
        await Plotly.react(target, data, layout, { responsive: true, displayModeBar: false });
      })
      .catch(() => {
        if (active) setFailed(true);
      });
    const resize = new ResizeObserver(() => {
      window.dispatchEvent(new Event('resize'));
    });
    resize.observe(target);
    return () => {
      active = false;
      resize.disconnect();
      dispose?.();
    };
  }, [data, stacked, axisLabel]);
  return (
    <div className="chart" role="img" aria-label={title}>
      {failed ? (
        <p>Chart unavailable. Values are available in the table below.</p>
      ) : (
        <div ref={ref} />
      )}
    </div>
  );
}
