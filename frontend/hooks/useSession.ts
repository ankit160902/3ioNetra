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

export interface ConversationalResponse {
  session_id: string;
  phase: 'listening' | 'clarification' | 'answering' | 'synthesis' | 'guidance' | 'closure';
  response: string;
  signals_collected: Record<string, string>;
  turn_count: number;
  is_complete: boolean;
  citations?: Citation[];
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
  rashi?: string;
  gotra?: string;
  nakshatra?: string;
  preferred_deity?: string;
}

/* =======================
   Config
======================= */

const API_URL =
  process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8080';

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

  return {
    session,
    isLoading,
    error,
    sendMessage,
    resetSession,
  };
}
