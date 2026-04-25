/**
 * API client functions for frontend.
 * Connects to backend FastAPI server.
 */

const API_BASE_URL = import.meta.env.VITE_API_URL || '';

export interface VideoProcessRequest {
  urls: string[];
  trip_title?: string;
}

export interface VideoProcessResponse {
  trip_id: string;
  status: 'processing' | 'completed' | 'failed';
  message: string;
  trip?: any;
  error?: string;
}

export interface ChatResponse {
  messages: Array<{
    id: string;
    type: 'user' | 'agent' | 'interrupt';
    content: string;
    timestamp: string;
    interrupt_type?: string;
    options?: any[];
    status?: string;
  }>;
  updated_trip?: any;
}

export interface WorkspaceSnapshotResponse {
  workspace_id: string;
  trip: any;
  media_by_place: Record<string, Array<{ title: string; url: string; source_url?: string; platform: string; autoplay: boolean }>>;
  runtime_state: Record<string, unknown>;
  workspace_memory: Record<string, unknown>;
  recent_events: Array<Record<string, unknown>>;
  updated_at: string;
}

export interface BrowserTakeoverSessionResponse {
  session_id: string;
  workspace_id?: string | null;
  active: boolean;
  current_url: string;
  embed_url: string;
}

export async function processVideos(
  urls: string[],
  tripTitle?: string
): Promise<VideoProcessResponse> {
  const response = await fetch(`${API_BASE_URL}/api/videos/process`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ urls, trip_title: tripTitle }),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to process videos');
  }

  return response.json();
}


export async function processWorkspaceVideos(
  workspaceId: string,
  urls: string[],
  tripTitle?: string,
): Promise<{ workspace_id: string; trip_id: string; snapshot: WorkspaceSnapshotResponse; imported_count: number; failed_count: number }> {
  const response = await fetch(`${API_BASE_URL}/api/workspaces/${workspaceId}/videos/process`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ urls, trip_title: tripTitle }),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to process workspace videos');
  }

  return response.json();
}

export async function listTrips() {
  const response = await fetch(`${API_BASE_URL}/api/trips`);

  if (!response.ok) {
    throw new Error('Failed to fetch trips');
  }

  return response.json();
}

export async function getTrip(tripId: string) {
  const response = await fetch(`${API_BASE_URL}/api/trips/${tripId}`);

  if (!response.ok) {
    throw new Error('Trip not found');
  }

  return response.json();
}

export async function deleteTrip(tripId: string) {
  const response = await fetch(`${API_BASE_URL}/api/trips/${tripId}`, {
    method: 'DELETE',
  });

  if (!response.ok) {
    throw new Error('Failed to delete trip');
  }

  return response.json();
}

export async function sendChatMessage(
  tripId: string,
  message: string,
  history?: { role: string; content: string }[]
): Promise<ChatResponse> {
  const response = await fetch(`${API_BASE_URL}/api/trips/${tripId}/chat`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ message, history: history || [] }),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to send message');
  }

  return response.json();
}

export async function sendWorkspaceMessage(
  workspaceId: string,
  message: string,
  userId?: string,
): Promise<ChatResponse> {
  const response = await fetch(`${API_BASE_URL}/api/workspaces/${workspaceId}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, workspace_id: workspaceId, user_id: userId, source: 'web' }),
  });
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to send workspace message');
  }
  return response.json();
}

export async function getWorkspaceSnapshot(
  workspaceId: string,
  token?: string,
): Promise<WorkspaceSnapshotResponse> {
  const qp = token ? `?token=${encodeURIComponent(token)}` : '';
  const response = await fetch(`${API_BASE_URL}/api/workspaces/${workspaceId}/snapshot${qp}`);
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to fetch workspace snapshot');
  }
  return response.json();
}

export function getWorkspaceEventsWebSocketUrl(workspaceId: string, token?: string): string {
  const base = (API_BASE_URL || window.location.origin)
    .replace(/^http:\/\//i, 'ws://')
    .replace(/^https:\/\//i, 'wss://')
    .replace(/\/$/, '');
  const qp = token ? `?token=${encodeURIComponent(token)}` : '';
  return `${base}/api/workspaces/${encodeURIComponent(workspaceId)}/events/ws${qp}`;
}

export async function createWorkspaceShareLink(workspaceId: string) {
  const response = await fetch(`${API_BASE_URL}/api/workspaces/${workspaceId}/share-link`, {
    method: 'POST',
  });
  if (!response.ok) {
    throw new Error('Failed to create workspace share link');
  }
  return response.json();
}

export async function getBrowserTakeoverSession(
  token: string,
): Promise<BrowserTakeoverSessionResponse> {
  const response = await fetch(`${API_BASE_URL}/api/browser/takeover?token=${encodeURIComponent(token)}`);
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail || 'Failed to load browser takeover session');
  }
  return response.json();
}

export async function healthCheck() {
  const response = await fetch(`${API_BASE_URL}/api/health`);
  return response.json();
}
