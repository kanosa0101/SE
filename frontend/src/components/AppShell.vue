<template>
  <div class="page-shell">
    <header class="topbar">
      <button class="mobile-menu" type="button" aria-label="Toggle navigation" @click="drawerOpen = !drawerOpen">☰</button>
      <RouterLink class="brand" to="/" aria-label="CVInsight Observatory home">
        <span class="brand-mark">CV</span>
        <span class="brand-copy"><strong>CVINSIGHT</strong><small>OBSERVATORY</small></span>
      </RouterLink>
      <div class="search-cluster">
        <label class="global-search">
          <span class="search-prefix">&gt;</span>
          <input v-model="searchText" aria-label="Search papers" placeholder="QUERY TITLE / AUTHOR / KEYWORD" @keyup.enter="search" />
          <span class="search-shortcut">⌘ K</span>
        </label>
        <ConferenceChips v-model="conference" />
      </div>
      <TelemetryBar :count="recordCount" @toggle-drawer="drawerOpen = !drawerOpen" @threshold="emitThreshold" />
    </header>

    <aside class="sidebar" :class="{ open: drawerOpen }">
      <div class="sidebar-label"><span>Navigation Matrix</span><span>⊢ 01</span></div>
      <nav class="nav-list" aria-label="Main navigation">
        <RouterLink v-for="item in navItems" :key="item.to" :to="item.to" class="nav-item">
          <span class="nav-glyph">{{ item.glyph }}</span><span class="nav-index">{{ item.index }}</span><span class="nav-label">{{ item.label }}</span>
        </RouterLink>
      </nav>
      <div class="sidebar-foot">
        <div class="foot-kicker">ENGINE BUILD / 05.24.26</div>
        <div class="foot-title">RESEARCH COORDINATES</div>
        <p>Local corpus · deterministic metrics<br />Signal integrity nominal</p>
        <div class="coordinates">31.2304° N / 121.4737° E</div>
      </div>
    </aside>

    <main class="main-content"><div class="content-wrap"><slot /></div></main>
  </div>
</template>

<script setup>
import { ref } from "vue"
import { RouterLink, useRouter } from "vue-router"

import ConferenceChips from "./ConferenceChips.vue"
import TelemetryBar from "./TelemetryBar.vue"

const router = useRouter()
const searchText = ref("")
const conference = ref("all")
const drawerOpen = ref(false)
const recordCount = 12486
const navItems = [
  { to: "/", label: "Overview / Signal", index: "01", glyph: "◈" },
  { to: "/trends", label: "Trend Observatory", index: "02", glyph: "⌁" },
  { to: "/papers", label: "Paper Registry", index: "03", glyph: "▤" },
  { to: "/import", label: "Ingest / Parse", index: "04", glyph: "⇩" },
  { to: "/about", label: "Methods / About", index: "05", glyph: "◎" },
]

function search() {
  const query = searchText.value.trim()
  if (query) router.push({ name: "papers", query: { q: query } })
}

function emitThreshold() {
  window.dispatchEvent(new CustomEvent("cvinsight:threshold"))
}
</script>

