import { useState, useRef, useEffect, useMemo } from 'react';
import Head from 'next/head';
import { Send, Loader2, RefreshCw, LogOut, User, History, ChevronDown, BookOpen, Activity } from 'lucide-react';
import { useSession, Citation, SourceReference, FlowMetadata, UserProfile, Product } from '../hooks/useSession';
import { PhaseIndicatorCompact } from '../components/PhaseIndicator';
import { useAuth } from '../hooks/useAuth';
import LoginPage from '../components/LoginPage';
import TTSButton from '../components/TTSButton';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8080';

interface Message {
  role: 'user' | 'assistant';
  content: string;
  citations?: Citation[];
  sources?: SourceReference[];
  flowMetadata?: FlowMetadata;
  recommendedProducts?: Product[];
  timestamp: Date;
  isWelcome?: boolean;
}

interface ConversationSummary {
  id: string;
  title: string;
  created_at: string;
  message_count: number;
}


/**
 * Detect verse lines in a response.
 * Returns an array of segments: { type: 'text' | 'verse', content: string }
 * A "verse" segment is any line that contains a scripture citation pattern.
 */
function parseResponseForVerses(text: string): { type: 'text' | 'verse'; content: string }[] {
  if (!text) return [{ type: 'text', content: '' }];

  // 1. Primary Method: Tag-based extraction for absolute precision
  if (text.includes('[VERSE]')) {
    const segments: { type: 'text' | 'verse'; content: string }[] = [];
    const regex = /\[VERSE\]([\s\S]*?)\[\/VERSE\]/g;
    let lastIndex = 0;
    let match;

    while ((match = regex.exec(text)) !== null) {
      // Add text before the verse
      const beforeText = text.substring(lastIndex, match.index);
      if (beforeText.trim()) {
        segments.push({ type: 'text', content: beforeText });
      }

      // Add the verse content
      const verseContent = match[1].trim();
      if (verseContent) {
        segments.push({ type: 'verse', content: verseContent });
      }

      lastIndex = regex.lastIndex;
    }

    // Add remaining text
    const remainingText = text.substring(lastIndex);
    if (remainingText.trim()) {
      segments.push({ type: 'text', content: remainingText });
    }

    return segments.length > 0 ? segments : [{ type: 'text', content: text }];
  }

  // 2. Fallback: Refined line-based detection for legacy responses
  const lines = text.split('\n');
  const segments: { type: 'text' | 'verse'; content: string }[] = [];

  // Patterns that indicate a verse/shloka line
  const versePatterns = [
    /[\u0900-\u097F]{3,}/, // Devanagari
    /^\s*["'""].*["'""]\s*[-–—]\s*/, // Quote with citation dash
    /^\s*["'""].*["'""]\s*$/, // Strictly quoted line
    /^\s*\(\b(Bhagavad\s*Gita|Gita|Yoga\s*Sutra|Upanishad|Vedas?|Mahabharata|Ramayana)\b.*\d+.*\)\s*$/i,
    /^\s*(Chapter|Verse|Shloka|Sutra|Mantra)\s*\d/i,
  ];

  let currentText: string[] = [];

  for (const line of lines) {
    const isVerse = versePatterns.some(p => p.test(line));

    if (isVerse) {
      if (currentText.length > 0) {
        segments.push({ type: 'text', content: currentText.join('\n') });
        currentText = [];
      }
      segments.push({ type: 'verse', content: line });
    } else {
      currentText.push(line);
    }
  }

  if (currentText.length > 0) {
    segments.push({ type: 'text', content: currentText.join('\n') });
  }

  return segments;
}

export default function Home() {
  const { user, isAuthenticated, login, register, logout, isLoading: authLoading, error: authError, getAuthHeader } = useAuth();
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  // Language is fixed to English (removed dropdown)
  const language = 'en';
  const [isProcessing, setIsProcessing] = useState(false);
  const [useConversationFlow, setUseConversationFlow] = useState(true);
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
    sendMessage,
    resetSession,
    error: sessionError,
  } = useSession(userProfile, getAuthHeader());

  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Clear messages when user changes (Session Isolation)
  useEffect(() => {
    setMessages([]);
    setCurrentConversationId(null);
  }, [user?.id]);


  // Initialize session when using conversation flow and authenticated



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
    } catch (error) {
      console.error('Failed to save conversation:', error);
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

        // Extract metadata to display on both user and assistant messages
        const flowMetadata = response.flow_metadata || undefined;

        const assistantMessage: Message = {
          role: 'assistant',
          content: responseText,
          citations: response.citations || [],
          sources: response.sources || [],
          recommendedProducts: response.recommended_products || [],
          flowMetadata: flowMetadata,
          timestamp: new Date(),
        };

        setMessages((prev) => {
          // Update the last user message with the detected metadata
          const nextMessages = [...prev];
          for (let i = nextMessages.length - 1; i >= 0; i--) {
            if (nextMessages[i].role === 'user') {
              nextMessages[i] = { ...nextMessages[i], flowMetadata: flowMetadata };
              break;
            }
          }
          return [...nextMessages, assistantMessage];
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
            signalsCollected={session.signalsCollected}
          />
        )}

        {/* Messages Area */}
        <div className="max-w-4xl mx-auto px-4 py-6 h-[calc(100vh-220px)] overflow-y-auto">
          {messages.length === 0 ? (
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
                    {/* Message content with verse detection */}
                    {message.role === 'assistant' && message.content ? (() => {
                      const segments = parseResponseForVerses(message.content);

                      return (
                        <div className="message-content">
                          {segments.map((seg, si) => (
                            seg.type === 'verse' ? (
                              <div key={si} className="my-2 pl-3 border-l-4 border-amber-400 bg-amber-50/60 rounded-r-lg py-2.5 pr-3 shadow-sm border border-transparent">
                                <p className="whitespace-pre-wrap text-amber-950 italic text-sm leading-relaxed font-serif">
                                  {seg.content}
                                </p>
                                <div className="mt-2">
                                  <TTSButton
                                    text={seg.content}
                                    lang="hi"
                                    variant="verse"
                                  />
                                </div>
                              </div>
                            ) : (
                              <p key={si} className="whitespace-pre-wrap mb-2 last:mb-0">
                                {seg.content}
                                {si === segments.length - 1 && isProcessing && index === messages.length - 1 ? '...' : ''}
                              </p>
                            )
                          ))}

                          {/* Full response TTS button */}
                          <div className="mt-4 pt-3 border-t border-orange-100 flex justify-end">
                            <TTSButton
                              text={message.content}
                              lang="en"
                              variant="response"
                              label="Listen to Full Response"
                            />
                          </div>
                        </div>
                      );
                    })() : (
                      <p
                        className={`whitespace-pre-wrap ${isProcessing && index === messages.length - 1
                          ? 'streaming-text'
                          : 'message-content'
                          }`}
                      >
                        {message.content ||
                          (isProcessing && index === messages.length - 1 ? '...' : '')}
                      </p>
                    )}

                    {/* Source Transparency Panel */}
                    {message.sources && message.sources.length > 0 && (
                      <details className="mt-3 pt-3 border-t border-orange-100 group">
                        <summary className="flex items-center gap-1.5 cursor-pointer text-xs font-semibold text-orange-700 hover:text-orange-900 transition-colors select-none">
                          <BookOpen className="w-3.5 h-3.5" />
                          Sources & Context ({message.sources.length})
                        </summary>
                        <div className="mt-2 space-y-2">
                          {message.sources.map((source, i) => (
                            <div key={i} className="bg-gradient-to-r from-orange-50 to-amber-50 rounded-lg p-3 border border-orange-100">
                              <div className="flex items-center justify-between mb-1">
                                <p className="text-xs font-bold text-orange-900">
                                  {source.scripture}
                                  {source.reference && <span className="font-normal text-orange-700"> — {source.reference}</span>}
                                </p>
                                <span className="text-[10px] font-mono font-bold text-orange-600 bg-orange-100 px-1.5 py-0.5 rounded">
                                  {(source.relevance_score * 100).toFixed(0)}%
                                </span>
                              </div>
                              {/* Relevance bar */}
                              <div className="w-full h-1 bg-orange-100 rounded-full mb-1.5 overflow-hidden">
                                <div
                                  className="h-full rounded-full transition-all duration-500"
                                  style={{
                                    width: `${source.relevance_score * 100}%`,
                                    background: source.relevance_score > 0.7
                                      ? 'linear-gradient(90deg, #f97316, #ea580c)'
                                      : source.relevance_score > 0.4
                                        ? 'linear-gradient(90deg, #fb923c, #f97316)'
                                        : 'linear-gradient(90deg, #fdba74, #fb923c)'
                                  }}
                                />
                              </div>
                              <p className="text-[11px] text-gray-600 leading-relaxed line-clamp-2">{source.context_text}</p>
                            </div>
                          ))}
                        </div>
                      </details>
                    )}

                    {/* Flow Metadata Badge - Reused for both roles */}
                    {(message.flowMetadata?.topics?.length || 0) > 0 || message.flowMetadata?.detected_domain ? (
                      <div className="mt-2 flex items-center gap-2 flex-wrap">
                        {message.flowMetadata?.topics && message.flowMetadata.topics.length > 0 ? (
                          message.flowMetadata.topics.map((topic, ti) => (
                            <span
                              key={ti}
                              className={`inline-flex items-center gap-1 text-[10px] font-semibold px-2 py-0.5 rounded-full border shadow-sm transition-all duration-300 hover:scale-105 ${message.role === 'user'
                                ? 'bg-white/20 text-white border-white/30 backdrop-blur-sm'
                                : 'bg-orange-50 text-orange-700 border-orange-200'
                                }`}
                            >
                              <Activity className="w-2.5 h-2.5" />
                              {topic}
                            </span>
                          ))
                        ) : (
                          message.flowMetadata?.detected_domain && (
                            <span className={`inline-flex items-center gap-1 text-[10px] font-semibold px-2 py-0.5 rounded-full border shadow-sm ${message.role === 'user'
                              ? 'bg-white/20 text-white border-white/30 backdrop-blur-sm'
                              : 'bg-orange-50 text-orange-700 border-orange-200'
                              }`}>
                              <Activity className="w-2.5 h-2.5" />
                              {message.flowMetadata.detected_domain}
                            </span>
                          )
                        )}

                        {/* Fallback for emotional state if not in topics */}
                        {!(message.flowMetadata?.topics?.includes(message.flowMetadata?.emotional_state || '')) && message.flowMetadata?.emotional_state && (
                          <span className={`text-[10px] font-medium opacity-80 ${message.role === 'user' ? 'text-white/80' : 'text-gray-500'}`}>
                            {message.flowMetadata.emotional_state}
                          </span>
                        )}
                      </div>
                    ) : null}

                    {/* Recommended Products Pop-up */}
                    {message.recommendedProducts && message.recommendedProducts.length > 0 && (
                      <div className="mt-6 p-4 bg-gradient-to-br from-orange-50/80 via-white to-amber-50/80 rounded-2xl border border-orange-200/50 shadow-inner relative overflow-hidden">
                        {/* Decorative background element */}
                        <div className="absolute -right-4 -top-4 w-24 h-24 bg-orange-100/30 rounded-full blur-2xl"></div>

                        <p className="text-[11px] font-bold text-orange-800 mb-4 uppercase tracking-widest flex items-center gap-2">
                          <span className="flex h-2 w-2 relative">
                            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-orange-400 opacity-75"></span>
                            <span className="relative inline-flex rounded-full h-2 w-2 bg-orange-500"></span>
                          </span>
                          Dharmic Tools for your journey
                        </p>

                        <div className="flex gap-4 overflow-x-auto pb-2 scrollbar-hide -mx-1 px-1">
                          {message.recommendedProducts.map((product, pi) => (
                            <div
                              key={pi}
                              className="flex-shrink-0 w-48 bg-white/90 backdrop-blur-md border border-white rounded-2xl overflow-hidden shadow-md hover:shadow-xl transition-all duration-300 hover:-translate-y-1.5 group"
                            >
                              {product.image_url && (
                                <div className="h-32 overflow-hidden relative">
                                  <img
                                    src={product.image_url}
                                    alt={product.name}
                                    className="w-full h-full object-cover group-hover:scale-110 transition-transform duration-700"
                                  />
                                  <div className="absolute top-2 right-2 bg-orange-600 text-white px-2 py-1 rounded-lg text-[10px] font-bold shadow-lg border border-orange-400/30">
                                    {product.currency} {product.amount}
                                  </div>
                                </div>
                              )}
                              <div className="p-3">
                                <span className="inline-block px-2 py-0.5 bg-orange-100 text-orange-700 text-[9px] font-bold rounded-full mb-1">
                                  {product.category}
                                </span>
                                <h4 className="text-[13px] font-bold text-gray-900 mb-1 line-clamp-1 group-hover:text-orange-600 transition-colors">
                                  {product.name}
                                </h4>
                                <p className="text-[10px] text-gray-500 line-clamp-2 mb-3 h-7 leading-tight mb-4">
                                  {product.description}
                                </p>
                                <a
                                  href={product.product_url || '#'}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  className="flex items-center justify-center gap-1.5 w-full py-2 bg-gradient-to-r from-orange-500 to-amber-500 hover:from-orange-600 hover:to-amber-600 text-white text-[11px] font-bold rounded-xl transition-all shadow-md active:scale-95"
                                >
                                  Explore Item
                                </a>
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Timestamp */}
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
        {
          session.isComplete && (
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
          )
        }

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
      </main >

    </>
  );
}
