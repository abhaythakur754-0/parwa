'use client';

export function MessageCounter({ used, limit, packType }: any) {
  const remaining = Math.max(0, limit - used);
  return (
    <div className="text-xs text-white/40 text-center">
      {remaining} messages remaining today
    </div>
  );
}
