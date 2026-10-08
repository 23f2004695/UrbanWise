import { createRouter, createWebHistory } from 'vue-router'

export const SECTIONS = [
  { id: 'overview', label: 'Overview', icon: 'face_with_medical_mask' },
  { id: 'smoke', label: 'Smoke Trail', short: 'Smoke', icon: 'fire' },
  { id: 'school', label: 'School', icon: 'school' },
  { id: 'health', label: 'Health', icon: 'lungs' },
  { id: 'ask', label: 'Ask', icon: 'speech_balloon' },
]

const routes = [
  { path: '/', name: 'landing', component: () => import('./pages/LandingPage.vue') },
  {
    path: '/dashboard/:section?',
    name: 'dashboard',
    component: () => import('./pages/DashboardPage.vue'),
    beforeEnter: (to) => {
      const ok = SECTIONS.some((s) => s.id === to.params.section)
      if (to.params.section && !ok) return { ...to, params: { section: '' } }
      return true
    },
  },
  { path: '/:pathMatch(.*)*', redirect: '/' },
]

export default createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior: (to, from, saved) => saved || (to.hash ? { el: to.hash, behavior: 'smooth' } : { top: 0 }),
})
