/** Redistribute integer basis points with largest remainders, preserving a 100% total. */
export function redistribute(
  weights: Record<string, number>,
  changed: string,
  percent: number,
): Record<string, number> {
  const keys = Object.keys(weights);
  if (!keys.includes(changed)) return weights;
  if (keys.length === 1) return { [changed]: 1 };
  const target = Math.round(Math.max(0, Math.min(100, percent)) * 100);
  const others = keys.filter((key) => key !== changed);
  const previous = others.reduce((total, key) => total + Math.max(0, weights[key] ?? 0), 0);
  const remaining = 10000 - target;
  const shares = others.map((key) => ({
    key,
    exact:
      remaining * (previous > 0 ? Math.max(0, weights[key] ?? 0) / previous : 1 / others.length),
  }));
  let spare = remaining - shares.reduce((total, item) => total + Math.floor(item.exact), 0);
  const ranked = [...shares].sort(
    (a, b) => (b.exact % 1) - (a.exact % 1) || a.key.localeCompare(b.key),
  );
  const units: Record<string, number> = Object.fromEntries(
    shares.map((item) => [item.key, Math.floor(item.exact)]),
  );
  for (const item of ranked) {
    if (spare-- > 0) units[item.key] = (units[item.key] ?? 0) + 1;
  }
  return Object.fromEntries(
    keys.map((key) => [key, (key === changed ? target : (units[key] ?? 0)) / 10000]),
  );
}
