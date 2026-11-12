import React from 'react';

export type DirectionFilter = 'increases' | 'decreases';

interface IntensitySliderProps {
  threshold: number;
  onThresholdChange: (threshold: number) => void;
  visibleCount: number;
  totalCount: number;
  direction: DirectionFilter;
  onDirectionChange: (direction: DirectionFilter) => void;
  increaseCount?: number;
  decreaseCount?: number;
}

export const IntensitySlider: React.FC<IntensitySliderProps> = ({
  threshold,
  onThresholdChange,
  visibleCount,
  totalCount,
  direction,
  onDirectionChange,
  increaseCount = 0,
  decreaseCount = 0,
}) => {
  const presets = [
    { label: 'All', value: 1.0 },
    { label: 'Moderate', value: 2.0 },
    { label: 'High', value: 3.5 },
    { label: 'Very High', value: 5.0 },
  ];

  const directionOptions: { label: string; value: DirectionFilter }[] = [
    { label: 'Increases', value: 'increases' },
    { label: 'Decreases', value: 'decreases' },
  ];

  return (
    <div className="bg-surface-elevated border border-border rounded-lg p-4 shadow-sm">
      <div className="flex items-center justify-between mb-3">
        <div>
          <h3 className="text-sm font-semibold text-text-primary">
            Impact Threshold
          </h3>
          <p className="text-xs text-text-secondary">
            Filter by significance and direction
          </p>
        </div>
        <div className="text-right">
          <div className="text-2xl font-bold text-primary">
            {threshold.toFixed(1)}×
          </div>
          <div className="text-xs text-text-secondary">
            {direction === 'increases'
              ? `${increaseCount} increases`
              : `${decreaseCount} decreases`
            }
          </div>
          <div className="text-xs text-text-secondary font-semibold">
            {visibleCount} of {totalCount} visible
          </div>
        </div>
      </div>

      {/* Direction Filter */}
      <div className="mb-3">
        <label className="text-xs font-medium text-text-secondary mb-2 block">
          Direction
        </label>
        <div className="flex gap-2">
          {directionOptions.map((option) => (
            <button
              key={option.value}
              onClick={() => onDirectionChange(option.value)}
              className={`flex-1 px-3 py-1.5 rounded text-xs font-medium transition-all ${
                direction === option.value
                  ? 'bg-primary text-white shadow-md'
                  : 'bg-surface border border-border text-text-secondary hover:bg-surface-elevated hover:border-primary'
              }`}
            >
              {option.label}
            </button>
          ))}
        </div>
      </div>

      {/* Slider */}
      <div className="mb-3">
        <input
          type="range"
          min="1.0"
          max="5.0"
          step="0.1"
          value={threshold}
          onChange={(e) => onThresholdChange(parseFloat(e.target.value))}
          className="w-full h-2 bg-border rounded-lg appearance-none cursor-pointer slider-thumb"
          style={{
            background: `linear-gradient(to right, #3b82f6 0%, #3b82f6 ${((threshold - 1) / 4) * 100}%, #e5e7eb ${((threshold - 1) / 4) * 100}%, #e5e7eb 100%)`
          }}
        />
      </div>

      {/* Preset Buttons */}
      <div className="flex gap-2">
        {presets.map((preset) => (
          <button
            key={preset.value}
            onClick={() => onThresholdChange(preset.value)}
            className={`flex-1 px-3 py-1.5 rounded text-xs font-medium transition-all ${
              Math.abs(threshold - preset.value) < 0.05
                ? 'bg-primary text-white shadow-md'
                : 'bg-surface border border-border text-text-secondary hover:bg-surface-elevated hover:border-primary'
            }`}
          >
            {preset.label}
          </button>
        ))}
      </div>

      <style jsx>{`
        .slider-thumb::-webkit-slider-thumb {
          appearance: none;
          width: 20px;
          height: 20px;
          border-radius: 50%;
          background: #3b82f6;
          cursor: pointer;
          box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
          transition: all 0.2s;
        }

        .slider-thumb::-webkit-slider-thumb:hover {
          transform: scale(1.2);
          box-shadow: 0 4px 8px rgba(0, 0, 0, 0.3);
        }

        .slider-thumb::-moz-range-thumb {
          width: 20px;
          height: 20px;
          border-radius: 50%;
          background: #3b82f6;
          cursor: pointer;
          border: none;
          box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
          transition: all 0.2s;
        }

        .slider-thumb::-moz-range-thumb:hover {
          transform: scale(1.2);
          box-shadow: 0 4px 8px rgba(0, 0, 0, 0.3);
        }
      `}</style>
    </div>
  );
};
