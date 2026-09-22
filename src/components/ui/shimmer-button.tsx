// MagicUI-inspired ShimmerButton + BorderBeam + Spotlight - ponytail: pure CSS + motion, no extra deps
import { motion } from "motion/react"
import { cn } from "../../lib/cn"

export function ShimmerButton({ children, className, ...p }: any) {
  return (
    <motion.button whileTap={{ scale:0.98 }} className={cn("relative inline-flex h-9 items-center justify-center overflow-hidden rounded-[12px] bg-[var(--accent)] px-5 text-sm font-medium text-white border border-[var(--accent)]", className)} {...p}>
      <span className="absolute inset-0 overflow-hidden rounded-[12px]">
        <span className="absolute inset-0 -translate-x-full animate-[shimmer_2s_infinite] bg-gradient-to-r from-transparent via-white/15 to-transparent" />
      </span>
      <span className="relative">{children}</span>
    </motion.button>
  )
}

export function BorderBeam({ className }: { className?: string }) {
  return <div className={cn("pointer-events-none absolute inset-0 rounded-[12px] border border-transparent", className)} style={{ background: "linear-gradient(90deg,transparent,rgba(255,255,255,0.4),transparent) border-box", mask:"linear-gradient(#fff 0 0) padding-box,linear-gradient(#fff 0 0)", WebkitMaskComposite:"xor" as any }} />
}

export function Spotlight({ className }: { className?: string }) {
  return <div className={cn("pointer-events-none absolute -top-24 left-1/2 h-[320px] w-[600px] -translate-x-1/2 rounded-full opacity-20 blur-[60px]", className)} style={{ background:"radial-gradient(ellipse at center, #c7b8ff 0%, transparent 70%)" }} />
}
