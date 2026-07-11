import { createRouter, createWebHistory } from 'vue-router';

import LibraryView from '@/views/LibraryView.vue';

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      name: 'library',
      component: LibraryView,
      meta: { title: 'Anchor 资料库' },
    },
    {
      path: '/items/:id',
      name: 'item-detail',
      component: () => import('@/views/ItemView.vue'),
      props: (route) => ({ id: route.params.id as string }),
      meta: { title: '条目详情 - Anchor 资料库' },
    },
  ],
});

router.beforeEach((to, from, next) => {
  if (to.meta?.title) {
    document.title = to.meta.title as string;
  }
  next();
});

export default router;
