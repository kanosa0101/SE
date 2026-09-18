import { createRouter, createWebHistory } from "vue-router"

import AboutView from "./views/AboutView.vue"
import ImportView from "./views/ImportView.vue"
import OverviewView from "./views/OverviewView.vue"
import PapersView from "./views/PapersView.vue"
import TrendsView from "./views/TrendsView.vue"

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/", name: "overview", component: OverviewView },
    { path: "/trends", name: "trends", component: TrendsView },
    { path: "/papers", name: "papers", component: PapersView },
    { path: "/import", name: "import", component: ImportView },
    { path: "/about", name: "about", component: AboutView },
  ],
})

export default router
