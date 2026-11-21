<template>
  <div class="page">
    <header class="page-heading"><div><h1>摄像头识别</h1><p>选择板材批次和识别方式，采集结果可在历史记录中查看。</p></div></header>
    <section class="surface">
      <div class="actions">
        <el-button type="primary" :disabled="opening || cameraRunning" @click="startCamera">打开摄像头</el-button>
        <el-button :disabled="!cameraRunning || running || processing" @click="manualCapture">拍照</el-button>
        <el-button :disabled="!cameraRunning" @click="stopCamera">关闭摄像头</el-button>
      </div>
      <div class="camera-grid">
        <figure><figcaption>实时画面</figcaption><div class="camera-frame"><video ref="video" autoplay playsinline muted></video><span v-if="!cameraRunning">等待开启摄像头</span></div></figure>
        <figure><figcaption>最近一次识别或拍照 {{ sampledAt }}</figcaption><div class="camera-frame"><canvas v-show="frame" ref="overlay" style="width:100%;height:auto"></canvas><span v-if="!frame">等待拍照或识别</span></div></figure>
      </div>
      <p v-if="stats" role="status">{{ stats }}</p>
      <DetectionSettings v-model="settings"/>
      <MaterialBatchPicker v-model="materialBatch" :disabled="running || processing"/>
      <fieldset :disabled="running || processing" class="modes"><legend>识别方式</legend>
        <label><input type="radio" v-model="mode" value="manual"> 手动拍照</label>
        <label><input type="radio" v-model="mode" value="archive"> 连续识别</label>
        <label><input type="radio" v-model="mode" value="preview"> 实时识别</label>
        <label v-if="mode === 'archive'">每张间隔（秒） <input type="number" v-model.number="interval" min="1" max="3600"></label>
      </fieldset>
      <p class="muted">{{ mode === 'manual' ? '拍照后可检查画面，再点击识别并保存。' : mode === 'archive' ? '按设定间隔识别，每张照片自动保存到历史记录。' : materialBatch ? '摄像头持续识别，每次完成的结果自动保存到所选批次。' : '摄像头持续显示检测框。停止后可保存当前画面；选择板材批次可自动归档。' }}</p>
      <div class="actions">
        <el-button v-if="mode !== 'manual'" type="primary" :disabled="!cameraRunning || running || processing || opening" @click="startLoop">开始{{ mode === 'archive' ? '连续识别' : '实时识别' }}</el-button>
        <el-button v-if="running" @click="stopLoop">停止识别</el-button>
        <el-button :disabled="!frame || running || processing || !!saved" @click="saveManual">识别并保存</el-button>
      </div>
      <p role="alert" v-if="error" class="inline-error">{{ error }}</p>
    </section>
    <p v-if="!materialBatch && sessionIds.length === 1000" class="muted">本次分析显示最近 1000 张未分批照片，更早照片可从历史记录查看。</p>
    <InspectionAnalysis v-if="!running && !processing && (materialBatch || sessionIds.length)" :material-batch="materialBatch" :record-ids="sessionIds" :revision="lastArchivedId" />
    <section v-if="saved" class="surface"><ResultDetails :key="saved.recordId" :result="saved"/></section>
  </div>
