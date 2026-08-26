import { onMounted, onUnmounted } from 'vue'

export function useAnimations() {
  let observers = []

  const observeElements = (selector = '.reveal', options = {}) => {
    const defaultOptions = {
      threshold: 0.1,
      rootMargin: '0px 0px -50px 0px'
    }

    const observerOptions = { ...defaultOptions, ...options }

    const observer = new IntersectionObserver((entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          entry.target.classList.add('active')
        }
      })
    }, observerOptions)

    onMounted(() => {
      setTimeout(() => {
        document.querySelectorAll(selector).forEach(el => {
          observer.observe(el)
        })
      }, 100)
    })

    observers.push(observer)

    onUnmounted(() => {
      observer.disconnect()
    })

    return observer
  }

  const animateOnScroll = (element, animationClass = 'fade-in-up') => {
    if (!element) return

    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach(entry => {
          if (entry.isIntersecting) {
            entry.target.classList.add(animationClass)
            observer.unobserve(entry.target)
          }
        })
      },
      { threshold: 0.1 }
    )

    observer.observe(element)
    observers.push(observer)
  }

  onUnmounted(() => {
    observers.forEach(observer => observer.disconnect())
  })

  return {
    observeElements,
    animateOnScroll
  }
}