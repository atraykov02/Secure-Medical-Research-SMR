export function useCodeParticles() {
  const getCodeParticleStyle = (n) => {
    return {
      left: Math.random() * 100 + '%',
      top: Math.random() * 100 + '%',
      animationDelay: Math.random() * 10 + 's',
      animationDuration: (Math.random() * 15 + 10) + 's'
    }
  }

  const getCodeSymbol = (n) => {
    const symbols = [
      '{ }', '[ ]', '< >', '( )', '++', '--', '=>', '&&', 
      '||', '!=', 'if', 'for', 'void', 'int', '#include',
      'const', 'let', 'var', '===', '!==', 'function', 'return'
    ]
    return symbols[n % symbols.length]
  }

  const getEmbeddedSymbol = (n) => {
    const symbols = ['⚡', '🔧', '⚙️', '🔌', '📡', '🔋', '💻', '📱']
    return symbols[n % symbols.length]
  }

  return {
    getCodeParticleStyle,
    getCodeSymbol,
    getEmbeddedSymbol
  }
}