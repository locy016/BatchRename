import { createRouter, createWebHashHistory } from 'vue-router'

const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    { path: '/', redirect: '/rename' },
    { path: '/rename', component: () => import('../views/RenameView.vue') },
    { path: '/history', component: () => import('../views/HistoryView.vue') },
    { path: '/undo', component: () => import('../views/UndoView.vue') },
    { path: '/help', component: () => import('../views/HelpView.vue') },
  ],
})

export default router