<style scoped>
.topbar { position: fixed; z-index: 10; top: 0; right: 0; left: 0; display: flex; align-items: center; gap: 26px; height: var(--topbar-height); padding: 0 24px; border-bottom: 1px solid var(--line); background: rgba(9, 14, 24, .92); backdrop-filter: blur(18px); }
.mobile-menu { display: none; border: 0; background: transparent; color: var(--cyan); font-size: 18px; }
.brand { display: flex; align-items: center; gap: 10px; min-width: 256px; }
.brand-mark { display: grid; width: 32px; height: 32px; place-items: center; border: 1px solid var(--cyan); border-radius: var(--radius-sm); color: var(--cyan); font: 600 10px var(--mono); box-shadow: inset 0 0 14px rgba(76, 215, 246, .12); }
.brand-copy { display: flex; align-items: baseline; gap: 8px; }
.brand-copy strong { color: var(--text); font: 600 14px var(--mono); letter-spacing: .12em; }
.brand-copy small { color: var(--cyan); font: 9px var(--mono); letter-spacing: .08em; }
.search-cluster { display: flex; align-items: center; flex: 1; gap: 12px; min-width: 0; }
.global-search { display: flex; align-items: center; flex: 1; max-width: 620px; height: 34px; border: 1px solid var(--outline-variant); border-radius: var(--radius-sm); background: var(--surface-container-low); }
.global-search:focus-within { border-color: var(--cyan); box-shadow: 0 0 0 2px rgba(76, 215, 246, .08); }
.search-prefix, .search-shortcut { padding: 0 10px; color: var(--cyan); font: 12px var(--mono); }
.search-shortcut { color: var(--text-dim); font-size: 9px; }
.global-search input { flex: 1; min-width: 0; border: 0; outline: 0; background: transparent; color: var(--text); font: 10px var(--mono); letter-spacing: .06em; }
.global-search input::placeholder { color: var(--text-dim); }
.sidebar { position: fixed; z-index: 5; top: var(--topbar-height); bottom: 0; left: 0; display: flex; width: var(--sidebar-width); flex-direction: column; padding: 26px 16px 18px; border-right: 1px solid var(--line); background: rgba(14, 19, 30, .95); }
.sidebar-label { display: flex; justify-content: space-between; padding: 0 10px 16px; color: var(--text-dim); font: 9px var(--mono); letter-spacing: .12em; text-transform: uppercase; }
.nav-list { display: grid; gap: 4px; }
.nav-item { display: grid; grid-template-columns: 20px 24px 1fr; align-items: center; gap: 8px; min-height: 44px; padding: 0 10px; border: 1px solid transparent; border-radius: var(--radius-sm); color: var(--text-soft); font-size: 12px; }
.nav-item:hover, .nav-item.router-link-exact-active { border-color: rgba(76, 215, 246, .2); background: var(--surface-container-high); color: var(--cyan); }
.nav-glyph { color: var(--amber); font-size: 14px; }
.nav-index { color: var(--text-dim); font: 10px var(--mono); }
.router-link-exact-active .nav-index { color: var(--cyan); }
.sidebar-foot { margin-top: auto; padding: 14px; border: 1px solid var(--outline-variant); border-radius: var(--radius-sm); background: var(--surface-container-low); }
.foot-kicker, .foot-title, .coordinates { color: var(--cyan); font: 9px var(--mono); letter-spacing: .1em; }
.foot-title { margin-top: 10px; color: var(--amber); }
.sidebar-foot p { margin: 9px 0 14px; color: var(--text-dim); font: 10px/1.7 var(--mono); }
.coordinates { color: var(--text-dim); font-size: 8px; }
@media (max-width: 1100px) { .brand { min-width: 210px; } .conference-chips { display: none; } }
@media (max-width: 900px) {
  .topbar { gap: 10px; padding: 0 14px; }
  .mobile-menu { display: block; }
  .brand { min-width: 0; }
  .brand-copy small { display: none; }
  .brand-copy strong { font-size: 11px; }
  .search-cluster { order: 3; }
  .global-search { max-width: none; }
  .sidebar { width: 58px; padding: 15px 8px; }
  .sidebar.open { width: 256px; box-shadow: 20px 0 40px rgba(0, 0, 0, .35); }
  .sidebar-label, .sidebar-foot, .nav-label { display: none; }
  .sidebar.open .sidebar-label, .sidebar.open .sidebar-foot, .sidebar.open .nav-label { display: flex; }
  .sidebar.open .sidebar-foot { display: block; }
  .nav-item { grid-template-columns: 1fr; justify-items: center; padding: 0; font-size: 0; }
  .sidebar.open .nav-item { grid-template-columns: 20px 24px 1fr; justify-items: stretch; padding: 0 10px; font-size: 12px; }
  .nav-index { display: none; }
  .sidebar.open .nav-index { display: block; }
  .main-content { margin-left: 58px; }
}
</style>
