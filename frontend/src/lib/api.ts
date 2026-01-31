"""
API client functions for frontend.
Connects to backend FastAPI server.
"""

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

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

export interface ChatRequest {
  message: string;
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
}

/**
 * Process video URLs to create a trip itinerary
 */
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

/**
 * Get all trips
 */
export async function listTrips() {
  const response = await fetch(`${API_BASE_URL}/api/trips`);
  
  if (!response.ok) {
    throw new Error('Failed to fetch trips');
  }

  return response.json();
}

/**
 * Get a specific trip
 */
export async function getTrip(tripId: string) {
  const response = await fetch(`${API_BASE_URL}/api/trips/${tripId}`);
  
  if (!response.ok) {
    throw new Error('Trip not found');
  }

  return response.json();
}

/**
 * Delete a trip
 */
export async function deleteTrip(tripId: string) {
  const response = await fetch(`${API_BASE_URL}/api/trips/${tripId}`, {
    method: 'DELETE',
  });
  
  if (!response.ok) {
    throw new Error('Failed to delete trip');
  }

  return response.json();
}

/**
 * Send a chat message
 */
export async function sendChatMessage(
  tripId: string,
  message: string
): Promise<ChatResponse> {
  const response = await fetch(`${API_BASE_URL}/api/trips/${tripId}/chat`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ message }),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to send message');
  }

  return response.json();
}

/**
 * Health check
 */
export async function healthCheck() {
  const response = await fetch(`${API_BASE_URL}/api/health`);
  return response.json();
}
