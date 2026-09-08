import type { AnalysisResponse, HealthStatus, ModelStatus, Prediction, Report, Study, UploadResponse } from '../types';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    ...options,
    headers: {
      ...(options.body instanceof FormData ? {} : { 'Content-Type': 'application/json' }),
      ...(options.headers || {}),
    },
  });

  if (!response.ok) {
    const payload = await response.json().catch(() => ({ detail: 'Request failed.' }));
    throw new Error(payload.detail || 'Request failed.');
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return response.json() as Promise<T>;
}

export const api = {
  health: () => request<HealthStatus>('/api/health'),
  modelStatus: () => request<ModelStatus>('/api/model/status'),
  getStudies: () => request<Study[]>('/api/studies'),
  uploadStudy: (files: File[]) => {
    const formData = new FormData();
    files.forEach((file) => formData.append('files', file));
    return request<UploadResponse>('/api/studies/upload', { method: 'POST', body: formData });
  },
  analyzeStudy: (studyId: string) => request<AnalysisResponse>(`/api/studies/${studyId}/analyze`, { method: 'POST' }),
  getStudy: (studyId: string) => request<Study>(`/api/studies/${studyId}`),
  getPredictions: (studyId: string) => request<{ studyId: string; predictions: Prediction[] }>(`/api/studies/${studyId}/predictions`),
  getReport: (studyId: string) => request<Report>(`/api/studies/${studyId}/report`),
  updateReport: (studyId: string, payload: Pick<Report, 'findings' | 'impression' | 'recommendation' | 'reviewStatus'>) => request<Report>(`/api/studies/${studyId}/report`, { method: 'PUT', body: JSON.stringify(payload) }),
  markReviewed: (studyId: string) => request<{ studyId: string; status: string }>(`/api/studies/${studyId}/review`, { method: 'POST' }),
};
