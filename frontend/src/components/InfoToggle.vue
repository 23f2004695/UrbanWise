<script setup>
// Collapsed "How this works" details, so cards show the answer first and the
// method/source notes only on request. Native <details> = keyboard and
// screen-reader friendly with no extra code.
defineProps({
  label: { type: String, default: 'How this works' },
})
</script>

<template>
  <details class="info">
    <summary><span class="i" aria-hidden="true">i</span>{{ label }}</summary>
    <div class="body small muted"><slot /></div>
  </details>
</template>

<style scoped>
.info { margin-top: 10px; }

summary {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: var(--muted);
  font-size: 0.85rem;
  font-weight: 600;
  cursor: pointer;
  list-style: none;
}

summary::-webkit-details-marker { display: none; }

summary:hover { color: var(--brand); }

.i {
  display: grid;
  place-items: center;
  width: 16px;
  height: 16px;
  border: 1.5px solid currentColor;
  border-radius: 50%;
  font-size: 0.7rem;
  font-style: italic;
  font-weight: 800;
}

.body { margin-top: 6px; line-height: 1.5; }

.body :deep(p) { margin: 0 0 6px; }
</style>
