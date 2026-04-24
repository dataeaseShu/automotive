import { useRef } from 'react'
import { uploadVideo } from '../services/api'

interface Props {
  sessionId: string
  currentCount: number
  maxCount?: number
  onUploaded: (material: unknown) => void
}

export default function UploadButton({ sessionId, currentCount, maxCount = 10, onUploaded }: Props) {
  const inputRef = useRef<HTMLInputElement>(null)

  const handleFiles = async (files: FileList | null) => {
    if (!files) return
    const remaining = maxCount - currentCount
    const toUpload = Array.from(files).slice(0, remaining)
    for (const file of toUpload) {
      try {
        const res = await uploadVideo(sessionId, file)
        onUploaded(res.material)
      } catch (e) {
        console.error('上传失败', e)
      }
    }
  }

  return (
    <div>
      <div
        className="upload-area"
        onClick={() => inputRef.current?.click()}
      >
        ＋ 点击上传视频素材（已选 {currentCount} / {maxCount}）
      </div>
      <input
        ref={inputRef}
        type="file"
        accept="video/*"
        multiple
        style={{ display: 'none' }}
        onChange={(e) => handleFiles(e.target.files)}
      />
    </div>
  )
}
