/**
 * PhaseIndicator Component
 * Shows the current phase of the conversation flow
 */
import React from 'react';

interface PhaseIndicatorProps {
  phase: 'clarification' | 'synthesis' | 'answering' | 'listening' | 'guidance' | 'closure';
  turnCount: number;
  maxTurns?: number;
  signalsCollected?: Record<string, string>;
}

const allPhases = [
  { id: 'listening', label: 'Listening', description: 'Learning about you' },
  { id: 'clarification', label: 'Listening', description: 'Learning about you' },
  { id: 'synthesis', label: 'Reflecting', description: 'Finding wisdom' },
  { id: 'answering', label: 'Guidance', description: 'Sharing wisdom' },
  { id: 'guidance', label: 'Guidance', description: 'Sharing wisdom' },
  { id: 'closure', label: 'Complete', description: 'Peace be with you' },
] as const;

export function PhaseIndicator({
  phase,
  turnCount,
  maxTurns = 6,
  signalsCollected = {},
}: PhaseIndicatorProps) {
  const displayPhases = [
    { id: 'listening', label: 'Listening', description: 'Understanding you' },
    { id: 'guidance', label: 'Guidance', description: 'Sharing wisdom' },
    { id: 'closure', label: 'Complete', description: 'Stay blessed' },
  ];

  const currentDisplayIndex = (phase === 'listening' || phase === 'clarification') ? 0
    : (phase === 'guidance' || phase === 'answering' || phase === 'synthesis') ? 1
      : 2;

  const signalCount = Object.keys(signalsCollected).length;

  return (
    <div className="w-full px-4 py-2 bg-white/50 backdrop-blur-sm border-b border-orange-100 flex items-center justify-between animate-fade-in">
      <div className="flex items-center gap-4">
        {displayPhases.map((p, index) => (
          <div key={p.id} className="flex items-center gap-2">
            <div
              className={`
                w-5 h-5 rounded-full flex items-center justify-center text-[9px] font-black
                transition-all duration-500 shadow-sm
                ${index < currentDisplayIndex
                  ? 'bg-green-500 text-white'
                  : index === currentDisplayIndex
                    ? 'bg-orange-500 text-white ring-2 ring-orange-200'
                    : 'bg-gray-100 text-gray-400'
                }
              `}
            >
              {index < currentDisplayIndex ? '✓' : index + 1}
            </div>
            <span
              className={`
                text-[10px] font-black uppercase tracking-widest
                ${index === currentDisplayIndex ? 'text-orange-700' : 'text-gray-400'}
                hidden sm:inline
              `}
            >
              {p.label}
            </span>
            {index < displayPhases.length - 1 && (
              <div className="w-4 h-px bg-orange-100 mx-1" />
            )}
          </div>
        ))}
      </div>

      <div className="flex items-center gap-4 text-[10px] font-black uppercase tracking-tighter text-gray-500">
        <span className="flex items-center gap-1.5 opacity-70">
          Turn {turnCount}/{maxTurns}
        </span>
        <span className="flex items-center gap-1.5 text-orange-600 bg-orange-50 px-2 py-0.5 rounded-full">
          {signalCount} signals
        </span>
      </div>
    </div>
  );
}

// Compact version for floating layouts
export function PhaseIndicatorCompact({
  phase,
  turnCount,
  maxTurns = 6,
  signalsCollected = {},
}: {
  phase: 'clarification' | 'synthesis' | 'answering' | 'listening' | 'guidance' | 'closure';
  turnCount: number;
  maxTurns?: number;
  signalsCollected?: Record<string, string>;
}) {
  const displayPhasesMap = {
    'listening': { label: 'Listening', color: 'orange' },
    'clarification': { label: 'Listening', color: 'orange' },
    'synthesis': { label: 'Reflecting', color: 'blue' },
    'guidance': { label: 'Guidance', color: 'green' },
    'answering': { label: 'Guidance', color: 'green' },
    'closure': { label: 'Complete', color: 'gray' },
  };

  const current = displayPhasesMap[phase];

  return (
    <div className="flex items-center justify-between px-5 py-1.5 bg-orange-50/40 backdrop-blur-md border-b border-orange-100/50 animate-fade-in shrink-0">
      <div className="flex items-center gap-3">
        <div className={`
          px-2.5 py-0.5 rounded-full text-[9px] font-black uppercase tracking-[0.2em] shadow-sm
          ${current.color === 'orange' ? 'bg-orange-100 text-orange-700 border border-orange-200' :
            current.color === 'blue' ? 'bg-blue-100 text-blue-700 border border-blue-200' :
              'bg-green-100 text-green-700 border border-green-200'}
        `}>
          {current.label}
        </div>
        <p className="text-[10px] font-bold text-gray-500/80 uppercase tracking-tight hidden sm:block">
          {phase === 'synthesis' ? 'Seeking profound essence' :
            phase === 'listening' ? 'Tell us your story' :
              'Divine guidance received'}
        </p>
      </div>

      <div className="flex items-center gap-4">
        <div className="flex items-center gap-1.5 bg-white/50 px-2 py-0.5 rounded-lg border border-orange-50">
          <span className="text-[9px] font-black text-gray-400">TURN</span>
          <span className="text-[10px] font-black text-orange-700">{turnCount}/{maxTurns}</span>
        </div>
        <div className="flex items-center gap-1.5 bg-white/50 px-2 py-0.5 rounded-lg border border-orange-50">
          <span className="text-[9px] font-black text-gray-400">SIGNALS</span>
          <span className="text-[10px] font-black text-orange-700">{Object.keys(signalsCollected).length}</span>
        </div>
      </div>
    </div>
  );
}

export default PhaseIndicator;
