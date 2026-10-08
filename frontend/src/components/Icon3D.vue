<script setup>
// A Fluent Emoji 3D illustration (MIT, see public/3d/LICENSE.txt) that floats gently.
defineProps({
  name: { type: String, required: true },
  size: { type: Number, default: 44 },
  float: { type: Boolean, default: true },
  delay: { type: Number, default: 0 }, // seconds, to desynchronise neighbours
})
</script>

<template>
  <img
    :src="`/3d/${name}.png`"
    :width="size"
    :height="size"
    alt=""
    aria-hidden="true"
    draggable="false"
    class="icon3d"
    :class="{ float }"
    :style="{ animationDelay: `${-delay}s` }"
  />
</template>

<style scoped>
.icon3d {
  flex: none;
  object-fit: contain;
  user-select: none;
  filter: drop-shadow(0 6px 8px rgba(16, 24, 40, 0.18));
}

.float { animation: bob 5s ease-in-out infinite; }

@keyframes bob {
  0%, 100% { transform: translateY(0) rotate(-2deg); }
  50% { transform: translateY(-5px) rotate(2deg); }
}

@media (prefers-reduced-motion: reduce) {
  .float { animation: none; }
}
</style>
