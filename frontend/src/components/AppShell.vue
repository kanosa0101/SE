<template>
  <div class="page-shell">
    <header class="topbar">
      <div class="brand">
        <div class="brand-mark">CV</div>
        <div>
          <div class="brand-name">CVINSIGHT <span>OBSERVATORY</span></div>
          <div class="brand-caption">顶会科研洞察 · CVPR / ICCV / ECCV</div>
        </div>
      </div>
      <div class="global-search">
        <span class="search-prefix">&gt;</span>
        <input v-model="searchText" placeholder="检索论文标题、作者或关键词" @keyup.enter="search" />
        <span class="search-shortcut">/</span>
      </div>
      <div class="top-status"><span class="status-dot" />数据接口在线</div>
    </header>

    <aside class="sidebar">
      <div class="sidebar-label">NAVIGATION MATRIX <span>⊢ 01</span></div>
      <nav class="nav-list" aria-label="主导航">
        <RouterLink v-for="item in navItems" :key="item.to" :to="item.to" class="nav-item">
          <span class="nav-index">{{ item.index }}</span>
          <span>{{ item.label }}</span>
        </RouterLink>
      </nav>
      <div class="sidebar-foot">
        <div class="foot-title">数据边界</div>
        <p>结果用于计算机视觉论文趋势探索，统计口径以平台说明为准。</p>
        <div class="coordinates">CVINSIGHT / LOCAL DATASET</div>
      </div>
    </aside>

    <main class="main-content">
      <div class="content-wrap"><slot /></div>
    </main>
  </div>
</template>

<script setup>
import { ref } from "vue"
import { RouterLink, useRouter } from "vue-router"

const router = useRouter()
const searchText = ref("")
const navItems = [
  { to: "/", label: "首页 / 热门方向", index: "01" },
  { to: "/trends", label: "热度趋势洞察", index: "02" },
  { to: "/papers", label: "论文学术管理", index: "03" },
  { to: "/import", label: "论文导入与解析", index: "04" },
  { to: "/about", label: "关于平台与口径", index: "05" },
]

function search() {
  if (searchText.value.trim()) {
    router.push({ name: "papers", query: { q: searchText.value.trim() } })
  }
}
</script>

<style scoped>
.topbar {
  position: fixed;
  z-index: 10;
  top: 0;
  right: 0;
  left: 0;
  display: flex;
  align-items: center;
  gap: 28px;
  height: 64px;
  padding: 0 24px;
  border-bottom: 1px solid var(--line);
  background: rgba(7, 12, 22, 0.94);
  backdrop-filter: blur(14px);
}

.brand {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 236px;
}

.brand-mark {
  display: grid;
  width: 32px;
  height: 32px;
  place-items: center;
  border: 1px solid var(--cyan);
  border-radius: 50%;
  color: var(--cyan);
  font: 600 11px var(--mono);
}

.brand-name {
  color: var(--cyan);
  font: 600 14px var(--mono);
  letter-spacing: 0.11em;
}

.brand-name span {
  margin-left: 5px;
  color: var(--text-soft);
  font-size: 9px;
}

.brand-caption {
  margin-top: 2px;
  color: var(--text-dim);
  font-size: 10px;
}

.global-search {
  display: flex;
  align-items: center;
  flex: 1;
  max-width: 560px;
  height: 36px;
  border: 1px solid var(--line);
  border-radius: var(--radius-sm);
  background: var(--ink-900);
}

.search-prefix,
.search-shortcut {
  padding: 0 10px;
  color: var(--cyan);
  font: 13px var(--mono);
}

.search-shortcut {
  color: var(--text-dim);
}

.global-search input {
  flex: 1;
  min-width: 0;
  border: 0;
  outline: 0;
  background: transparent;
  color: var(--text);
  font: 12px var(--mono);
}

.top-status {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-left: auto;
  color: var(--text-soft);
  font: 11px var(--mono);
}

.sidebar {
  position: fixed;
  z-index: 5;
  top: 64px;
  bottom: 0;
  left: 0;
  display: flex;
  width: 236px;
  flex-direction: column;
  padding: 22px 14px 18px;
  border-right: 1px solid var(--line);
  background: rgba(11, 18, 32, 0.96);
}

.sidebar-label {
  display: flex;
  justify-content: space-between;
  padding: 0 10px 14px;
  color: var(--text-dim);
  font: 10px var(--mono);
  letter-spacing: 0.1em;
}

.nav-list {
  display: grid;
  gap: 5px;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 11px;
  min-height: 42px;
  padding: 0 10px;
  border: 1px solid transparent;
  border-radius: var(--radius-sm);
  color: var(--text-soft);
  font-size: 13px;
}

.nav-item:hover,
.nav-item.router-link-exact-active {
  border-color: rgba(34, 211, 238, 0.25);
  background: rgba(34, 211, 238, 0.08);
  color: var(--cyan);
}

.nav-index {
  color: var(--text-dim);
  font: 11px var(--mono);
}

.router-link-exact-active .nav-index {
  color: var(--cyan);
}

.sidebar-foot {
  margin-top: auto;
  padding: 14px;
  border: 1px solid var(--line);
  border-radius: var(--radius-sm);
  background: rgba(7, 12, 22, 0.7);
}

.foot-title,
.coordinates {
  color: var(--cyan);
  font: 10px var(--mono);
  letter-spacing: 0.08em;
}

.sidebar-foot p {
  margin: 10px 0 14px;
  color: var(--text-dim);
  font-size: 11px;
}

.coordinates {
  color: var(--text-dim);
  font-size: 9px;
}

@media (max-width: 900px) {
  .topbar {
    padding: 0 14px;
  }

  .brand {
    min-width: auto;
  }

  .brand-caption,
  .top-status,
  .sidebar-label,
  .sidebar-foot {
    display: none;
  }

  .sidebar {
    top: 64px;
    width: 58px;
    padding: 15px 8px;
  }

  .nav-item {
    justify-content: center;
    padding: 0;
    font-size: 0;
  }

  .nav-index {
    font-size: 10px;
  }

  .main-content {
    margin-left: 58px;
  }
}
</style>
