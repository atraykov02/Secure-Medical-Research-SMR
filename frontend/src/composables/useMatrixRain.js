import { onMounted, onUnmounted, ref } from 'vue'

export function useMatrixRain() {
  const matrixChars = ref([])
  let intervalId = null

  const createMatrixRain = () => {
    const chars = '01アイウエオカキクケコサシスセソタチツテトナニヌネノハヒフヘホマミムメモヤユヨラリルレロワヲン'
    const rainChars = []
    
    for (let i = 0; i < 50; i++) {
      rainChars.push({
        id: i,
        char: chars[Math.floor(Math.random() * chars.length)],
        style: {
          left: Math.random() * 100 + '%',
          animationDelay: Math.random() * 4 + 's',
          animationDuration: (Math.random() * 3 + 2) + 's'
        }
      })
    }
    
    matrixChars.value = rainChars
  }

  const startMatrixRain = () => {
    createMatrixRain()
    intervalId = setInterval(createMatrixRain, 8000)
  }

  const stopMatrixRain = () => {
    if (intervalId) {
      clearInterval(intervalId)
      intervalId = null
    }
  }

  onMounted(() => {
    startMatrixRain()
  })

  onUnmounted(() => {
    stopMatrixRain()
  })

  return {
    matrixChars,
    startMatrixRain,
    stopMatrixRain,
    createMatrixRain
  }
}