import {
  Bot,
  Bug,
  ClipboardCheck,
  FileSearch,
  FolderKanban,
  Frame,
  LayoutDashboard,
  ListChecks,
  PieChart,
  Settings,
  type LucideIcon,
} from "lucide-react";

export interface NavItem {
  href: string;
  label: string;
  icon: LucideIcon;
  /** Roadmap phase that delivers the module; undefined = available now. */
  phase?: number;
  summary?: string;
}

export const NAV_ITEMS: NavItem[] = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/projects", label: "Projects", icon: FolderKanban },
  {
    href: "/figma-analyzer",
    label: "Figma Analyzer",
    icon: Frame,
    phase: 3,
    summary: "Connect Figma or upload screenshots and get a structured screen and component analysis.",
  },
  {
    href: "/requirement-analysis",
    label: "Requirement Analysis",
    icon: FileSearch,
    phase: 2,
    summary: "Extract requirements, business rules and acceptance criteria from your documents with stable REQ IDs.",
  },
  {
    href: "/gap-analysis",
    label: "Gap Analysis",
    icon: ClipboardCheck,
    phase: 3,
    summary: "Find missing requirements, validations, states and conflicts, each backed by evidence.",
  },
  {
    href: "/test-case-generator",
    label: "Test Case Generator",
    icon: ListChecks,
    phase: 3,
    summary: "Generate “Verify that …” test cases traced to approved requirements and designs.",
  },
  {
    href: "/bug-report-generator",
    label: "Bug Report Generator",
    icon: Bug,
    phase: 3,
    summary: "Turn a bug title and evidence into a complete report, with unknown fields marked for confirmation.",
  },
  {
    href: "/automation",
    label: "Automation Center",
    icon: Bot,
    phase: 4,
    summary: "Generate, review and run Playwright scripts in an isolated sandbox.",
  },
  {
    href: "/reports",
    label: "QA Reports",
    icon: PieChart,
    phase: 5,
    summary: "Coverage, gap, bug and automation analytics computed from your stored project data.",
  },
  { href: "/settings", label: "Settings", icon: Settings },
];
