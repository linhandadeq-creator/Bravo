"use client";

import type { PredictionProvider, Provider } from "@/lib/api";

export interface WorldClassScheme {
  key: string;
  topN: number;
  simulationFormat: string;
  referenceBuild: string;
}

export const WORLD_CLASS_SCHEME: WorldClassScheme = {
  key: "mainstream-mrna-tier1",
  topN: 10,
  simulationFormat: "mRNA-LNP",
  referenceBuild: "GRCh38",
};

export interface SchemeComponent {
  id: string;
  labelKey: string;
  valueKey: string;
}

export const SCHEME_COMPONENTS: SchemeComponent[] = [
  { id: "annotation", labelKey: "scheme.c.annotation", valueKey: "scheme.v.annotation" },
  { id: "prediction", labelKey: "scheme.c.prediction", valueKey: "scheme.v.prediction" },
  { id: "benchmark", labelKey: "scheme.c.benchmark", valueKey: "scheme.v.benchmark" },
  { id: "self-filter", labelKey: "scheme.c.selfFilter", valueKey: "scheme.v.selfFilter" },
  { id: "ranking", labelKey: "scheme.c.ranking", valueKey: "scheme.v.ranking" },
  { id: "design", labelKey: "scheme.c.design", valueKey: "scheme.v.design" },
  { id: "quality", labelKey: "scheme.c.quality", valueKey: "scheme.v.quality" },
];

export interface SchemeApplication {
  provider: string;
  annotationProvider: string;
  topN: number;
  simulationFormat: string;
  referenceBuild: string;
  providerReal: boolean;
  annotationReal: boolean;
}

/**
 * Resolve the tier-1 mainstream scheme against the providers that are
 * actually available on this installation. Real providers are preferred and
 * never silently substituted by mock — the flags report what was achieved.
 */
export function resolveWorldClassScheme(
  predictionProviders: PredictionProvider[],
  annotationProviders: Provider[]
): SchemeApplication {
  const available = (p: PredictionProvider) => !p.is_mock && p.status === "AVAILABLE";

  let provider = "panel";
  let providerReal = false;
  if (predictionProviders.some((p) => p.name === "panel" && available(p))) {
    providerReal = true;
  } else {
    const real = predictionProviders.find(available);
    if (real) {
      provider = real.name;
      providerReal = true;
    }
  }

  let annotationProvider = "offline";
  let annotationReal = false;
  const offline = annotationProviders.find((p) => p.name === "offline");
  const vep = annotationProviders.find((p) => p.name === "vep");
  if (offline?.available) {
    annotationReal = true;
  } else if (vep?.available) {
    annotationProvider = "vep";
    annotationReal = true;
  }

  return {
    provider,
    annotationProvider,
    topN: WORLD_CLASS_SCHEME.topN,
    simulationFormat: WORLD_CLASS_SCHEME.simulationFormat,
    referenceBuild: WORLD_CLASS_SCHEME.referenceBuild,
    providerReal,
    annotationReal,
  };
}
