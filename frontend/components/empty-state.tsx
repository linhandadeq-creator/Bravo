export function EmptyState({
  title,
  description,
}: {
  title: string;
  description?: string;
}) {
  return (
    <div className="rounded-lg border border-dashed border-border px-6 py-12 text-center">
      <div className="text-sm font-medium">{title}</div>
      {description ? (
        <div className="mt-1 text-sm text-muted-foreground">{description}</div>
      ) : null}
    </div>
  );
}
