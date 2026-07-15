const BASE_URL = process.env.EXPO_PUBLIC_API_BASE_URL || 'http://127.0.0.1:8000';
const API_KEY = process.env.EXPO_PUBLIC_API_KEY || '';

async function request(path, options = {}) {
  const res = await fetch(`${BASE_URL}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      'X-API-Key': API_KEY,
      ...options.headers,
    },
  });
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    const message = body?.detail?.message || `요청 실패 (${res.status})`;
    const error = new Error(message);
    error.status = res.status;
    error.code = body?.detail?.code;
    throw error;
  }
  if (res.status === 204) return null;
  return res.json();
}

// ---- 목소리 프로필 ----
export const createVoiceProfile = (payload) =>
  request('/v1/voice-profiles', { method: 'POST', body: JSON.stringify(payload) });

export const listVoiceProfiles = () => request('/v1/voice-profiles');

export const addVoiceSample = (profileId, formData) =>
  request(`/v1/voice-profiles/${profileId}/samples`, {
    method: 'POST',
    headers: { 'Content-Type': 'multipart/form-data' },
    body: formData,
  });

export const generateProfilePreview = (profileId, text) =>
  request(`/v1/voice-profiles/${profileId}/preview`, {
    method: 'POST',
    body: JSON.stringify({ text }),
  });

// ---- 동화책 ----
export const createBook = (payload) =>
  request('/v1/books', { method: 'POST', body: JSON.stringify(payload) });

export const getBook = (bookId) => request(`/v1/books/${bookId}`);

export const putPageRecording = (bookId, pageNumber, formData) =>
  request(`/v1/books/${bookId}/pages/${pageNumber}/recording`, {
    method: 'PUT',
    headers: { 'Content-Type': 'multipart/form-data' },
    body: formData,
  });

export const getPlaybackManifest = (bookId) => request(`/v1/books/${bookId}/playback-manifest`);

// ---- 자장가 ----
export const createLullaby = (payload) =>
  request('/v1/lullabies', { method: 'POST', body: JSON.stringify(payload) });

export const getLullaby = (lullabyId) => request(`/v1/lullabies/${lullabyId}`);

// ---- 라이브러리 / 작업 상태 ----
export const getLibrary = () => request('/v1/library');

export const getJob = (jobId) => request(`/v1/jobs/${jobId}`);

/**
 * 202로 접수된 비동기 작업을 완료될 때까지 폴링합니다.
 * intervalMs 간격으로 status_url을 조회하고, succeeded/failed에서 멈춥니다.
 */
export async function pollJob(jobId, { intervalMs = 1500, timeoutMs = 120000 } = {}) {
  const startedAt = Date.now();
  while (Date.now() - startedAt < timeoutMs) {
    const job = await getJob(jobId);
    if (job.status === 'succeeded' || job.status === 'failed') return job;
    await new Promise((resolve) => setTimeout(resolve, intervalMs));
  }
  throw new Error('작업 처리 시간이 초과됐습니다');
}

/**
 * X-API-Key 인증이 필요한 미디어(오디오/이미지)를 fetch로 받아 Blob URL로 변환합니다.
 * <audio src>/<img src>는 커스텀 헤더를 못 보내므로 이 방식을 씁니다.
 * 사용이 끝나면 URL.revokeObjectURL(url)로 해제해야 합니다.
 */
export async function fetchAuthedMediaUrl(path) {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { 'X-API-Key': API_KEY },
  });
  if (!res.ok) throw new Error(`미디어를 불러오지 못했습니다 (${res.status})`);
  const blob = await res.blob();
  return URL.createObjectURL(blob);
}

export const isApiConfigured = () => Boolean(API_KEY) && API_KEY !== 'replace-with-at-least-32-random-characters';
