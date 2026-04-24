"""
上传素材路由
POST /api/upload  - 上传视频文件（multipart），返回素材信息加入候选池
"""
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from typing import Optional

from app.services import session_service
from app.services.creative_service import upload_material
from app.config import get_settings

router = APIRouter(prefix="/api/upload", tags=["upload"])
_settings = get_settings()


@router.post("")
async def upload_video(
    session_id: str = Form(...),
    file: UploadFile = File(...),
):
    session = session_service.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="会话不存在或已过期")

    MAX = _settings.MAX_UPLOADS
    current_total = len(session.selected_creative_ids) + len(session.uploaded_material_ids)
    if current_total >= MAX:
        raise HTTPException(
            status_code=400,
            detail=f"素材总数已达上限 {MAX} 个，请先删减已选成片后再上传。",
        )

    content = await file.read()
    result = await upload_material(file.filename or "video.mp4", content)

    material_id = result["material_id"]
    session.uploaded_material_ids.append(material_id)
    # 上传成功后直接加入已选成片候选
    session.selected_creative_ids.append(material_id)
    session_service.save_session(session)

    return {
        "success": True,
        "material": result,
        "selected_count": len(session.selected_creative_ids),
        "remaining_slots": MAX - len(session.selected_creative_ids),
    }
