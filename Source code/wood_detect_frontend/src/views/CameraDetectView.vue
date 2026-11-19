<template>
  <div class="page">
    <header class="page-heading"><div><h1>摄像头识别</h1><p>逐帧取样，完成上一帧后才提交下一帧。检测框显示在对应的采样画面上。</p></div></header>
    <section class="surface">
      <div class="actions">
        <el-button type="primary" :disabled="opening || cameraRunning" @click="startCamera">打开摄像头</el-button>
        <el-button :disabled="!cameraRunning || running || processing" @click="manualCapture">拍照</el-button>
        <el-button :disabled="!cameraRunning" @click="stopCamera">关闭摄像头</el-button>
      </div>
      <div class="camera-grid">
        <figure><figcaption>实时画面</figcaption><div class="camera-frame"><video ref="video" autoplay playsinline muted></video><span v-if="!cameraRunning">等待开启摄像头</span></div></figure>
        <figure><figcaption>最近一次采样 {{ sampledAt }}</figcaption><div class="camera-frame"><canvas v-show="frame" ref="overlay" style="width:100%;height:auto"></canvas><span v-if="!frame">等待采样</span></div></figure>
      </div>
      <p v-if="stats" role="status">{{ stats }}</p>
      <DetectionSettings v-model="settings"/>
      <fieldset :disabled="running || processing" class="capture-options"><legend>采样与归档</legend>
        <label>连续模式 <select v-model="mode"><option value="preview">实时抽帧预览</option><option value="archive">定点连续留档</option></select></label>
        <label v-if="mode==='archive'">采样最短间隔（秒） <input type="number" v-model.number="interval" min="1" max="3600"></label>
        <label>归档板面 <select :value="boardId" @change="loadBoard(Number($event.target.value))"><option value="">仅存历史</option><option v-for="b in boards" :key="b.id" :value="b.id">{{ b.code }} · {{ b.face }} 面</option></select></label>
        <PlacementFields v-if="board" v-model="placement" :view="board" />
      </fieldset>
      <p class="muted">{{ mode==='archive'?'每次采样都会生成一条历史记录。板材移动时，请选择待定位或与同板基准局部照配准。':'预览帧不计入历史，点击保存可将选中帧识别归档。' }}</p>
      <div class="actions">
        <el-button type="primary" :disabled="!cameraRunning || running || processing || opening || (boardId && !board)" @click="startLoop">开始连续识别</el-button>
        <el-button :disabled="!running" @click="stopLoop">停止连续识别</el-button>
        <el-button :disabled="!frame || running || processing || !!saved || (boardId && !board)" @click="saveManual">识别并保存选中帧</el-button>
      </div>
      <p role="alert" v-if="error" class="inline-error">{{ error }}</p>
    </section>
    <section v-if="saved" class="surface"><ResultDetails :key="saved.recordId" :result="saved"/></section>
  </div>
</template>
<script setup>
import { onBeforeUnmount, onMounted, ref, shallowRef } from 'vue'
import { useRoute } from 'vue-router'
import DetectionSettings from '../components/DetectionSettings.vue'
import ResultDetails from '../components/ResultDetails.vue'
import PlacementFields from '../components/PlacementFields.vue'
import { cameraUploadDetect, previewDetect } from '../api/detect'
import { getBoard, listBoards, placeRecord } from '../api/boards'
import { classNameZh } from '../utils/detection'
const route=useRoute(), video=ref(null), overlay=ref(null)
const cameraRunning=ref(false), opening=ref(false), running=ref(false), processing=ref(false)
const frame=shallowRef(null), saved=ref(null), stats=ref(''), error=ref(''), sampledAt=ref('')
const mode=ref('preview'), interval=ref(3), settings=ref({modelMode:'FAST',confidenceThreshold:0.25,precision:'AUTO'})
const boards=ref([]), board=ref(null), boardId=ref(''), placement=ref({mode:'UNKNOWN',row:1,col:1,anchorId:null})
let stream=null, epoch=0, timer=null, controller=null, disposed=false, boardRequest=0
onMounted(async()=>{
  try {boards.value=(await listBoards()).data;if(route.query.board) await loadBoard(Number(route.query.board))}
  catch(e) {error.value=e.message}
})
async function loadBoard(id) {
  const revision=++boardRequest
  board.value=null;boardId.value=id || '';placement.value={mode:'UNKNOWN',row:1,col:1,anchorId:null}
  if(!id) return
  try {const value=(await getBoard(id)).data;if(revision===boardRequest)board.value=value}
  catch(e) {if(revision===boardRequest){error.value=e.message;boardId.value=''}}
}
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
  if (mode.value==='preview') controller?.abort()
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
  if(!blob)throw new Error('采样失败')
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
  const r=(await cameraUploadDetect(sample.file,options,config)).data
  if(r.status!=='SUCCESS')throw new Error(r.errorMessage||'识别失败')
  saved.value=r
  if(board.value) {
    const id=board.value.board.id
    await placeRecord(id,r.recordId,{mode:'UNKNOWN'})
    if(placement.value.mode!=='UNKNOWN')await placeRecord(id,r.recordId,{...placement.value})
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
  if(mode.value==='archive' && !(interval.value>=1 && interval.value<=3600)){error.value='采样间隔须为 1–3600 秒';return}
  error.value='';stats.value='';saved.value=null;running.value=true
  tick(++epoch)
}
async function tick(generation) {
  const start=performance.now()
  processing.value=true;controller=new AbortController()
  try {
    const sample=await grab()
    if(generation!==epoch)return
    const options={...settings.value},config={signal:controller.signal,timeout:145000}
    const data=mode.value==='archive'?await archive(sample,options,config):(await previewDetect(sample.file,options,config)).data
    if(generation!==epoch)return
    show(sample,data.details)
    stats.value='本帧 '+(data.details?.length || 0)+' 个检测框 · 采集至返回 '+Math.round(performance.now()-start)+' ms'
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
