"use client";

import { History } from "lucide-react";

import { useCurrentProject } from "@/components/project/project-context";
import { ActivityList } from "@/components/shared/activity-list";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { EmptyState, ErrorState, LoadingRows } from "@/components/ui/states";
import { useActivity } from "@/lib/queries";

export default function ActivityPage() {
  const { project } = useCurrentProject();
  const activity = useActivity(project.id);
  const items = activity.data?.pages.flatMap((p) => p.data) ?? [];

  if (activity.isPending) return <LoadingRows rows={6} />;
  if (activity.isError) return <ErrorState error={activity.error} onRetry={() => activity.refetch()} />;
  if (items.length === 0) return <EmptyState icon={History} title="No activity yet" />;

  return (
    <Card>
      <CardContent className="p-5">
        <ActivityList items={items} />
        {activity.hasNextPage && (
          <Button
            variant="outline"
            className="mt-6"
            loading={activity.isFetchingNextPage}
            onClick={() => activity.fetchNextPage()}
          >
            Load older activity
          </Button>
        )}
      </CardContent>
    </Card>
  );
}
