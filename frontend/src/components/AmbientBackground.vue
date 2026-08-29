<script setup lang="ts">
const particles = [
  { label: '🧬', x: 7, y: 14, delay: -2, emoji: true },
  { label: 'P1', x: 14, y: 38, delay: -6 },
  { label: '🔬', x: 20, y: 72, delay: -10, emoji: true },
  { label: 'Σ', x: 29, y: 20, delay: -4 },
  { label: '🧪', x: 35, y: 85, delay: -12, emoji: true },
  { label: 'GF(p)', x: 42, y: 52, delay: -1 },
  { label: '📊', x: 49, y: 10, delay: -8, emoji: true },
  { label: 'P2', x: 56, y: 76, delay: -9 },
  { label: '🧫', x: 63, y: 31, delay: -3, emoji: true },
  { label: 't = 1', x: 70, y: 60, delay: -7 },
  { label: '🧠', x: 77, y: 16, delay: -11, emoji: true },
  { label: 'P3', x: 84, y: 82, delay: -5 },
  { label: '🔐', x: 91, y: 43, delay: -13, emoji: true },
  { label: '∑', x: 10, y: 91, delay: -8 },
  { label: '🩺', x: 31, y: 57, delay: -14, emoji: true },
  { label: 'f(x)', x: 67, y: 93, delay: -4 },
  { label: '🧑‍🔬', x: 95, y: 10, delay: -6, emoji: true },
  { label: '01', x: 87, y: 69, delay: -1 }
]
</script>

<template>
  <div class="ambient-layer" aria-hidden="true">
    <span
      v-for="particle in particles"
      :key="particle.label + particle.x"
      class="data-particle"
      :class="{ 'data-particle-emoji': particle.emoji }"
      :style="{ left: particle.x + '%', top: particle.y + '%', animationDelay: particle.delay + 's' }"
    >{{ particle.label }}</span>
  </div>
</template>
