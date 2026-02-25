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

    const isVerse = variant === 'verse';

    // Icon SVGs
    const PlayIcon = () => (
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-3 h-3">
            <path d="M8 5v14l11-7z" />
        </svg>
    );

    const PauseIcon = () => (
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-3 h-3">
            <path d="M6 19h4V5H6v14zm8-14v14h4V5h-4z" />
        </svg>
    );

    const LoadingIcon = () => (
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="w-3 h-3 animate-spin text-current">
            <circle cx="12" cy="12" r="10" strokeOpacity="0.25" />
            <path d="M12 2a10 10 0 0 1 10 10" strokeLinecap="round" />
        </svg>
    );

    const getIcon = () => {
        switch (state) {
            case 'loading': return <LoadingIcon />;
            case 'playing': return <PauseIcon />;
            case 'paused': return <PlayIcon />;
            default: return <PlayIcon />;
        }
    };

    const getLabelText = () => {
        if (label) return label;
        if (isVerse) {
            switch (state) {
                case 'loading': return 'fetching...';
                case 'playing': return 'pause verse';
                case 'paused': return 'resume verse';
                default: return 'play verse';
            }
        }
        switch (state) {
            case 'loading': return 'fetching...';
            case 'playing': return 'pause';
            case 'paused': return 'resume';
            default: return 'listen';
        }
    };

    const baseClasses = isVerse
        ? 'inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[9px] font-black uppercase tracking-wider transition-all duration-300 cursor-pointer select-none border'
        : 'inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full text-[10px] font-black uppercase tracking-widest transition-all duration-300 cursor-pointer select-none border';

    const colorClasses = isVerse
        ? state === 'playing'
            ? 'bg-amber-100/50 text-amber-800 border-amber-300/50 shadow-inner ring-4 ring-amber-500/5'
            : 'bg-white text-amber-700 border-amber-100 hover:bg-amber-50 hover:border-amber-200'
        : state === 'playing'
            ? 'bg-orange-100/50 text-orange-800 border-orange-300/50 shadow-inner ring-4 ring-orange-500/5'
            : 'bg-white text-orange-700 border-orange-100 hover:bg-orange-50 hover:border-orange-200';

    return (
        <button
            onClick={handleClick}
            disabled={state === 'loading'}
            className={`${baseClasses} ${colorClasses} ${className} active:scale-90`}
            title={isVerse ? 'Play verse in Hindi' : 'Play response in Hindi'}
        >
            {getIcon()}
            <span>{getLabelText()}</span>
        </button>
    );
}
