// 共享类型定义

export interface Product {
  product_id: string
  product_name: string
  brand: string
  model: string
  thumbnail?: string
  audience_package_id?: string
  audience_package_name?: string
  targeting_package_id?: string
  targeting_package_name?: string
  status: string
}

export interface Creative {
  creative_id: string
  title: string
  duration: number
  thumbnail?: string
  play_count: number
  conversion_rate: number
  labels: string[]
  status: string
}

export type MessageType =
  | 'text'
  | 'product_cards'
  | 'creative_cards'
  | 'preview_card'
  | 'upload_button'
  | 'confirm_button'
  | 'plan_confirm_card'
  | 'error'

export interface PlanConfirmData {
  vehicle: string
  scene: string
  goal: string
  location: string
  budget: number
  bid_strategy: string
  schedule: string
  audience: Record<string, string>
}

export interface ChatMessageData {
  role: 'user' | 'assistant'
  type: MessageType
  content: string
  products?: Product[]
  creatives?: Creative[]
  selected_ids?: string[]
  preview?: PlanPreview
  plan_confirm?: PlanConfirmData
  timestamp?: number
}

export interface PlanPreview {
  product: Product | null
  audience_package: { id: string; name: string } | null
  targeting_package: { id: string; name: string } | null
  vehicle: string | null
  scene: string | null
  goal: string | null
  location: string
  audience: Record<string, string> | null
  budget: string
  bid_strategy: string
  schedule: string
  creatives: string[]
  creative_count: number
  slot_explanations: Record<string, string>
}

export interface SlotsSummary {
  vehicle: string | null
  scene: string | null
  goal: string | null
  location: Record<string, unknown> | null
  budget: number | null
  bid_strategy: Record<string, unknown> | null
  schedule: Record<string, unknown> | null
  audience: Record<string, unknown> | null
}

export type SessionState =
  | 'init'
  | 'slot_filling'
  | 'clarifying'
  | 'product_search'
  | 'product_selected'
  | 'creative_selection'
  | 'upload_prompt'
  | 'uploading'
  | 'preview'
  | 'submitted'
