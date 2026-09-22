import { motion } from "motion/react"
import { cn } from "../../lib/cn"

const variants: Record<string,string> = {
  default: "bg-[var(--accent)] text-white border-transparent hover:opacity-[0.92] shadow-sm",
  secondary: "bg-white text-[var(--text-h)] border-[var(--border)] hover:bg-[var(--skim)]",
  ghost: "bg-transparent border-transparent hover:bg-[var(--skim)] text-[var(--text)]",
  outline: "bg-white border-[var(--border)] text-[var(--text-h)] hover:bg-[var(--skim)]",
}
const sizes: Record<string,string> = {
  sm: "h-7 px-2.5 text-xs rounded-[8px]",
  md: "h-8 px-3.5 text-[13px] rounded-[10px]",
  lg: "h-10 px-5 text-sm rounded-[12px]",
  icon: "h-8 w-8 p-0 rounded-[10px]",
}

export function Button({ variant="default", size="md", className, children, ...props }: any & { variant?: keyof typeof variants; size?: keyof typeof sizes }) {
  return (
    <motion.button
      whileTap={{ scale: 0.97 }}
      whileHover={{ y: variant==="ghost" ? 0 : -0.5 }}
      transition={{ type:"spring", stiffness:400, damping:25 }}
      className={cn("inline-flex items-center justify-center gap-1.5 font-medium border cursor-pointer disabled:opacity-50", variants[variant], sizes[size], className)}
      {...props}
    >{children}</motion.button>
  )
}
