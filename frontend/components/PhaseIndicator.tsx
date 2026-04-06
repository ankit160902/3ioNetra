import React from 'react';

const phases = [
  { key: 'listening', label: 'Listening', subtitle: 'Tell us your story' },
  { key: 'synthesis', label: 'Reflecting', subtitle: 'Seeking profound essence' },
  { key: 'guidance', label: 'Guidance', subtitle: 'Divine guidance received' },
  { key: 'closure', label: 'Complete', subtitle: 'Session complete' },
] as const;

const phaseToStep: Record<string, number> = {
  listening: 0,
  clarification: 0,
  synthesis: 1,
  answering: 2,
  guidance: 2,
  closure: 3,
};

export function PhaseIndicatorCompact({
  phase,
}: {
  phase: 'clarification' | 'synthesis' | 'answering' | 'listening' | 'guidance' | 'closure';
}) {
  const currentStep = phaseToStep[phase] ?? 0;

  return (
    <div data-testid="phase-indicator" className="flex items-center px-5 py-2 bg-orange-50/40 dark:bg-gray-900/60 backdrop-blur-md border-b border-orange-100/50 dark:border-gray-800 animate-fade-in shrink-0">
      <div className="flex items-center gap-1.5 w-full max-w-md mx-auto">
        {phases.map((p, i) => (
          <React.Fragment key={p.key}>
            <div className="flex items-center gap-1.5 shrink-0" title={p.subtitle}>
              <div className={`
                w-5 h-5 rounded-full flex items-center justify-center text-[8px] font-black transition-all duration-500
                ${i < currentStep
                  ? 'bg-orange-500 text-white'
                  : i === currentStep
                    ? 'bg-orange-500 text-white ring-[3px] ring-orange-500/20'
                    : 'bg-gray-200 dark:bg-gray-700 text-gray-400 dark:text-gray-500'}
              `}>
                {i < currentStep ? '\u2713' : i + 1}
              </div>
              <span className={`text-[9px] font-black uppercase tracking-wider hidden sm:inline transition-colors duration-300 ${
                i === currentStep ? 'text-orange-700 dark:text-orange-300' : 'text-gray-400 dark:text-gray-500'
              }`}>
                {p.label}
              </span>
            </div>
            {i < phases.length - 1 && (
              <div className={`flex-1 h-0.5 min-w-[12px] rounded-full transition-all duration-500 ${
                i < currentStep ? 'bg-orange-500' : 'bg-gray-200 dark:bg-gray-700'
              }`} />
            )}
          </React.Fragment>
        ))}
      </div>
    </div>
  );
}
