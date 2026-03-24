/**
 * useSession Hook
 * Clean, deterministic session management for Spiritual Companion
 */

import { useState, useEffect, useCallback } from 'react';

/* =======================
   Types
======================= */

export interface Citation {
  reference: string;
  scripture: string;
  text: string;
  score: number;
}

export interface SourceReference {
  scripture: string;
  reference: string;
  context_text: string;
  relevance_score: number;
}

export interface Product {
  name: string;
  category: string;
  amount: number;
  currency: string;
  description?: string;
  image_url?: string;
  product_url?: string;
}

export interface FlowMetadata {
  detected_domain: string | null;
  emotional_state: string | null;
  topics?: string[];
  readiness_score: number;
  guidance_type: string | null;
}

export interface ConversationalResponse {
  session_id: string;
  phase: 'listening' | 'clarification' | 'answering' | 'synthesis' | 'guidance' | 'closure';
  response: string;
  signals_collected: Record<string, string>;
  turn_count: number;
  is_complete: boolean;
  citations?: Citation[];
  sources?: SourceReference[];
  recommended_products?: Product[];
  flow_metadata?: FlowMetadata;
}

export interface SessionState {
  sessionId: string | null;
  phase: ConversationalResponse['phase'];
  turnCount: number;
  signalsCollected: Record<string, string>;
  isComplete: boolean;
}

export interface UserProfile {
  age_group?: string;
  gender?: string;
  profession?: string;
  name?: string;
  preferred_deity?: string;
  rashi?: string;
  gotra?: string;
  nakshatra?: string;
}

/* =======================
   Config
======================= */

const rawApiUrl = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8080';
const API_URL = rawApiUrl.endsWith('/') ? rawApiUrl.slice(0, -1) : rawApiUrl;

const STORAGE_KEY = 'spiritual_session_id';

/* =======================
   Hook
======================= */

