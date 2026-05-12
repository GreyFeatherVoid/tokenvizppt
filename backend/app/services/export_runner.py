import asyncio

from app.services.dom_to_pptx_exporter import export_session_with_dom_to_pptx
from app.services.pptx_exporter import export_session_to_editable_pptx
from app.services.session_store import get_session_store
from app.services.spec_pptx_exporter import export_session_from_spec


async def run_pptx_export(export_run_id: str) -> None:
    store = get_session_store()
    run = store.get_export_run(export_run_id)
    try:
        store.update_export_run(export_run_id, {"status": "running", "progress": 10})
        result = await export_session_to_pptx(run["session_id"])
        store.update_export_run(
            export_run_id,
            {
                "status": "completed",
                "progress": 100,
                "file_name": result.path.name,
                "url": result.url,
                "error": None,
            },
        )
    except Exception as exc:
        store.update_export_run(
            export_run_id,
            {
                "status": "failed",
                "progress": 100,
                "error": str(exc),
            },
        )
        raise


async def export_session_to_pptx(session_id: str):
    try:
        return await export_session_from_spec(session_id)
    except Exception:
        try:
            return await export_session_with_dom_to_pptx(session_id)
        except Exception:
            return await export_session_to_editable_pptx(session_id)


def run_pptx_export_sync(export_run_id: str) -> None:
    asyncio.run(run_pptx_export(export_run_id))
