import { onMounted, onUnmounted, ref } from 'vue'

export function useStars() {
  const stars = ref([])
  const shootingStars = ref([])
  let animationId = null
  let lastStarTime = 0
  const STAR_INTERVAL = 3000 // New star every 3 seconds minimum

  // Detect device performance
  const isLowPerformance = () => {
    return navigator.hardwareConcurrency <= 4 || 
           /Android|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent)
  }

  // Generate static background stars (reduced for performance)
  const generateBackgroundStars = () => {
    const starCount = isLowPerformance() ? 100 : 150 // Reduced from 200
    const backgroundStars = []
    
    for (let i = 0; i < starCount; i++) {
      backgroundStars.push({
        id: `bg-star-${i}`,
        x: Math.random() * 100,
        y: Math.random() * 100,
        size: Math.random() * 3 + 1.5, // Увеличено от 2+1 на 3+1.5 (1.5-4.5px)
        opacity: Math.random() * 0.6 + 0.4, // Увеличено от 0.6+0.3 на 0.6+0.4 (по-ярки)
        twinkleDelay: Math.random() * 5,
        twinkleType: Math.floor(Math.random() * 3) + 1
      })
    }
    stars.value = backgroundStars
  }

  // Generate shooting star with 45-degree angle (/ direction)
  const createShootingStar = () => {
    // 45-degree diagonal movement (top-right to bottom-left) like "/"
    const startX = Math.random() * 60 + 40 // Start from 40% to 100% (right side)
    const startY = Math.random() * 30 // Start from top 30%
    
    // Calculate 45-degree movement in "/" direction
    const distance = 40 + Math.random() * 30 // 40-70% diagonal distance
    const endX = startX - distance // Move LEFT
    const endY = startY + distance // Move DOWN
    
    return {
      id: `shooting-star-${Date.now()}-${Math.random()}`,
      startX,
      startY,
      endX,
      endY,
      duration: 1.5 + Math.random() * 2, // Faster: 1.5-3.5 seconds
      delay: 0, // No delay for immediate start
      size: Math.random() * 2 + 1.5, // Увеличено от 1.2+0.8 на 2+1.5 (1.5-3.5px)
      opacity: 0.9,
      created: Date.now()
    }
  }

  // Optimized animation loop with throttling
  const animateShootingStars = () => {
    const now = Date.now()
    
    // Clean up old shooting stars (remove after 6 seconds instead of 10)
    shootingStars.value = shootingStars.value.filter(star => 
      now - star.created < 6000
    )

    // Limit maximum shooting stars for performance
    const maxStars = isLowPerformance() ? 3 : 5
    
    // Add new shooting star with timing control
    if (shootingStars.value.length < maxStars && 
        now - lastStarTime > STAR_INTERVAL &&
        Math.random() < 0.3) { // 30% chance when conditions are met
      shootingStars.value.push(createShootingStar())
      lastStarTime = now
    }

    animationId = requestAnimationFrame(animateShootingStars)
  }

  // Generate optimized twinkling effect
  const generateTwinkleKeyframes = () => {
    if (document.querySelector('#star-animations')) return // Already exists
    
    const style = document.createElement('style')
    style.id = 'star-animations'
    style.textContent = `
      @keyframes twinkle-1 {
        0%, 100% { opacity: 0.3; }
        50% { opacity: 0.8; }
      }
      @keyframes twinkle-2 {
        0%, 100% { opacity: 0.4; }
        30% { opacity: 0.2; }
        70% { opacity: 0.9; }
      }
      @keyframes twinkle-3 {
        0%, 100% { opacity: 0.35; }
        25% { opacity: 0.8; }
        75% { opacity: 0.5; }
      }
    `
    document.head.appendChild(style)
  }

  const startStarField = () => {
    generateBackgroundStars()
    generateTwinkleKeyframes()
    
    // Start with fewer initial shooting stars for performance
    const initialStars = isLowPerformance() ? 1 : 2
    for (let i = 0; i < initialStars; i++) {
      setTimeout(() => {
        shootingStars.value.push(createShootingStar())
      }, i * 1500)
    }
    
    animateShootingStars()
  }

  const stopStarField = () => {
    if (animationId) {
      cancelAnimationFrame(animationId)
      animationId = null
    }
    // Clean up styles
    const styleEl = document.querySelector('#star-animations')
    if (styleEl) {
      styleEl.remove()
    }
  }

  onMounted(() => {
    startStarField()
  })

  onUnmounted(() => {
    stopStarField()
  })

  return {
    stars,
    shootingStars,
    startStarField,
    stopStarField
  }
}