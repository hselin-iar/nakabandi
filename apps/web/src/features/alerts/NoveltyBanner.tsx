/**
 * NoveltyBanner.tsx — Novelty & exploration banner for exploratory alerts.
 * DOC 3 Web App Shell: features/alerts — NoveltyBanner (B4/S4)
 */

import React from "react";
import { Icon } from "../../shared/ui/Icon";

interface NoveltyBannerProps {
  isProbe?: boolean;
  noveltyScore?: number;
  patternName?: string;
}

export function NoveltyBanner({
  isProbe = false,
  noveltyScore,
  patternName,
}: NoveltyBannerProps) {
  if (!isProbe && !noveltyScore) return null;

  return (
    <div className="nk-novelty-banner" role="status" aria-label="Novelty probe alert">
      <div className="nk-novelty-banner__icon" aria-hidden="true">
        <Icon name="flask" size={16} />
      </div>
      <div className="nk-novelty-banner__content">
        <div className="nk-novelty-banner__title">
          Exploration Probe Pattern
          {noveltyScore !== undefined && (
            <span className="nk-novelty-score">
              (Novelty {(noveltyScore * 100).toFixed(0)}%)
            </span>
          )}
        </div>
        <div className="nk-novelty-banner__desc">
          {patternName ??
            "Seeded exploration alert under controlled evaluation budget. Verify destination location activity."}
        </div>
      </div>
    </div>
  );
}
