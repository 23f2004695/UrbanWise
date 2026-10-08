<script setup>
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import {
  BarController, BarElement, CategoryScale, Chart, LinearScale, Tooltip,
} from 'chart.js'
import { categoryStyle, formatDay, formatHour } from '../lib/aqi'
import Icon3D from './Icon3D.vue'

Chart.register(BarController, BarElement, CategoryScale, LinearScale, Tooltip)

const props = defineProps({
  forecast: { type: Array, default: () => [] },
})

const canvas = ref(null)
let chart = null

function cssVar(name) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim()
}

function render() {
  if (!canvas.value || !props.forecast.length) return
  const muted = cssVar('--muted')
  const border = cssVar('--border')
  const data = {
    labels: props.forecast.map((f) => f.time),
    datasets: [{
      data: props.forecast.map((f) => f.aqi),
      backgroundColor: props.forecast.map((f) => categoryStyle(f.category).bg),
      borderRadius: 3,
      barPercentage: 0.9,
      categoryPercentage: 1,
    }],
  }
  const options = {
    responsive: true,
    maintainAspectRatio: false,
    animation: false,
    plugins: {
      legend: { display: false },
      tooltip: {
        callbacks: {
          title: ([item]) => `${formatDay(item.label)}, ${formatHour(item.label)}`,
          label: (item) => {
            const f = props.forecast[item.dataIndex]
            return [`AQI ${f.aqi} · ${f.category}`, `PM2.5 ${f.pm25} µg/m³`]
          },
        },
      },
    },
    scales: {
      x: {
        grid: { display: false },
        ticks: {
          color: muted,
          autoSkip: false,
          maxRotation: 0,
          // Mark midnight with the day name; label every 6 h (12 h on phones).
          callback(value) {
            const t = this.getLabelForValue(value)
            const hour = Number(t.slice(11, 13))
            if (hour === 0) return formatDay(t)
            const step = this.chart.width < 520 ? 12 : 6
            return hour % step === 0 ? formatHour(t) : ''
          },
        },
      },
      y: {
        beginAtZero: true,
        suggestedMax: 200,
        grid: { color: border },
        ticks: { color: muted },
        title: { display: true, text: 'AQI (CPCB)', color: muted },
      },
    },
  }
  if (chart) {
    chart.data = data
    chart.options = options
    chart.update()
  } else {
    chart = new Chart(canvas.value, { type: 'bar', data, options })
  }
}

onMounted(render)
watch(() => props.forecast, render)
onBeforeUnmount(() => chart?.destroy())
</script>

<template>
  <section class="card">
    <div class="card-head">
      <Icon3D name="chart_increasing" :size="44" :delay="0.4" />
      <div>
        <h2>Next 48 hours</h2>
        <p class="muted small">Hourly AQI from CAMS model forecasts of PM2.5 and PM10. Plan outdoor time around the lower bars.</p>
      </div>
    </div>
    <div class="chart">
      <canvas ref="canvas" role="img" aria-label="Bar chart of hourly AQI for the next 48 hours"></canvas>
    </div>
  </section>
</template>

<style scoped>
.chart {
  position: relative;
  height: 260px;
  margin-top: 12px;
}
</style>
