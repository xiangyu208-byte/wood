import { createApp } from 'vue'
import App from './App.vue'
import router from './router'
import {
  ElButton,
  ElDatePicker,
  ElForm,
  ElFormItem,
  ElInput,
  ElInputNumber,
  ElOption,
  ElPagination,
  ElProgress,
  ElSelect,
  ElSlider,
  ElTable,
  ElTableColumn,
  ElUpload
} from 'element-plus'
import 'element-plus/dist/index.css'
import './assets/main.css'

const app = createApp(App)

app.use(router)
;[
  ElButton,
  ElDatePicker,
  ElForm,
  ElFormItem,
  ElInput,
  ElInputNumber,
  ElOption,
  ElPagination,
  ElProgress,
  ElSelect,
  ElSlider,
  ElTable,
  ElTableColumn,
  ElUpload
].forEach(component => app.use(component))

app.mount('#app')
