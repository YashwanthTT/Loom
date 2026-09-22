import { cn } from "../../lib/cn"
export function Badge({ className, ...p }: React.HTMLAttributes<HTMLSpanElement>) {
  return <span className={cn("inline-flex items-center rounded-full border border-[var(--border)] bg-[var(--skim)] px-2 py-0.5 text-[11px] font-medium text-[var(--text)]", className)} {...p} />
}
