'use client';

interface JarvisSpinnerProps {
  size?: 'xs' | 'sm' | 'md';
  label?: string;
}

export default function JarvisSpinner({ size = 'sm', label }: JarvisSpinnerProps) {
  const sizes = {
    xs: 'w-3 h-3 border border-jarvis-green/50 border-t-transparent',
    sm: 'w-5 h-5 border border-jarvis-green/50 border-t-transparent',
    md: 'w-8 h-8 border-2 border-jarvis-green/30 border-t-jarvis-green',
  };

  return (
    <span className="flex items-center justify-center gap-2">
      <span className={`inline-block ${sizes[size]} rounded-full animate-spin`} />
      {label && (
        <span className="text-[10px] text-jarvis-muted tracking-widest uppercase">{label}</span>
      )}
    </span>
  );
}
