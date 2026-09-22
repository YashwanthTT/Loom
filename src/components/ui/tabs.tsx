import * as React from "react"
import { motion } from "motion/react"
import { cn } from "../../lib/cn"

export function Tabs({ value, onValueChange, children, className }: { value: string; onValueChange: (v:string)=>void; children: React.ReactNode; className?: string }) {
  return <div className={cn(className)} data-value={value} children={React.Children.map(children as any, (c:any)=> c?.type?.displayName==="TabsList" ? React.cloneElement(c, { value, onValueChange } as any) : c)} />
}
export function TabsList({ children, value, onValueChange, className }: any) {
  return <div className={cn("inline-flex items-center gap-1 rounded-[10px] border border-[var(--border)] bg-[var(--skim)] p-1", className)}>{React.Children.map(children, (c:any)=> React.cloneElement(c, { selected: c.props.value===value, onSelect: ()=> onValueChange(c.props.value) }))}</div>
}
TabsList.displayName="TabsList"
export function TabsTrigger({ children, selected, onSelect, value:_, ...p }: any) {
  return <button onClick={onSelect} className={cn("relative rounded-[8px] px-3 py-1 text-xs font-medium transition-colors", selected ? "text-[var(--text-h)]" : "text-[var(--text-muted)] hover:text-[var(--text)]")} {...p}>
    {selected && <motion.div layoutId="tab-indicator" className="absolute inset-0 bg-white border border-[var(--border)] rounded-[8px] shadow-sm" transition={{ type:"spring", stiffness:400, damping:30 }} />}
    <span className="relative">{children}</span>
  </button>
}
TabsTrigger.displayName="TabsTrigger"
