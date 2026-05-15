/**
 * useSession Hook
 * Clean, deterministic session management for Spiritual Companion
 */

import { useState, useEffect, useCallback, useRef } from 'react';

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
   Errors
======================= */

export class AuthExpiredError extends Error {
  constructor() {
    super('Session expired. Please log in again.');
    this.name = 'AuthExpiredError';
  }
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

  // Mounted guard — prevents setState after unmount (Fix 3).
  //
  // The body MUST set mountedRef.current=true on every effect run so the
  // hook works under React 18 StrictMode (and Next.js dev mode). StrictMode
  // intentionally runs the effect cleanup once during the initial mount
  // before re-running the effect, to surface incorrect cleanup logic. If
  // the body doesn't set the ref back to true, the cleanup's
  // `mountedRef.current = false` sticks and every subsequent setState
  // guarded by `mountedRef.current && ...` is silently dropped — including
  // the SSE metadata handler that persists session.sessionId to
  // localStorage. The user-visible symptom: chat works but session ID is
  // never restored on reload.
  const mountedRef = useRef(true);
  useEffect(() => {
    mountedRef.current = true;
    return () => { mountedRef.current = false; };
  }, []);

  // Fix 5: AbortController for cancelling in-flight non-streaming requests
  const messageAbortRef = useRef<AbortController | null>(null);

  // Fix 6: Ref for authHeader to avoid stale closures in callbacks
  const authHeaderRef = useRef(authHeader);
  useEffect(() => { authHeaderRef.current = authHeader; }, [authHeader]);

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
     Send message (CORE)
  ======================= */

  const sendMessage = useCallback(
    async (message: string, language: string = 'en'): Promise<ConversationalResponse> => {
      // Fix 5: Cancel any in-flight request before starting a new one
      messageAbortRef.current?.abort();
      messageAbortRef.current = new AbortController();

      setIsLoading(true);
      setError(null);

      try {
        const body: Record<string, unknown> = {
          session_id: session.sessionId,
          message,
          language,
        };

        // Send user profile ONLY on first turn
        if (session.turnCount === 0 && userProfile) {
          body.user_profile = userProfile;
        }

        // Fix 6: Use ref for fresh authHeader (avoid stale closure)
        const headers: Record<string, string> = {
          'Content-Type': 'application/json',
          ...(authHeaderRef.current || {}),
        };

        const res = await fetch(`${API_URL}/api/conversation`, {
          method: 'POST',
          headers,
          body: JSON.stringify(body),
          signal: messageAbortRef.current.signal,
          credentials: 'include',  // Fix 4: httpOnly cookie auth
        });

        if (!res.ok) {
          if (res.status === 401) throw new AuthExpiredError();
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
    [session.sessionId, session.turnCount, userProfile, authHeader]
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
      onStatus?: (status: { stage: string; message: string }) => void,
    ): Promise<void> => {
      setIsLoading(true);
      setError(null);

      try {
        const body: Record<string, unknown> = { session_id: session.sessionId, message, language };
        if (session.turnCount === 0 && userProfile) {
          body.user_profile = userProfile;
        }

        // Fix 6: Use ref for fresh authHeader
        const headers: Record<string, string> = {
          'Content-Type': 'application/json',
          ...(authHeaderRef.current || {}),
        };

        // AbortController for timeout — cancel request if no data for 180s
        const controller = new AbortController();
        let lastDataTime = Date.now();
        const timeoutInterval = setInterval(() => {
          if (Date.now() - lastDataTime > 180000) {
            controller.abort();
            clearInterval(timeoutInterval);
          }
        }, 5000);

        const res = await fetch(`${API_URL}/api/conversation/stream`, {
          method: 'POST',
          headers,
          credentials: 'include',  // Fix 4: httpOnly cookie auth
          body: JSON.stringify(body),
          signal: controller.signal,
        });

        if (!res.ok) {
          clearInterval(timeoutInterval);
          if (res.status === 401) throw new AuthExpiredError();
          const err = await res.json().catch(() => ({}));
          throw new Error(err.detail || 'Stream request failed');
        }

        const reader = res.body!.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        let currentEvent = '';

        try {
          while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            lastDataTime = Date.now(); // reset timeout on each chunk
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
                    // Guard: only update state if component is still mounted (Fix 3)
                    if (mountedRef.current && (data.session_id || data.phase || data.turn_count !== undefined)) {
                      setSession((prev) => ({
                        ...prev,
                        sessionId: data.session_id || prev.sessionId,
                        phase: data.phase || prev.phase,
                        turnCount: data.turn_count ?? prev.turnCount,
                        signalsCollected: data.signals_collected || prev.signalsCollected,
                      }));
                    }
                    onMetadata(data);
                  }
                  else if (currentEvent === 'token') onToken(data.text);
                  else if (currentEvent === 'done') onDone(data);
                  else if (currentEvent === 'status' && onStatus) onStatus(data);
                  else if (currentEvent === 'error') onError(new Error(data.message));
                } catch {
                  // skip malformed JSON lines
                }
                currentEvent = '';
              }
            }
          }
        } finally {
          clearInterval(timeoutInterval);  // Fix 1: always clear interval
          reader.releaseLock();            // Fix 2: release SSE reader
        }
      } catch (e: any) {
        setError(e.message || 'Stream failed');
        onError(e);
      } finally {
        setIsLoading(false);
      }
    },
    [session.sessionId, session.turnCount, userProfile, authHeader]
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
        credentials: 'include',  // Fix 4: httpOnly cookie auth
        headers: {
          ...(authHeaderRef.current || {}),
        },
      });

      if (!res.ok) {
        if (res.status === 401) throw new AuthExpiredError();
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
