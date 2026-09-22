import * as React from "react"
import { cn } from "../../lib/cn"
export const Input = React.forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement>>(({ className, ...p }, ref) =>
  <input ref={ref} className={cn("h-9 w-full rounded-[10px] border border-[var(--border)] bg-white px-3 text-[13px] placeholder:text-[var(--text-muted)] focus:outline-none focus:ring-2 focus:ring-[var(--accent)]/20 focus:border-[var(--accent)]/30", className)} {...p} />
)
Input.displayName = "Input"
