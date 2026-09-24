import { createRouter, createWebHistory } from 'vue-router'
import DetectView from '../views/DetectView.vue'
import CameraDetectView from '../views/CameraDetectView.vue'
import HistoryView from '../views/HistoryView.vue'
import HistoryDetailView from '../views/HistoryDetailView.vue'

const routes = [
  {
    path: '/',
    redirect: '/detect'
  },
  {
    path: '/detect',
    name: 'Detect',
    component: DetectView
  },
  {
    path: '/camera-detect',
    name: 'CameraDetect',
    component: CameraDetectView
  },
  {
    path: '/history',
    name: 'History',
    component: HistoryView
  },
  {
    path: '/history/:id',
    name: 'HistoryDetail',
    component: HistoryDetailView,
    props: true
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router