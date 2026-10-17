import {
  Activity,
  Database,
  Dna,
  FileText,
  Fingerprint,
  FlaskConical,
  LayoutDashboard,
  Microscope,
  Settings,
  ShieldCheck,
  SlidersHorizontal,
  Sparkles,
  type LucideIcon,
} from "lucide-react";

export type NavItem = { key: string; href: string; icon: LucideIcon };

export const NAV_ITEMS: NavItem[] = [
  { key: "nav.dashboard", href: "/", icon: LayoutDashboard },
  { key: "nav.generate", href: "/generate", icon: Sparkles },
  { key: "nav.projects", href: "/projects", icon: FlaskConical },
  { key: "nav.variants", href: "/variants", icon: Dna },
  { key: "nav.hla", href: "/hla", icon: Fingerprint },
  { key: "nav.expression", href: "/expression", icon: Activity },
  { key: "nav.neoantigens", href: "/neoantigens", icon: Microscope },
  { key: "nav.simulation", href: "/simulation", icon: SlidersHorizontal },
  { key: "nav.validation", href: "/validation", icon: ShieldCheck },
  { key: "nav.reports", href: "/reports", icon: FileText },
  { key: "nav.database", href: "/database", icon: Database },
  { key: "nav.settings", href: "/settings", icon: Settings },
];

const QUICK_KEYS = new Set([
  "nav.dashboard",
  "nav.generate",
  "nav.neoantigens",
  "nav.validation",
  "nav.settings",
]);

export const QUICK_NAV: NavItem[] = NAV_ITEMS.filter((item) =>
  QUICK_KEYS.has(item.key)
);

export function isActive(pathname: string, href: string): boolean {
  return href === "/" ? pathname === "/" : pathname.startsWith(href);
}
