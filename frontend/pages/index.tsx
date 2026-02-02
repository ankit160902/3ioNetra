import { useState, useRef, useEffect } from 'react';
import Head from 'next/head';
import { Send, Loader2, RefreshCw, LogOut, User, History, ChevronDown } from 'lucide-react';
import { useSession, Citation, UserProfile } from '../hooks/useSession';
import { PhaseIndicatorCompact } from '../components/PhaseIndicator';
import { useAuth } from '../hooks/useAuth';
import LoginPage from '../components/LoginPage';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8080';

interface Message {
  role: 'user' | 'assistant';
  content: string;
  citations?: Citation[];
  timestamp: Date;
  isWelcome?: boolean;
}

interface ConversationSummary {
  id: string;
  title: string;
  created_at: string;
  message_count: number;
}

export default function Home() {
  const { user, isAuthenticated, login, register, logout, isLoading: authLoading, error: authError, getAuthHeader } = useAuth();
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  // Language is fixed to English (removed dropdown)
  const language = 'en';
  const [isProcessing, setIsProcessing] = useState(false);
  const [useConversationFlow, setUseConversationFlow] = useState(true);
  const [conversationHistory, setConversationHistory] = useState<ConversationSummary[]>([]);
  const [showHistory, setShowHistory] = useState(false);
  const [currentConversationId, setCurrentConversationId] = useState<string | null>(null);

  // Build user profile for personalization from authenticated user
  const userProfile: UserProfile | undefined = user ? {
    age_group: user.age_group || '',
    gender: user.gender || '',
    profession: user.profession || '',
    name: user.name || '',
  } : undefined;

  const {
    session,
    isLoading: sessionLoading,
    welcomeMessage,
    createSession,
    sendMessage,
    resetSession,
  } = useSession(userProfile, getAuthHeader());

  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Load conversation history when authenticated
  useEffect(() => {
    if (isAuthenticated && user) {
      loadConversationHistory();
    }
  }, [isAuthenticated, user]);

  // Initialize session when using conversation flow and authenticated
  useEffect(() => {
    if (isAuthenticated && useConversationFlow && !session.sessionId && messages.length === 0) {
      initializeSession();
    }
  }, [useConversationFlow, isAuthenticated]);

  // Add welcome message when session is created
  useEffect(() => {
    if (welcomeMessage && messages.length === 0) {
      setMessages([
        {
          role: 'assistant',
          content: welcomeMessage,
          timestamp: new Date(),
          isWelcome: true,
        },
      ]);
    }
  }, [welcomeMessage]);

  const loadConversationHistory = async () => {
    try {
      const response = await fetch(`${API_URL}/api/user/conversations`, {
        headers: {
          ...getAuthHeader(),
        },
      });
      if (response.ok) {
        const data = await response.json();
        setConversationHistory(data.conversations || []);
      }
    } catch (error) {
      console.error('Failed to load conversation history:', error);
    }
  };

  const loadConversation = async (conversationId: string) => {
    try {
      const response = await fetch(`${API_URL}/api/user/conversations/${conversationId}`, {
        headers: {
          ...getAuthHeader(),
        },
      });
      if (response.ok) {
        const data = await response.json();
        setMessages(data.messages.map((msg: any) => ({
          ...msg,
          timestamp: new Date(msg.timestamp),
        })));
        setCurrentConversationId(conversationId);
        setShowHistory(false);
      }
    } catch (error) {
      console.error('Failed to load conversation:', error);
    }
  };

  const saveConversation = async () => {
    if (!isAuthenticated || messages.length <= 1) return;

    try {
      const title = messages.find(m => m.role === 'user')?.content.slice(0, 50) || 'Conversation';
      await fetch(`${API_URL}/api/user/conversations`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...getAuthHeader(),
        },
        body: JSON.stringify({
          conversation_id: currentConversationId,
          title,
          messages: messages.map(m => ({
            role: m.role,
            content: m.content,
            citations: m.citations,
            timestamp: m.timestamp.toISOString(),
          })),
        }),
      });
      loadConversationHistory();
    } catch (error) {
      console.error('Failed to save conversation:', error);
    }
  };

  const initializeSession = async () => {
    try {
      await createSession();
    } catch (error) {
      console.error('Failed to create session:', error);
    }
  };

  const handleNewConversation = async () => {
    // Save current conversation before starting new one
    if (messages.length > 1) {
      await saveConversation();
    }

    resetSession();
    setMessages([]);
    setCurrentConversationId(null);
    if (useConversationFlow) {
      await initializeSession();
    }
  };

  const handleTextSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isProcessing) return;

    const userMessage: Message = {
      role: 'user',
      content: input,
      timestamp: new Date(),
    };

    const currentInput = input;
    setMessages((prev) => [...prev, userMessage]);
    setInput('');
    setIsProcessing(true);

    try {
      if (useConversationFlow) {
        // Use new conversation flow API
        console.log('📤 Sending message:', currentInput);
        const response = await sendMessage(currentInput, language);
        console.log('📥 Received full response:', JSON.stringify(response, null, 2));

        // Validate response structure
        if (!response) {
          console.error('❌ Response is null or undefined');
          throw new Error('No response received from server');
        }

        // Extract the response text - handle different possible structures
        let responseText = '';
        if (typeof response.response === 'string') {
          responseText = response.response;
        } else if (typeof response === 'string') {
          responseText = response;
        } else {
          console.error('❌ Invalid response structure:', response);
          responseText = 'I apologize, but I received an invalid response. Please try again.';
        }

        console.log('📝 Response text extracted:', responseText);
        console.log('📝 Response text length:', responseText?.length || 0);

        // Ensure we have content
        if (!responseText || responseText.trim().length === 0) {
          console.warn('⚠️ Empty response text, using fallback');
          responseText = 'I received your message, but I\'m having trouble formulating a response. Please try again.';
        }

        const assistantMessage: Message = {
          role: 'assistant',
          content: responseText,
          citations: response.citations || [],
          timestamp: new Date(),
        };

        console.log('✅ Creating assistant message:', {
          content: assistantMessage.content.substring(0, 100) + '...',
          contentLength: assistantMessage.content.length,
          hasCitations: (assistantMessage.citations?.length || 0) > 0
        });

        setMessages((prev) => {
          const newMessages = [...prev, assistantMessage];
          console.log('📊 Total messages after update:', newMessages.length);
          console.log('📊 Last message:', newMessages[newMessages.length - 1]);
          return newMessages;
        });

        // Auto-save conversation periodically
        if (isAuthenticated) {
          setTimeout(() => saveConversation(), 1000);
        }
      } else {
        // Use original streaming endpoint
        const conversationHistoryData = messages.slice(-6).map((msg) => ({
          role: msg.role,
          content: msg.content,
        }));

        const response = await fetch(`${API_URL}/api/text/query/stream`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            query: currentInput,
            language: language,
            include_citations: true,
            conversation_history: conversationHistoryData,
          }),
        });

        if (!response.ok) {
          throw new Error('Failed to fetch response');
        }

        // Create assistant message placeholder
        const assistantMessage: Message = {
          role: 'assistant',
          content: '',
          citations: [],
          timestamp: new Date(),
        };
        setMessages((prev) => [...prev, assistantMessage]);

        // Read the streaming response
        const reader = response.body?.getReader();
        const decoder = new TextDecoder();

        if (reader) {
          let accumulatedContent = '';
          let buffer = '';

          while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            const chunk = decoder.decode(value, { stream: true });
            buffer += chunk;

            const lines = buffer.split('\n');
            buffer = lines.pop() || '';

            for (const line of lines) {
              if (line.startsWith('data: ')) {
                const content = line.slice(6).trim();
                if (content && content !== '[DONE]' && !content.startsWith('[ERROR]')) {
                  try {
                    const decoded = JSON.parse(content);
                    accumulatedContent += decoded;
                  } catch {
                    accumulatedContent += content;
                  }

                  setMessages((prev) => {
                    const newMessages = [...prev];
                    const lastMessage = newMessages[newMessages.length - 1];
                    if (lastMessage && lastMessage.role === 'assistant') {
                      lastMessage.content = accumulatedContent;
                    }
                    return newMessages;
                  });

                  await new Promise((resolve) => setTimeout(resolve, 10));
                }
              }
            }
          }
        }
      }
    } catch (error) {
      console.error('❌ Error in handleTextSubmit:', error);
      if (error instanceof Error) {
        console.error('Error details:', error.message);
        console.error('Stack trace:', error.stack);
      } else {
        console.error('Unknown error object:', JSON.stringify(error));
      }

      const errorMessage: Message = {
        role: 'assistant',
        content: 'I apologize, but I encountered an error. Please try again.',
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setIsProcessing(false);
    }
  };

  // Show login page if not authenticated
  if (!isAuthenticated) {
    return (
      <>
        <Head>
          <title>3ioNetra Spiritual Companion - Login</title>
          <meta name="description" content="Sign in to your spiritual companion based on Sanatan Dharma" />
          <meta name="viewport" content="width=device-width, initial-scale=1" />
          <link rel="icon" href="/favicon.ico" />
        </Head>
        <LoginPage
          onLogin={login}
          onRegister={register}
          isLoading={authLoading}
          error={authError}
        />
      </>
    );
  }

  return (
    <>
      <Head>
        <title>3ioNetra Spiritual Companion</title>
        <meta name="description" content="Your personal spiritual companion based on Sanatan Dharma" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <link rel="icon" href="/favicon.ico" />
        <style>{`
          @keyframes fadeIn {
            from { opacity: 0; transform: translateY(5px); }
            to { opacity: 1; transform: translateY(0); }
          }
          .message-content {
            animation: fadeIn 0.3s ease-in;
            white-space: pre-line;
            line-height: 1.6;
          }
          .streaming-text {
            animation: fadeIn 0.2s ease-in;
            white-space: pre-line;
            line-height: 1.6;
          }
        `}</style>
      </Head>

      <main className="min-h-screen bg-gradient-to-br from-orange-50 via-white to-amber-50">
        {/* Header */}
        <header className="bg-white shadow-sm border-b border-orange-200">
          <div className="max-w-4xl mx-auto px-4 py-4 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div>
                <h1 className="text-xl font-bold text-gray-900">3ioNetra</h1>
                <p className="text-xs text-orange-600">Spiritual Companion</p>
              </div>
            </div>

            <div className="flex items-center gap-2">
              {/* Conversation History Button */}
              <div className="relative">
                <button
                  onClick={() => setShowHistory(!showHistory)}
                  className="p-2 text-gray-600 hover:text-orange-600 hover:bg-orange-50 rounded-lg transition-colors flex items-center gap-1"
                  title="Conversation History"
                >
                  <History className="w-5 h-5" />
                  <ChevronDown className="w-4 h-4" />
                </button>

                {/* History Dropdown */}
                {showHistory && (
                  <div className="absolute right-0 mt-2 w-72 bg-white rounded-lg shadow-lg border border-orange-100 z-50 max-h-96 overflow-y-auto">
                    <div className="p-3 border-b border-orange-100">
                      <p className="text-sm font-semibold text-gray-700">Recent Conversations</p>
                    </div>
                    {conversationHistory.length === 0 ? (
                      <div className="p-4 text-center text-sm text-gray-500">
                        No previous conversations
                      </div>
                    ) : (
                      <div className="divide-y divide-orange-50">
                        {conversationHistory.map((conv) => (
                          <button
                            key={conv.id}
                            onClick={() => loadConversation(conv.id)}
                            className="w-full p-3 text-left hover:bg-orange-50 transition-colors"
                          >
                            <p className="text-sm font-medium text-gray-800 truncate">
                              {conv.title}
                            </p>
                            <p className="text-xs text-gray-500 mt-1">
                              {new Date(conv.created_at).toLocaleDateString()} - {conv.message_count} messages
                            </p>
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>

              {/* New Conversation Button */}
              {messages.length > 0 && (
                <button
                  onClick={handleNewConversation}
                  className="p-2 text-gray-600 hover:text-orange-600 hover:bg-orange-50 rounded-lg transition-colors"
                  title="New Conversation"
                >
                  <RefreshCw className="w-5 h-5" />
                </button>
              )}

              {/* User Menu */}
              <div className="flex items-center gap-2 pl-2 border-l border-orange-200">
                <div className="flex items-center gap-2">
                  <div className="w-8 h-8 bg-orange-100 rounded-full flex items-center justify-center">
                    <User className="w-4 h-4 text-orange-600" />
                  </div>
                  <span className="text-sm font-medium text-gray-700 hidden sm:inline">
                    {user?.name?.split(' ')[0]}
                  </span>
                </div>
                <button
                  onClick={logout}
                  className="p-2 text-gray-500 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors"
                  title="Sign Out"
                >
                  <LogOut className="w-4 h-4" />
                </button>
              </div>
            </div>
          </div>
        </header>

        {/* Phase Indicator */}
        {useConversationFlow && session.sessionId && (
          <PhaseIndicatorCompact
            phase={session.phase}
            turnCount={session.turnCount}
            maxTurns={6}
          />
        )}

        {/* Messages Area */}
        <div className="max-w-4xl mx-auto px-4 py-6 h-[calc(100vh-220px)] overflow-y-auto">
          {messages.length === 0 && !welcomeMessage ? (
            <div className="text-center py-20">
              <div className="mb-6">
                <h1 className="text-4xl font-bold text-gray-900">3ioNetra</h1>
                <p className="text-lg text-orange-600">Spiritual Companion</p>
              </div>
              <h2 className="text-2xl font-bold text-gray-900 mb-2">
                Namaste, {user?.name?.split(' ')[0]}!
              </h2>
              <p className="text-gray-600 mb-4 max-w-lg mx-auto">
                I'm your spiritual companion. Share what's on your mind - whether it's stress,
                confusion, or just curiosity about life's deeper questions. I'll listen, understand,
                and share wisdom from Sanatan Dharma that speaks to your situation.
              </p>
              <div className="max-w-md mx-auto text-left bg-white rounded-lg p-4 shadow-sm">
                <p className="text-sm text-gray-700 mb-2 font-semibold">You can simply say:</p>
                <ul className="text-sm text-gray-600 space-y-1">
                  <li>• "I'm feeling really stressed lately"</li>
                  <li>• "I'm struggling with my relationships"</li>
                  <li>• "I feel lost and don't know my purpose"</li>
                  <li>• "I have trouble controlling my mind"</li>
                </ul>
              </div>

              {sessionLoading && (
                <div className="mt-4 flex items-center justify-center gap-2 text-orange-600">
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span className="text-sm">Starting session...</span>
                </div>
              )}
            </div>
          ) : (
            <div className="space-y-4">
              {messages.map((message, index) => (
                <div
                  key={index}
                  className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
                >
                  <div
                    className={`max-w-[80%] rounded-lg p-4 ${message.role === 'user'
                      ? 'bg-orange-500 text-white'
                      : 'bg-white shadow-sm border border-orange-100'
                      }`}
                  >
                    <p
                      className={`whitespace-pre-wrap ${isProcessing && index === messages.length - 1
                        ? 'streaming-text'
                        : 'message-content'
                        }`}
                    >
                      {message.content ||
                        (isProcessing && index === messages.length - 1 ? '...' : '')}
                    </p>

                    {/* message.citations && message.citations.length > 0 && (
                      <div className="mt-3 pt-3 border-t border-orange-200">
                        <p className="text-sm font-semibold text-gray-700 mb-2">Citations:</p>
                        <div className="space-y-2">
                          {message.citations.map((citation, i) => (
                            <div key={i} className="text-sm bg-orange-50 rounded p-2">
                              <p className="font-semibold text-orange-900">{citation.reference}</p>
                              <p className="text-gray-700 text-xs mt-1">{citation.text}</p>
                            </div>
                          ))}
                        </div>
                      </div>
                    ) */}

                    <p className="text-xs mt-2 opacity-70">
                      {message.timestamp.toLocaleTimeString()}
                    </p>
                  </div>
                </div>
              ))}

              {isProcessing && (
                <div className="flex justify-start">
                  <div className="bg-white shadow-sm border border-orange-100 rounded-lg p-4">
                    <div className="flex items-center gap-2">
                      <Loader2 className="w-5 h-5 animate-spin text-orange-500" />
                      <span className="text-sm text-gray-600">
                        {(session.phase === 'clarification' || session.phase === 'listening')
                          ? 'Listening...'
                          : session.phase === 'synthesis'
                            ? 'Reflecting...'
                            : (session.phase === 'closure')
                              ? 'Concluding...'
                              : 'Finding wisdom...'}
                      </span>
                    </div>
                  </div>
                </div>
              )}

              <div ref={messagesEndRef} />
            </div>
          )}
        </div>

        {/* Conversation Complete Banner */}
        {session.isComplete && (
          <div className="max-w-4xl mx-auto px-4 mb-2">
            <div className="bg-green-50 border border-green-200 rounded-lg p-3 flex items-center justify-between">
              <p className="text-sm text-green-700">
                Guidance shared. You can continue the conversation or start a new topic.
              </p>
              <button
                onClick={handleNewConversation}
                className="text-sm text-green-700 hover:text-green-800 font-medium underline"
              >
                New Topic
              </button>
            </div>
          </div>
        )}

        {/* Input Area */}
        <div className="fixed bottom-0 left-0 right-0 bg-white border-t border-orange-200 shadow-lg">
          <div className="max-w-4xl mx-auto px-4 py-4">
            <form onSubmit={handleTextSubmit} className="flex gap-2">
              <input
                id="chat-input"
                name="message"
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="Share what's on your mind..."
                disabled={isProcessing}
                autoComplete="off"
                className="flex-1 px-4 py-3 border border-orange-300 rounded-full focus:ring-2 focus:ring-orange-500 focus:border-transparent disabled:bg-gray-100 disabled:cursor-not-allowed"
              />

              <button
                type="submit"
                disabled={isProcessing || !input.trim()}
                className="p-3 bg-orange-500 hover:bg-orange-600 text-white rounded-full disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                {isProcessing ? (
                  <Loader2 className="w-6 h-6 animate-spin" />
                ) : (
                  <Send className="w-6 h-6" />
                )}
              </button>
            </form>
          </div>
        </div>
      </main>

      {/* Click outside to close history dropdown */}
      {showHistory && (
        <div
          className="fixed inset-0 z-40"
          onClick={() => setShowHistory(false)}
        />
      )}
    </>
  );
}
