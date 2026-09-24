/**
 * Tooltip.tsx — Themed tooltip built on @radix-ui/react-tooltip.
 *
 * Used to explain unlabelled metrics (Novelty %, Confidence, Ladder, ...) on hover/focus,
 * with real positioning and keyboard/focus handling instead of the browser's native `title`
 * attribute (no styling, slow to appear, invisible to keyboard-only users until hover).
 */

import type { ReactNode } from "react";
import * as TooltipPrimitive from "@radix-ui/react-tooltip";

export const TooltipProvider = TooltipPrimitive.Provider;

interface TooltipProps {
  content: ReactNode;
  children: ReactNode;
}

export function Tooltip({ content, children }: TooltipProps) {
  return (
    <TooltipPrimitive.Root delayDuration={200}>
      <TooltipPrimitive.Trigger asChild>{children}</TooltipPrimitive.Trigger>
      <TooltipPrimitive.Portal>
        <TooltipPrimitive.Content className="nk-tooltip-content" sideOffset={6}>
          {content}
          <TooltipPrimitive.Arrow className="nk-tooltip-arrow" />
        </TooltipPrimitive.Content>
      </TooltipPrimitive.Portal>
    </TooltipPrimitive.Root>
  );
}
