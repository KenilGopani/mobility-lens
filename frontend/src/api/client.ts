import type { Simulation, Operations } from './types';
import type {
  Area,
  Cells,
  Comparison,
  Detail,
  Metrics,
  Page,
  Preview,
  Quality,
  ScoringModel,
  Summary,
} from './types';

const DEFAULT_BASE_URL = 'http://localhost:8000';

export function getApiBaseUrl(): string {
  const raw = import.meta.env.VITE_API_BASE_URL as string | undefined;
  return (raw && raw.length > 0 ? raw : DEFAULT_BASE_URL).replace(/\/+$/, '');
}

export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

export interface HealthResponse {
  status: string;
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(`${getApiBaseUrl()}${path}`, {
    ...options,
    headers: {
      Accept: 'application/json',
      ...(options.body ? { 'Content-Type': 'application/json' } : {}),
    },
  });
  if (!response.ok) {
    const payload = (await response.json().catch(() => null)) as {
      error?: { message?: string };
    } | null;
    throw new ApiError(
      response.status,
      payload?.error?.message ?? `Request failed (${response.status})`,
    );
  }
  return (await response.json()) as T;
}

export function getHealth(): Promise<HealthResponse> {
  return request<HealthResponse>('/health');
}

const areaPath = (id: string) => `/api/v1/service-areas/${encodeURIComponent(id)}`;
export async function getAreas(signal?: AbortSignal): Promise<Area[]> {
  const items: Area[] = [];
  let offset = 0;
  while (true) {
    const page = await request<Page<Area>>(`/api/v1/service-areas?limit=200&offset=${offset}`, {
      signal,
    });
    items.push(...page.items);
    offset += page.items.length;
    if (offset >= page.total || page.items.length === 0) return items;
  }
}
export const getSummary = (id: string, signal?: AbortSignal) =>
  request<Summary>(`${areaPath(id)}/summary`, { signal });
export const getDetail = (id: string, signal?: AbortSignal) =>
  request<Detail>(areaPath(id), { signal });
export const getMetrics = (id: string, signal?: AbortSignal) =>
  request<Metrics>(`${areaPath(id)}/metrics`, { signal });
export const getQuality = (id: string, signal?: AbortSignal) =>
  request<Quality>(`${areaPath(id)}/quality`, { signal });
export const getCells = (id: string, metric: string, bbox: number[], signal?: AbortSignal) =>
  request<Cells>(
    `${areaPath(id)}/cells?${new URLSearchParams({ metric, bbox: bbox.join(','), limit: '2000' })}`,
    { signal },
  );
export const getModels = (signal?: AbortSignal) =>
  request<{ items: ScoringModel[] }>('/api/v1/scoring-models', { signal });
export const compareAreas = (ids: string[], signal?: AbortSignal) =>
  request<Comparison>('/api/v1/comparisons', {
    method: 'POST',
    body: JSON.stringify({ service_area_ids: ids }),
    signal,
  });
export const previewScores = (
  ids: string[],
  weights: Record<string, number>,
  signal?: AbortSignal,
) =>
  request<Preview>('/api/v1/scoring/preview', {
    method: 'POST',
    body: JSON.stringify({ service_area_ids: ids, weights }),
    signal,
  });

export async function getSimulations(id: string, signal?: AbortSignal): Promise<Page<Simulation>> {
  const all: Simulation[] = [];
  let offset = 0;
  while (true) {
    const page = await request<Page<Simulation>>(
      `${areaPath(id)}/simulations?limit=200&offset=${offset}`,
      { signal },
    );
    all.push(...page.items);
    offset += page.items.length;
    if (offset >= page.total || !page.items.length) return { ...page, items: all, offset: 0 };
  }
}
export const getOperations = (id: string, simulation?: string, signal?: AbortSignal) =>
  request<Operations>(
    `${areaPath(id)}/operations${simulation ? `?simulation_run_id=${encodeURIComponent(simulation)}` : ''}`,
    { signal },
  );