</template>
<script setup>
import { onBeforeUnmount, ref, shallowRef, watch } from 'vue'
import DetectionSettings from '../components/DetectionSettings.vue'
import ResultDetails from '../components/ResultDetails.vue'
import MaterialBatchPicker from '../components/MaterialBatchPicker.vue'
import InspectionAnalysis from '../components/InspectionAnalysis.vue'
import { cameraUploadDetect, previewDetect } from '../api/detect'
import { classNameZh } from '../utils/detection'
const video=ref(null), overlay=ref(null)
const cameraRunning=ref(false), opening=ref(false), running=ref(false), processing=ref(false)
const frame=shallowRef(null), saved=ref(null), stats=ref(''), error=ref(''), sampledAt=ref('')
const mode=ref('manual'), interval=ref(3), settings=ref({modelMode:'FAST',confidenceThreshold:0.25,precision:'AUTO'})
const materialBatch = ref(''), sessionIds = ref([]), lastArchivedId = ref(0)
let stream=null, epoch=0, timer=null, controller=null, disposed=false
watch(materialBatch, () => { sessionIds.value=[]; lastArchivedId.value=0; frame.value=null; saved.value=null; stats.value=''; sampledAt.value='' })
async function startCamera() {
  error.value='';opening.value=true
  try {
    const media=await navigator.mediaDevices.getUserMedia({video:{facingMode:'environment',width:{ideal:1920},height:{ideal:1080}},audio:false})
    if(disposed){media.getTracks().forEach(t=>t.stop());return}
    stream=media;video.value.srcObject=media;await video.value.play();cameraRunning.value=true
  } catch {stopCamera();error.value='无法打开摄像头，请检查设备、权限及 HTTPS 或 localhost 连接'}
  finally {opening.value=false}
}
function stopLoop() {
  epoch++;running.value=false;clearTimeout(timer)
  if (mode.value==='preview' && !materialBatch.value) controller?.abort()
}
function stopCamera() {
  stopLoop();stream?.getTracks().forEach(t=>t.stop());stream=null
  if(video.value) video.value.srcObject=null
  cameraRunning.value=false
}
async function grab() {
  const v=video.value
  if(!v?.videoWidth || !v.videoHeight)throw new Error('摄像头画面尚未就绪')
  const canvas=document.createElement('canvas')
  canvas.width=v.videoWidth;canvas.height=v.videoHeight
  canvas.getContext('2d').drawImage(v,0,0)
  const time=new Date()
  const blob=await new Promise(resolve=>canvas.toBlob(resolve,'image/jpeg',0.92))
  if(!blob)throw new Error('摄像头照片读取失败')
  return {canvas,time,file:new File([blob],'camera_'+time.getTime()+'.jpg',{type:'image/jpeg'})}
}
function show(sample,details=[]) {
  const c=overlay.value
  c.width=sample.canvas.width;c.height=sample.canvas.height
  const ctx=c.getContext('2d');ctx.drawImage(sample.canvas,0,0)
  ctx.lineWidth=Math.max(2,c.width/450);ctx.font=Math.max(14,c.width/55)+'px sans-serif'
  for (const b of details) {
    ctx.strokeStyle='#ffb448';ctx.fillStyle='#ffb448';ctx.strokeRect(b.x1,b.y1,b.x2-b.x1,b.y2-b.y1)
    const label=classNameZh(b.className)+' '+Math.round(b.confidence*100)+'%'
    const y=Math.max(25,b.y1);ctx.fillStyle='#18221d';ctx.fillRect(b.x1,y-24,ctx.measureText(label).width+6,26)
    ctx.fillStyle='#fff';ctx.fillText(label,b.x1+3,y-2)
  }
  frame.value=sample;sampledAt.value=sample.time.toLocaleTimeString()
}
async function manualCapture() {
  const generation=epoch;processing.value=true
  try {const sample=await grab();if(generation===epoch){show(sample);saved.value=null;stats.value='';error.value=''}}
  catch(e) {error.value=e.message} finally {processing.value=false}
}
async function archive(sample,options,config) {
  const r=(await cameraUploadDetect(sample.file,{...options,materialBatch:materialBatch.value},config)).data
  if(r.status!=='SUCCESS')throw new Error(r.errorMessage||'识别失败')
  if (!disposed) {
    saved.value=r
    lastArchivedId.value=r.recordId
    if (!materialBatch.value) sessionIds.value=[...sessionIds.value.slice(-999),r.recordId]
  }
  return r
}
async function saveManual() {
  processing.value=true;error.value=''
  try {const r=await archive(frame.value,{...settings.value},{timeout:145000});if(!disposed)show(frame.value,r.details)}
  catch(e){error.value=e.message} finally{processing.value=false}
}
function startLoop() {
  if(!cameraRunning.value || running.value || processing.value)return
  if(mode.value==='archive' && !(interval.value>=1 && interval.value<=3600)){error.value='图片间隔须为 1–3600 秒';return}
  error.value='';stats.value='';running.value=true
  tick(++epoch)
}
async function tick(generation) {
  const start=performance.now()
  processing.value=true;controller=new AbortController()
  try {
    const sample=await grab()
    if(generation!==epoch)return
    const options={...settings.value},config={signal:controller.signal,timeout:145000}
    const persist = mode.value === 'archive' || Boolean(materialBatch.value)
    const data = persist ? await archive(sample,options,config) : (await previewDetect(sample.file,options,config)).data
    if(disposed || (generation!==epoch && !persist))return
    if (!persist) saved.value=null
    show(sample,data.details)
    stats.value='本次识别 '+(data.details?.length || 0)+' 个检测框 · 处理耗时 '+Math.round(performance.now()-start)+' ms'
  } catch(e) {
    if(generation===epoch){error.value=e.message;stopLoop()}
  } finally {
    processing.value=false;controller=null
    if(generation===epoch && running.value) {
      const delay=mode.value==='archive'?Math.max(0,interval.value*1000-(performance.now()-start)):80
      timer=setTimeout(()=>tick(generation),delay)
    }
  }
}
onBeforeUnmount(()=>{disposed=true;stopCamera()})
</script>

<style scoped>
.modes { display:flex; flex-wrap:wrap; align-items:center; gap:14px; padding:12px; border:1px solid var(--color-border); border-radius:8px }
.modes label { display:flex; align-items:center; gap:5px } .modes input[type=number] { width:75px }
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
