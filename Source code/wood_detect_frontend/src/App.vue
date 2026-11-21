<template>
  <div class="app-shell">
    <a class="skip-link" href="#main-content">跳到主要内容</a>
    <header class="app-header">
      <router-link class="brand" to="/detect" aria-label="木材缺陷检测系统首页">
        <span class="brand-mark" aria-hidden="true">木</span>
        <span><strong>木材缺陷检测</strong><small>Wood Inspect</small></span>
      </router-link>

      <nav class="primary-nav" aria-label="主要导航">
        <router-link to="/detect">在线识别</router-link>
        <router-link to="/camera-detect">摄像头</router-link>
        <router-link to="/history">历史记录</router-link>
      </nav>
    </header>

    <main id="main-content" class="app-main" tabindex="-1">
      <router-view v-slot="{ Component }">
        <Suspense>
          <component :is="Component" />
          <template #fallback>
            <div class="route-loading" role="status">正在加载页面…</div>
          </template>
        </Suspense>
      </router-view>
    </main>

    <footer class="app-footer">检测结果用于项目辅助评价，请结合人工复核。</footer>
  </div>
</template>
