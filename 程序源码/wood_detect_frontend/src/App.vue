<template>
  <div class="app-container">
    <!-- 背景遮罩层 -->
    <div class="bg-mask"></div>

    <el-container class="main-layout">
      <el-header class="header">
        <div class="title">木材缺陷检测系统</div>
        <el-menu
            mode="horizontal"
            :default-active="$route.path"
            router
            class="menu"
        >
          <el-menu-item index="/detect">在线识别</el-menu-item>
          <el-menu-item index="/camera-detect">摄像头识别</el-menu-item>
          <el-menu-item index="/history">历史记录</el-menu-item>
        </el-menu>
      </el-header>

      <el-main class="main-content">
        <router-view />
      </el-main>
    </el-container>
  </div>
</template>

<style scoped>
.app-container {
  position: relative;
  min-height: 100vh;
  overflow: hidden;
  background: url('./assets/school.JPG') no-repeat center center;
  background-size: cover;
}

/* 半透明遮罩，避免背景太花影响内容阅读 */
.bg-mask {
  position: absolute;
  inset: 0;
  background: rgba(255, 255, 255, 0.45);
  z-index: 0;
}

/* 主体内容层放在遮罩上面 */
.main-layout {
  position: relative;
  z-index: 1;
  min-height: 100vh;
}

.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: rgba(64, 158, 255, 0.88);
  color: white;
  padding: 0 24px;
  backdrop-filter: blur(4px);
}

.title {
  font-size: 20px;
  font-weight: bold;
}

.menu {
  background: transparent;
  border-bottom: none;
}

:deep(.el-card) {
  background: rgba(255, 255, 255, 0.88);
  border: none;
  border-radius: 12px;
}
/* 主体区域透明化一点，和背景更融合 */
.main-content {
  padding: 20px;
}
</style>