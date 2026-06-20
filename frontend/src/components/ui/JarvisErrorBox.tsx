'use client';

interface JarvisErrorBoxProps {
  message: string;
  className?: string;
}

export default function JarvisErrorBox({ message, className = '' }: JarvisErrorBoxProps) {
  if (!message) return null;
  return (
    <div className={`p-2 bg-jarvis-red/10 border border-jarvis-red/30 rounded text-[10px] text-jarvis-red ${className}`}>
      {message}
    </div>
  );
}
