import { createRouter, createWebHistory } from 'vue-router'
const routes = [
  {
    path: '/',
    redirect: '/detect'
  },
  {
    path: '/detect',
    name: 'Detect',
    component: () => import('../views/DetectView.vue')
  },
  {
    path: '/camera-detect',
    name: 'CameraDetect',
    component: () => import('../views/CameraDetectView.vue')
  },
  {
    path: '/history',
    name: 'History',
    component: () => import('../views/HistoryView.vue')
  },
  {
    path: '/history/:id',
    name: 'HistoryDetail',
    component: () => import('../views/HistoryDetailView.vue'),
    props: true
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router
