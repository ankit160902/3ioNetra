import { useState, useRef, useEffect, useMemo } from 'react';
import { Send, Loader2, RefreshCw, LogOut, User, History, ChevronDown, BookOpen, Activity, ThumbsUp, ThumbsDown } from 'lucide-react';
import Head from 'next/head';
import { useSession, Citation, SourceReference, FlowMetadata, UserProfile, Product } from '../hooks/useSession';
import { PhaseIndicatorCompact } from '../components/PhaseIndicator';
import { useAuth } from '../hooks/useAuth';
import LoginPage from '../components/LoginPage';
import TTSButton from '../components/TTSButton';
import { ShoppingBag, ExternalLink } from 'lucide-react';
import { parseResponseForVerses, ParsedSegment } from '../utils/parseResponseForVerses';

/* ============================================================================
   Components
   ============================================================================ */

/**
 * Product Card Component
 */
function ProductCard({ product }: { product: Product }) {
  return (
    <div className="flex flex-col bg-white border border-gray-100 rounded-2xl overflow-hidden shadow-sm hover:shadow-md transition-all group w-[180px] shrink-0">
      <div className="h-28 bg-gray-50 relative overflow-hidden">
        {product.image_url ? (
          <img
            src={product.image_url}
            alt={product.name}
            className="w-full h-full object-cover group-hover:scale-110 transition-transform duration-500"
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center text-gray-300">
            <ShoppingBag className="w-8 h-8" />
          </div>
        )}
        <div className="absolute top-2 right-2">
          <span className="bg-orange-600 text-[8px] font-black text-white px-1.5 py-0.5 rounded-full uppercase tracking-widest shadow-lg">
            Essential
          </span>
        </div>
      </div>
      <div className="p-3 flex flex-col flex-1">
        <h4 className="text-[11px] font-black text-gray-900 leading-tight mb-1 truncate">{product.name}</h4>
        <p className="text-[9px] font-bold text-orange-600 uppercase tracking-tighter mb-2">{product.category}</p>

        <div className="mt-auto flex items-center justify-between gap-2">
          <span className="text-[11px] font-black text-gray-900">{product.currency} {product.amount}</span>
          <a
            href={product.product_url || 'https://my3ionetra.com'}
            target="_blank"
            rel="noopener noreferrer"
            className="p-1.5 bg-gray-900 text-white rounded-lg hover:bg-orange-600 transition-colors"
          >
            <ExternalLink className="w-3 h-3" />
          </a>
        </div>
      </div>
    </div>
  );
}

/**
 * Product Recommendations Horizontal Section
 */
function ProductDisplay({ products }: { products: Product[] }) {
  if (!products || products.length === 0) return null;

  return (
    <div className="mt-4 pt-4 border-t border-orange-50/50">
      <div className="flex items-center gap-2 mb-3">
        <div className="p-1.5 bg-orange-100/50 rounded-lg">
          <ShoppingBag className="w-3 h-3 text-orange-600" />
        </div>
        <span className="text-[9px] font-black text-orange-900 uppercase tracking-widest">
          Recommended for your journey
        </span>
      </div>
      <div className="flex gap-3 overflow-x-auto pb-2 scrollbar-hide -mx-1 px-1">
        {products.map((product, i) => (
          <ProductCard key={i} product={product} />
        ))}
        {/* View all card */}
        <a
          href="https://my3ionetra.com"
          target="_blank"
          rel="noopener noreferrer"
          className="flex flex-col items-center justify-center bg-orange-50/30 border border-dashed border-orange-200 rounded-2xl p-4 w-[120px] shrink-0 hover:bg-orange-50 transition-all group"
        >
          <div className="w-8 h-8 bg-white rounded-full flex items-center justify-center mb-2 shadow-sm border border-orange-100 group-hover:scale-110 transition-transform">
            <ExternalLink className="w-4 h-4 text-orange-600" />
          </div>
          <span className="text-[9px] font-black text-orange-800 uppercase text-center leading-tight">Visit<br />Netra Store</span>
        </a>
      </div>
    </div>
  );
}

const rawApiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8080';
const API_URL = rawApiUrl.endsWith('/') ? rawApiUrl.slice(0, -1) : rawApiUrl;

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
  session_id?: string;
  title: string;
  created_at: string;
  message_count: number;
}


