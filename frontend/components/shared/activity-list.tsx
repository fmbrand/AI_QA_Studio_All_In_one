import type { Activity } from "@/lib/types";
import { formatDateTime, timeAgo } from "@/lib/utils";

export function ActivityList({ items, showProject }: { items: Activity[]; showProject?: (id: string) => string }) {
  return (
    <ol className="grid gap-3">
      {items.map((a) => (
        <li key={a.id} className="flex gap-3 text-sm">
          <span className="mt-1.5 size-2 shrink-0 rounded-full bg-primary/60" aria-hidden />
          <div className="min-w-0 flex-1">
            <p className="break-words">
              <span className="font-medium">{a.actor_name ?? "System"}</span> · {a.summary}
            </p>
            <p className="text-xs text-muted-foreground">
              <time dateTime={a.created_at} title={formatDateTime(a.created_at)}>
                {timeAgo(a.created_at)}
              </time>
              {showProject && a.project_id && <> · {showProject(a.project_id)}</>}
            </p>
          </div>
        </li>
      ))}
    </ol>
  );
}
