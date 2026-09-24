import axios from 'axios'

const request = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api',
  timeout: 60000
})

/**
 * 单张图片识别
 */
export function uploadDetect(file) {
  const formData = new FormData()
  formData.append('file', file)

  return request.post('/detect/upload', formData, {
    headers: {
      'Content-Type': 'multipart/form-data'
    }
  })
}

/**
 * 摄像头截图识别
 */
export function cameraUploadDetect(file) {
  const formData = new FormData()
  formData.append('file', file)

  return request.post('/detect/camera-upload', formData, {
    headers: {
      'Content-Type': 'multipart/form-data'
    }
  })
}

/**
 * 批量图片识别
 */
export function batchUploadDetect(files) {
  const formData = new FormData()

  files.forEach(file => {
    formData.append('files', file)
  })

  return request.post('/detect/batch-upload', formData, {
    headers: {
      'Content-Type': 'multipart/form-data'
    }
  })
}

/**
 * 历史记录
 */
export function getHistory(params) {
  return request.get('/detect/history', {
    params
  })
}

/**
 * 详情
 */
export function getDetail(id) {
  return request.get(`/detect/${id}`)
}

/**
 * 删除单条历史记录
 */
export function deleteRecord(id) {
  return request.delete(`/detect/${id}`)
}

/**
 * 按勾选ID批量删除
 */
export function batchDeleteRecords(ids) {
  return request.post('/detect/batch-delete', ids)
}

/**
 * 按筛选条件一键删除全部记录
 */
export function deleteRecordsByCondition(condition) {
  return request.post('/detect/delete-by-condition', null, {
    params: condition
  })
}
