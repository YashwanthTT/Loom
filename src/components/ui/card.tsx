import * as React from "react"
import { motion } from "motion/react"
import { cn } from "../../lib/cn"

export function Card({ className, ...p }: any) {
  return <motion.div initial={{ opacity:0, y:6 }} animate={{ opacity:1, y:0 }} transition={{ duration:0.35, ease:[0.25,0.1,0.25,1] }} className={cn("bg-white border border-[var(--border)] rounded-[12px] shadow-[var(--shadow)]", className)} {...p} />
}
export function CardHeader({ className, ...p }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("p-4 pb-3 flex flex-col gap-1", className)} {...p} />
}
export function CardTitle({ className, ...p }: React.HTMLAttributes<HTMLHeadingElement>) {
  return <h3 className={cn("text-[13px] font-semibold text-[var(--text-h)] tracking-[-0.01em]", className)} {...p} />
}
export function CardDesc({ className, ...p }: React.HTMLAttributes<HTMLParagraphElement>) {
  return <p className={cn("text-xs text-[var(--text-muted)] leading-relaxed", className)} {...p} />
}
export function CardContent({ className, ...p }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("p-4 pt-0", className)} {...p} />
}
