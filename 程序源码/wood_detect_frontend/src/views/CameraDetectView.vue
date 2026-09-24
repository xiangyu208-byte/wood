<template>
  <div class="page">
    <header class="page-heading">
      <div>
        <p class="eyebrow">现场采集</p>
        <h1>摄像头识别</h1>
        <p>打开摄像头、拍摄当前木材表面，再提交识别。浏览器会在首次使用时请求摄像头权限。</p>
      </div>
      <StatusBadge v-if="resultData" :status="resultData.status" />
    </header>

    <section class="surface" aria-labelledby="camera-title">
      <div class="section-heading">
        <h2 id="camera-title">采集画面</h2>
        <span class="muted">{{ cameraRunning ? '摄像头运行中' : '摄像头未开启' }}</span>
      </div>

      <div class="actions">
        <el-button type="primary" :disabled="cameraRunning" @click="startCamera">打开摄像头</el-button>
        <el-button :disabled="!cameraRunning" @click="captureImage">拍照</el-button>
        <el-button :disabled="!capturedImageUrl" @click="resetCapture">重拍</el-button>
        <el-button :disabled="!cameraRunning" @click="stopCamera">关闭摄像头</el-button>
      </div>

      <div class="camera-grid">
        <figure>
          <figcaption>实时画面</figcaption>
          <div class="camera-frame">
            <video ref="videoRef" autoplay playsinline muted aria-label="摄像头实时画面"></video>
            <span v-if="!cameraRunning">打开摄像头后将在此显示画面</span>
          </div>
        </figure>
        <figure>
          <figcaption>拍照结果</figcaption>
          <div class="camera-frame">
            <img v-if="capturedImageUrl" :src="capturedImageUrl" alt="待识别的摄像头拍照结果" />
            <span v-else>尚未拍照</span>
          </div>
        </figure>
      </div>

      <DetectionSettings v-model="settings" />
      <div class="actions detect-actions">
        <el-button type="primary" :loading="loading" :disabled="!capturedFile || loading" @click="handleDetect">
          {{ resultData ? '重新识别' : '开始识别' }}
        </el-button>
        <el-button v-if="loading" plain @click="cancelRequest">取消等待</el-button>
      </div>
    </section>

    <section v-if="loading" class="surface">
      <StatePanel tone="loading" title="正在识别当前画面" description="请保持页面开启，完成后会显示原图、结果图和缺陷明细。" />
    </section>

    <section v-else-if="lastError" class="surface">
      <StatePanel :tone="errorTone" title="本次识别未完成" :description="lastError.message">
        <template #action><el-button type="primary" :disabled="!capturedFile" @click="handleDetect">重试识别</el-button></template>
      </StatePanel>
    </section>

    <section v-else-if="resultData" class="surface">
      <ResultDetails :result="resultData" />
    </section>

    <canvas ref="canvasRef" hidden></canvas>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, ref } from 'vue'
import { ElMessage } from 'element-plus'
import DetectionSettings from '../components/DetectionSettings.vue'
import ResultDetails from '../components/ResultDetails.vue'
import StatePanel from '../components/StatePanel.vue'
import StatusBadge from '../components/StatusBadge.vue'
import { cameraUploadDetect } from '../api/detect'

const videoRef = ref(null)
const canvasRef = ref(null)
const cameraRunning = ref(false)
const loading = ref(false)
const resultData = ref(null)
const lastError = ref(null)
const capturedImageUrl = ref('')
const capturedFile = ref(null)
const settings = ref({ modelMode: 'STANDARD', confidenceThreshold: 0.25, precision: 'AUTO' })
let mediaStream = null
let requestController = null

const errorTone = computed(() => ['offline', 'service'].includes(lastError.value?.kind) ? 'offline' : 'error')

async function startCamera() {
  if (!navigator.mediaDevices?.getUserMedia) {
    lastError.value = new Error('当前浏览器不支持摄像头访问，请改用在线识别上传图片')
    return
  }
  try {
    mediaStream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment' }, audio: false })
    videoRef.value.srcObject = mediaStream
    cameraRunning.value = true
    lastError.value = null
  } catch {
    lastError.value = new Error('无法打开摄像头，请允许摄像头权限并确认没有被其他应用占用')
  }
}

function stopCamera() {
  mediaStream?.getTracks().forEach(track => track.stop())
  mediaStream = null
  if (videoRef.value) videoRef.value.srcObject = null
  cameraRunning.value = false
}

function captureImage() {
  const video = videoRef.value
  const canvas = canvasRef.value
  if (!video?.videoWidth || !video?.videoHeight) {
    ElMessage.warning('画面尚未准备好，请稍后再拍')
    return
  }
  canvas.width = video.videoWidth
  canvas.height = video.videoHeight
  canvas.getContext('2d').drawImage(video, 0, 0, canvas.width, canvas.height)
  capturedImageUrl.value = canvas.toDataURL('image/jpeg', 0.92)
  canvas.toBlob(blob => {
    if (!blob) return ElMessage.error('拍照失败，请重试')
    capturedFile.value = new File([blob], `camera_${Date.now()}.jpg`, { type: 'image/jpeg' })
    resultData.value = null
    lastError.value = null
  }, 'image/jpeg', 0.92)
}

function resetCapture() {
  capturedImageUrl.value = ''
  capturedFile.value = null
  resultData.value = null
  lastError.value = null
}

async function handleDetect() {
  if (!capturedFile.value) return
  requestController = new AbortController()
  loading.value = true
  lastError.value = null
  try {
    const payload = await cameraUploadDetect(capturedFile.value, settings.value, { signal: requestController.signal })
    resultData.value = payload.data
    if (payload.data.status === 'SUCCESS') ElMessage.success('摄像头识别完成')
  } catch (error) {
    if (error.kind !== 'cancelled') lastError.value = error
  } finally {
    loading.value = false
    requestController = null
  }
}

function cancelRequest() {
  requestController?.abort()
  loading.value = false
  ElMessage.info('已停止等待本次识别响应')
}

onBeforeUnmount(() => {
  requestController?.abort()
  stopCamera()
})
</script>

<style scoped>
.camera-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px; margin-top: 18px; }
.camera-grid figure { min-width: 0; margin: 0; }
.camera-grid figcaption { margin-bottom: 8px; font-size: 13px; font-weight: 650; }
.camera-frame { position: relative; display: grid; min-height: 330px; place-items: center; overflow: hidden; border: 1px solid var(--color-border); border-radius: var(--radius-md); background: var(--color-surface-muted); color: var(--color-text-muted); }
.camera-frame video, .camera-frame img { width: 100%; height: 100%; max-height: 480px; object-fit: contain; }
.camera-frame > span { padding: 24px; text-align: center; }
.detect-actions { margin-top: 18px; }

@media (max-width: 700px) {
  .camera-grid { grid-template-columns: 1fr; }
  .camera-frame { min-height: min(68vw, 340px); }
}
</style>
