/**
 * useSession Hook - Manages conversation session state
 */
import { useState, useCallback, useEffect } from 'react';

// Types
export interface Citation {
  reference: string;
  scripture: string;
  text: string;
  score: number;
}

export interface SessionState {
  sessionId: string | null;
  phase: 'clarification' | 'synthesis' | 'answering';
  turnCount: number;
  signalsCollected: Record<string, string>;
  isComplete: boolean;
}

export interface ConversationalResponse {
  session_id: string;
  phase: 'clarification' | 'synthesis' | 'answering';
  response: string;
  signals_collected: Record<string, string>;
  turn_count: number;
  is_complete: boolean;
  citations?: Citation[];
}

// User profile for personalization
export interface UserProfile {
  age_group?: string;
  gender?: string;
  profession?: string;
  name?: string;
}

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8080';

export function useSession(userProfile?: UserProfile, authHeader?: Record<string, string>) {
  const [session, setSession] = useState<SessionState>({
    sessionId: null,
    phase: 'clarification',
    turnCount: 0,
    signalsCollected: {},
    isComplete: false,
  });

  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [welcomeMessage, setWelcomeMessage] = useState<string>('');

  // Create new session
  const createSession = useCallback(async (): Promise<string> => {
    setIsLoading(true);
    setError(null);

    try {
      const response = await fetch(`${API_URL}/api/session/create`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
      });

      if (!response.ok) {
        throw new Error('Failed to create session');
      }

      const data = await response.json();

      setSession({
        sessionId: data.session_id,
        phase: data.phase,
        turnCount: 0,
        signalsCollected: {},
        isComplete: false,
      });

      setWelcomeMessage(data.message);
      return data.session_id;
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to create session';
      setError(message);
      throw err;
    } finally {
      setIsLoading(false);
    }
  }, []);

  // Send message and get response
  const sendMessage = useCallback(
    async (message: string, language: string = 'en'): Promise<ConversationalResponse> => {
      setIsLoading(true);
      setError(null);

      try {
        // Build request body, including user profile for new sessions
        const requestBody: Record<string, unknown> = {
          session_id: session.sessionId,
          message,
          language,
        };

        // Include user profile for personalization (especially for new sessions)
        if (userProfile && (!session.sessionId || session.turnCount === 0)) {
          requestBody.user_profile = {
            age_group: userProfile.age_group || '',
            gender: userProfile.gender || '',
            profession: userProfile.profession || '',
            name: userProfile.name || '',
          };
        }

        const headers: Record<string, string> = { 'Content-Type': 'application/json' };
        // Add auth header if provided
        if (authHeader) {
          Object.assign(headers, authHeader);
        }

        const response = await fetch(`${API_URL}/api/conversation`, {
          method: 'POST',
          headers,
          body: JSON.stringify(requestBody),
        });

        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}));
          throw new Error(errorData.detail || 'Failed to get response');
        }

        const data: ConversationalResponse = await response.json();

        setSession((prev) => ({
          ...prev,
          sessionId: data.session_id,
          phase: data.phase,
          turnCount: data.turn_count,
          signalsCollected: data.signals_collected,
          isComplete: data.is_complete,
        }));

        return data;
      } catch (err) {
        const message = err instanceof Error ? err.message : 'Failed to send message';
        setError(message);
        throw err;
      } finally {
        setIsLoading(false);
      }
    },
    [session.sessionId, session.turnCount, userProfile, authHeader]
  );

  // Send message with streaming (for future use)
  const sendMessageStream = useCallback(
    async (
      message: string,
      language: string = 'en',
      onChunk: (chunk: string) => void
    ): Promise<ConversationalResponse | null> => {
      setIsLoading(true);
      setError(null);

      try {
        const headers: Record<string, string> = { 'Content-Type': 'application/json' };
        // Add auth header if provided
        if (authHeader) {
          Object.assign(headers, authHeader);
        }

        const response = await fetch(`${API_URL}/api/conversation/stream`, {
          method: 'POST',
          headers,
          body: JSON.stringify({
            session_id: session.sessionId,
            message,
            language,
          }),
        });

        if (!response.ok) {
          throw new Error('Failed to get response');
        }

        const reader = response.body?.getReader();
        if (!reader) {
          throw new Error('No response body');
        }

        const decoder = new TextDecoder();
        let metadata: ConversationalResponse | null = null;

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          const chunk = decoder.decode(value);
          const lines = chunk.split('\n');

          for (const line of lines) {
            if (line.startsWith('data: ')) {
              const data = line.slice(6);
              if (data === '[DONE]') continue;

              try {
                const parsed = JSON.parse(data);
                // First message is metadata
                if (parsed.session_id) {
                  metadata = parsed as ConversationalResponse;
                  setSession((prev) => ({
                    ...prev,
                    sessionId: metadata!.session_id,
                    phase: metadata!.phase,
                    turnCount: metadata!.turn_count,
                    signalsCollected: metadata!.signals_collected,
                    isComplete: metadata!.is_complete,
                  }));
                } else {
                  // Subsequent messages are response chunks
                  onChunk(parsed);
                }
              } catch {
                // Not JSON, might be raw text
                onChunk(data);
              }
            }
          }
        }

        return metadata;
      } catch (err) {
        const message = err instanceof Error ? err.message : 'Failed to send message';
        setError(message);
        throw err;
      } finally {
        setIsLoading(false);
      }
    },
    [session.sessionId, authHeader]
  );

  // Get session state
  const getSessionState = useCallback(async (sessionId: string) => {
    try {
      const response = await fetch(`${API_URL}/api/session/${sessionId}`);

      if (!response.ok) {
        if (response.status === 404) {
          return null;
        }
        throw new Error('Failed to get session state');
      }

      const data = await response.json();

      setSession({
        sessionId: data.session_id,
        phase: data.phase,
        turnCount: data.turn_count,
        signalsCollected: data.signals_collected,
        isComplete: false,
      });

      return data;
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to get session';
      setError(message);
      return null;
    }
  }, []);

  // Reset session
  const resetSession = useCallback(() => {
    setSession({
      sessionId: null,
      phase: 'clarification',
      turnCount: 0,
      signalsCollected: {},
      isComplete: false,
    });
    setWelcomeMessage('');
    setError(null);
  }, []);

  // Delete session on server
  const deleteSession = useCallback(async () => {
    if (!session.sessionId) return;

    try {
      await fetch(`${API_URL}/api/session/${session.sessionId}`, {
        method: 'DELETE',
      });
    } catch {
      // Ignore errors on delete
    }

    resetSession();
  }, [session.sessionId, resetSession]);

  return {
    session,
    isLoading,
    error,
    welcomeMessage,
    createSession,
    sendMessage,
    sendMessageStream,
    getSessionState,
    resetSession,
    deleteSession,
  };
}