export function useSession(userProfile?: UserProfile, authHeader?: Record<string, string>) {
  const [session, setSession] = useState<SessionState>({
    sessionId: null,
    phase: 'listening',
    turnCount: 0,
    signalsCollected: {},
    isComplete: false,
  });

  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  /* =======================
     Restore session once
  ======================= */

  useEffect(() => {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved) {
      setSession((prev) => ({
        ...prev,
        sessionId: saved,
      }));
    }
  }, []);

  /* =======================
     Persist session
  ======================= */

  useEffect(() => {
    if (session.sessionId) {
      localStorage.setItem(STORAGE_KEY, session.sessionId);
    }
  }, [session.sessionId]);

  /* =======================
     Create session
  ======================= */

  const createSession = useCallback(async (): Promise<string> => {
    const res = await fetch(`${API_URL}/api/session/create`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
    });

    if (!res.ok) {
      throw new Error('Failed to create session');
    }

    const data = await res.json();

    setSession({
      sessionId: data.session_id,
      phase: data.phase,
      turnCount: 0,
      signalsCollected: {},
      isComplete: false,
    });

    return data.session_id;
  }, []);

  /* =======================
     Send message (CORE)
  ======================= */

  const sendMessage = useCallback(
    async (message: string, language: string = 'en'): Promise<ConversationalResponse> => {
      setIsLoading(true);
      setError(null);

      try {
        let sessionId = session.sessionId;

        // First message → create session
        if (!sessionId) {
          sessionId = await createSession();
        }

        const body: any = {
          session_id: sessionId,
          message,
          language,
        };

        // Send user profile ONLY on first turn
        if (session.turnCount === 0 && userProfile) {
          body.user_profile = userProfile;
        }

        const headers: Record<string, string> = {
          'Content-Type': 'application/json',
          ...authHeader,
        };

        const res = await fetch(`${API_URL}/api/conversation`, {
          method: 'POST',
          headers,
          body: JSON.stringify(body),
        });

        if (!res.ok) {
          const err = await res.json().catch(() => ({}));
          throw new Error(err.detail || 'Conversation failed');
        }

        const data: ConversationalResponse = await res.json();

        setSession({
          sessionId: data.session_id,
          phase: data.phase,
          turnCount: data.turn_count,
          signalsCollected: data.signals_collected,
          isComplete: data.is_complete,
        });

        return data;
      } catch (e: any) {
        setError(e.message || 'Failed to send message');
        throw e;
      } finally {
        setIsLoading(false);
      }
    },
    [session.sessionId, session.turnCount, userProfile, authHeader, createSession]
  );

  /* =======================
     Send message stream (SSE)
  ======================= */

  const sendMessageStream = useCallback(
    async (
      message: string,
      language: string,
      onToken: (text: string) => void,
      onMetadata: (meta: any) => void,
      onDone: (final: any) => void,
      onError: (error: Error) => void,
    ): Promise<void> => {
      setIsLoading(true);
      setError(null);

      const controller = new AbortController();
      let timeout: ReturnType<typeof setTimeout> | null = null;

      try {
        let sessionId = session.sessionId;
        if (!sessionId) {
          sessionId = await createSession();
        }

        const body: any = { session_id: sessionId, message, language };
        if (session.turnCount === 0 && userProfile) {
          body.user_profile = userProfile;
        }

        const headers: Record<string, string> = {
          'Content-Type': 'application/json',
          ...authHeader,
        };

        timeout = setTimeout(() => controller.abort(), 180000);

        const res = await fetch(`${API_URL}/api/conversation/stream`, {
          method: 'POST',
          headers,
          body: JSON.stringify(body),
          signal: controller.signal,
        });

        if (!res.ok) {
          clearTimeout(timeout);
          const err = await res.json().catch(() => ({}));
          throw new Error(err.detail || 'Stream request failed');
        }

        const reader = res.body!.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        let currentEvent = '';
        let doneReceived = false;

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          clearTimeout(timeout);
          timeout = setTimeout(() => controller.abort(), 120000);
          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split('\n');
          buffer = lines.pop() || '';

          for (const line of lines) {
            if (line.startsWith('event: ')) {
              currentEvent = line.slice(7).trim();
            } else if (line.startsWith('data: ') && currentEvent) {
              try {
                const data = JSON.parse(line.slice(6));
                if (currentEvent === 'metadata') {
                  setSession(prev => ({
                    ...prev,
                    sessionId: data.session_id || prev.sessionId,
                    phase: data.phase || prev.phase,
                    turnCount: data.turn_count ?? prev.turnCount,
                    signalsCollected: data.signals_collected || prev.signalsCollected,
                  }));
                  onMetadata(data);
                }
                else if (currentEvent === 'token') onToken(data.text);
                else if (currentEvent === 'done') { doneReceived = true; onDone(data); }
                else if (currentEvent === 'error') { /* logged; event: done follows with fallback text */ }
              } catch {
                // skip malformed JSON lines
              }
              currentEvent = '';
            }
          }
        }

        // Safety net: stream closed without done event
        if (!doneReceived) {
          onError(new Error('Stream ended unexpectedly'));
        }
      } catch (e: any) {
        setError(e.message || 'Stream failed');
        onError(e);
      } finally {
        if (timeout) clearTimeout(timeout);
        setIsLoading(false);
      }
    },
    [session.sessionId, session.turnCount, userProfile, authHeader, createSession]
  );

  /* =======================
     Reset session
  ======================= */

  const resetSession = useCallback(() => {
    localStorage.removeItem(STORAGE_KEY);
    setSession({
      sessionId: null,
      phase: 'listening',
      turnCount: 0,
      signalsCollected: {},
      isComplete: false,
    });
    setError(null);
  }, []);

  /* =======================
     Load session (NEW)
  ======================= */
  const loadSession = useCallback(async (sessionId: string): Promise<any> => {
    setIsLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_URL}/api/user/conversations/${sessionId}`, {
        method: 'GET',
        headers: {
          ...authHeader,
        },
      });

      if (!res.ok) {
        throw new Error('Failed to load session');
      }

      const data = await res.json();

      // Update local session state from the session metadata if available
      // Note: Backend conversation doc might have different structure than active session
      setSession({
        sessionId: data.session_id || sessionId,
        phase: (data.phase as any) || 'listening',
        turnCount: data.turn_count || (data.messages ? data.messages.length : 0),
        signalsCollected: data.signals_collected || {},
        isComplete: data.is_complete || false,
      });

      return data;
    } catch (e: any) {
      setError(e.message || 'Failed to load session');
      throw e;
    } finally {
      setIsLoading(false);
    }
  }, [authHeader]);

  return {
    session,
    isLoading,
    error,
    sendMessage,
    sendMessageStream,
    resetSession,
    loadSession,
  };
}
