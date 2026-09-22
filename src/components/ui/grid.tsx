import { motion } from "motion/react"
import { cn } from "../../lib/cn"

// Aceternity-style BentoGrid
export function BentoGrid({ children, className }: { children: React.ReactNode; className?: string }) {
  return <div className={cn("grid grid-cols-1 md:grid-cols-3 gap-3 auto-rows-[minmax(140px,auto)]", className)}>{children}</div>
}
export function BentoCard({ title, desc, icon, className, span, delay=0 }: { title:string; desc:string; icon?:string; className?:string; span?:string; delay?:number }) {
  return (
    <motion.div initial={{ opacity:0, y:12 }} animate={{ opacity:1, y:0 }} transition={{ duration:0.4, delay }} whileHover={{ y:-2 }}
      className={cn("group relative overflow-hidden rounded-[14px] border border-[var(--border)] bg-white p-4 flex flex-col gap-2 shadow-[var(--shadow)]", span, className)}>
      <div className="absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity bg-gradient-to-br from-violet-500/[0.06] via-transparent to-transparent" />
      {icon && <div className="h-8 w-8 rounded-[10px] bg-[var(--skim)] border border-[var(--border)] grid place-items-center text-sm">{icon}</div>}
      <div className="text-[13px] font-semibold text-[var(--text-h)]">{title}</div>
      <div className="text-xs text-[var(--text-muted)] leading-relaxed">{desc}</div>
      <div className="mt-auto flex items-center gap-1 text-xs text-[var(--text-muted)]">explore →</div>
    </motion.div>
  )
}

// Dot pattern - MagicUI
export function DotPattern() {
  return <div className="absolute inset-0 -z-10 opacity-[0.35]" style={{ backgroundImage:"radial-gradient(circle at 1px 1px, #d6d3d1 1px, transparent 0)", backgroundSize:"20px 20px" }} />
}
