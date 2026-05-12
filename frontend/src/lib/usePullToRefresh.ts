import { useEffect, useRef, useState } from "react";
import { haptic } from "./telegram";

interface Opts {
  onRefresh: () => Promise<void> | void;
  threshold?: number; // px, при котором триггерим refresh (default 70)
}

/**
 * Хук pull-to-refresh для скролл-контейнера.
 *
 * Возвращает:
 *   - ref: повесить на скролл-контейнер
 *   - pull: текущее смещение в пикселях (для индикатора)
 *   - refreshing: идёт ли в данный момент обновление
 */
export function usePullToRefresh({ onRefresh, threshold = 70 }: Opts) {
  const ref = useRef<HTMLDivElement | null>(null);
  const startY = useRef<number | null>(null);
  const [pull, setPull] = useState(0);
  const [refreshing, setRefreshing] = useState(false);
  const triggered = useRef(false);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;

    function onTouchStart(e: TouchEvent) {
      if (refreshing) return;
      // Срабатывает только если мы на самом верху скролла.
      if (el!.scrollTop > 0) return;
      startY.current = e.touches[0]?.clientY ?? null;
      triggered.current = false;
    }

    function onTouchMove(e: TouchEvent) {
      if (refreshing || startY.current === null) return;
      if (el!.scrollTop > 0) {
        startY.current = null;
        setPull(0);
        return;
      }
      const dy = (e.touches[0]?.clientY ?? 0) - startY.current;
      if (dy > 0) {
        // Затухающее смещение, чтобы тянуло «упруго».
        const eased = Math.min(dy * 0.5, threshold * 1.5);
        setPull(eased);
        if (eased >= threshold && !triggered.current) {
          triggered.current = true;
          haptic("medium");
        }
      }
    }

    async function onTouchEnd() {
      if (refreshing) return;
      if (triggered.current) {
        setRefreshing(true);
        try {
          await onRefresh();
        } finally {
          setRefreshing(false);
          setPull(0);
          triggered.current = false;
        }
      } else {
        setPull(0);
      }
      startY.current = null;
    }

    el.addEventListener("touchstart", onTouchStart, { passive: true });
    el.addEventListener("touchmove", onTouchMove, { passive: true });
    el.addEventListener("touchend", onTouchEnd);
    el.addEventListener("touchcancel", onTouchEnd);

    return () => {
      el.removeEventListener("touchstart", onTouchStart);
      el.removeEventListener("touchmove", onTouchMove);
      el.removeEventListener("touchend", onTouchEnd);
      el.removeEventListener("touchcancel", onTouchEnd);
    };
  }, [onRefresh, refreshing, threshold]);

  return { ref, pull, refreshing };
}
