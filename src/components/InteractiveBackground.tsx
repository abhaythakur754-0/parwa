'use client';

/**
 * SHOBH Interactive Background
 *
 * Modern graphic layer living behind all content:
 *  - Soft silver/grey aurora blobs that drift continuously — each blob runs
 *    on its own duration + scale path, so the composition is never the same
 *    twice ("changes every time we see").
 *  - Mouse parallax — blobs follow the cursor with different depth factors,
 *    smoothly interpolated (lerp) for a living, physical feel.
 *
 * Sits at -z-10 with pointer-events-none so it never blocks interaction.
 * Honours prefers-reduced-motion (blobs freeze, no JS loop).
 */

import { useEffect, useRef } from 'react';

type BlobDef = {
  /** Parallax strength in px when cursor is at a screen edge */
  depth: number;
  /** Position + size (wrapper, driven by JS parallax) */
  pos: string;
  /** Gradient + autonomous drift animation (inner, CSS keyframes) */
  look: string;
};

const BLOBS: BlobDef[] = [
  {
    depth: 70,
    pos: 'left-[-14%] top-[-20%] h-[58vmax] w-[58vmax]',
    look: 'bg-[radial-gradient(circle_at_center,rgba(161,161,170,0.32),transparent_65%)] animate-[shobh-drift-a_23s_ease-in-out_infinite_alternate]',
  },
  {
    depth: 95,
    pos: 'right-[-16%] bottom-[-22%] h-[62vmax] w-[62vmax]',
    look: 'bg-[radial-gradient(circle_at_center,rgba(139,139,147,0.34),transparent_65%)] animate-[shobh-drift-b_29s_ease-in-out_infinite_alternate]',
  },
  {
    depth: 45,
    pos: 'right-[6%] top-[-12%] h-[38vmax] w-[38vmax]',
    look: 'bg-[radial-gradient(circle_at_center,rgba(212,212,216,0.20),transparent_65%)] animate-[shobh-drift-c_19s_ease-in-out_infinite_alternate]',
  },
  {
    depth: 60,
    pos: 'left-[10%] bottom-[-20%] h-[48vmax] w-[48vmax]',
    look: 'bg-[radial-gradient(circle_at_center,rgba(82,82,91,0.55),transparent_65%)] animate-[shobh-drift-d_33s_ease-in-out_infinite_alternate]',
  },
];

export default function InteractiveBackground() {
  const layersRef = useRef<Array<HTMLDivElement | null>>([]);

  useEffect(() => {
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;

    let raf = 0;
    let targetX = 0;
    let targetY = 0;
    let curX = 0;
    let curY = 0;

    const onMove = (e: MouseEvent) => {
      targetX = (e.clientX / window.innerWidth - 0.5) * 2; // -1..1
      targetY = (e.clientY / window.innerHeight - 0.5) * 2;
    };

    const tick = () => {
      curX += (targetX - curX) * 0.045;
      curY += (targetY - curY) * 0.045;
      for (const el of layersRef.current) {
        if (!el) continue;
        const depth = Number(el.dataset.depth ?? 60);
        el.style.transform = `translate3d(${(curX * depth).toFixed(2)}px, ${(curY * depth).toFixed(2)}px, 0)`;
      }
      raf = requestAnimationFrame(tick);
    };

    window.addEventListener('mousemove', onMove, { passive: true });
    raf = requestAnimationFrame(tick);

    return () => {
      window.removeEventListener('mousemove', onMove);
      cancelAnimationFrame(raf);
    };
  }, []);

  return (
    <div
      aria-hidden="true"
      className="pointer-events-none fixed inset-0 -z-10 overflow-hidden"
    >
      {BLOBS.map((b, i) => (
        <div
          key={i}
          data-depth={b.depth}
          ref={(el) => {
            layersRef.current[i] = el;
          }}
          className={`absolute will-change-transform ${b.pos}`}
        >
          <div className={`h-full w-full rounded-full blur-[80px] ${b.look}`} />
        </div>
      ))}
    </div>
  );
}
