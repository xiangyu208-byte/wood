<template>
  <div class="page board-page">
    <header class="page-heading"><div><h1>板材地图</h1><p>按板号与板面归集局部照片，查看缺陷在板面上的相对位置。</p></div></header>
    <p v-if="error" role="alert" class="inline-error">{{ error }}</p>
    <section class="surface">
      <div class="toolbar">
        <label>板材与板面<select :value="selected" :disabled="busy" @change="selectBoard(Number($event.target.value))">
          <option value="">选择已有板材</option>
          <option v-for="b in boards" :key="b.id" :value="b.id">{{ b.code }} · {{ b.face }} 面</option>
        </select></label>
        <el-button :disabled="busy" @click="creating=!creating">新建板面</el-button>
        <router-link v-if="view" :to="{path:'/camera-detect',query:{board:selected}}">使用摄像头采集此板面</router-link>
      </div>
      <form v-if="creating || !boards.length" class="toolbar setup" @submit.prevent="addBoard">
        <label>板号<input required v-model.trim="setup.code" maxlength="80" placeholder="例如 B-001"></label>
        <label>板面<select v-model="setup.face"><option>A</option><option>B</option></select></label>
        <label>等分行数<input type="number" v-model.number="setup.rows" required min="1" max="100"></label>
        <label>等分列数<input type="number" v-model.number="setup.cols" required min="1" max="100"></label>
        <el-button native-type="submit" type="primary" :disabled="busy">建立板面</el-button>
      </form>
    </section>
    <template v-if="view">
      <section class="surface">
        <div class="section-heading"><h2>{{ view.board.code }} · {{ view.board.face }} 面</h2><span>{{ view.board.rows }} 行 × {{ view.board.cols }} 列</span></div>
        <div class="metrics">
          <div><small>局部照片</small><strong>{{ view.captures.length }}</strong></div>
          <div><small>待定位照片</small><strong>{{ view.captures.length-located.length }}</strong></div>
          <div><small>视野覆盖估计</small><strong>{{ percent(coverage(located.map(c=>c.area))) }}</strong></div>
          <div><small>逐图缺陷观测</small><strong>{{ view.boxes.length }}</strong></div>
        </div>
        <div class="map" :style="{backgroundSize:(100/view.board.cols)+'% '+(100/view.board.rows)+'%'}" aria-label="整板相对坐标图">
          <div v-for="c in located" :key="c.recordId" class="footprint" :style="position(c.area)"></div>
          <button v-for="(box,i) in mapped" :key="i" class="mark" :class="{active:focused===box.recordId}" :style="position(box.area)"
            :aria-label="classNameZh(box.category)+'，照片 '+box.recordId" :title="classNameZh(box.category)+' · #'+box.recordId" @click="focused=box.recordId"></button>
        </div>
        <p class="muted">左上角为原点，向右为 X、向下为 Y。浅绿为已定位视野，灰色为未覆盖区，红框为缺陷观测。重叠照片的观测分别保留。</p>
        <figure v-if="focusedCapture" class="evidence"><img :src="fullImageUrl(focusedCapture.imageUrl)" alt="选中局部照片"><figcaption>
          <router-link :to="'/history/'+focusedCapture.recordId">查看 #{{ focusedCapture.recordId }} {{ focusedCapture.name }} 的检测框</router-link>
        </figcaption></figure>
        <div v-if="histogram.length" class="bars" aria-label="按类别统计观测次数">
          <button v-for="[category,count] in histogram" :key="category" :aria-pressed="filter===category" @click="filter=filter===category?'':category">
            <span>{{ classNameZh(category) }}</span><i :style="{width:(count/histogram[0][1]*100)+'%'}"></i><b>{{ count }}</b>
          </button>
        </div>
        <div v-if="view.boxes.length" class="scroll"><table class="detail-table"><caption>缺陷中心点（板长、板宽百分比）</caption><thead><tr><th>照片</th><th>类别</th><th>X</th><th>Y</th></tr></thead>
          <tbody><tr v-for="(b,i) in visibleBoxes" :key="i" :class="{highlight:b.recordId===focused}">
            <td><router-link :to="'/history/'+b.recordId">#{{ b.recordId }}</router-link></td><td>{{ classNameZh(b.category) }}</td>
            <td>{{ b.area ? percent(b.area.x+b.area.width/2) : '待定位' }}</td><td>{{ b.area ? percent(b.area.y+b.area.height/2) : '待定位' }}</td>
          </tr></tbody></table></div>
      </section>
      <section class="surface">
        <h2>添加或定位局部照片</h2>
        <div class="toolbar">
          <label>选择新照片<input ref="photoInput" type="file" accept="image/jpeg,image/png,image/bmp" :disabled="busy" @change="chooseFile"></label>
          <label>或使用已有检测记录号<input type="number" v-model.number="record" min="1" :disabled="busy || !!file"></label>
        </div>
        <PlacementFields v-model="placement" :view="view" :record-id="Number(record) || undefined" />
        <el-button type="primary" :loading="busy" :disabled="!file && !record" @click="attach">{{ file?'识别并归档':'保存定位' }}</el-button>
        <div v-if="view.captures.length" class="scroll"><table class="detail-table"><caption>板面照片</caption><tbody>
          <tr v-for="c in view.captures" :key="c.recordId"><td><router-link :to="'/history/'+c.recordId">#{{ c.recordId }} {{ c.name }}</router-link></td>
            <td>{{ c.area ? (c.anchorId ? '重叠估计 · 基准 #'+c.anchorId+' · '+c.matches+' 个匹配点' : '已知格位') : '待定位' }}</td>
            <td><button :disabled="busy" @click="edit(c)">调整</button> <button :disabled="busy" @click="detach(c)">解除关联</button></td></tr>
        </tbody></table></div>
      </section>
      <section class="surface">
        <details><summary>整板参考照片（可选）</summary><p>仅供目视对照。</p>
          <input type="file" accept="image/jpeg,image/png,image/bmp" :disabled="busy" @change="reference">
          <img v-if="view.board.hasReference" class="reference" :src="referenceUrl" alt="板面参考照片">
        </details>
      </section>
      <section class="surface">
        <div class="section-heading"><h2>板面质检报告</h2><el-button :disabled="busy || !view.captures.length || !aiAvailable" @click="report">生成 DeepSeek 报告</el-button></div>
        <p class="muted">{{ aiAvailable?'发送本板面汇总与检测记录编号生成摘要。':'服务端配置 DEEPSEEK_API_KEY 后可生成报告。' }}</p>
        <article v-if="analysis"><strong>{{ analysis.model }}</strong><p class="report">{{ analysis.text }}</p></article>
      </section>
    </template>
  </div>
