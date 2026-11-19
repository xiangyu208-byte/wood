import { request } from './detect'

export const listBoards = () => request.get('/boards')
export const getBoard = id => request.get('/boards/' + id)
export const createBoard = setup => request.post('/boards', setup)
export const placeRecord = (id, record, placement) => request.put('/boards/' + id + '/records/' + record, placement)
export const removeFromBoard = (id, record) => request.delete('/boards/' + id + '/records/' + record)
export const aiConfig = () => request.get('/boards/ai/config')
export const generateReport = id => request.post('/boards/' + id + '/report', {}, { timeout: 95000 })
export const reviewImage = record => request.post('/boards/review/' + record, {}, { timeout: 95000 })
export function saveReference(id, file) {
  const form = new FormData()
  form.append('file', file)
  return request.post('/boards/' + id + '/reference', form)
}

