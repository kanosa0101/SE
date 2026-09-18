import { createRouter, createWebHistory } from "vue-router"

import AboutView from "./views/AboutView.vue"
import ImportView from "./views/ImportView.vue"
import OverviewView from "./views/OverviewView.vue"
import PapersView from "./views/PapersView.vue"
import TrendsView from "./views/TrendsView.vue"

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/", name: "overview", component: OverviewView, meta: { index: "01" } },
    { path: "/trends", name: "trends", component: TrendsView, meta: { index: "02" } },
    { path: "/papers", name: "papers", component: PapersView, meta: { index: "03" } },
    { path: "/import", name: "import", component: ImportView, meta: { index: "04" } },
    { path: "/about", name: "about", component: AboutView, meta: { index: "05" } },
  ],
})

export default router