</template>
<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import PlacementFields from '../components/PlacementFields.vue'
import { aiConfig, createBoard, getBoard, listBoards, placeRecord, removeFromBoard, saveReference, generateReport } from '../api/boards'
import { uploadDetect, request } from '../api/detect'
import { classNameZh,fullImageUrl } from '../utils/detection'
import { coverage,countClasses } from '../utils/boardMap'
const route=useRoute()
const boards=ref([]), selected=ref(''), view=ref(null), busy=ref(false), creating=ref(false), error=ref('')
const setup=ref({code:'',face:'A',rows:1,cols:4}), placement=ref({mode:'UNKNOWN',row:1,col:1,anchorId:null})
const record=ref(Number(route.query.record)||''), file=ref(null), photoInput=ref(null), filter=ref(''), focused=ref(null)
const analysis=ref(null), aiAvailable=ref(false), revision=ref(0)
const referenceUrl=computed(()=>request.defaults.baseURL+'/boards/'+selected.value+'/reference?v='+revision.value)
const located=computed(()=>view.value.captures.filter(c=>c.area))
const focusedCapture=computed(()=>view.value.captures.find(c=>c.recordId===focused.value))
const histogram=computed(()=>countClasses(view.value.boxes))
const visibleBoxes=computed(()=>view.value.boxes.filter(b=>!filter.value || b.category===filter.value))
const mapped=computed(()=>visibleBoxes.value.filter(b=>b.area))
const percent=v=>(100*v).toFixed(1)+'%'
function position(r) {return {left:r.x*100+'%',top:r.y*100+'%',width:r.width*100+'%',height:r.height*100+'%'}}
async function run(fn) {
  if(busy.value) return
  busy.value=true;error.value=''
  try {await fn()} catch(e) {error.value=e.message;ElMessage.error(e.message)} finally {busy.value=false}
}
async function refresh() {
  view.value=(await getBoard(selected.value)).data
  analysis.value=null
}
async function open(id) {
  selected.value=id
  view.value=null;filter.value='';focused.value=null;file.value=null
  placement.value={mode:'UNKNOWN',row:1,col:1,anchorId:null}
  if(id) await refresh()
}
function selectBoard(id) {run(()=>open(id))}
onMounted(()=>run(async()=>{
  boards.value=(await listBoards()).data
  if(boards.value.length) await open(boards.value[0].id)
  aiAvailable.value=(await aiConfig()).data.configured
}))
function addBoard(){run(async()=>{
  const b=(await createBoard(setup.value)).data
  boards.value.unshift(b);creating.value=false;setup.value.code=''
  await open(b.id)
})}
function chooseFile(e) {file.value=e.target.files[0]??null;if(file.value)record.value=''}
function edit(c) {
  record.value=c.recordId;file.value=null;photoInput.value.value='';focused.value=c.recordId
  placement.value={mode:c.area?(c.anchorId?'OVERLAP':'GRID'):'UNKNOWN',row:c.area?Math.round(c.area.y*view.value.board.rows)+1:1,
    col:c.area?Math.round(c.area.x*view.value.board.cols)+1:1,anchorId:c.anchorId}
}
function attach(){run(async()=>{
  if(file.value) {
    const result=(await uploadDetect(file.value,{modelMode:'STANDARD'},{timeout:145000})).data
    if(result.status!=='SUCCESS') throw new Error(result.errorMessage || '局部照片识别失败')
    record.value=result.recordId;file.value=null;photoInput.value.value=''
    await placeRecord(selected.value,record.value,{mode:'UNKNOWN'})
  }
  try {await placeRecord(selected.value,record.value,placement.value);focused.value=record.value;ElMessage.success('板面照片已保存')}
  finally {await refresh()}
})}
function detach(c) {run(async()=>{await removeFromBoard(selected.value,c.recordId);await refresh()})}
function reference(e){const f=e.target.files[0];if(f)run(async()=>{await saveReference(selected.value,f);revision.value++;await refresh();e.target.value=''})}
function report(){run(async()=>{analysis.value=(await generateReport(selected.value)).data})}
</script>
<style scoped>
.board-page h2 {margin-top:0}.toolbar {display:flex;flex-wrap:wrap;align-items:end;gap:1rem;margin:.8rem 0 1rem}.toolbar label {display:grid;gap:.35rem;font-size:.88rem}
.toolbar input,.toolbar select {border:1px solid var(--color-border);background:var(--color-surface);color:inherit;border-radius:6px;padding:.55rem;max-width:100%}
.toolbar input[type=number] {width:8rem}.metrics {display:grid;grid-template-columns:repeat(auto-fit,minmax(125px,1fr));gap:.8rem;margin:1rem 0}
.metrics div {padding:.75rem;background:var(--color-surface-muted);border-radius:8px}.metrics strong,.metrics small {display:block}.metrics strong {font-size:1.5rem}
.map {position:relative;aspect-ratio:4/1;min-height:120px;border:1px solid #83958b;background-color:#e3e5e3;background-image:linear-gradient(to right,#abb4b0 1px,transparent 1px),linear-gradient(to bottom,#abb4b0 1px,transparent 1px);overflow:hidden}
.footprint,.mark {position:absolute}.footprint {background:rgba(62,138,93,.18);outline:1px solid #579067}.mark {background:#b7382428;border:2px solid #a53222;min-width:4px;min-height:4px;padding:0;cursor:pointer}.mark.active {outline:2px solid #33201d}
.bars {max-width:550px;display:grid;gap:.25rem;margin:1rem 0}.bars button {display:grid;grid-template-columns:8rem 1fr 2rem;align-items:center;gap:.6rem;text-align:left;background:none;border:0;cursor:pointer;color:inherit}
.bars i {display:block;height:.65rem;background:#38795c;border-radius:3px}.bars [aria-pressed=true] {font-weight:700;text-decoration:underline}.scroll {overflow:auto;max-height:380px;margin-top:1rem}.highlight {background:var(--color-surface-muted)}
.reference {display:block;max-width:100%;max-height:360px;margin-top:1rem}.report {white-space:pre-wrap;line-height:1.7}summary {cursor:pointer;font-weight:650}
.evidence {display:flex;gap:1rem;align-items:center;margin:1rem 0}.evidence img {max-width:40%;height:85px;object-fit:contain}
</style>

