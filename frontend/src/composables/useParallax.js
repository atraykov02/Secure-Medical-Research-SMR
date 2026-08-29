import { onUnmounted } from 'vue'

export function useParallax() {
  let rafId = null

  const initParallax = () => {
    const handleScroll = () => {
      if (rafId) {
        cancelAnimationFrame(rafId)
      }

      rafId = requestAnimationFrame(() => {
        const scrolled = window.pageYOffset
        const parallaxElements = document.querySelectorAll('.glow-orb')
        
        parallaxElements.forEach((el, index) => {
          const speed = 0.5 + (index * 0.1)
          el.style.transform = `translateY(${scrolled * speed}px)`
        })
      })
    }

    window.addEventListener('scroll', handleScroll, { passive: true })
    
    return () => {
      window.removeEventListener('scroll', handleScroll)
      if (rafId) {
        cancelAnimationFrame(rafId)
      }
    }
  }

  const initMouseParallax = () => {
    const handleMouseMove = (e) => {
      const mouseX = e.clientX / window.innerWidth
      const mouseY = e.clientY / window.innerHeight
      
      const orbs = document.querySelectorAll('.glow-orb')
      orbs.forEach((orb, index) => {
        const speed = (index + 1) * 0.02
        const x = (mouseX - 0.5) * speed * 100
        const y = (mouseY - 0.5) * speed * 100
        
        // Preserve existing transform and add mouse effect
        const baseTransform = orb.style.transform || ''
        orb.style.transform = baseTransform + ` translate(${x}px, ${y}px)`
      })
    }

    document.addEventListener('mousemove', handleMouseMove, { passive: true })
    
    return () => {
      document.removeEventListener('mousemove', handleMouseMove)
    }
  }

  onUnmounted(() => {
    if (rafId) {
      cancelAnimationFrame(rafId)
    }
  })

  return {
    initParallax,
    initMouseParallax
  }
}