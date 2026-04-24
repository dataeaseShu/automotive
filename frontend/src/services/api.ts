import axios from 'axios'
import type { ChatMessageData, SlotsSummary, SessionState, Product } from '../types'

const api = axios.create({ baseURL: '/api' })

export interface MessageResponse {
  session_id: string
  state: SessionState
  messages: (ChatMessageData & Record<string, unknown>)[]
  slots_summary: SlotsSummary
}

export const startChat = async (): Promise<{ session_id: string; message: string }> => {
  const { data } = await api.post('/chat/start')
  return data
}

export const sendMessage = async (sessionId: string, message: string): Promise<MessageResponse> => {
  const { data } = await api.post('/chat/message', { session_id: sessionId, message })
  return data
}

export const getState = async (sessionId: string) => {
  const { data } = await api.get(`/chat/${sessionId}/state`)
  return data
}

export const selectProduct = async (
  sessionId: string,
  productId: string,
  product: Product,
): Promise<MessageResponse> => {
  const { data } = await api.post('/chat/select-product', {
    session_id: sessionId,
    product_id: productId,
    product,
  })
  return data
}

export const updateCreatives = async (sessionId: string, creativeIds: string[]) => {
  const { data } = await api.post('/chat/update-creatives', {
    session_id: sessionId,
    creative_ids: creativeIds,
  })
  return data
}

export const uploadVideo = async (sessionId: string, file: File) => {
  const form = new FormData()
  form.append('session_id', sessionId)
  form.append('file', file)
  const { data } = await api.post('/upload', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return data
}
