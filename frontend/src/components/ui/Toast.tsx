import { AnimatePresence, motion } from 'framer-motion'
import { useStore } from '../../store/useStore'

export function Toast() {
  const toast = useStore(s => s.toast)
  const clearToast = useStore(s => s.clearToast)

  return (
    <AnimatePresence>
      {toast && (
        <motion.div
          key={toast.id}
          initial={{ opacity: 0, y: 16, scale: .95 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          exit={{ opacity: 0, y: 8, scale: .95 }}
          transition={{ duration: .22 }}
          onClick={clearToast}
          className="fixed bottom-6 left-1/2 -translate-x-1/2 z-50 flex items-center gap-2.5 px-4 py-2.5 rounded-lg cursor-pointer select-none"
          style={{
            background: 'rgba(15,15,24,.95)',
            border: '1px solid rgba(255,255,255,.1)',
            backdropFilter: 'blur(12px)',
            boxShadow: '0 8px 32px rgba(0,0,0,.5)',
            maxWidth: '90vw',
          }}
        >
          <span className="w-2 h-2 rounded-full flex-shrink-0" style={{ background: toast.color }} />
          <span className="text-xs font-mono text-qa-text whitespace-nowrap">{toast.msg}</span>
        </motion.div>
      )}
    </AnimatePresence>
  )
}
