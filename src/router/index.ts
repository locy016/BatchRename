import { createRouter, createWebHashHistory } from 'vue-router'

const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    { path: '/', redirect: '/rename' },
    { path: '/rename', component: () => import('../views/RenameView.vue') },
    { path: '/history', component: () => import('../views/HistoryView.vue') },
    { path: '/help', redirect: '/help/guide' },
    { path: '/help/guide', component: () => import('../views/UsageGuideView.vue') },
    { path: '/help/about', component: () => import('../views/AboutView.vue') },
  ],
})

export default router
