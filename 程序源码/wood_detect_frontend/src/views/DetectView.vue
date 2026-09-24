<template>
  <div class="page-container">
    <el-card>
      <template #header>
        <span>上传图片识别</span>
      </template>

      <div class="upload-section">
        <el-upload
            :auto-upload="false"
            :show-file-list="true"
            :on-change="handleFileChange"
            :on-remove="handleFileRemove"
            multiple
            :limit="20"
            accept=".jpg,.jpeg,.png"
        >
          <el-button type="primary">选择图片</el-button>
        </el-upload>

        <el-button
            type="success"
            :disabled="selectedFiles.length === 0 || loading"
            :loading="loading"
            @click="handleBatchUpload"
            style="margin-left: 12px;"
        >
          开始批量识别
        </el-button>
      </div>

      <div class="tips">
        <p>支持一次上传多张木材图片进行批量识别。</p>
        <p>支持格式：jpg / jpeg / png</p>
      </div>
    </el-card>

    <div v-if="resultList.length > 0" style="margin-top: 20px;">
      <el-card
          v-for="item in resultList"
          :key="item.recordId"
          class="result-card"
      >
        <template #header>
          <div class="card-header">
            <span>识别结果 - {{ item.imageName }}</span>
            <el-tag type="success">{{ item.status }}</el-tag>
          </div>
        </template>

        <div class="summary">
          <p><strong>记录ID：</strong>{{ item.recordId }}</p>
          <p><strong>图片名称：</strong>{{ item.imageName }}</p>
          <p><strong>检测总数：</strong>{{ item.totalCount }}</p>
          <p><strong>创建时间：</strong>{{ item.createTime }}</p>
        </div>

        <el-row :gutter="20" style="margin-top: 16px;">
          <el-col :span="12">
            <el-card shadow="never">
              <template #header>
                <span>原图</span>
              </template>
              <img :src="fullImageUrl(item.imageUrl)" class="preview-image" />
            </el-card>
          </el-col>

          <el-col :span="12">
            <el-card shadow="never">
              <template #header>
                <span>识别结果图</span>
              </template>
              <img :src="fullImageUrl(item.resultImageUrl)" class="preview-image" />
            </el-card>
          </el-col>
        </el-row>

        <el-card shadow="never" style="margin-top: 16px;">
          <template #header>
            <span>缺陷明细</span>
          </template>

          <el-table :data="item.details || []" border style="width: 100%;">
            <el-table-column prop="className" label="缺陷类别" />
            <el-table-column prop="confidence" label="置信度" />
            <el-table-column prop="x1" label="x1" />
            <el-table-column prop="y1" label="y1" />
            <el-table-column prop="x2" label="x2" />
            <el-table-column prop="y2" label="y2" />
          </el-table>
        </el-card>
      </el-card>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { batchUploadDetect } from '../api/detect'

const selectedFiles = ref([])
const resultList = ref([])
const loading = ref(false)

/**
 * 选择文件时触发
 */
function handleFileChange(file, fileList) {
  selectedFiles.value = fileList.map(item => item.raw).filter(Boolean)
}

/**
 * 删除文件时触发
 */
function handleFileRemove(file, fileList) {
  selectedFiles.value = fileList.map(item => item.raw).filter(Boolean)
}

/**
 * 批量上传并识别
 */
async function handleBatchUpload() {
  if (selectedFiles.value.length === 0) {
    ElMessage.warning('请先选择图片')
    return
  }

  try {
    loading.value = true
    const res = await batchUploadDetect(selectedFiles.value)
    resultList.value = res.data.data || []
    ElMessage.success('批量识别成功')
  } catch (error) {
    ElMessage.error(error?.response?.data?.message || '批量识别失败')
  } finally {
    loading.value = false
  }
}

/**
 * 拼接完整图片地址
 */
function fullImageUrl(url) {
  if (!url) return ''
  return new URL(url, window.location.origin).toString()
}
</script>

<style scoped>

.page-container {
  padding: 20px;
}

.upload-section {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
}

.tips {
  margin-top: 12px;
  color: #666;
  font-size: 14px;
}

.result-card {
  margin-bottom: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.preview-image {
  width: 100%;
  max-height: 400px;
  object-fit: contain;
  border: 1px solid #ddd;
  background: #fafafa;
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
