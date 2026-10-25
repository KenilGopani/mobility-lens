import { afterEach, describe, expect, it, vi } from 'vitest';
import { ApiError, getHealth } from '../src/api/client';

afterEach(() => {
  vi.unstubAllGlobals();
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
