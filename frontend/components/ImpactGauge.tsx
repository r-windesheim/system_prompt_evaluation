interface ImpactGaugeProps {
  score: number;
}

export default function ImpactGauge({ score }: ImpactGaugeProps) {
  // Calculate ring progress (0-100 to 0-360 degrees)
  const rotation = (score / 100) * 360;

  return (
    <div className="inline-block">
      <div className="relative w-48 h-48 mx-auto">
        {/* Background ring */}
        <svg className="w-full h-full" viewBox="0 0 100 100">
          <circle
            cx="50"
            cy="50"
            r="40"
            fill="none"
            stroke="#e5e7eb"
            strokeWidth="8"
          />
          {/* Progress ring */}
          <circle
            cx="50"
            cy="50"
            r="40"
            fill="none"
            stroke="url(#gradient)"
            strokeWidth="8"
            strokeDasharray={`${2 * Math.PI * 40}`}
            strokeDashoffset={`${2 * Math.PI * 40 * (1 - score / 100)}`}
            strokeLinecap="round"
            transform="rotate(-90 50 50)"
            className="transition-all duration-1000 ease-out"
          />
          <defs>
            <linearGradient id="gradient" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor="#667eea" />
              <stop offset="100%" stopColor="#764ba2" />
            </linearGradient>
          </defs>
        </svg>

        {/* Score text */}
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <div className="text-5xl font-bold bg-gradient-primary bg-clip-text text-transparent">
            {score}
          </div>
          <div className="text-xs text-gray-600 uppercase tracking-wider mt-1">
            Impact
          </div>
        </div>
      </div>
    </div>
  );
}
