/**
 * TTSButton - Text-to-Speech audio playback button
 * Calls backend /api/tts endpoint and plays the returned MP3 audio.
 * Uses Indian Hindi female voice for authentic Sanskrit/Hindi verse reading.
 */

import { useState, useRef, useCallback } from 'react';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8080';

interface TTSButtonProps {
    /** The text to be spoken */
    text: string;
    /** Language: 'hi' for Hindi/Sanskrit verses, 'en' for English */
    lang?: string;
    /** Label text shown next to the button */
    label?: string;
    /** Visual variant */
    variant?: 'response' | 'verse';
    /** Additional CSS class */
    className?: string;
}

type PlayState = 'idle' | 'loading' | 'playing' | 'paused';

export default function TTSButton({
    text,
    lang = 'hi',
    label,
    variant = 'response',
    className = '',
}: TTSButtonProps) {
    const [state, setState] = useState<PlayState>('idle');
    const audioRef = useRef<HTMLAudioElement | null>(null);
    const blobUrlRef = useRef<string | null>(null);

    const cleanup = useCallback(() => {
        if (audioRef.current) {
            audioRef.current.pause();
            audioRef.current.removeAttribute('src');
            audioRef.current = null;
        }
        if (blobUrlRef.current) {
            URL.revokeObjectURL(blobUrlRef.current);
            blobUrlRef.current = null;
        }
    }, []);

    const handleClick = useCallback(async () => {
        // If playing → pause
        if (state === 'playing' && audioRef.current) {
            audioRef.current.pause();
            setState('paused');
            return;
        }

        // If paused → resume
        if (state === 'paused' && audioRef.current) {
            audioRef.current.play();
            setState('playing');
            return;
        }

        // If idle or needs fresh fetch → load & play
        setState('loading');
        cleanup();

        try {
            const res = await fetch(`${API_URL}/api/tts`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ text, lang }),
            });

            if (!res.ok) {
                throw new Error(`TTS failed: ${res.status}`);
            }

            const blob = await res.blob();
            const url = URL.createObjectURL(blob);
            blobUrlRef.current = url;

            const audio = new Audio(url);
            audioRef.current = audio;

            audio.onended = () => {
                setState('idle');
                cleanup();
            };

            audio.onerror = () => {
                console.error('Audio playback error');
                setState('idle');
                cleanup();
            };

            await audio.play();
            setState('playing');
        } catch (err) {
            console.error('TTS error:', err);
            setState('idle');
            cleanup();
        }
    }, [state, text, lang, cleanup]);

    // Stop on unmount
    // (Note: using useRef for cleanup reference to avoid stale closures)

    const isVerse = variant === 'verse';

    // Icon SVGs
    const PlayIcon = () => (
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-3.5 h-3.5">
            <path d="M8 5v14l11-7z" />
        </svg>
    );

    const PauseIcon = () => (
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-3.5 h-3.5">
            <path d="M6 19h4V5H6v14zm8-14v14h4V5h-4z" />
        </svg>
    );

    const LoadingIcon = () => (
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="w-3.5 h-3.5 animate-spin">
            <circle cx="12" cy="12" r="10" strokeOpacity="0.25" />
            <path d="M12 2a10 10 0 0 1 10 10" strokeLinecap="round" />
        </svg>
    );

    const StopIcon = () => (
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-3.5 h-3.5">
            <rect x="6" y="6" width="12" height="12" rx="1" />
        </svg>
    );

    const getIcon = () => {
        switch (state) {
            case 'loading':
                return <LoadingIcon />;
            case 'playing':
                return <PauseIcon />;
            case 'paused':
                return <PlayIcon />;
            default:
                return <PlayIcon />;
        }
    };

    const getLabel = () => {
        if (label) return label;
        if (isVerse) {
            switch (state) {
                case 'loading': return 'Loading...';
                case 'playing': return 'Pause Verse';
                case 'paused': return 'Resume Verse';
                default: return '🔊 Play Verse';
            }
        }
        switch (state) {
            case 'loading': return 'Loading...';
            case 'playing': return 'Pause';
            case 'paused': return 'Resume';
            default: return '🔊 Listen';
        }
    };

    const baseClasses = isVerse
        ? 'inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium transition-all duration-200 cursor-pointer select-none border'
        : 'inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium transition-all duration-200 cursor-pointer select-none border';

    const colorClasses = isVerse
        ? state === 'playing'
            ? 'bg-amber-100 text-amber-800 border-amber-300 shadow-sm'
            : 'bg-amber-50 text-amber-700 border-amber-200 hover:bg-amber-100 hover:border-amber-300'
        : state === 'playing'
            ? 'bg-orange-100 text-orange-800 border-orange-300 shadow-sm'
            : 'bg-orange-50 text-orange-700 border-orange-200 hover:bg-orange-100 hover:border-orange-300';

    return (
        <button
            onClick={handleClick}
            disabled={state === 'loading'}
            className={`${baseClasses} ${colorClasses} ${className}`}
            title={isVerse ? 'Play verse in Hindi' : 'Play response in Hindi'}
        >
            {getIcon()}
            <span>{getLabel()}</span>
        </button>
    );
}