export default function Home() {
  const { user, isAuthenticated, login, register, logout, isLoading: authLoading, error: authError, getAuthHeader } = useAuth();
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const language = 'en';
  const [isProcessing, setIsProcessing] = useState(false);
  const [useConversationFlow, setUseConversationFlow] = useState(true);
  const [currentConversationId, setCurrentConversationId] = useState<string | null>(null);
  const [history, setHistory] = useState<ConversationSummary[]>([]);
  const [isHistoryOpen, setIsHistoryOpen] = useState(false);
  const [feedback, setFeedback] = useState<Record<number, 'like' | 'dislike'>>({});

  const handleFeedback = async (messageIndex: number, responseText: string, type: 'like' | 'dislike') => {
    const prev = feedback[messageIndex];
    if (prev === type) return;
    setFeedback((f) => ({ ...f, [messageIndex]: type }));
    try {
      const headers: Record<string, string> = { 'Content-Type': 'application/json' };
      const auth = getAuthHeader();
      if (auth) Object.assign(headers, auth);
      const res = await fetch(`${API_URL}/api/feedback`, {
        method: 'POST',
        headers,
        body: JSON.stringify({
          session_id: session.sessionId || '',
          message_index: messageIndex,
          response_text: responseText,
          feedback: type,
        }),
      });
      if (!res.ok) {
        console.error('Feedback API error:', res.status, await res.text());
      }
    } catch (err) {
      console.error('Failed to submit feedback:', err);
    }
  };

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
    sendMessageStream,
    resetSession,
    loadSession,
    error: sessionError,
  } = useSession(userProfile, getAuthHeader());

  const parsedMessages = useMemo(
    () => messages.map(m => m.role === 'assistant' && m.content ? parseResponseForVerses(m.content) : null),
    [messages]
  );

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const messagesRef = useRef<Message[]>(messages);
  messagesRef.current = messages;
  const rafIdRef = useRef<number | null>(null);
  const lastScrollRef = useRef<number>(0);
  const targetTextRef = useRef<string>('');
  const displayedLengthRef = useRef<number>(0);
  const isStreamingRef = useRef<boolean>(false);

  useEffect(() => {
    const now = Date.now();
    if (isProcessing && now - lastScrollRef.current < 100) return;
    lastScrollRef.current = now;
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isProcessing]);

  useEffect(() => {
    return () => {
      if (rafIdRef.current) {
        cancelAnimationFrame(rafIdRef.current);
        rafIdRef.current = null;
      }
    };
  }, []);

  // Auto-save conversation whenever messages change
  useEffect(() => {
    if (!isAuthenticated || messages.length < 2) return;
    const convId = currentConversationId || session.sessionId;
    if (!convId) return;

    const timer = setTimeout(async () => {
      try {
        await saveConversation(convId);
        await fetchHistory();
      } catch (err) { console.error('Auto-save failed:', err); }
    }, 1500);

    return () => clearTimeout(timer);
  }, [messages, currentConversationId, session.sessionId, isAuthenticated]);

  useEffect(() => {
    setMessages([]);
    setCurrentConversationId(null);
    if (isAuthenticated) {
      fetchHistory();
    }
  }, [user?.id, isAuthenticated]);

  const fetchHistory = async () => {
    if (!isAuthenticated) return;
    try {
      const res = await fetch(`${API_URL}/api/user/conversations`, {
        headers: getAuthHeader(),
      });
      if (res.ok) {
        const data = await res.json();
        const conversations = Array.isArray(data.conversations) ? data.conversations : [];
        setHistory(conversations);
      }
    } catch (error) {
      console.error('Failed to fetch history:', error);
    }
  };

  const handleSelectSession = async (sessionId: string) => {
    try {
      setIsProcessing(true);
      const data = await loadSession(sessionId);
      if (data && data.messages) {
        setMessages(data.messages.map((m: any) => ({
          ...m,
          timestamp: new Date(m.timestamp)
        })));
        setCurrentConversationId(data.session_id || sessionId);
        setIsHistoryOpen(false);
      }
    } catch (error) {
      console.error('Failed to switch session:', error);
    } finally {
      setIsProcessing(false);
    }
  };

  const saveConversation = async (overrideId?: string) => {
    if (!isAuthenticated || messages.length <= 1) return;
    const convId = overrideId || currentConversationId || session.sessionId;
    if (!convId) return;
    try {
      const title = messages.find(m => m.role === 'user')?.content.slice(0, 50) || 'Conversation';
      await fetch(`${API_URL}/api/user/conversations`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...getAuthHeader(),
        },
        body: JSON.stringify({
          conversation_id: convId,
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
    if (messages.length > 1) {
      await saveConversation();
    }
    resetSession();
    setMessages([]);
    setCurrentConversationId(null);
    setFeedback({});
    fetchHistory();
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
        // Add empty placeholder for streaming text
        const placeholder: Message = { role: 'assistant', content: '', timestamp: new Date() };
        setMessages((prev) => [...prev, placeholder]);

        let accumulatedText = '';
        targetTextRef.current = '';
        displayedLengthRef.current = 0;

        const typewriterTick = () => {
          const target = targetTextRef.current;
          const displayed = displayedLengthRef.current;

          if (displayed < target.length) {
            const remaining = target.length - displayed;
            const chars = remaining > 200 ? 30
                        : remaining > 80  ? 15
                        : remaining > 30  ? 6
                        :                   2;
            displayedLengthRef.current = Math.min(displayed + chars, target.length);
            const snapshot = target.slice(0, displayedLengthRef.current);
            setMessages((prev) => {
              const updated = [...prev];
              updated[updated.length - 1] = { ...updated[updated.length - 1], content: snapshot };
              return updated;
            });
          }

          if (isStreamingRef.current || displayedLengthRef.current < targetTextRef.current.length) {
            rafIdRef.current = requestAnimationFrame(typewriterTick);
          } else {
            rafIdRef.current = null;
          }
        };

        await sendMessageStream(
          currentInput,
          language,
          // onToken — accumulate into ref, typewriter reveals progressively
          (text) => {
            accumulatedText += text;
            targetTextRef.current = accumulatedText;
            if (!rafIdRef.current) {
              isStreamingRef.current = true;
              typewriterTick();
            }
          },
          // onMetadata — update session state
          (meta) => {
            if (!currentConversationId && meta.session_id) {
              setCurrentConversationId(meta.session_id);
            }
          },
          // onDone — finalize with clean text, products, citations
          (final) => {
            isStreamingRef.current = false;
            if (rafIdRef.current) {
              cancelAnimationFrame(rafIdRef.current);
              rafIdRef.current = null;
            }
            targetTextRef.current = '';
            displayedLengthRef.current = 0;
            const flowMetadata = final.flow_metadata || undefined;
            setMessages((prev) => {
              const updated = [...prev];
              // Attach flowMetadata to the last user message
              for (let i = updated.length - 1; i >= 0; i--) {
                if (updated[i].role === 'user') {
                  updated[i] = { ...updated[i], flowMetadata };
                  break;
                }
              }
              // Finalize assistant message
              updated[updated.length - 1] = {
                ...updated[updated.length - 1],
                content: final.full_response || accumulatedText,
                recommendedProducts: final.recommended_products || [],
                flowMetadata,
                citations: final.citations || [],
                sources: final.sources || [],
              };
              return updated;
            });
          },
          // onError — fallback to non-streaming sendMessage()
          async (err) => {
            isStreamingRef.current = false;
            if (rafIdRef.current) {
              cancelAnimationFrame(rafIdRef.current);
              rafIdRef.current = null;
            }
            targetTextRef.current = '';
            displayedLengthRef.current = 0;
            console.warn('Stream failed, falling back:', err);
            // Remove placeholder
            setMessages((prev) => prev.slice(0, -1));
            try {
              const response = await sendMessage(currentInput, language);
              if (!response) throw new Error('No response received');
              let responseText = typeof response.response === 'string' ? response.response : '';
              if (!responseText.trim()) responseText = 'I apologize, but I received an invalid response. Please try again.';
              const flowMetadata = response.flow_metadata || undefined;
              const assistantMessage: Message = {
                role: 'assistant',
                content: responseText,
                citations: response.citations || [],
                sources: response.sources || [],
                recommendedProducts: response.recommended_products || [],
                flowMetadata,
                timestamp: new Date(),
              };
              setMessages((prev) => {
                const nextMessages = [...prev];
                for (let i = nextMessages.length - 1; i >= 0; i--) {
                  if (nextMessages[i].role === 'user') {
                    nextMessages[i] = { ...nextMessages[i], flowMetadata };
                    break;
                  }
                }
                return [...nextMessages, assistantMessage];
              });
              if (!currentConversationId && response.session_id) {
                setCurrentConversationId(response.session_id);
              }
            } catch (fallbackErr) {
              console.error('Fallback also failed:', fallbackErr);
              setMessages((prev) => [...prev, {
                role: 'assistant',
                content: 'I apologize, but I encountered an error. Please try again.',
                timestamp: new Date(),
              }]);
            }
          }
        );
      }
    } catch (error) {
      console.error('Error in handleTextSubmit:', error);
      // Remove placeholder if it exists
      setMessages((prev) => {
        if (prev.length > 0 && prev[prev.length - 1].role === 'assistant' && prev[prev.length - 1].content === '') {
          return prev.slice(0, -1);
        }
        return prev;
      });
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

  if (!isAuthenticated) {
    return (
      <>
        <Head>
          <title>3ioNetra Spiritual Companion - Login</title>
          <meta name="viewport" content="width=device-width, initial-scale=1" />
        </Head>
        <LoginPage onLogin={login} onRegister={register} isLoading={authLoading} error={authError} />
      </>
    );
  }

  return (
    <>
      <Head>
        <title>3ioNetra Spiritual Companion</title>
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <style>{`
          @keyframes fadeIn { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: translateY(0); } }
          .animate-fade-in { animation: fadeIn 0.4s cubic-bezier(0.16, 1, 0.3, 1) forwards; }
          .scrollbar-hide::-webkit-scrollbar { display: none; }
          .scrollbar-hide { -ms-overflow-style: none; scrollbar-width: none; }
          @keyframes blink { 0%, 100% { opacity: 1; } 50% { opacity: 0; } }
          .streaming-cursor { display: inline-block; width: 2px; height: 1em; background: #c2410c; margin-left: 2px; vertical-align: text-bottom; animation: blink 0.8s step-end infinite; }
        `}</style>
      </Head>

      <main className="h-[100dvh] bg-[#fcfcfc] flex overflow-hidden font-['Inter']">
        <aside data-testid="sidebar" className={`fixed inset-y-0 left-0 z-50 w-72 bg-white/90 backdrop-blur-xl border-r border-orange-100 shadow-2xl transform transition-all duration-500 ease-in-out lg:relative ${isHistoryOpen ? 'translate-x-0' : '-translate-x-full lg:-ml-72'}`}>
          <div className="h-full flex flex-col">
            <div className="p-5 border-b border-orange-100/50 flex items-center justify-between">
              <h2 className="font-black text-gray-900 flex items-center gap-2 text-lg tracking-tight">
                <History className="w-4 h-4 text-orange-600" />
                Conversations
              </h2>
              <button onClick={() => setIsHistoryOpen(false)} className="p-2 text-gray-400 hover:text-orange-600 hover:bg-orange-50 rounded-xl transition-all">
                <ChevronDown className="w-5 h-5 rotate-90" />
              </button>
            </div>

            <div className="flex-1 overflow-y-auto p-3 space-y-1.5 scrollbar-hide">
              <button onClick={handleNewConversation} className="w-full p-3.5 text-left rounded-2xl border-2 border-dashed border-orange-200 text-orange-600 hover:bg-orange-50 hover:border-orange-300 transition-all flex items-center gap-2.5 group bg-white/50 mb-3">
                <RefreshCw className="w-4 h-4 group-hover:rotate-180 transition-transform duration-700" />
                <span className="text-xs font-black uppercase tracking-wider">New Session</span>
              </button>

              {history.map((item) => (
                <button
                  key={item.id}
                  onClick={() => handleSelectSession(item.session_id || item.id)}
                  className={`w-full p-4 text-left rounded-2xl transition-all border ${currentConversationId === (item.session_id || item.id) ? 'bg-orange-50 border-orange-200 shadow-sm' : 'border-transparent hover:bg-gray-50'}`}
                >
                  <p className="text-sm font-bold text-gray-900 truncate mb-0.5">{item.title}</p>
                  <div className="flex items-center justify-between opacity-50">
                    <span className="text-[9px] font-bold">{new Date(item.created_at).toLocaleDateString()}</span>
                    <span className="text-[9px] font-bold uppercase">{item.message_count} msgs</span>
                  </div>
                </button>
              ))}
            </div>

            <div className="p-5 border-t border-orange-100 bg-orange-50/10">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 bg-gradient-to-br from-orange-100 to-amber-100 rounded-xl flex items-center justify-center border border-white shadow-sm ring-1 ring-orange-200/50">
                  <User className="w-5 h-5 text-orange-600" />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-black text-gray-900 truncate">{user?.name}</p>
                  <button onClick={logout} className="text-[10px] text-orange-600 font-black uppercase tracking-tighter hover:underline">Sign Out</button>
                </div>
              </div>
            </div>
          </div>
        </aside>

        {isHistoryOpen && <div className="fixed inset-0 bg-black/10 backdrop-blur-sm z-40 lg:hidden" onClick={() => setIsHistoryOpen(false)} />}

        <div className="flex-1 flex flex-col h-screen overflow-hidden relative">
          <header className="sticky top-0 z-30 bg-white/70 backdrop-blur-md border-b border-orange-50 shrink-0 px-4 py-2.5">
            <div className="max-w-4xl mx-auto flex items-center justify-between">
              <div className="flex items-center gap-3">
                <button data-testid="sidebar-toggle" onClick={() => setIsHistoryOpen(!isHistoryOpen)} className="p-2 text-gray-600 hover:text-orange-600 hover:bg-orange-50 rounded-xl transition-all shadow-sm border border-orange-50 bg-white">
                  <History className={`w-4 h-4 transition-transform duration-500 ${isHistoryOpen ? 'rotate-180' : ''}`} />
                </button>
                <div className="flex flex-col">
                  <h1 className="text-xl font-black flex items-center gap-2 tracking-tighter">
                    <img src="/logo-circle.jpg" alt="3ioNetra" className="w-8 h-8 rounded-full shadow-sm" />
                    <span className="text-[#1a2b56]">3ioNetra</span>
                  </h1>
                </div>
              </div>
              <button
                onClick={handleNewConversation}
                className="flex items-center gap-1.5 px-4 py-2 text-xs font-black text-orange-600 hover:bg-orange-50 border border-orange-100 rounded-xl transition-all shadow-sm bg-white active:scale-95"
              >
                <RefreshCw className="w-3.5 h-3.5" />
                <span className="hidden sm:inline uppercase">New Session</span>
              </button>
            </div>
          </header>

          <div className="flex-1 relative overflow-hidden flex flex-col">
            {useConversationFlow && session.sessionId && (
              <PhaseIndicatorCompact phase={session.phase} turnCount={session.turnCount} maxTurns={6} signalsCollected={session.signalsCollected} />
            )}

            <div className="flex-1 overflow-y-auto pt-4 pb-32 scroll-smooth scrollbar-hide">
              <div className="max-w-4xl mx-auto px-5">
                {messages.length === 0 ? (
                  <div className="text-center py-12 md:py-16 animate-fade-in px-4">
                    <div className="mb-8 md:mb-12 relative inline-block">
                      <div className="absolute -inset-10 bg-orange-200/20 blur-[80px] rounded-full -z-10"></div>
                      <div className="flex flex-col items-center">
                        <img src="/logo-full.png" alt="3ioNetra" className="h-16 md:h-20 lg:h-24 object-contain mb-4" />
                        <div className="h-1 w-48 bg-gradient-to-r from-orange-400 via-amber-500 to-orange-400 rounded-full shadow shadow-orange-100"></div>
                      </div>
                      <p className="text-[10px] md:text-xs text-orange-600 font-black uppercase tracking-[0.3em] mt-3">Elevate your spirit</p>
                    </div>

                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 md:gap-6 mt-8 md:mt-12 max-w-2xl mx-auto">
                      <div className="p-6 md:p-8 bg-white border border-gray-100 rounded-3xl shadow-sm hover:shadow-xl hover:-translate-y-1 transition-all text-left group">
                        <div className="w-10 h-10 md:w-12 md:h-12 bg-orange-50 rounded-2xl flex items-center justify-center mb-4 md:mb-6 text-orange-600 group-hover:scale-110 group-hover:bg-orange-600 group-hover:text-white transition-all duration-500 shadow-inner">
                          <BookOpen className="w-5 h-5 md:w-6 md:h-6" />
                        </div>
                        <h3 className="font-black text-gray-900 mb-1.5 text-lg md:text-xl tracking-tight">Seek Wisdom</h3>
                        <p className="text-xs md:text-sm text-gray-500 leading-relaxed font-medium">Explore Sanatan Dharma through sacred scriptures and tailored guidance.</p>
                      </div>
                      <div className="p-6 md:p-8 bg-white border border-gray-100 rounded-3xl shadow-sm hover:shadow-xl hover:-translate-y-1 transition-all text-left group">
                        <div className="w-10 h-10 md:w-12 md:h-12 bg-amber-50 rounded-2xl flex items-center justify-center mb-4 md:mb-6 text-amber-600 group-hover:scale-110 group-hover:bg-amber-600 group-hover:text-white transition-all duration-500 shadow-inner">
                          <Activity className="w-5 h-5 md:w-6 md:h-6" />
                        </div>
                        <h3 className="font-black text-gray-900 mb-1.5 text-lg md:text-xl tracking-tight">Daily Support</h3>
                        <p className="text-xs md:text-sm text-gray-500 leading-relaxed font-medium">Share your life's challenges and find spiritual peace and direction.</p>
                      </div>
                    </div>
                  </div>
                ) : (
                  <div className="space-y-6 md:space-y-8 pb-10">
                    {messages.map((message, index) => {
                      if (message.role === 'assistant' && !message.content) return null;
                      return (
                      <div key={index} className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'} animate-fade-in`}>
                        <div className={`max-w-[85%] sm:max-w-[70%] rounded-2xl px-4 py-3 md:px-6 md:py-4 shadow-xl shadow-orange-900/[0.03] transition-all relative group ${message.role === 'user'
                          ? 'bg-gradient-to-br from-orange-500 to-amber-600 text-white shadow-orange-200/30 rounded-tr-sm'
                          : 'bg-white border border-orange-50/50 text-gray-800 rounded-tl-sm shadow-sm'
                          }`}>
                          {message.role === 'assistant' && message.content ? (() => {
                            const segments = parsedMessages[index] || parseResponseForVerses(message.content);
                            return (
                              <div className="message-content space-y-2.5 md:space-y-3 text-sm md:text-[15px]">
                                {segments.map((seg, si) => (
                                  seg.type !== 'text' ? (
                                    <div key={si} className="my-3 md:my-4 pl-3.5 md:pl-5 border-l-4 border-amber-400 bg-amber-50/40 rounded-r-xl py-3 md:py-4 pr-3.5 md:pr-5 border border-orange-100/30 relative overflow-hidden">
                                      <p className="whitespace-pre-wrap text-amber-950 italic text-[14px] leading-relaxed font-serif relative z-10">
                                        &quot;{seg.content}&quot;
                                      </p>
                                      <div className="mt-2.5 relative z-10">
                                        <TTSButton text={seg.content} lang="hi" variant={seg.type as 'verse' | 'mantra'} />
                                      </div>
                                    </div>
                                  ) : (
                                    <p key={si} className="whitespace-pre-wrap leading-[1.65] md:leading-[1.7] font-medium text-gray-700/90">
                                      {seg.content}
                                      {isProcessing && index === messages.length - 1 && si === segments.length - 1 && seg.type === 'text' && (
                                        <span className="streaming-cursor" />
                                      )}
                                    </p>
                                  )
                                ))}
                                <div className="pt-3 border-t border-orange-50/50 flex items-center justify-between">
                                  <div className="flex items-center gap-1">
                                    <button
                                      onClick={() => handleFeedback(index, message.content, 'like')}
                                      className={`p-1.5 rounded-lg transition-all ${feedback[index] === 'like' ? 'bg-green-100 text-green-600' : 'text-gray-500 hover:text-green-500 hover:bg-green-50'}`}
                                      title="Helpful"
                                    >
                                      <ThumbsUp className="w-3.5 h-3.5" />
                                    </button>
                                    <button
                                      onClick={() => handleFeedback(index, message.content, 'dislike')}
                                      className={`p-1.5 rounded-lg transition-all ${feedback[index] === 'dislike' ? 'bg-red-100 text-red-600' : 'text-gray-500 hover:text-red-500 hover:bg-red-50'}`}
                                      title="Not helpful"
                                    >
                                      <ThumbsDown className="w-3.5 h-3.5" />
                                    </button>
                                  </div>
                                  <TTSButton text={message.content} lang="en" variant="response" label="Listen to Full Response" />
                                </div>
                              </div>
                            );
                          })() : (
                            <p className="whitespace-pre-wrap text-[14px] md:text-[15px] leading-[1.65] md:leading-[1.7] font-bold">
                              {message.content}
                            </p>
                          )}



                          {message.role === 'assistant' && message.recommendedProducts && message.recommendedProducts.length > 0 && (
                            <ProductDisplay products={message.recommendedProducts} />
                          )}

                          <div className={`mt-2 text-[8px] md:text-[9px] font-black tracking-widest uppercase opacity-30 ${message.role === 'user' ? 'text-white' : 'text-gray-400'}`}>
                            {message.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                          </div>
                        </div>
                      </div>
                      );
                    })}

                    {isProcessing && (!messages.length || messages[messages.length - 1]?.content === '') && (
                      <div className="flex justify-start animate-fade-in pl-1">
                        <div className="bg-white/90 backdrop-blur-xl border border-orange-100 shadow-lg rounded-xl px-5 py-3 flex items-center gap-4">
                          <div className="flex gap-1">
                            <div className="w-1 h-1 bg-orange-400 rounded-full animate-bounce [animation-duration:0.8s]"></div>
                            <div className="w-1 h-1 bg-orange-500 rounded-full animate-bounce [animation-delay:0.2s] [animation-duration:0.8s]"></div>
                            <div className="w-1 h-1 bg-orange-600 rounded-full animate-bounce [animation-delay:0.4s] [animation-duration:0.8s]"></div>
                          </div>
                          <span className="text-[9px] font-black text-orange-900 uppercase tracking-widest">{session.phase === 'synthesis' ? 'Seeking Essence' : 'Listening'}</span>
                        </div>
                      </div>
                    )}
                    <div ref={messagesEndRef} />
                  </div>
                )}
              </div>
            </div>

            <div className="absolute bottom-0 left-0 right-0 p-4 md:p-6 pointer-events-none">
              <div className="max-w-3xl mx-auto pointer-events-auto">
                <div className="bg-white/90 backdrop-blur-[12px] border border-orange-100 shadow-xl rounded-2xl p-1 pr-2.5 flex items-center gap-1 group transition-all duration-700 hover:shadow-orange-900/5 focus-within:ring-[6px] focus-within:ring-orange-500/[0.04]">
                  <form onSubmit={handleTextSubmit} className="flex-1 flex items-center">
                    <input
                      id="chat-input"
                      data-testid="chat-input"
                      name="message"
                      type="text"
                      value={input}
                      onChange={(e) => setInput(e.target.value)}
                      placeholder="Share your spiritual journey..."
                      disabled={isProcessing}
                      autoComplete="off"
                      className="flex-1 px-4 md:px-6 py-3 md:py-4 bg-transparent text-gray-950 placeholder:text-gray-400 border-none focus:ring-0 text-[14px] md:text-[15px] font-bold tracking-tight outline-none"
                    />
                    <button
                      type="submit"
                      data-testid="send-button"
                      disabled={isProcessing || !input.trim()}
                      className="p-3 md:p-3.5 bg-gradient-to-br from-orange-500 to-amber-700 hover:from-orange-600 hover:to-amber-800 text-white rounded-xl shadow-lg disabled:grayscale disabled:opacity-20 transition-all duration-500 active:scale-95"
                    >
                      {isProcessing ? <Loader2 className="w-4.5 h-4.5 animate-spin" /> : <Send className="w-4.5 h-4.5" />}
                    </button>
                  </form>
                </div>
              </div>
            </div>
          </div>
        </div>
      </main>
    </>
  );
}
