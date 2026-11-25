import Link from "next/link";

import { Button } from "@/components/ui/button";

import { PageHeader } from "./app-shell";
import { NAV_ITEMS } from "./nav";

/** An honest placeholder for a module that is on the roadmap but not built yet. No fake data. */
export function ComingSoon({ href }: { href: string }) {
  const item = NAV_ITEMS.find((n) => n.href === href);
  if (!item) return null;
  const Icon = item.icon;
  return (
    <>
      <PageHeader title={item.label} />
      <div className="flex flex-col items-center rounded-lg border border-dashed px-6 py-14 text-center">
        <Icon className="mb-3 size-8 text-muted-foreground" />
        <p className="font-medium">Arrives in Phase {item.phase}</p>
        <p className="mt-1 max-w-lg text-sm text-muted-foreground">{item.summary}</p>
        <p className="mt-3 max-w-lg text-sm text-muted-foreground">
          Prepare now by adding your project’s modules and uploading its requirements and business rules. This module
          will use them as context.
        </p>
        <Button asChild variant="outline" className="mt-5">
          <Link href="/projects">Go to projects</Link>
        </Button>
      </div>
    </>
  );
}
