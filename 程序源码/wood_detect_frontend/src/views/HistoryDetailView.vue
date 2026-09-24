<template>
  <div class="page-container">
    <el-card v-if="detailData">
      <template #header>
        <span>历史详情</span>
      </template>

      <div class="summary">
        <p><strong>记录ID：</strong>{{ detailData.recordId }}</p>
        <p><strong>图片名称：</strong>{{ detailData.imageName }}</p>
        <p><strong>状态：</strong>{{ detailData.status }}</p>
        <p><strong>检测总数：</strong>{{ detailData.totalCount }}</p>
        <p><strong>创建时间：</strong>{{ detailData.createTime }}</p>
      </div>
    </el-card>

    <el-row :gutter="20" style="margin-top: 20px;" v-if="detailData">
      <el-col :span="12">
        <el-card>
          <template #header>
            <span>原图</span>
          </template>
          <img :src="fullImageUrl(detailData.imageUrl)" class="preview-image" />
        </el-card>
      </el-col>

      <el-col :span="12">
        <el-card>
          <template #header>
            <span>结果图</span>
          </template>
          <img :src="fullImageUrl(detailData.resultImageUrl)" class="preview-image" />
        </el-card>
      </el-col>
    </el-row>

    <el-card style="margin-top: 20px;" v-if="detailData">
      <template #header>
        <span>缺陷明细</span>
      </template>

      <el-table :data="detailData.details || []" border style="width: 100%;">
        <el-table-column prop="className" label="缺陷类别" />
        <el-table-column prop="confidence" label="置信度" />
        <el-table-column prop="x1" label="x1" />
        <el-table-column prop="y1" label="y1" />
        <el-table-column prop="x2" label="x2" />
        <el-table-column prop="y2" label="y2" />
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { getDetail } from '../api/detect'
import { ElMessage } from 'element-plus'

const route = useRoute()
const detailData = ref(null)

async function loadDetail() {
  try {
    const id = route.params.id
    const res = await getDetail(id)
    detailData.value = res.data.data
  } catch (error) {
    ElMessage.error(error?.response?.data?.message || '加载详情失败')
  }
}

function fullImageUrl(url) {
  if (!url) return ''
  return new URL(url, window.location.origin).toString()
}

onMounted(() => {
  loadDetail()
})
</script>

<style scoped>
.page-container {
  padding: 20px;
}

.preview-image {
  width: 100%;
  max-height: 500px;
  object-fit: contain;
  border: 1px solid #ddd;
}

.summary p {
  margin: 6px 0;
}

:deep(.el-card) {
  background: rgba(255, 255, 255, 0.88);
  border: none;
  border-radius: 12px;
}

</style>
