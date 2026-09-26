import axios from 'axios'

export class ApiError extends Error {
  constructor(message, kind = 'request', status = null, cause = null) {
    super(message)
    this.name = 'ApiError'
    this.kind = kind
    this.status = status
    this.cause = cause
  }
}

const request = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api',
  timeout: 60000
})

request.interceptors.response.use(
  response => {
    const payload = response.data
    if (payload && typeof payload === 'object' && 'code' in payload && payload.code !== 200) {
      throw new ApiError(payload.message || '请求处理失败', 'business', response.status)
    }
    return payload
  },
  error => {
    if (axios.isCancel(error) || error.code === 'ERR_CANCELED') {
      return Promise.reject(new ApiError('请求已取消', 'cancelled', null, error))
    }
    if (error.code === 'ECONNABORTED') {
      return Promise.reject(new ApiError('请求超时，请稍后重试', 'timeout', null, error))
    }
    if (!error.response) {
      return Promise.reject(new ApiError('网络连接中断，请检查网络后重试', 'offline', null, error))
    }

    const status = error.response.status
    const message = error.response.data?.message
      || (status === 503 ? '识别服务暂时不可用，请稍后重试' : '请求处理失败')
    const kind = status === 503 ? 'service' : status >= 500 ? 'server' : 'request'
    return Promise.reject(new ApiError(message, kind, status, error))
  }
)

function appendOptions(formData, options = {}) {
  formData.append('modelMode', options.modelMode || 'STANDARD')
  formData.append('confidenceThreshold', String(options.confidenceThreshold ?? 0.25))
  formData.append('precision', options.precision || 'AUTO')
}

export function uploadDetect(file, options, config = {}) {
  const formData = new FormData()
  formData.append('file', file)
  appendOptions(formData, options)
  return request.post('/detect/upload', formData, config)
}

export function cameraUploadDetect(file, options, config = {}) {
  const formData = new FormData()
  formData.append('file', file)
  appendOptions(formData, options)
  return request.post('/detect/camera-upload', formData, config)
}

export function batchUploadDetectAsync(files, options, config = {}) {
  const formData = new FormData()
  files.forEach(file => formData.append('files', file))
  appendOptions(formData, options)
  return request.post('/detect/batch-upload-async', formData, config)
}

export function getBatchStatus(batchNo) {
  return request.get(`/detect/batch-status/${encodeURIComponent(batchNo)}`)
}

export function cancelBatch(batchNo) {
  return request.post(`/detect/batch-cancel/${encodeURIComponent(batchNo)}`)
}

export function retryBatch(batchNo) {
  return request.post(`/detect/batch-retry/${encodeURIComponent(batchNo)}`)
}

export function getHistory(params) {
  return request.get('/detect/history', { params })
}

export function getDetail(id) {
  return request.get(`/detect/${id}`)
}

export function deleteRecord(id) {
  return request.delete(`/detect/${id}`)
}

export function batchDeleteRecords(ids) {
  return request.post('/detect/batch-delete', ids)
}

export function deleteRecordsByCondition(condition) {
  return request.post('/detect/delete-by-condition', null, { params: condition })
}

export function submitReview(recordId, review) {
  return request.put(`/review/${recordId}`, review)
}

export function getModelVersionStats() {
  return request.get('/review/model-versions')
}
