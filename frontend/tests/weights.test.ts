import { expect, it } from 'vitest';
import { redistribute } from '../src/features/scoring/weights';
it('preserves exactly 100 percent through repeated edits and zero-weight redistribution', () => {
  let weights = { a: 0.25, b: 0.25, c: 0.2, d: 0.15, e: 0.15 };
  for (let i = 0; i < 101; i++) {
    weights = redistribute(weights, 'a', i) as typeof weights;
    expect(Object.values(weights).reduce((a, b) => a + b, 0)).toBeCloseTo(1, 10);
    expect(Object.values(weights).every((w) => w >= 0 && w <= 1)).toBe(true);
    expect(weights.a).toBeCloseTo(i / 100, 10);
  }
  expect(redistribute(weights, 'a', 0)).toEqual({ a: 0, b: 0.25, c: 0.25, d: 0.25, e: 0.25 });
});
