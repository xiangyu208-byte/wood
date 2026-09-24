<template>
  <div class="page-container">
    <el-card>
      <template #header>
        <span>摄像头识别</span>
      </template>

      <div class="tips">
        <p>此页面用于模拟工业应用场景：通过电脑摄像头采集木材图像并进行识别。</p>
        <p>请先点击“打开摄像头”，将木材图片放到摄像头前，再点击“拍照识别”。</p>
      </div>

      <div class="action-buttons">
        <el-button type="primary" @click="startCamera" :disabled="cameraRunning">
          打开摄像头
        </el-button>

        <el-button type="warning" @click="stopCamera" :disabled="!cameraRunning">
          关闭摄像头
        </el-button>

        <el-button type="success" @click="captureImage" :disabled="!cameraRunning">
          拍照
        </el-button>

        <el-button @click="resetCapture" :disabled="!capturedImageUrl">
          重拍
        </el-button>

        <el-button
            type="danger"
            :loading="loading"
            :disabled="!capturedFile || loading"
            @click="handleDetect"
        >
          开始识别
        </el-button>
      </div>

      <el-row :gutter="20" style="margin-top: 20px;">
        <el-col :span="12">
          <el-card shadow="never">
            <template #header>
              <span>摄像头实时画面</span>
            </template>
            <div class="camera-box">
              <video
                  ref="videoRef"
                  autoplay
                  playsinline
                  muted
                  class="preview-video"
              ></video>
            </div>
          </el-card>
        </el-col>

        <el-col :span="12">
          <el-card shadow="never">
            <template #header>
              <span>拍照结果</span>
            </template>
            <div class="camera-box">
              <img
                  v-if="capturedImageUrl"
                  :src="capturedImageUrl"
                  class="preview-image"
              />
              <div v-else class="empty-tip">尚未拍照</div>
            </div>
          </el-card>
        </el-col>
      </el-row>
    </el-card>

    <el-row :gutter="20" style="margin-top: 20px;" v-if="resultData">
      <el-col :span="12">
        <el-card>
          <template #header>
            <span>原图</span>
          </template>
          <img :src="fullImageUrl(resultData.imageUrl)" class="result-image" />
        </el-card>
      </el-col>

      <el-col :span="12">
        <el-card>
          <template #header>
            <span>识别结果图</span>
          </template>
          <img :src="fullImageUrl(resultData.resultImageUrl)" class="result-image" />
        </el-card>
      </el-col>
    </el-row>

    <el-card style="margin-top: 20px;" v-if="resultData">
      <template #header>
        <span>识别结果明细</span>
      </template>

      <div class="summary">
        <p><strong>记录ID：</strong>{{ resultData.recordId }}</p>
        <p><strong>图片名称：</strong>{{ resultData.imageName }}</p>
        <p><strong>来源类型：</strong>{{ resultData.sourceType }}</p>
        <p><strong>状态：</strong>{{ resultData.status }}</p>
        <p><strong>检测总数：</strong>{{ resultData.totalCount }}</p>
      </div>

      <el-table :data="resultData.details || []" border style="width: 100%; margin-top: 12px;">
        <el-table-column prop="className" label="缺陷类别" />
        <el-table-column prop="confidence" label="置信度" />
        <el-table-column prop="x1" label="x1" />
        <el-table-column prop="y1" label="y1" />
        <el-table-column prop="x2" label="x2" />
        <el-table-column prop="y2" label="y2" />
      </el-table>
    </el-card>

    <!-- 隐藏 canvas，用于截帧 -->
    <canvas ref="canvasRef" style="display: none;"></canvas>
  </div>
</template>

<script setup>
import { ref, onBeforeUnmount } from 'vue'
import { ElMessage } from 'element-plus'
import { cameraUploadDetect } from '../api/detect'

const videoRef = ref(null)
const canvasRef = ref(null)

const cameraRunning = ref(false)
const loading = ref(false)
const resultData = ref(null)

const capturedImageUrl = ref('')
const capturedFile = ref(null)

let mediaStream = null

async function startCamera() {
  try {
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      ElMessage.error('当前浏览器不支持摄像头访问')
      return
    }

    mediaStream = await navigator.mediaDevices.getUserMedia({
      video: true,
      audio: false
    })

    videoRef.value.srcObject = mediaStream
    cameraRunning.value = true
    ElMessage.success('摄像头已打开')
  } catch (error) {
    ElMessage.error('无法打开摄像头，请检查权限设置')
  }
}

function stopCamera() {
  if (mediaStream) {
    mediaStream.getTracks().forEach(track => track.stop())
    mediaStream = null
  }

  if (videoRef.value) {
    videoRef.value.srcObject = null
  }

  cameraRunning.value = false
}

function captureImage() {
  if (!videoRef.value || !canvasRef.value) {
    ElMessage.warning('摄像头未准备好')
    return
  }

  const video = videoRef.value
  const canvas = canvasRef.value
  const context = canvas.getContext('2d')

  if (!video.videoWidth || !video.videoHeight) {
    ElMessage.warning('当前还没有可用画面，请稍后再试')
    return
  }

  canvas.width = video.videoWidth
  canvas.height = video.videoHeight

  context.drawImage(video, 0, 0, canvas.width, canvas.height)

  capturedImageUrl.value = canvas.toDataURL('image/png')

  canvas.toBlob(blob => {
    if (!blob) {
      ElMessage.error('拍照失败')
      return
    }

    capturedFile.value = new File(
        [blob],
        `camera_${Date.now()}.png`,
        { type: 'image/png' }
    )

    ElMessage.success('拍照成功')
  }, 'image/png')
}

function resetCapture() {
  capturedImageUrl.value = ''
  capturedFile.value = null
  resultData.value = null
}

async function handleDetect() {
  if (!capturedFile.value) {
    ElMessage.warning('请先拍照')
    return
  }

  try {
    loading.value = true
    const res = await cameraUploadDetect(capturedFile.value)
    resultData.value = res.data.data
    ElMessage.success('摄像头识别成功')
  } catch (error) {
    ElMessage.error(error?.response?.data?.message || '摄像头识别失败')
  } finally {
    loading.value = false
  }
}

function fullImageUrl(url) {
  if (!url) return ''
  return new URL(url, window.location.origin).toString()
}

onBeforeUnmount(() => {
  stopCamera()
})
</script>

<style scoped>
.page-container {
  padding: 20px;
}

.tips {
  color: #666;
  font-size: 14px;
  line-height: 1.8;
}

.action-buttons {
  margin-top: 16px;
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}

.camera-box {
  width: 100%;
  min-height: 360px;
  border: 1px solid #ddd;
  background: #fafafa;
  display: flex;
  justify-content: center;
  align-items: center;
}

.preview-video,
.preview-image,
.result-image {
  width: 100%;
  max-height: 500px;
  object-fit: contain;
}

.empty-tip {
  color: #999;
  font-size: 14px;
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
