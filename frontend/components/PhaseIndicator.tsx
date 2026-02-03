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

const phases = [
  { id: 'listening', label: 'Understanding', description: 'Learning about your situation' },
  { id: 'guidance', label: 'Guidance', description: 'Sharing wisdom' },
  { id: 'closure', label: 'Closing', description: 'Wrapping up' },
] as const;

// Combined phases mapping for indices
const allPhases = [
  { id: 'listening', label: 'Understanding', description: 'Learning about your situation' },
  { id: 'clarification', label: 'Understanding', description: 'Learning about your situation' },
  { id: 'synthesis', label: 'Reflecting', description: 'Finding the right guidance' },
  { id: 'answering', label: 'Guidance', description: 'Sharing wisdom' },
  { id: 'guidance', label: 'Guidance', description: 'Sharing wisdom' },
  { id: 'closure', label: 'Closing', description: 'Wrapping up' },
] as const;

export function PhaseIndicator({
  phase,
  turnCount,
  maxTurns = 6,
  signalsCollected = {},
}: PhaseIndicatorProps) {
  const currentIndex = allPhases.findIndex((p) => p.id === phase);

  // Map current phase to display phase index (0, 1, or 2)
  let displayIndex = 0;
  if (phase === 'synthesis') displayIndex = 1;
  else if (phase === 'answering' || phase === 'guidance' || phase === 'closure') displayIndex = 1; // Show as middle or end?

  // Re-define display phases for UI
  const displayPhases = [
    { id: 'listening', label: 'Understanding', description: 'Learning about your situation' },
    { id: 'guidance', label: 'Guidance', description: 'Sharing dharmic wisdom' },
    { id: 'closure', label: 'Complete', description: 'Peace be with you' },
  ];

  const currentDisplayIndex = (phase === 'listening' || phase === 'clarification') ? 0
    : (phase === 'guidance' || phase === 'answering' || phase === 'synthesis') ? 1
      : 2;

  const signalCount = Object.keys(signalsCollected).length;

  return (
    <div className="w-full px-4 py-3 bg-gradient-to-r from-orange-50 to-amber-50 border-b border-orange-100">
      {/* Phase Progress */}
      <div className="flex items-center justify-center gap-2 mb-2">
        {displayPhases.map((p, index) => (
          <React.Fragment key={p.id}>
            {/* Phase Circle */}
            <div className="flex flex-col items-center">
              <div
                className={`
                  w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium
                  transition-all duration-300
                  ${index < currentDisplayIndex
                    ? 'bg-green-500 text-white'
                    : index === currentDisplayIndex
                      ? 'bg-orange-500 text-white ring-2 ring-orange-300 ring-offset-2'
                      : 'bg-gray-200 text-gray-500'
                  }
                `}
              >
                {index < currentDisplayIndex ? (
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                  </svg>
                ) : (
                  index + 1
                )}
              </div>
              <span
                className={`
                  text-xs mt-1 font-medium
                  ${index === currentDisplayIndex ? 'text-orange-700' : 'text-gray-500'}
                `}
              >
                {p.label}
              </span>
            </div>

            {/* Connector Line */}
            {index < displayPhases.length - 1 && (
              <div
                className={`
                  w-12 h-0.5 -mt-4
                  ${index < currentDisplayIndex ? 'bg-green-500' : 'bg-gray-200'}
                `}
              />
            )}
          </React.Fragment>
        ))}
      </div>

      {/* Phase Description and Progress */}
      <div className="text-center">
        <p className="text-sm text-gray-600">{displayPhases[currentDisplayIndex]?.description}</p>

        {/* Show turn count and signals during clarification */}
        {phase === 'clarification' && (
          <div className="flex items-center justify-center gap-4 mt-2 text-xs text-gray-500">
            <span className="flex items-center gap-1">
              <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
              </svg>
              Turn {turnCount}/{maxTurns}
            </span>
            <span className="flex items-center gap-1">
              <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              {signalCount} signals
            </span>
          </div>
        )}

        {/* Show completion message */}
        {(phase === 'answering' || phase === 'guidance') && (
          <p className="text-xs text-green-600 mt-1">Ready to share dharmic guidance</p>
        )}
        {phase === 'closure' && (
          <p className="text-xs text-green-600 mt-1">Conversation complete</p>
        )}
      </div>
    </div>
  );
}

// Compact version for mobile
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
    'listening': { label: 'Listening', description: 'Learning about you' },
    'clarification': { label: 'Listening', description: 'Learning about you' },
    'synthesis': { label: 'Reflecting', description: 'Finding wisdom' },
    'guidance': { label: 'Guidance', description: 'Sharing wisdom' },
    'answering': { label: 'Guidance', description: 'Sharing wisdom' },
    'closure': { label: 'Complete', description: 'Peace be with you' },
  };

  const currentPhase = displayPhasesMap[phase];

  return (
    <div className="flex items-center justify-between px-4 py-2 bg-orange-50 border-b border-orange-100 text-sm">
      <div className="flex items-center gap-2">
        <span
          className={`
            px-2 py-0.5 rounded-full text-xs font-medium
            ${(phase === 'clarification' || phase === 'listening')
              ? 'bg-orange-100 text-orange-700'
              : (phase === 'synthesis')
                ? 'bg-blue-100 text-blue-700'
                : 'bg-green-100 text-green-700'
            }
          `}
        >
          {currentPhase?.label}
        </span>
        <span className="text-gray-600">{currentPhase?.description}</span>
      </div>

      {(phase === 'clarification' || phase === 'listening') && (
        <div className="flex flex-col items-end">
          <span className="text-xs text-gray-500">
            Turns: {turnCount}/{maxTurns}
          </span>
          <span className="text-[10px] text-orange-600 font-medium">
            {Object.keys(signalsCollected).length} traits learned
          </span>
        </div>
      )}
    </div>
  );
}

export default PhaseIndicator;
