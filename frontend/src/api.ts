/** API Client with XHR upload progress tracking and live SSE subscription. */

export async function apiRequest<T = any>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const token = localStorage.getItem('unico_token');
  const headers: Record<string, string> = {
    ...(options.headers as Record<string, string>),
  };
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  if (!(options.body instanceof FormData) && !headers['Content-Type']) {
    headers['Content-Type'] = 'application/json';
  }

  const res = await fetch(path, { ...options, headers });
  if (!res.ok) {
    let errText = `HTTP ${res.status}`;
    try {
      const data = await res.json();
      if (typeof data.detail === 'string') {
        errText = data.detail;
      } else if (data.detail?.message) {
        errText = data.detail.message;
      } else {
        errText = JSON.stringify(data.detail || data);
      }
    } catch {
      errText = await res.text();
    }
    throw new Error(errText);
  }
  return res.json();
}

export function uploadFileWithProgress(
  url: string,
  formData: FormData,
  onProgress: (pct: number) => void
): Promise<any> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open('POST', url);
    const token = localStorage.getItem('unico_token');
    if (token) {
      xhr.setRequestHeader('Authorization', `Bearer ${token}`);
    }
    xhr.upload.onprogress = (ev) => {
      if (ev.lengthComputable) {
        onProgress(Math.round((ev.loaded / ev.total) * 100));
      }
    };
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        try {
          resolve(JSON.parse(xhr.responseText));
        } catch {
          resolve({});
        }
      } else {
        try {
          const parsed = JSON.parse(xhr.responseText);
          reject(new Error(parsed.detail?.message || parsed.detail || `Upload failed (${xhr.status})`));
        } catch {
          reject(new Error(`Upload failed (${xhr.status})`));
        }
      }
    };
    xhr.onerror = () => reject(new Error('Network error during file upload'));
    xhr.send(formData);
  });
}

export const api = {
  getHealth: () => apiRequest('/api/system/health'),
  getCapabilities: () => apiRequest('/api/system/capabilities'),
  getSettings: () => apiRequest('/api/system/settings'),
  updateSettings: (settings: Record<string, any>) =>
    apiRequest('/api/system/settings', {
      method: 'PUT',
      body: JSON.stringify({ settings }),
    }),
  getOnboarding: () => apiRequest('/api/system/onboarding'),
  updateOnboarding: (onboarding_complete: boolean) =>
    apiRequest('/api/system/onboarding', {
      method: 'PUT',
      body: JSON.stringify({ onboarding_complete }),
    }),
  listReferences: (category?: string) =>
    apiRequest(
      category && category !== 'all'
        ? `/api/reference-library?category=${encodeURIComponent(category)}`
        : '/api/reference-library'
    ),
  createCategory: (category: string, subcategory?: string) => {
    const fd = new FormData();
    fd.append('category', category);
    if (subcategory) fd.append('subcategory', subcategory);
    return apiRequest('/api/reference-library/categories', {
      method: 'POST',
      body: fd,
    });
  },
  matchCategory: (filename: string, category: string) =>
    apiRequest(
      `/api/reference-library/match-category?filename=${encodeURIComponent(
        filename
      )}&category=${encodeURIComponent(category)}`
    ),
  ingestReference: (formData: FormData) =>
    apiRequest('/api/reference-library/ingest', {
      method: 'POST',
      body: formData,
    }),
  ingestReferenceWithProgress: (
    formData: FormData,
    onProgress: (pct: number) => void
  ) => uploadFileWithProgress('/api/reference-library/ingest', formData, onProgress),
  deleteReference: (assetId: string) =>
    apiRequest(`/api/reference-library/${assetId}`, { method: 'DELETE' }),
  searchReferences: (payload: any) =>
    apiRequest('/api/reference-library/search', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  listProjects: () => apiRequest('/api/projects'),
  createProject: (payload: any) =>
    apiRequest('/api/projects', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  deleteProject: (projectId: string) =>
    apiRequest(`/api/projects/${projectId}`, { method: 'DELETE' }),
  uploadSourceVideo: (
    projectId: string,
    file: File,
    onProgress?: (pct: number) => void
  ) => {
    const fd = new FormData();
    fd.append('file', file);
    if (onProgress) {
      return uploadFileWithProgress(
        `/api/projects/${projectId}/upload/source`,
        fd,
        onProgress
      );
    }
    return apiRequest(`/api/projects/${projectId}/upload/source`, {
      method: 'POST',
      body: fd,
    });
  },
  uploadReferenceVideo: (
    projectId: string,
    file: File,
    onProgress?: (pct: number) => void
  ) => {
    const fd = new FormData();
    fd.append('file', file);
    if (onProgress) {
      return uploadFileWithProgress(
        `/api/projects/${projectId}/upload/reference`,
        fd,
        onProgress
      );
    }
    return apiRequest(`/api/projects/${projectId}/upload/reference`, {
      method: 'POST',
      body: fd,
    });
  },
  startEditJob: (projectId: string, payload: any) =>
    apiRequest(`/api/projects/${projectId}/edit`, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  startGenerateJob: (projectId: string, payload: any) =>
    apiRequest(`/api/projects/${projectId}/generate`, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  generateAutoScript: (payload: any) =>
    apiRequest('/api/projects/meta/auto-script', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  listJobs: () => apiRequest('/api/jobs'),
  cancelJob: (jobId: string) =>
    apiRequest(`/api/jobs/${jobId}/cancel`, { method: 'POST' }),
  listTemplates: () => apiRequest('/api/templates'),
};
