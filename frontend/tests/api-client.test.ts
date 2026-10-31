import { afterEach, describe, expect, it, vi } from 'vitest';
import { ApiError, getAreas, getCells, getHealth, previewScores } from '../src/api/client';

afterEach(() => {
  vi.unstubAllGlobals();
});

it('loads all pages of service areas', async () => {
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce(new Response(JSON.stringify({ items: [{ id: 'a' }], total: 2 })))
    .mockResolvedValueOnce(new Response(JSON.stringify({ items: [{ id: 'b' }], total: 2 })));
  vi.stubGlobal('fetch', fetchMock);
  expect(await getAreas()).toEqual([{ id: 'a' }, { id: 'b' }]);
  expect(fetchMock.mock.calls[1]?.[0]).toContain('offset=1');
});

it('sends bounded cell queries and cancellable JSON previews', async () => {
  const fetchMock = vi.fn().mockImplementation(async () => new Response('{}'));
  vi.stubGlobal('fetch', fetchMock);
  const signal = new AbortController().signal;
  await getCells('area', 'road_density', [-122, 37, -121, 38], signal);
  expect(new URL(fetchMock.mock.calls[0]?.[0]).searchParams.get('bbox')).toBe('-122,37,-121,38');
  await previewScores(['area'], { road_density: 1 }, signal);
  expect(fetchMock.mock.calls[1]?.[1]).toMatchObject({
    method: 'POST',
    body: JSON.stringify({ service_area_ids: ['area'], weights: { road_density: 1 } }),
    signal,
    headers: { 'Content-Type': 'application/json' },
  });
});

it('surfaces the API error message', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn(
      async () =>
        new Response(JSON.stringify({ error: { message: 'No successful analysis' } }), {
          status: 404,
        }),
    ),
  );
  await expect(getCells('area', 'overall_score', [-122, 37, -121, 38])).rejects.toMatchObject({
    status: 404,
    message: 'No successful analysis',
  });
});

describe('getHealth', () => {
  it('requests /health on the configured base URL and returns the payload', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ status: 'ok' }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    );
    vi.stubGlobal('fetch', fetchMock);

    const result = await getHealth();

    expect(result).toEqual({ status: 'ok' });
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(String(fetchMock.mock.calls[0]?.[0])).toBe('http://localhost:8000/health');
  });

  it('throws ApiError on a non-OK response', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('boom', { status: 503 })));

    await expect(getHealth()).rejects.toMatchObject({ name: 'ApiError', status: 503 });
    await expect(getHealth()).rejects.toBeInstanceOf(ApiError);
  });
});
