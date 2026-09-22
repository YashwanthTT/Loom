import { motion } from "motion/react"
export function Marquee({ items }: { items: string[] }) {
  const dup = [...items, ...items]
  return (
    <div className="relative overflow-hidden rounded-[10px] border border-[var(--border)] bg-white py-2">
      <motion.div className="flex gap-2 whitespace-nowrap" animate={{ x: ["0%", "-50%"] }} transition={{ duration: 18, repeat: Infinity, ease:"linear" }}>
        {dup.map((t,i)=><span key={i} className="shrink-0 rounded-full border border-[var(--border)] bg-[var(--skim)] px-3 py-1 text-xs text-[var(--text)]">{t}</span>)}
      </motion.div>
      <div className="pointer-events-none absolute inset-y-0 left-0 w-12 bg-gradient-to-r from-white to-transparent" />
      <div className="pointer-events-none absolute inset-y-0 right-0 w-12 bg-gradient-to-l from-white to-transparent" />
    </div>
  )
}
