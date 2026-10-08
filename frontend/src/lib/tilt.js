// v-tilt: tilts an element in 3D towards the mouse pointer.
// Off for touch screens and for people who prefer reduced motion.
const MAX_DEG = 8

function enabled() {
  return typeof window !== 'undefined'
    && window.matchMedia('(hover: hover) and (pointer: fine)').matches
    && !window.matchMedia('(prefers-reduced-motion: reduce)').matches
}

export const tilt = {
  mounted(el, binding) {
    if (!enabled()) return
    const max = binding.value ?? MAX_DEG
    let frame = 0

    const move = (e) => {
      cancelAnimationFrame(frame)
      frame = requestAnimationFrame(() => {
        const r = el.getBoundingClientRect()
        const x = (e.clientX - r.left) / r.width - 0.5
        const y = (e.clientY - r.top) / r.height - 0.5
        el.style.transform = `perspective(800px) rotateY(${x * max}deg) rotateX(${-y * max}deg)`
      })
    }
    const leave = () => {
      cancelAnimationFrame(frame)
      el.style.transform = ''
    }

    el.style.transition = 'transform 0.25s ease-out'
    el.style.transformStyle = 'preserve-3d'
    el.addEventListener('pointermove', move)
    el.addEventListener('pointerleave', leave)
    el._tiltCleanup = () => {
      el.removeEventListener('pointermove', move)
      el.removeEventListener('pointerleave', leave)
    }
  },
  unmounted(el) {
    el._tiltCleanup?.()
  },
}
