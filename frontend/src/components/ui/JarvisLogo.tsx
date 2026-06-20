'use client';

interface JarvisLogoProps {
  size?: 'sm' | 'md' | 'lg';
  subtitle?: string;
}

export default function JarvisLogo({ size = 'sm', subtitle }: JarvisLogoProps) {
  const sizes = {
    sm: { icon: 'w-8 h-8 rounded-lg', iconText: 'text-sm', title: 'text-sm', sub: 'text-[10px]' },
    md: { icon: 'w-12 h-12 rounded-xl', iconText: 'text-lg', title: 'text-lg', sub: 'text-xs' },
    lg: { icon: 'w-16 h-16 rounded-2xl', iconText: 'text-2xl', title: 'text-2xl', sub: 'text-xs' },
  };
  const s = sizes[size];

  return (
    <div className="flex items-center gap-3">
      <div className={`${s.icon} bg-jarvis-green/10 border border-jarvis-green/30 flex items-center justify-center`}>
        <span className={`text-jarvis-green font-bold ${s.iconText} glow-green`}>J</span>
      </div>
      <div>
        <h1 className={`${s.title} font-bold tracking-wider text-jarvis-text`}>
          JARVIS<span className="text-jarvis-green">.</span>OS
        </h1>
        {subtitle !== undefined ? (
          <p className={`${s.sub} text-jarvis-muted tracking-widest uppercase`}>{subtitle}</p>
        ) : null}
      </div>
    </div>
  );
}
