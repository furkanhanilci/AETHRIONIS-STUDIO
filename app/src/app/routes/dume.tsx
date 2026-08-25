import { createFileRoute } from "@tanstack/react-router";

import { DumeScreen } from "@/features/aethrionis/ui/DumeScreen";

type DumeRouteSearch = { wp?: string };

function validateDumeSearch(search: Record<string, unknown>): DumeRouteSearch {
  return {
    wp:
      typeof search.wp === "string" && search.wp.length > 0
        ? search.wp
        : undefined,
  };
}

export const Route = createFileRoute("/dume")({
  validateSearch: validateDumeSearch,
  component: DumeRouteComponent,
});

function DumeRouteComponent() {
  const { wp } = Route.useSearch();
  return <DumeScreen wpId={wp} />;
}
