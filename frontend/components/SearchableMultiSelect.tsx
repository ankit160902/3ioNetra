import { useState, useRef, useEffect } from 'react';
import { Search, X, ChevronDown, Loader2 } from 'lucide-react';

interface SearchableMultiSelectProps {
  label: string;
  options: string[];
  selected: string[];
  onChange: (selected: string[]) => void;
  placeholder?: string;
  loading?: boolean;
}

export default function SearchableMultiSelect({
  label,
  options,
  selected,
  onChange,
  placeholder = 'Search...',
  loading = false,
}: SearchableMultiSelectProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const containerRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Close on click outside
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setIsOpen(false);
        setSearchTerm('');
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  const filtered = options.filter((opt) =>
    opt.toLowerCase().includes(searchTerm.toLowerCase())
  );

  const handleToggle = (item: string) => {
    if (selected.includes(item)) {
      onChange(selected.filter((i) => i !== item));
    } else {
      onChange([...selected, item]);
    }
  };

  const handleRemove = (item: string, e: React.MouseEvent) => {
    e.stopPropagation();
    onChange(selected.filter((i) => i !== item));
  };

  const openDropdown = () => {
    setIsOpen(true);
    setTimeout(() => {
      inputRef.current?.focus();
      // Auto-scroll the trigger into view so the dropdown is visible
      containerRef.current?.scrollIntoView({ block: 'center', behavior: 'smooth' });
    }, 50);
  };

  return (
    <div ref={containerRef} className="relative">
      <label className="block text-[10px] font-black uppercase tracking-widest text-gray-400 dark:text-gray-500 mb-1.5 ml-1">
        {label}
      </label>

      {/* Trigger area */}
      <div
        onClick={openDropdown}
        className={`w-full px-4 py-3 bg-gray-50/50 dark:bg-gray-800/50 border rounded-2xl cursor-pointer transition-all ${
          isOpen
            ? 'border-orange-200 dark:border-orange-700 ring-4 ring-orange-500/5 bg-white dark:bg-gray-800'
            : 'border-orange-100 dark:border-gray-700 hover:border-orange-200 dark:hover:border-gray-600'
        }`}
      >
        {/* Selected chips */}
        {selected.length > 0 && (
          <div className="flex flex-wrap gap-1.5 mb-2">
            {selected.map((item) => (
              <span
                key={item}
                className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-[11px] font-bold bg-orange-500 text-white"
              >
                <span className="max-w-[120px] truncate">{item}</span>
                <X
                  onClick={(e) => handleRemove(item, e)}
                  className="w-3 h-3 cursor-pointer shrink-0 hover:opacity-70"
                />
              </span>
            ))}
          </div>
        )}

        {/* Search input row */}
        <div className="flex items-center gap-2">
          <Search className="w-3.5 h-3.5 text-gray-400 dark:text-gray-500 shrink-0" />
          <input
            ref={inputRef}
            value={searchTerm}
            onChange={(e) => {
              setSearchTerm(e.target.value);
              if (!isOpen) setIsOpen(true);
            }}
            onClick={(e) => {
              e.stopPropagation();
              if (!isOpen) openDropdown();
            }}
            onFocus={() => {
              if (!isOpen) openDropdown();
            }}
            placeholder={selected.length > 0 ? 'Add more...' : placeholder}
            className="flex-1 bg-transparent outline-none text-base md:text-sm font-bold text-gray-700 dark:text-gray-200 placeholder:text-gray-400 dark:placeholder:text-gray-500 min-w-0"
          />
          <ChevronDown
            className={`w-3.5 h-3.5 text-gray-400 dark:text-gray-500 shrink-0 transition-transform ${isOpen ? 'rotate-180' : ''}`}
          />
        </div>
      </div>

      {/* Dropdown */}
      {isOpen && (
        <div className="absolute left-0 right-0 top-full mt-1 z-50 bg-white dark:bg-gray-800 border border-orange-100 dark:border-gray-700 rounded-2xl shadow-lg dark:shadow-black/30 max-h-[200px] overflow-y-auto">
          {loading ? (
            <div className="flex items-center gap-2 py-3 px-4 text-xs text-gray-400 dark:text-gray-500">
              <Loader2 className="animate-spin w-3 h-3 shrink-0" />
              Loading options...
            </div>
          ) : filtered.length === 0 ? (
            <p className="text-xs text-gray-400 dark:text-gray-500 py-3 px-4 text-center">
              No results for &ldquo;{searchTerm}&rdquo;
            </p>
          ) : (
            filtered.map((option) => {
              const isSelected = selected.includes(option);
              return (
                <button
                  key={option}
                  type="button"
                  onClick={() => handleToggle(option)}
                  className={`w-full text-left px-4 py-2.5 text-sm font-bold flex items-center justify-between transition-colors ${
                    isSelected
                      ? 'bg-orange-50 dark:bg-orange-900/30 text-orange-700 dark:text-orange-300'
                      : 'text-gray-700 dark:text-gray-200 hover:bg-orange-50/50 dark:hover:bg-orange-900/20'
                  }`}
                >
                  <span className="truncate">{option}</span>
                  {isSelected && (
                    <span className="text-orange-500 dark:text-orange-400 shrink-0 ml-2 text-xs">✓</span>
                  )}
                </button>
              );
            })
          )}
        </div>
      )}
    </div>
  );
}
